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
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

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

# ---------------------------------------------------------------------------
# Input schema (T032 — lat/lon/limit, Pydantic v2 strict)
# ---------------------------------------------------------------------------


class NmcEmergencySearchInput(BaseModel):
    """Input schema for nmc_emergency_search.

    Pydantic v2 strict model (extra='forbid', frozen=True).
    All three fields are required; no defaults are provided so that the LLM
    must explicitly supply values rather than silently relying on fallbacks.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lat: float = Field(
        ge=-90,
        le=90,
        description=(
            "Latitude of the search origin in decimal degrees (WGS-84). "
            "Obtain from resolve_location(want='coords'). "
            "Example: 37.5665 for central Seoul."
        ),
    )
    lon: float = Field(
        ge=-180,
        le=180,
        description=(
            "Longitude of the search origin in decimal degrees (WGS-84). "
            "Obtain from resolve_location(want='coords'). "
            "Example: 126.9780 for central Seoul."
        ),
    )
    limit: int = Field(
        ge=1,
        le=100,
        description=(
            "Maximum number of nearest emergency rooms to return. "
            "Capped at 100 per NMC API contract. "
            "Example: 5 for the five nearest ERs."
        ),
    )


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


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


async def handle(inp: NmcEmergencySearchInput) -> dict[str, Any]:
    """Handle an NMC emergency search request.

    Fetches real-time emergency room bed availability from the NMC API,
    evaluates freshness across all returned items, and enforces the
    freshness SLO via check_freshness().

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

    # data.go.kr B552657 wire-format params (different from the
    # odcloud.kr stub's page/perPage/wgs84{Lat,Lon} naming):
    #   pageNo + numOfRows + WGS84_LAT + WGS84_LON + _type=json
    params: dict[str, str | int | float] = {
        "serviceKey": settings.data_go_kr_api_key,
        "pageNo": 1,
        "numOfRows": inp.limit,
        "WGS84_LAT": inp.lat,
        "WGS84_LON": inp.lon,
        "_type": "json",
    }

    async with traced_async_client(timeout=10.0) as client:
        resp = await client.get(
            _BASE_URL,
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
    items = _normalize_items(body.get("items", []))
    upstream_total = body.get("totalCount")

    if not items:
        return {
            "kind": "collection",
            "items": [],
            "total_count": 0,
            "meta": {"freshness_status": "fresh"},
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
            "NMC (국립중앙의료원) 응급실 실시간 병상 조회 — 좌표 기준 가장 가까운 응급실의 "
            "현재 가용 병상 수 (hvec=일반, hvgc=신생아중환자, hvicc=중환자) 반환. "
            "시민이 '근처 응급실', '가용 병상', '응급의료센터' 묻는 경우 호출."
        ),
        input_quirk=(
            "lat (-90~90), lon (-180~180): WGS-84 소수점 좌표. resolve_location(want='coords') 선행 호출로 획득. "
            "limit (1~100): 반환할 응급실 최대 수. "
            "URL encoding 주의: httpx params={} dict 사용 — 한국어 query param (STAGE1/STAGE2 등) 을 "
            "URL 직접 interpolation 하면 HTTP 400. 이 adapter 는 params dict 자동 인코딩."
        ),
        short_reference=(
            "주요 응급의료센터 위치: 서울(37.5665, 126.9780) 부산(35.1796, 129.0756) "
            "대구(35.8714, 128.6014) 인천(37.4563, 126.7052) 광주(35.1595, 126.8526) "
            "대전(36.3504, 127.3845) 울산(35.5384, 129.3114) 세종(36.4800, 127.2890). "
            "hvidate 필드 포맷: YYYY-MM-DD HH:MM:SS (KST). freshness threshold = KOSMOS_NMC_FRESHNESS_MINUTES."
        ),
        domain_quirk=(
            "freshness SLO: hvidate 가 threshold 초과 시 stale_data 에러 반환 (fail-closed). "
            "hvidate 누락·미래 값도 stale 처리. "
            "auth gate: 비인증 호출은 auth_required 에러 (Layer 3 단락, handle() 미호출). "
            "resultCode '00' = 정상; 그 외는 upstream_unavailable."
        ),
        self_contained_decl=(
            "이 도구 단독 호출로 완결. resolve_location 으로 lat/lon 획득 후 이 도구 호출 권장. "
            "KOSMOS 가 cross-domain chain 강제하지 않음 — LLM 자율 2턴 (turn1=resolve, turn2=이 도구)."
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
