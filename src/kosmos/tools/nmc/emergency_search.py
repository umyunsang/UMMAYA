# SPDX-License-Identifier: Apache-2.0
"""NMC emergency room search adapter — T032/T022.

Calls the NMC real-time bed availability endpoint and enforces data freshness
via ``check_freshness()`` before returning results to the caller.

FR-034: Freshness enforcement via check_freshness() — see freshness.py.
Stale responses are rejected with ``LookupError(reason="stale_data")`` so the
LLM is informed of data age and threshold rather than receiving silently-stale data.

Epic δ #2295: citizen-facing gate = login (NMC emergency search requires authentication).
The Layer 3 auth-gate in ``executor.invoke()`` short-circuits unauthenticated
calls to ``LookupError(reason="auth_required")`` before handle() is reached
(FR-025, FR-026, SC-006). handle() is therefore only invoked when a valid
session identity is present.

T022 (Spec 2522 v4): URL encoding safety — Korean query params (e.g. STAGE1/STAGE2
region names) must NEVER be string-interpolated into a URL directly, as non-ASCII
characters in query strings cause HTTP 400 from the NMC/data.go.kr upstream.
This adapter uses ``httpx params={}`` dict exclusively so that httpx performs
automatic percent-encoding for all parameter values.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from kosmos.tools._description_template import build_description_v4
from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import LookupErrorReason
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.nmc.freshness import FreshnessResult

logger = logging.getLogger(__name__)

# NMC emergency room locator endpoint (data.go.kr B552657 service).
# Discovered via integration-verification probe on 2026-05-04 — the previously
# documented `api1.odcloud.kr/api/nmc/v1/realtime-beds` host does not resolve;
# the real endpoint is `apis.data.go.kr/B552657/ErmctInfoInqireService/...`
# (note: `ErmctInfoInqireService`, NOT `ErmctInsttInfoInqireService` as
# spelled in some early drafts of docs/api/nmc/emergency_search.md).
# Returns nearest emergency rooms by WGS-84 coordinate (lat/lon) — same
# semantic surface the LLM consumes, but real-time bed counts (hvec/hvgc/...)
# require the sibling `getEmrrmRltmUsefulSckbdInfoInqire` endpoint which is
# region-name parameterised (STAGE1/STAGE2) instead of coordinate-driven and
# is left for a follow-up adapter once region resolution lands.
_BASE_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
_LIST_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"

# ---------------------------------------------------------------------------
# Input schema (T032 — lat/lon/limit, Pydantic v2 strict)
# ---------------------------------------------------------------------------


class NmcEmergencySearchInput(BaseModel):
    """Input schema for nmc_emergency_search.

    Pydantic v2 strict model (extra='forbid', frozen=True).
    ``mode`` is explicit because the official NMC V4 guide exposes separate
    operations for coordinate lookup and regional list lookup. KOSMOS models
    those operations directly; it does not silently retry one operation with
    the other when an upstream response is empty.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["coordinate", "region"] = Field(
        description=(
            "Official NMC operation selector. Use 'coordinate' for "
            "getEgytLcinfoInqire with WGS84_LAT/WGS84_LON. Use 'region' for "
            "getEgytListInfoInqire with q0/q1 from resolve_location(want='all')."
        ),
    )
    lat: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description=(
            "Coordinate-mode latitude in decimal degrees (WGS-84). Required "
            "when mode='coordinate'. Obtain from resolve_location(want='coords')."
        ),
    )
    lon: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description=(
            "Coordinate-mode longitude in decimal degrees (WGS-84). Required "
            "when mode='coordinate'. Obtain from resolve_location(want='coords')."
        ),
    )
    q0: str | None = Field(
        default=None,
        min_length=1,
        max_length=40,
        description=(
            "Region-mode NMC Q0 시도 parameter, e.g. '부산광역시'. Required "
            "when mode='region'. Populate from resolve_location(...).region.region_1depth_name."
        ),
    )
    q1: str | None = Field(
        default=None,
        min_length=1,
        max_length=40,
        description=(
            "Region-mode NMC Q1 시군구 parameter, e.g. '사하구'. Required "
            "when mode='region'. Populate from resolve_location(...).region.region_2depth_name."
        ),
    )
    qn: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description=(
            "Optional NMC QN institution-name filter. Leave unset for general "
            "nearby ER search; do not invent a hospital name."
        ),
    )
    origin_lat: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description=(
            "Optional original query latitude for distance sorting in region mode. "
            "Populate from resolve_location(...).coords.lat when available."
        ),
    )
    origin_lon: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description=(
            "Optional original query longitude for distance sorting in region mode. "
            "Populate from resolve_location(...).coords.lon when available."
        ),
    )
    limit: int = Field(
        ge=1,
        le=100,
        description=(
            "Maximum number of emergency institutions to return. Capped at 100 "
            "per NMC API contract."
        ),
    )

    @model_validator(mode="after")
    def _validate_operation_params(self) -> NmcEmergencySearchInput:
        if self.mode == "coordinate" and (self.lat is None or self.lon is None):
            raise ValueError("mode='coordinate' requires lat and lon")
        if self.mode == "region" and (not self.q0 or not self.q1):
            raise ValueError("mode='region' requires q0 and q1 from resolve_location region")
        if (self.origin_lat is None) ^ (self.origin_lon is None):
            raise ValueError("origin_lat and origin_lon must be supplied together")
        return self


# ---------------------------------------------------------------------------
# Placeholder output schema
# ---------------------------------------------------------------------------


class _NmcEmergencySearchOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema for GovAPITool registration.

    Real output shape is deferred until NMC auth is provisioned.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ---------------------------------------------------------------------------
# Handler helpers
# ---------------------------------------------------------------------------


def _normalize_items(raw_items: object) -> list[dict[str, Any]]:
    """Flatten data.go.kr B552657's `body.items.item` into a list of dicts.

    The wire format wraps results as `body.items.item` where `item` is either
    a single dict (1 result) or a list of dicts (≥2 results) — the
    XML-shaped JSON quirk. The legacy odcloud-style flat list shape is also
    tolerated for backward compatibility with any cached responses.
    """
    if isinstance(raw_items, dict):
        item_field = raw_items.get("item", [])
        if isinstance(item_field, dict):
            return [item_field]
        if isinstance(item_field, list):
            return item_field
        return []
    if isinstance(raw_items, list):
        return raw_items
    return []


# ---------------------------------------------------------------------------
# Field-semantics enrichment (safety-critical — Spec 2637 Epic F)
# ---------------------------------------------------------------------------
#
# `getEgytLcinfoInqire` returns abbreviated fields whose names mislead a
# downstream LLM into rendering them as ER hours. The location endpoint's
# `startTime`/`endTime` are the institution's *representative outpatient
# (외래) consultation* open/close time — typically Monday's `dutyTime1s` /
# `dutyTime1c` from the sibling `getEgytBassInfoInqire` endpoint — NOT the
# emergency-room operating window. Every record returned by this endpoint
# is by definition a registered 응급의료기관 (emergency medical institution)
# whose ER itself runs **365일 24시간** continuously. Surfacing the raw
# `startTime: "0830", endTime: 1700` as "운영시간: 08:30~17:00" is a
# safety-critical mis-info pattern observed during integration verification
# (snap-010, 2026-05-04) that risks a citizen being told the ER closes at
# 5pm during an actual emergency.
#
# Live evidence (Jongno-gu coordinates, 2026-05-04):
#   - 강북삼성병원 (지역응급의료센터, G006): startTime=0830, endTime=1700
#   - 서울대학교병원 (권역응급의료센터, G001): startTime=0800, endTime=1800
#   - 국립중앙의료원 (지역응급의료센터, G006): startTime=0830, endTime=1700
# All three operate 24/7 ER per the dutyEryn=1 flag in the sibling
# getEgytBassInfoInqire endpoint and per the 응급의료에 관한 법률 §31.
# ---------------------------------------------------------------------------


def _format_hhmm(value: object) -> str | None:
    """Normalize raw HHMM scalar into a `HH:MM` display string.

    The location endpoint returns `startTime` as a string ("0830") and
    `endTime` as an integer (1700) — the JSON shape is inconsistent across
    fields. We accept both and emit a normalized `HH:MM` string. Anything
    unparseable returns None so the LLM does not render a bogus value.
    """
    if value is None or value == "":
        return None
    try:
        digits = str(value).strip()
        if not digits.isdigit():
            return None
        # Pad with leading zeros (e.g. 830 → "0830", 0 → "0000")
        padded = digits.rjust(4, "0")
        if len(padded) != 4:
            return None
        hh = int(padded[:2])
        mm = int(padded[2:])
        if 0 <= hh <= 24 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
    except (ValueError, TypeError):
        return None
    return None


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            stripped = value.strip()
            return float(stripped) if stripped else None
        if isinstance(value, int | float):
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def _haversine_km(
    *,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _attach_coordinates(item: dict[str, Any]) -> None:
    lat = _as_float(item.get("latitude")) or _as_float(item.get("wgs84Lat"))
    lon = _as_float(item.get("longitude")) or _as_float(item.get("wgs84Lon"))
    if lat is not None:
        item["latitude"] = lat
    if lon is not None:
        item["longitude"] = lon


def _attach_phone_fields(item: dict[str, Any]) -> None:
    duty_tel1 = item.get("dutyTel1")
    if duty_tel1:
        item["hospital_main_phone"] = duty_tel1
    duty_tel3 = item.get("dutyTel3")
    if duty_tel3:
        item["er_direct_phone"] = duty_tel3
        item["er_phone_note"] = "dutyTel3 = 응급실 직통 전화. 응급 상황은 119 우선."
        return
    item["er_phone_note"] = (
        "dutyTel1 = 병원 대표번호. 응급실 직통(dutyTel3) 은 본 endpoint 에서 미제공 — "
        "의료기관 기본정보(getEgytBassInfoInqire) 또는 119 안내 권장."
    )


def _attach_classification_fields(item: dict[str, Any]) -> None:
    duty_div_name = item.get("dutyDivName")
    if duty_div_name:
        item["hospital_type"] = duty_div_name
        item["hospital_type_note"] = (
            "dutyDivName 은 의료기관 종별(종합병원/병원/의원), 응급의료센터 등급 아님. "
            "본 endpoint 의 모든 결과는 응급의료기관 등록 시설 (24시간 응급실 운영)."
        )
    duty_emcls_name = item.get("dutyEmclsName")
    if duty_emcls_name:
        item["er_classification"] = duty_emcls_name


def _enrich_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Rewrite raw NMC location item into safety-clear semantic fields.

    Replaces the misleading `startTime`/`endTime` (institutional outpatient
    hours, mistaken for ER hours by the LLM) with explicit semantic field
    names AND adds an `er_24h_operating: True` flag so the LLM cannot
    surface the wrong operating window in an emergency context.

    The original raw fields are preserved under `_raw_outpatient_*` keys so
    that any downstream consumer that explicitly wants the upstream value
    can still access it — but the canonical field names no longer collide
    with the safety-critical "응급실 운영시간" semantics.
    """
    # Copy so we never mutate the caller's dict.
    item: dict[str, Any] = dict(raw)

    raw_start = item.pop("startTime", None)
    raw_end = item.pop("endTime", None)
    open_time = _format_hhmm(raw_start)
    close_time = _format_hhmm(raw_end)

    # Canonical safety-critical fields (LLM-visible).
    item["er_24h_operating"] = True
    item["er_operating_hours_note"] = (
        "응급실은 24시간 운영. outpatient_open_time/close_time은 "
        "외래진료 시간이며 응급실 운영시간이 아님."
    )
    item["outpatient_open_time"] = open_time
    item["outpatient_close_time"] = close_time
    if open_time and close_time:
        item["outpatient_hours_display"] = f"{open_time}~{close_time} (외래진료)"
    elif open_time or close_time:
        item["outpatient_hours_display"] = (
            f"{open_time or '미상'}~{close_time or '미상'} (외래진료)"
        )
    else:
        item["outpatient_hours_display"] = None

    # Preserve raw values for explicit-access consumers.
    if raw_start is not None:
        item["_raw_outpatient_start_hhmm"] = raw_start
    if raw_end is not None:
        item["_raw_outpatient_end_hhmm"] = raw_end

    _attach_coordinates(item)

    # Phone field clarification: dutyTel1 is the hospital main switchboard,
    # NOT the ER hotline. The region-list endpoint may provide dutyTel3
    # (ER direct), while the coordinate endpoint omits it.
    _attach_phone_fields(item)

    # Hospital-type vs ER-classification clarification: dutyDivName ('종합병원')
    # is the institution's hospital classification (general hospital), NOT the
    # ER tier (지역응급의료센터/권역응급의료센터/응급의료시설 — that is
    # `dutyEmclsName` from getEgytListInfoInqire). Make this explicit.
    _attach_classification_fields(item)

    return item


def _evaluate_freshness(items: list[dict[str, Any]]) -> FreshnessResult:
    """Return the worst-case freshness across all items (fail-closed).

    If any item is missing hvidate or is stale, the entire batch is stale.
    """
    from kosmos.tools.nmc.freshness import check_freshness

    if not items:
        return check_freshness(None)

    worst: FreshnessResult | None = None
    for item in items:
        hv = item.get("hvidate")
        if not hv:
            return check_freshness(None)
        result = check_freshness(hv)
        if worst is None or not result.is_fresh:
            worst = result
            if not result.is_fresh:
                break

    assert worst is not None
    return worst


def _stale_message(freshness: FreshnessResult) -> str:
    """Build a human-readable stale-data message."""
    if freshness.data_age_minutes == float("inf"):
        return (
            f"NMC data is stale: hvidate missing or unparseable "
            f"(threshold: {freshness.threshold_minutes} min)"
        )
    if freshness.data_age_minutes < 0:
        return (
            f"NMC data is stale: hvidate is in the future "
            f"(age={freshness.data_age_minutes:.1f} min, "
            f"threshold: {freshness.threshold_minutes} min)"
        )
    return (
        f"NMC data is stale: {freshness.data_age_minutes:.0f} min old "
        f"(threshold: {freshness.threshold_minutes} min)"
    )


def _build_request(
    inp: NmcEmergencySearchInput,
    *,
    service_key: str,
) -> tuple[str, dict[str, str | int | float], str]:
    params: dict[str, str | int | float] = {
        "serviceKey": service_key,
        "pageNo": 1,
        "numOfRows": inp.limit,
        "_type": "json",
    }
    if inp.mode == "coordinate":
        assert inp.lat is not None
        assert inp.lon is not None
        params["WGS84_LAT"] = inp.lat
        params["WGS84_LON"] = inp.lon
        return _BASE_URL, params, "getEgytLcinfoInqire"

    assert inp.q0 is not None
    assert inp.q1 is not None
    params["Q0"] = inp.q0
    params["Q1"] = inp.q1
    params["ORD"] = "ADDR"
    if inp.qn:
        params["QN"] = inp.qn
    return _LIST_URL, params, "getEgytListInfoInqire"


def _sort_region_items_by_origin(
    items: list[dict[str, Any]],
    *,
    origin_lat: float | None,
    origin_lon: float | None,
) -> None:
    if origin_lat is None or origin_lon is None:
        return
    for item in items:
        lat = _as_float(item.get("latitude"))
        lon = _as_float(item.get("longitude"))
        if lat is None or lon is None:
            continue
        item["distance"] = round(
            _haversine_km(
                lat1=origin_lat,
                lon1=origin_lon,
                lat2=lat,
                lon2=lon,
            ),
            3,
        )
    items.sort(
        key=lambda item: (
            item.get("distance") is None,
            float(item.get("distance", 0.0)) if item.get("distance") is not None else 0.0,
        )
    )


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def handle(inp: NmcEmergencySearchInput) -> dict[str, Any]:
    """Handle an NMC emergency search request.

    Fetches emergency medical institution data from the NMC API operation
    explicitly selected by ``inp.mode``. Coordinate mode maps to
    getEgytLcinfoInqire. Region mode maps to getEgytListInfoInqire. Empty
    results from either operation are surfaced as empty results; no hidden
    alternate-operation retry is performed.

    Returns a LookupCollection dict when data is fresh, or a LookupError
    dict (reason=stale_data) when the data exceeds the freshness threshold.

    Raises:
        httpx.HTTPStatusError: When the upstream NMC API returns a non-2xx status.
        httpx.TimeoutException: When the upstream NMC API does not respond within 10 s.
    """
    from kosmos.settings import settings

    if not settings.data_go_kr_api_key:
        return {
            "kind": "error",
            "reason": LookupErrorReason.upstream_unavailable,
            "message": "KOSMOS_DATA_GO_KR_API_KEY is not configured",
            "retryable": False,
        }

    endpoint, params, operation = _build_request(
        inp,
        service_key=settings.data_go_kr_api_key,
    )

    async with traced_async_client(timeout=10.0) as client:
        resp = await client.get(
            endpoint,
            params=params,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type.lower():
            return {
                "kind": "error",
                "reason": LookupErrorReason.upstream_unavailable,
                "message": f"NMC API returned non-JSON content-type: {content_type!r}",
                "retryable": True,
            }

        try:
            data = resp.json()
        except ValueError:
            return {
                "kind": "error",
                "reason": LookupErrorReason.upstream_unavailable,
                "message": "NMC API returned invalid JSON body",
                "retryable": True,
            }

    header = data.get("response", {}).get("header", {})
    result_code = header.get("resultCode", "")
    if result_code != "00":
        return {
            "kind": "error",
            "reason": LookupErrorReason.upstream_unavailable,
            "message": (
                f"NMC API error: resultCode={result_code!r}, "
                f"resultMsg={header.get('resultMsg', 'unknown')!r}"
            ),
            "retryable": True,
        }

    body = data.get("response", {}).get("body", {})
    raw_items = _normalize_items(body.get("items", []))
    upstream_total = body.get("totalCount")

    # Enrich every record with safety-critical semantic fields BEFORE the
    # freshness check so downstream serialization always sees the corrected
    # field names. _enrich_item is pure (returns a fresh dict) so the
    # enriched copy is what the LLM sees.
    items = [_enrich_item(item) for item in raw_items if isinstance(item, dict)]
    for item in items:
        item["_nmc_operation"] = operation

    if inp.mode == "region":
        _sort_region_items_by_origin(
            items,
            origin_lat=inp.origin_lat,
            origin_lon=inp.origin_lon,
        )
    items = items[: inp.limit]

    if not items:
        return {
            "kind": "collection",
            "items": [],
            "total_count": 0,
            "meta": {"freshness_status": "not_applicable"},
        }

    # Endpoint-aware freshness check.
    # `getEgytLcinfoInqire` (the location endpoint we now use) returns ER
    # static metadata (dutyName / dutyAddr / dutyTel1 / latitude / longitude)
    # but does NOT include `hvidate` or real-time bed counts (`hvec` / `hvgc`
    # / `hvicc`) — those live in the sibling `getEmrrmRltmUsefulSckbdInfoInqire`
    # endpoint (region-name parameterised). Without endpoint-aware logic,
    # _evaluate_freshness sees every item as `hvidate`-missing and fails
    # closed with stale_data, which made the citizen experience surface
    # `Tool execution failed` in integration-verification frame 11. When
    # ALL items lack hvidate, treat the response as static-location data and
    # tag freshness_status="not_applicable" instead of treating it as stale.
    has_any_hvidate = any(item.get("hvidate") for item in items if isinstance(item, dict))

    if not has_any_hvidate:
        return {
            "kind": "collection",
            "items": items,
            "total_count": upstream_total if upstream_total is not None else len(items),
            "meta": {"freshness_status": "not_applicable"},
        }

    freshness = _evaluate_freshness(items)

    if freshness.is_fresh:
        return {
            "kind": "collection",
            "items": items,
            "total_count": upstream_total if upstream_total is not None else len(items),
            "meta": {"freshness_status": "fresh"},
        }

    return {
        "kind": "error",
        "reason": LookupErrorReason.stale_data,
        "message": _stale_message(freshness),
        "retryable": False,
    }


# ---------------------------------------------------------------------------
# Tool definition (T033 will call register() from register_all.py)
# ---------------------------------------------------------------------------

NMC_EMERGENCY_SEARCH_TOOL = GovAPITool(
    id="nmc_emergency_search",
    name_ko="응급실 실시간 병상 조회 (국립중앙의료원)",
    ministry="NMC",
    category=["응급의료", "실시간병상", "의료기관"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=NmcEmergencySearchInput,
    output_schema=_NmcEmergencySearchOutput,
    llm_description=build_description_v4(
        purpose=(
            "NMC 응급의료기관 조회. mode='coordinate'는 getEgytLcinfoInqire "
            "(WGS84_LAT/LON), mode='region'은 getEgytListInfoInqire(Q0/Q1). "
            "결과는 등록 응급의료기관이며 실시간 병상은 별도 endpoint."
        ),
        input_quirk=(
            "하단역/동네/역 근처 응급실은 resolve_location(want='all') 먼저 호출 후 "
            "mode='region', q0=region.region_1depth_name, q1=region.region_2depth_name, "
            "origin_lat/lon=coords. 좌표 operation은 upstream 0건 가능. QZ 임의 설정 금지."
        ),
        short_reference=(
            "NMC Q0=시도, Q1=시군구, QN=기관명(optional), ORD=ADDR. "
            "coordinate params: WGS84_LAT/WGS84_LON. "
            "dutyEmclsName=응급의료 분류, dutyTel3=응급실 직통."
        ),
        domain_quirk=(
            "★응급실 = 365일 24시간★. outpatient_open_time/outpatient_close_time 은 "
            "외래진료 시간이며 응급실 시간 아님. dutyTel1=대표번호, dutyTel3=응급실 직통. "
            "URL interpolation 금지; params dict 인코딩. hvidate가 있으면 stale_data 단락. "
            "비인증 시 auth_required."
        ),
        self_contained_decl=(
            "ORDERING: turn1 resolve_location(want='all'), turn2 본 도구. "
            "역/동/주소 근처 검색은 region mode. 좌표만 알고 coordinate mode를 쓸 때도 "
            "응급실 시간 답변은 '24시간 운영', outpatient_hours_display는 외래진료로만 설명."
        ),
    ),
    search_hint=(
        "응급실 실시간 병상 응급의료센터 국립중앙의료원 가까운 응급실 "
        "emergency room bed availability nearest ER NMC real-time Korea"
    ),
    # Epic δ #2295: Real-time ER bed availability — login gate (citizen session required).
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.nemc.or.kr/info/dataInfoView.do",
        real_classification_text="국립의료원 응급의료 공공데이터 이용약관 — 응급실 정보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="login",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    # Metadata for T033 registration:
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    is_core=False,
    # search_hint_ko and search_hint_en are collapsed into search_hint above.
    # Canonical hint values (kept here as comments for T033 reference):
    #   search_hint_ko = "응급실 실시간 병상 · 응급의료센터"
    #   search_hint_en = "emergency room bed availability nearest ER"
    # Spec 031 T032/T033 dual-axis fields — None during pre-v1.2 compatibility window FR-028
    primitive="lookup",
    published_tier_minimum=None,
    nist_aal_hint=None,
    trigger_examples=[
        "근처 응급실",
        "야간 응급의료센터",
        "어린이 응급실",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register the NMC emergency search tool and its adapter.

    Called by ``register_all.py`` in Stage 3 (T033). Do NOT call this
    function from Stage 2 — it is intentionally left unregistered until
    Stage 3 serial integration.

    The Layer 3 auth-gate short-circuits unauthenticated calls on
    Epic δ #2295: auth gate based on policy.citizen_facing_gate (FR-025, SC-006).
    handle() is only reached when a valid session identity is present.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, NmcEmergencySearchInput)
        return await handle(inp)

    registry.register(NMC_EMERGENCY_SEARCH_TOOL)
    executor.register_adapter("nmc_emergency_search", _adapter)
    logger.info("Registered tool: nmc_emergency_search (auth_required gate — freshness SLO active)")
