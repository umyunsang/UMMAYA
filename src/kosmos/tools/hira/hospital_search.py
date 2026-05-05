# SPDX-License-Identifier: Apache-2.0
"""HIRA hospital search adapter — T054.

Wraps the ``getHospBasisList`` endpoint from HIRA
(건강보험심사평가원, Health Insurance Review and Assessment Service).

Input: WGS84 coordinates (xPos, yPos) + radius in meters,
       optional medical specialty (dgsbjt) + institution type (clCd).
Output: LookupCollection of hospital records, sorted by distance ASC client-side.

Endpoint: https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList

FR-021: Accepts (xPos, yPos, radius) — native coord+radius spatial input.
FR-023: Ships happy-path AND error-path tests with recorded fixtures.
FR-024: Fail-closed defaults (non-auth tool — read-only gate per Epic δ #2295,
        is_concurrency_safe=True, cache_ttl_seconds=0).
FR-037: Adapter is an async coroutine.

D + E fix (2026-05-04, snap-009 강남역 내과 lookup regression):
  D — HIRA's getHospBasisList returns ``distance`` (a high-precision decimal
      string in meters from the query xPos/yPos) but does NOT sort by it.
      Live verification 2026-05-04: baseline call near 강남역 returned
      d=829, 760, 479, 610, 757 (registration order, not distance ASC).
      We now sort items by distance ascending client-side after deserializing
      the upstream response.
  E — Add ``dgsbjt`` (medical specialty natural-language input → 진료과목코드
      mapping; e.g. "내과" → "01") and ``clCd`` (종별코드, e.g. "31"=의원,
      "21"=병원, "11"=상급종합) so the citizen's "근처 내과" query becomes
      ``dgsbjt='내과'`` server-side filter (118 results, not 907) instead of
      a generic radius search returning every clinic and hospital mixed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from kosmos.tools._description_template import build_description_v4
from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ToolExecutionError, _require_env
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"

# ---------------------------------------------------------------------------
# Code maps (HIRA canonical 진료과목코드 + 종별코드, verified live 2026-05-04)
# ---------------------------------------------------------------------------

# 진료과목코드 — HIRA dgsbjtCd. Source: 한국사회보장정보원 보건기관 진료과목 코드정보
# (data.go.kr 15049696) cross-checked against live getHospBasisList probe near
# 강남역 (37.498, 127.028, r=500) returning non-zero totals for 01–16, 19, 21,
# 23, 24, 26, 80 on 2026-05-04. Aliases include common citizen vocabulary
# (e.g. "이비인후과" / "ENT" → 24).
_DGSBJT_CODE_MAP: dict[str, str] = {
    # 01 내과
    "내과": "01",
    "internal medicine": "01",
    # 02 신경과
    "신경과": "02",
    "neurology": "02",
    # 03 정신건강의학과
    "정신건강의학과": "03",
    "정신과": "03",
    "psychiatry": "03",
    # 04 외과
    "외과": "04",
    "surgery": "04",
    # 05 정형외과
    "정형외과": "05",
    "orthopedics": "05",
    # 06 신경외과
    "신경외과": "06",
    "neurosurgery": "06",
    # 07 흉부외과
    "흉부외과": "07",
    "thoracic surgery": "07",
    # 08 성형외과
    "성형외과": "08",
    "plastic surgery": "08",
    # 09 마취통증의학과
    "마취통증의학과": "09",
    "마취과": "09",
    "통증의학과": "09",
    "anesthesiology": "09",
    # 10 산부인과
    "산부인과": "10",
    "obstetrics": "10",
    "gynecology": "10",
    "ob/gyn": "10",
    # 11 소아청소년과
    "소아청소년과": "11",
    "소아과": "11",
    "pediatrics": "11",
    # 12 안과
    "안과": "12",
    "ophthalmology": "12",
    # 13 이비인후과
    "이비인후과": "13",
    "ent": "13",
    "otolaryngology": "13",
    # 14 피부과
    "피부과": "14",
    "dermatology": "14",
    # 15 비뇨의학과
    "비뇨의학과": "15",
    "비뇨기과": "15",
    "urology": "15",
    # 16 영상의학과
    "영상의학과": "16",
    "방사선과": "16",
    "radiology": "16",
    # 17 방사선종양학과
    "방사선종양학과": "17",
    "radiation oncology": "17",
    # 18 병리과
    "병리과": "18",
    "pathology": "18",
    # 19 진단검사의학과
    "진단검사의학과": "19",
    "임상병리과": "19",
    "laboratory medicine": "19",
    # 20 결핵과
    "결핵과": "20",
    "tuberculosis": "20",
    # 21 재활의학과
    "재활의학과": "21",
    "rehabilitation": "21",
    # 22 핵의학과
    "핵의학과": "22",
    "nuclear medicine": "22",
    # 23 가정의학과
    "가정의학과": "23",
    "family medicine": "23",
    # 24 응급의학과
    "응급의학과": "24",
    "emergency medicine": "24",
    # 25 직업환경의학과
    "직업환경의학과": "25",
    "산업의학과": "25",
    "occupational medicine": "25",
    # 26 예방의학과
    "예방의학과": "26",
    "preventive medicine": "26",
    # 80 한방
    "한의원": "80",
    "한방": "80",
    "한의과": "80",
    "korean medicine": "80",
}

# 종별코드 — HIRA clCd. Source: HIRA 활용가이드 (병원정보서비스). Verified live
# 2026-05-04 with clCd=31 returning 673 / clCd=21 returning N (의원/병원 split).
_CLCD_CODE_MAP: dict[str, str] = {
    # 11 상급종합병원
    "상급종합": "11",
    "상급종합병원": "11",
    "tertiary hospital": "11",
    # 21 종합병원
    "종합병원": "21",
    "general hospital": "21",
    # 28 병원 (HIRA uses 21 for 종합병원 + 28 for 병원 in some tables; live API
    # accepts 21 broadly — keep canonical 21 for "병원").
    "병원": "21",
    "hospital": "21",
    # 29 치과병원
    "치과병원": "29",
    "dental hospital": "29",
    # 31 의원
    "의원": "31",
    "clinic": "31",
    # 41 조산원
    "조산원": "41",
    "midwifery clinic": "41",
    # 51 보건소
    "보건소": "51",
    "public health center": "51",
    # 81 한의원
    "한의원종별": "81",  # disambiguate from 진료과 한의원
    # 92 약국
    "약국": "92",
    "pharmacy": "92",
}

# ---------------------------------------------------------------------------
# Input schema (T054 — xPos + yPos + radius)
# ---------------------------------------------------------------------------


class HiraHospitalSearchInput(BaseModel):
    """Input schema for hira_hospital_search.

    Queries HIRA's hospital basis list endpoint by WGS84 coordinate and
    radius. All three parameters are required.

    Obtain xPos / yPos from resolve_location(want='coords') before calling
    this tool — never guess coordinate values from model memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    xPos: float = Field(  # noqa: N815
        ge=124.0,
        le=132.0,
        description=(
            "Longitude (WGS84, decimal degrees). Korean peninsula range: 124–132. "
            "Obtain from resolve_location(want='coords'). Never guess."
        ),
    )
    yPos: float = Field(  # noqa: N815
        ge=33.0,
        le=39.0,
        description=(
            "Latitude (WGS84, decimal degrees). Korean peninsula range: 33–39. "
            "Obtain from resolve_location(want='coords'). Never guess."
        ),
    )
    radius: int = Field(
        ge=1,
        le=10000,
        default=2000,
        description=(
            "Search radius in meters. Default 2000 m (2 km). Max 10 000 m. "
            "Citizen vocabulary mapping: '근처' / 'nearby' = 1500 m, "
            "'주변' = 3000 m, '인근' = 2000 m, '한 5km 안' = 5000 m. "
            "Do NOT inflate radius to grow result count — KOSMOS sorts results "
            "client-side by distance ascending, so a tighter radius is more "
            "relevant. Increasing radius only adds farther matches."
        ),
    )
    dgsbjt: str | None = Field(
        default=None,
        description=(
            "Optional medical-specialty filter (HIRA 진료과목코드). "
            "Accepts either the natural-language Korean name or the 2-digit "
            "code. Examples: '내과' → 01, '소아과' → 11, '안과' → 12, "
            "'이비인후과' → 13, '피부과' → 14, '정형외과' → 05, "
            "'산부인과' → 10, '치과' (use clCd=치과병원 instead). "
            "ENGLISH aliases: 'internal medicine' / 'pediatrics' / 'ENT' / "
            "'dermatology' / 'orthopedics'. WHEN TO USE: citizen mentions a "
            "specific 진료과 ('근처 내과 알려줘' → dgsbjt='내과'). When omitted, "
            "all specialties returned. Without this filter '근처 병원' returns "
            "성형외과, 안과, 정형외과 etc. mixed — usually NOT what citizens want."
        ),
    )
    clCd: str | None = Field(  # noqa: N815
        default=None,
        description=(
            "Optional institution-type filter (HIRA 종별코드). "
            "Accepts natural-language Korean or the 2-digit code. "
            "'의원' / 'clinic' → 31 (small primary care, single-specialty), "
            "'병원' / 'hospital' → 21 (mid-size), '종합병원' → 21, "
            "'상급종합' / 'tertiary hospital' → 11 (large university hospitals "
            "like 서울대병원, 세브란스), '치과병원' → 29, '한의원' → 81, "
            "'약국' / 'pharmacy' → 92, '보건소' → 51. WHEN TO USE: citizen "
            "specifies institution scale ('근처 종합병원', '큰 병원'). When "
            "omitted, all types returned mixed. Combine with dgsbjt for "
            "best precision: dgsbjt='내과' + clCd='의원' = '내과의원'."
        ),
    )
    pageNo: int = Field(  # noqa: N815
        default=1,
        ge=1,
        description="Page number for pagination (1-based). Default 1.",
    )
    numOfRows: int = Field(  # noqa: N815
        default=20,
        ge=1,
        le=100,
        description="Number of rows per page (1–100). Default 20.",
    )

    @field_validator("dgsbjt")
    @classmethod
    def _resolve_dgsbjt(cls, v: str | None) -> str | None:
        """Map natural-language specialty → 2-digit dgsbjtCd, or pass through code."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # If it's already a 2-digit code, accept as-is.
        if v.isdigit() and len(v) == 2:
            return v
        # Lowercase for English-alias lookup, raw Korean for Korean lookup.
        lookup_key = v.lower()
        if lookup_key in _DGSBJT_CODE_MAP:
            return _DGSBJT_CODE_MAP[lookup_key]
        if v in _DGSBJT_CODE_MAP:
            return _DGSBJT_CODE_MAP[v]
        # Unrecognized — raise so the executor returns invalid_params with a
        # clear hint rather than silently dropping the filter.
        valid_examples = "내과 / 소아과 / 안과 / 이비인후과 / 정형외과 / 피부과"
        raise ValueError(
            f"Unknown medical specialty '{v}'. Pass either the Korean name "
            f"(e.g. {valid_examples}) or a 2-digit dgsbjtCd (01–26, 80)."
        )

    @field_validator("clCd")
    @classmethod
    def _resolve_clcd(cls, v: str | None) -> str | None:
        """Map natural-language institution type → 2-digit clCd, or pass through code."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if v.isdigit() and len(v) == 2:
            return v
        lookup_key = v.lower()
        if lookup_key in _CLCD_CODE_MAP:
            return _CLCD_CODE_MAP[lookup_key]
        if v in _CLCD_CODE_MAP:
            return _CLCD_CODE_MAP[v]
        valid_examples = "의원 / 병원 / 종합병원 / 상급종합 / 치과병원 / 약국"
        raise ValueError(
            f"Unknown institution type '{v}'. Pass either the Korean name "
            f"(e.g. {valid_examples}) or a 2-digit clCd."
        )


# ---------------------------------------------------------------------------
# Async adapter handler
# ---------------------------------------------------------------------------


async def handle(  # noqa: C901
    inp: HiraHospitalSearchInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Invoke the HIRA hospital search endpoint and return a LookupCollection dict.

    FR-037: This is an async coroutine.
    FR-021: Returns LookupCollection with yadmNm, addr, telno, clCd, etc.

    Args:
        inp: Validated HiraHospitalSearchInput.
        client: Optional httpx.AsyncClient for test injection.

    Returns:
        A dict suitable for envelope normalization into LookupCollection.

    Raises:
        ConfigurationError: If KOSMOS_DATA_GO_KR_API_KEY is not set.
        RuntimeError: On upstream API errors (non-00 resultCode or HTTP error).
    """
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    params: dict[str, str | int | float] = {
        "serviceKey": api_key,
        "xPos": inp.xPos,
        "yPos": inp.yPos,
        "radius": inp.radius,
        "pageNo": inp.pageNo,
        "numOfRows": inp.numOfRows,
        "_type": "json",
    }
    # E-fix: forward server-side filters when the citizen specified a
    # specialty / institution type. Validators have already mapped natural-
    # language input to the canonical 2-digit codes.
    if inp.dgsbjt is not None:
        params["dgsbjtCd"] = inp.dgsbjt
    if inp.clCd is not None:
        params["clCd"] = inp.clCd

    logger.debug(
        "hira_hospital_search: xPos=%.5f yPos=%.5f radius=%d page=%d rows=%d dgsbjt=%s clCd=%s",
        inp.xPos,
        inp.yPos,
        inp.radius,
        inp.pageNo,
        inp.numOfRows,
        inp.dgsbjt,
        inp.clCd,
    )

    own_client = client is None
    # Epic #2766 issue C — HIRA's `getHospBasisList` regularly takes 20-45 s
    # on cold-cache regional queries. The previous 30 s ceiling tripped on
    # second-attempt citizen flows ("Baked for 1m 5s" with no result, see
    # spec.md US3). Bump to 60 s so genuine slow upstreams complete; a real
    # network outage still surfaces as a clean timeout envelope (executor
    # _classify_adapter_exception → reason='upstream_unavailable').
    _client: httpx.AsyncClient = (
        traced_async_client(timeout=60.0) if own_client else client  # type: ignore[assignment]
    )

    try:
        response = await _client.get(_BASE_URL, params=params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "hira_hospital_search",
                f"HIRA API returned XML instead of JSON "
                f"(Content-Type: {content_type!r}). "
                "Ensure '_type=json' (underscore prefix) is in the request params.",
            )

        raw: dict[str, Any] = response.json()
    finally:
        if own_client:
            await _client.aclose()

    # HIRA uses a nested response envelope: response → body → items / totalCount
    response_body = raw.get("response", {})
    header = response_body.get("header", {})
    result_code = str(header.get("resultCode", ""))
    result_msg = str(header.get("resultMsg", "Unknown"))

    if result_code == "03":
        # NODATA_ERROR — return empty collection
        return {
            "kind": "collection",
            "items": [],
            "total_count": 0,
        }

    if result_code != "00":
        raise ToolExecutionError(
            "hira_hospital_search",
            f"HIRA API error: resultCode={result_code!r} resultMsg={result_msg!r}",
        )

    body = response_body.get("body", {})
    total_count = int(body.get("totalCount", 0))
    raw_items = body.get("items", {})

    item_list: list[dict[str, Any]] = []
    if raw_items and not isinstance(raw_items, str):
        raw_item = raw_items.get("item", [])
        if isinstance(raw_item, dict):
            item_list = [raw_item]
        elif isinstance(raw_item, list):
            item_list = raw_item

    items = [
        {
            "ykiho": item.get("ykiho", ""),
            "yadmNm": item.get("yadmNm", ""),
            "addr": item.get("addr", ""),
            "telno": item.get("telno", ""),
            "clCd": item.get("clCd", ""),
            "clCdNm": item.get("clCdNm", ""),
            "xPos": item.get("XPos"),
            "yPos": item.get("YPos"),
            "distance": item.get("distance"),
            "sidoCdNm": item.get("sidoCdNm", ""),
            "sgguCdNm": item.get("sgguCdNm", ""),
        }
        for item in item_list
    ]

    # D-fix: HIRA does NOT sort by distance server-side. Verified live
    # 2026-05-04: baseline call near 강남역 (37.498, 127.028) returned
    # d=829, 760, 479, 610, 757 (registration order). Citizens expect
    # "근처 X" to mean the actually-closest match. Sort ascending by the
    # `distance` string parsed as float; entries with missing/invalid
    # distance sink to the end deterministically.
    def _distance_key(rec: dict[str, Any]) -> tuple[int, float]:
        raw = rec.get("distance")
        if raw is None or raw == "":
            return (1, 0.0)  # missing distance → sort last
        try:
            return (0, float(raw))
        except (TypeError, ValueError):
            return (1, 0.0)

    items.sort(key=_distance_key)

    return {
        "kind": "collection",
        "items": items,
        "total_count": total_count,
    }


# ---------------------------------------------------------------------------
# Tool definition and registration helper (T054)
# ---------------------------------------------------------------------------


class _HiraHospitalSearchOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema for GovAPITool registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


_HIRA_DESCRIPTION = build_description_v4(
    purpose=(
        "Search HIRA (건강보험심사평가원) hospital registry for medical facilities "
        "within a WGS84 coordinate radius, optionally filtered by medical "
        "specialty (진료과목) and/or institution type (종별). Returns hospital "
        "name, address, phone, institution type, and distance — sorted by "
        "distance ascending (closest first). "
        "Use for: nearby hospitals, clinics, specialty-specific search "
        "(내과/소아과/안과/이비인후과/etc.), specific institution scale "
        "(의원 vs 종합병원 vs 상급종합)."
    ),
    input_quirk=(
        "xPos = longitude (124–132). yPos = latitude (33–39). "
        "Citizen location → resolve_location(want='coords') first. "
        "radius: 1500m '근처' / 3000m '주변' / max 10000m. "
        "dgsbjt + clCd are optional natural-language filters (see short_reference)."
    ),
    short_reference=(
        "Lat/lon direct (no grid). Response: yadmNm, addr, telno, clCdNm, ykiho, distance.\n"
        "DGSBJT pass Korean: 내과→01, 신경과→02, 정신과→03, 외과→04, 정형외과→05, "
        "신경외과→06, 흉부외과→07, 성형외과→08, 산부인과→10, 소아과→11, 안과→12, "
        "이비인후과→13, 피부과→14, 비뇨기과→15, 영상의학과→16, 재활의학과→21, "
        "가정의학과→23, 응급의학과→24, 한의원→80. English: pediatrics/ENT/dermatology.\n"
        "CLCD: 의원→31, 병원/종합병원→21, 상급종합→11, 치과병원→29, 약국→92, 보건소→51.\n"
        "Without dgsbjt result mixes 성형/안과/내과 — citizen rarely wants that."
    ),
    domain_quirk=(
        "JSON requires '_type=json' (underscore prefix). 'type=json' silently "
        "returns XML. Response coord fields uppercase: XPos/YPos. "
        "HIRA does NOT sort — KOSMOS sorts client-side by distance ASC, so the "
        "first item is the closest. Response does NOT echo dgsbjtCd back."
    ),
    self_contained_decl=(
        "REQUIRED: xPos/yPos. Citizen location ('동아대학교', '강남역') needs "
        "resolve_location(want='coords') first. ORDERING: turn1=resolve_location, "
        "turn2=this tool. When citizen says '근처 내과' / '강남역 소아과' / "
        "'큰 종합병원', map specialty/type to dgsbjt / clCd in the SAME call."
    ),
)

HIRA_HOSPITAL_SEARCH_TOOL = GovAPITool(
    id="hira_hospital_search",
    name_ko="병원 기본정보 조회 (좌표+반경)",
    ministry="HIRA",
    category=["의료", "병원", "의료기관", "진료"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=HiraHospitalSearchInput,
    output_schema=_HiraHospitalSearchOutput,
    llm_description=_HIRA_DESCRIPTION,
    search_hint=(
        "병원 검색 진료과목 의료기관 정보 근처 병원 내과 외과 소아과 "
        "hospital search medical specialty clinic nearby HIRA healthcare Korea"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.hira.or.kr/bbs/informationNotice.do?pgmid=HIRAA030011000000",
        real_classification_text="건강보험심사평가원 공공데이터 이용약관 — 병원 정보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    is_core=False,
    # Spec 031 T032/T033 dual-axis fields — None during pre-v1.2 compatibility window FR-028
    primitive="lookup",
    published_tier_minimum=None,
    nist_aal_hint=None,
    trigger_examples=[
        "근처 내과 병원",
        "강남역 소아과",
        "이비인후과 추천",
        "동아대 근처 종합병원",
        "성형외과 의원",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register HIRA hospital search tool and its adapter.

    Call this from register_all.py (Stage 3 / T056) to wire the adapter
    into the global registry and executor. Do NOT call from this module
    directly — the global registry is managed by register_all.py.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, HiraHospitalSearchInput)
        return await handle(inp)

    registry.register(HIRA_HOSPITAL_SEARCH_TOOL)
    executor.register_adapter("hira_hospital_search", _adapter)
    logger.info("Registered tool: hira_hospital_search")
