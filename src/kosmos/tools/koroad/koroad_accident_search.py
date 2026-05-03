# SPDX-License-Identifier: Apache-2.0
"""KOROAD accident hotspot search adapter.

Wraps the ``getRestFrequentzoneLg`` endpoint from KOROAD (B552061/frequentzoneLg/).
Returns accident-prone zones by municipality and year category, with full coordinates.

Wire format quirks handled by this module:
  - Single-item response returns `item` as a dict (not array) — normalized to list.
  - XML is the default; JSON is requested via ``type=json``.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ToolExecutionError, _require_env
from kosmos.tools.koroad._short_references import (
    KOROAD_GUGUN_REFERENCE,
    KOROAD_SIDO_SHORT_REFERENCE,
)
from kosmos.tools.koroad.code_tables import (
    GANGWON_NEW_CODE_YEAR,
    JEONBUK_NEW_CODE_YEAR,
    GugunCode,
    SearchYearCd,
    SidoCode,
)
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KOROAD API endpoint constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://apis.data.go.kr/B552061/frequentzoneLg/getRestFrequentzoneLg"


# ---------------------------------------------------------------------------
# Pydantic v2 I/O Models (T014)
# ---------------------------------------------------------------------------


class AccidentHotspot(BaseModel):
    """A single accident hotspot zone returned by KOROAD getRestFrequentzoneLg."""

    model_config = ConfigDict(frozen=True, coerce_numbers_to_str=True)

    spot_cd: str
    """Unique spot code."""

    spot_nm: str
    """Location name (Korean)."""

    sido_sgg_nm: str
    """Province + district combined name (Korean)."""

    bjd_cd: str
    """Administrative district (법정동) code."""

    occrrnc_cnt: int
    """Accident occurrence count."""

    caslt_cnt: int
    """Total casualty count."""

    dth_dnv_cnt: int
    """Death count."""

    se_dnv_cnt: int
    """Serious injury count."""

    sl_dnv_cnt: int
    """Minor injury count."""

    wnd_dnv_cnt: int
    """Injury count."""

    la_crd: float
    """Latitude (decimal degrees)."""

    lo_crd: float
    """Longitude (decimal degrees)."""

    geom_json: str | None = None
    """GeoJSON polygon string; may be absent in the wire response."""

    afos_id: str
    """Year-dataset identifier (e.g. '2025119' for 2024 general)."""

    afos_fid: str
    """Feature ID within the dataset."""


class KoroadAccidentSearchInput(BaseModel):
    """Input parameters for the koroad_accident_search tool.

    Cross-validates legacy sido codes against modern search year codes.
    """

    model_config = ConfigDict(frozen=True)

    search_year_cd: SearchYearCd = Field(
        ...,
        description=(
            "사고 통계 연도 / 카테고리 코드 (KOROAD searchYearCd wire param). "
            "보통 직전 연도 사용 (당해 데이터는 매년 6월 이후 publish). "
            "valid 값은 SearchYearCd enum 참조."
        ),
    )

    si_do: SidoCode = Field(
        description=(
            # Section 1 — what this field is
            "2-digit 광역시도 code for the KOROAD siDo wire parameter. "
            # Section 2 — sourcing rule (mandatory geocoding prerequisite)
            "MUST be derived from a prior resolve_location geocoding tool call "
            "on the user-provided location string — never fill this from model memory. "
            # Section 3 — short reference table (17 시도, 2-digit codes)
            f"[SHORT REFERENCE] {KOROAD_SIDO_SHORT_REFERENCE}. "
            # Section 4 — empirical counter-example
            "Empirical counter-example: a Korean-domain LLM produced gu_gun=110 (Jongno) "
            "instead of gu_gun=680 (Gangnam) for a '강남역' query because it guessed from "
            "memory rather than consulting geocoding. "
            # Section 5 — authoritative enum reference
            "Valid codes are defined in the SidoCode enumeration."
        )
    )
    """2-digit 광역시도 code (siDo wire parameter). See Field description for sourcing rules."""

    gu_gun: GugunCode = Field(
        description=(
            "3-digit 시군구 code for the KOROAD guGun wire parameter. Required by the KOROAD API. "
            "MUST be derived from a prior resolve_location geocoding tool call "
            "on the user-provided location string — never fill this from model memory. "
            "[WIRE FORMAT] siDo is 2-digit (e.g. '11'=서울), guGun is 3-digit (e.g. '680'=강남구). "
            "Do NOT use 4-digit 행정구역코드 (e.g. '1100', '1168') — the API rejects them. "
            "Empirical counter-example: a Korean-domain LLM produced gu_gun=110 (Jongno) "
            "instead of gu_gun=680 (Gangnam) for a '강남역' query because it guessed from "
            "memory rather than consulting geocoding. "
            # Spec 2522 — 사용자 디렉티브 "코드체계 노출". GugunCode IntEnum name 의
            # 영문 transliteration → K-EXAONE 시민 한국어 발화 ("강남구") → "seoul
            # gangnam=680" 매칭 추론. Pydantic JSON schema 가 IntEnum name 을
            # standard export X 라 description 에 인라인.
            f"매핑 (광역시도+시군구=KOROAD wire code): {KOROAD_GUGUN_REFERENCE}"
        )
    )
    """3-digit 시군구 code (guGun wire parameter). See Field description for sourcing rules."""

    num_of_rows: int = Field(
        default=10,
        ge=1,
        le=100,
        description="결과 행 수 (default 10, max 100). 보통 기본값.",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1).",
    )

    @model_validator(mode="after")
    def _validate_legacy_sido(self) -> KoroadAccidentSearchInput:
        """Reject legacy sido codes used with 2023+ year codes."""
        year = self.search_year_cd.year
        if self.si_do == SidoCode.GANGWON_LEGACY and year >= GANGWON_NEW_CODE_YEAR:
            raise ValueError(
                "sido=42 (강원도) is only valid for pre-2023 datasets. "
                "Use sido=51 (강원특별자치도) for 2023+ data."
            )
        if self.si_do == SidoCode.JEONBUK_LEGACY and year >= JEONBUK_NEW_CODE_YEAR:
            raise ValueError(
                "sido=45 (전라북도) is only valid for pre-2023 datasets. "
                "Use sido=52 (전북특별자치도) for 2023+ data."
            )
        return self


class KoroadAccidentSearchOutput(BaseModel):
    """Output from the koroad_accident_search tool."""

    model_config = ConfigDict(frozen=True)

    total_count: int
    """Total number of hotspot records matching the query."""

    page_no: int
    """Current page number."""

    num_of_rows: int
    """Rows per page requested."""

    hotspots: list[AccidentHotspot]
    """List of accident hotspot zones. Empty when no results."""


# ---------------------------------------------------------------------------
# Response normalization helpers (T015)
# ---------------------------------------------------------------------------


def _normalize_items(items: object) -> list[dict[str, Any]]:
    """Normalize the ``items.item`` value from KOROAD wire response.

    The KOROAD API returns:
    - A list of dicts when multiple results are found.
    - A single dict (not wrapped in a list) when exactly one result is found.
    - An empty string, None, or missing key when no results are found.

    This function normalizes all three cases to a plain Python list.

    Args:
        items: The raw value of ``response.body.items`` (or its ``item`` key).

    Returns:
        A list of item dicts. Empty list for no-data responses.
    """
    if not items:
        return []
    if isinstance(items, dict):
        # Single-item quirk: wrap in list
        return [items]
    if isinstance(items, list):
        return items
    # Unexpected type; log and treat as empty
    logger.warning("Unexpected items type %s from KOROAD API; treating as empty", type(items))
    return []


def _parse_response(raw: dict[str, Any]) -> KoroadAccidentSearchOutput:
    """Parse the full KOROAD JSON response body into a KoroadAccidentSearchOutput.

    The KOROAD ``type=json`` response is flat::

        {"resultCode": "00", "resultMsg": "NORMAL_CODE",
         "items": {"item": [...]}, "totalCount": 3, ...}

    Args:
        raw: Parsed JSON dict from the KOROAD API.

    Returns:
        Validated KoroadAccidentSearchOutput.

    Raises:
        ToolExecutionError: If resultCode is not "00".
    """
    result_code = str(raw.get("resultCode", ""))
    result_msg = str(raw.get("resultMsg", "Unknown error"))

    # NODATA_ERROR (code "03") means no matching records — return empty results.
    if result_code == "03":
        logger.info("KOROAD NODATA_ERROR: no matching records for query")
        return KoroadAccidentSearchOutput(
            total_count=0,
            page_no=int(raw.get("pageNo", 1)),
            num_of_rows=int(raw.get("numOfRows", 10)),
            hotspots=[],
        )

    if result_code != "00":
        raise ToolExecutionError(
            "koroad_accident_search",
            f"KOROAD API returned error: code={result_code!r} msg={result_msg!r}",
        )

    total_count = int(raw.get("totalCount", 0))
    page_no = int(raw.get("pageNo", 1))
    num_of_rows = int(raw.get("numOfRows", 10))

    # items may be {"item": [...]} or {"item": {}} or "" or missing
    raw_items = raw.get("items", {})
    if isinstance(raw_items, str) or not raw_items:
        item_list: list[dict[str, Any]] = []
    else:
        raw_item = raw_items.get("item", [])
        item_list = _normalize_items(raw_item)

    hotspots = [AccidentHotspot(**item) for item in item_list]

    return KoroadAccidentSearchOutput(
        total_count=total_count,
        page_no=page_no,
        num_of_rows=num_of_rows,
        hotspots=hotspots,
    )


# ---------------------------------------------------------------------------
# Async adapter function (T016)
# ---------------------------------------------------------------------------


async def _call(
    inp: KoroadAccidentSearchInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Async adapter for koroad_accident_search.

    Fetches accident hotspot data from the KOROAD getRestFrequentzoneLg endpoint.
    Handles JSON vs. XML content-type guard, error code mapping, and response parsing.

    Args:
        inp: Validated input parameters.
        client: Optional httpx.AsyncClient for test injection. If None, a new
                client is created for this call.

    Returns:
        A plain dict matching KoroadAccidentSearchOutput schema.

    Raises:
        ConfigurationError: If KOSMOS_DATA_GO_KR_API_KEY is not set.
        ToolExecutionError: If the API returns a non-"00" result code.
    """
    # KOROAD APIs are hosted on apis.data.go.kr and share the same
    # service key as other data.go.kr APIs (KMA, etc.).
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "searchYearCd": inp.search_year_cd.value,
        "siDo": inp.si_do.value,
        "numOfRows": inp.num_of_rows,
        "pageNo": inp.page_no,
        "type": "json",
    }
    params["guGun"] = inp.gu_gun.value

    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client() if own_client else client  # type: ignore[assignment]
    assert _client is not None  # narrowed: always an AsyncClient at this point

    try:
        logger.debug(
            "Calling KOROAD getRestFrequentzoneLg: sido=%s gugun=%s year=%s",
            inp.si_do.value,
            inp.gu_gun,
            inp.search_year_cd.value,
        )
        response = await _client.get(_BASE_URL, params=params, timeout=30.0)
        response.raise_for_status()

        # XML fallback guard: some data.go.kr endpoints ignore _type=json
        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "koroad_accident_search",
                f"KOROAD API returned XML instead of JSON (Content-Type: {content_type!r}). "
                "Add Accept: application/json header or check _type parameter.",
            )

        raw = response.json()
        output = _parse_response(raw)
        return output.model_dump()

    finally:
        if own_client:
            await _client.aclose()


# ---------------------------------------------------------------------------
# Tool definition and registration helper (T017)
# ---------------------------------------------------------------------------

KOROAD_ACCIDENT_SEARCH_TOOL = GovAPITool(
    id="koroad_accident_search",
    name_ko="교통사고 위험지역 조회",
    ministry="KOROAD",
    category=["교통안전", "사고통계", "위험지역"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KoroadAccidentSearchInput,
    output_schema=KoroadAccidentSearchOutput,
    llm_description=(
        "Query the authoritative KOROAD accident-prone hotspot dataset for a "
        "Korean municipality. To call this tool correctly: first invoke "
        "`resolve_location` with the citizen's place name to obtain the "
        "accurate si_do and gu_gun codes, then pass those codes here. "
        "This is the canonical source for Korean accident hotspot data — "
        "use it whenever the citizen asks about traffic accidents, dangerous "
        "zones, or road safety in a named location."
    ),
    search_hint=(
        "교통사고 위험지역 조회 사고다발구역 지자체별 위험지점 "
        "accident hotspot dangerous zone traffic safety municipality"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.koroad.or.kr/main/web/policy/data_use.do",
        real_classification_text="도로교통공단 공공데이터 이용약관 — 교통사고 위험지역 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=3600,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="lookup",
    trigger_examples=[
        "교차로 사고 통계",
        "음주운전 사고 다발",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register KOROAD accident search tool and its adapter.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, KoroadAccidentSearchInput)
        return await _call(inp)

    registry.register(KOROAD_ACCIDENT_SEARCH_TOOL)
    executor.register_adapter("koroad_accident_search", _adapter)
    logger.info("Registered tool: koroad_accident_search")
