# SPDX-License-Identifier: Apache-2.0
"""KMA weather warning list adapter (기상특보목록 조회).

Wraps the ``getWthrWrnList`` endpoint from the Korea Meteorological Administration
(기상청) via the shared data.go.kr service key.
Returns a list of active weather warning (특보) announcements including
호우 / 폭염 / 한파 / 태풍 / 강풍 / 대설 / 황사 / 건조 / 풍랑.

Wire format quirks handled by this module:
  - Single-item response returns ``item`` as a dict (not array) — normalized to list.
  - XML is the default; JSON is requested via ``_type=json`` and ``dataType=JSON``.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
  - ``resultCode == "03"`` means no data — returns empty list, not an error.
  - Wire fields use camelCase; output model fields use snake_case.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kosmos.tools._description_template import build_description_v4
from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ToolExecutionError, _require_env
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.kma._short_references import KMA_STATION_SHORT_REFERENCE
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList"

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class KmaPreWarningInput(BaseModel):
    """Input parameters for the KMA weather pre-warning list (기상예비특보목록) API."""

    model_config = ConfigDict(frozen=True)

    num_of_rows: int = Field(
        default=100,
        ge=1,
        description="결과 행 수 (default 100, 보통 기본값).",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1).",
    )
    stn_id: str | None = Field(
        default=None,
        description=(
            "관측소 ID (optional, KMA station code). 없으면 전국 결과. "
            "예: 서울=108, 부산=159, 대구=143, 인천=112. 시민 발화에 명확한 시도/광역시가 "
            "있을 때만 명시. 모호하거나 전국 단위면 null."
        ),
    )
    data_type: Literal["JSON", "XML"] = Field(
        default="JSON",
        description="응답 형식 (JSON 권장).",
    )


class PreWarningItem(BaseModel):
    """A single pre-warning announcement from KMA getWthrPwnList."""

    model_config = ConfigDict(frozen=True)

    stn_id: str
    """Station/region ID that issued the pre-warning."""

    title: str
    """Announcement title (e.g., '[예비] 제06-7호 : 2017.06.07.07:30')."""

    tm_fc: str
    """Announcement time in YYYYMMDDHHMI format."""

    tm_seq: int
    """Monthly sequence number of this announcement."""


class KmaPreWarningOutput(BaseModel):
    """Output from the kma_pre_warning tool."""

    model_config = ConfigDict(frozen=True)

    total_count: int
    """Total number of pre-warning items available."""

    items: list[PreWarningItem]
    """Pre-warning announcement items for the requested page."""


# ---------------------------------------------------------------------------
# Response normalization helpers
# ---------------------------------------------------------------------------


def _normalize_items(raw: object) -> list[dict[str, Any]]:
    """Normalize the ``items.item`` value from the KMA wire response.

    The KMA API returns:
    - A list of dicts when multiple results are found.
    - A single dict (not wrapped in a list) when exactly one result is found.
    - An empty string, None, or missing key when no results are found.

    Args:
        raw: The raw value of ``response.body.items.item``.

    Returns:
        A list of item dicts. Empty list for no-data responses.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return raw
    logger.warning(
        "Unexpected items type %s from KMA pre-warning API; treating as empty", type(raw)
    )
    return []


def _parse_response(raw: dict[str, Any]) -> KmaPreWarningOutput:
    """Parse the full KMA getWthrPwnList JSON response body into a KmaPreWarningOutput.

    Args:
        raw: Parsed JSON dict from the KMA API.

    Returns:
        Validated KmaPreWarningOutput with announcement items.

    Raises:
        ToolExecutionError: If resultCode is not "00" or "03".
    """
    header = raw.get("response", {}).get("header", {})
    result_code = str(header.get("resultCode", ""))
    result_msg = str(header.get("resultMsg", "Unknown error"))

    # Code "03" means NO_DATA — no active pre-warnings.  This is a
    # legitimate empty result (common when no weather events are developing).
    if result_code == "03":
        logger.info("KMA pre-warning: no pre-warnings available (resultCode=03)")
        return KmaPreWarningOutput(total_count=0, items=[])

    if result_code != "00":
        raise ToolExecutionError(
            "kma_pre_warning",
            f"KMA API returned error: code={result_code!r} msg={result_msg!r}",
        )

    body = raw.get("response", {}).get("body", {})
    total_count = int(str(body.get("totalCount", 0)))

    # items may be {"item": [...]} or {"item": {}} or "" or missing
    raw_items_container = body.get("items", {})
    if isinstance(raw_items_container, str) or not raw_items_container:
        item_list: list[dict[str, Any]] = []
    else:
        raw_item = raw_items_container.get("item", [])
        item_list = _normalize_items(raw_item)

    parsed_items: list[PreWarningItem] = []
    for wire_item in item_list:
        parsed_items.append(
            PreWarningItem(
                stn_id=str(wire_item.get("stnId", "")),
                title=str(wire_item.get("title", "")),
                tm_fc=str(wire_item.get("tmFc", "")),
                tm_seq=int(str(wire_item.get("tmSeq", 0))),
            )
        )

    return KmaPreWarningOutput(total_count=total_count, items=parsed_items)


# ---------------------------------------------------------------------------
# Async adapter function
# ---------------------------------------------------------------------------


async def _call(
    inp: KmaPreWarningInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Async adapter for kma_pre_warning.

    Fetches weather warning list data from the KMA getWthrWrnList endpoint.
    Handles JSON vs. XML content-type guard, error code mapping, and response parsing.

    Args:
        inp: Validated input parameters.
        client: Optional httpx.AsyncClient for test injection. If None, a new
                client is created for this call.

    Returns:
        A plain dict matching KmaPreWarningOutput schema.

    Raises:
        ConfigurationError: If KOSMOS_DATA_GO_KR_API_KEY is not set.
        ToolExecutionError: If the API returns a non-"00" result code or XML response.
    """
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "numOfRows": inp.num_of_rows,
        "pageNo": inp.page_no,
        "dataType": inp.data_type,
        "_type": "json",
    }

    if inp.stn_id is not None:
        params["stnId"] = inp.stn_id

    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client() if own_client else client  # type: ignore[assignment]
    assert _client is not None  # narrow: either injected or freshly created above

    try:
        logger.debug(
            "Calling KMA getWthrPwnList: numOfRows=%s pageNo=%s stnId=%s",
            inp.num_of_rows,
            inp.page_no,
            inp.stn_id,
        )
        response = await _client.get(_BASE_URL, params=params, timeout=30.0)
        response.raise_for_status()

        # XML fallback guard: some data.go.kr endpoints ignore _type=json
        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "kma_pre_warning",
                f"KMA API returned XML instead of JSON (Content-Type: {content_type!r}). "
                "Add Accept: application/json header or check _type parameter.",
            )

        raw = response.json()
        output = _parse_response(raw)
        return output.model_dump()

    finally:
        if own_client:
            await _client.aclose()


# ---------------------------------------------------------------------------
# Tool definition and registration helper
# ---------------------------------------------------------------------------

KMA_PRE_WARNING_TOOL = GovAPITool(
    id="kma_pre_warning",
    name_ko="기상특보목록 조회",
    llm_description=build_description_v4(
        purpose=(
            "기상청 특보목록 (getWthrWrnList) — 현재 발효 중인 기상특보 목록 조회. "
            "호우 / 폭염 / 한파 / 태풍 / 강풍 / 대설 / 황사 / 건조 / 풍랑 특보 포함. "
            "시민이 '경보 있어' / '특보 확인' / '호우 주의보 떠 있나' 묻는 경우 호출."
        ),
        input_quirk=(
            "stn_id (optional): 기상청 관측소 코드. "
            "시민 발화에 명확한 시도/광역시가 있을 때만 사용; 모호하면 null (전국 결과). "
            "num_of_rows default=100, page_no default=1. dataType=JSON 권장."
        ),
        short_reference=KMA_STATION_SHORT_REFERENCE,
        domain_quirk=(
            "resultCode '00'=정상, '03'=특보없음 (에러 아님, 빈 목록 반환). "
            "HTTP 200 이어도 resultCode 확인 필수. "
            "tmFc 는 integer (yyyyMMddHHmi), tmSeq 는 당월 순번."
        ),
        self_contained_decl=(
            "이 도구 단독 호출로 완결. cross-domain chain 불필요. "
            "특보 상세 내용이 필요하면 LLM 이 자율적으로 "
            "turn 2 = kma_weather_alert_status (stn_id 전달) 선택 가능."
        ),
    ),
    ministry="KMA",
    category=["기상", "예비특보", "특보"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaPreWarningInput,
    output_schema=KmaPreWarningOutput,
    search_hint=(
        "기상예비특보 예비특보 태풍예고 호우예고 대설예고 한파예고 폭염예고 강풍예고 "
        "미세먼지 지역 알림 부모님 확인 "
        "weather pre-warning preliminary alert typhoon heavy-rain snow cold-wave heat wind"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 기상특보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="lookup",
    trigger_examples=[
        "오늘 서울 호우주의 예비특보",
        "태풍 예비특보",
    ],
)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register KMA pre-warning tool and its adapter.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from typing import cast

    from kosmos.tools.executor import AdapterFn

    registry.register(KMA_PRE_WARNING_TOOL)

    # Audit G4 / F-beta-01 fix — wrap raw KmaPreWarningOutput in a
    # ``LookupCollection``-shaped envelope so ``envelope.normalize()``
    # accepts it (5-variant LookupOutput discriminator). The previous
    # registration handed ``_call`` directly to ``register_adapter``,
    # which returned ``{total_count, items}`` — no ``kind`` field, so
    # the discriminator extraction failed and surfaced as
    # ``Unable to extract tag using discr`` in β6 capture (2026-05-05).
    # Sibling pattern: ``kma_short_term_forecast.py:432-440``.
    async def _kma_pre_warning_adapter(inp: BaseModel) -> dict[str, object]:
        raw = await _call(cast("KmaPreWarningInput", inp))
        # Pre-warning is a list of announcements; ``collection`` is the
        # canonical 5-variant variant for "list of records".
        return {
            "kind": "collection",
            "items": list(raw.get("items", [])),
            "total_count": int(raw.get("total_count", 0)),
        }

    executor.register_adapter("kma_pre_warning", cast(AdapterFn, _kma_pre_warning_adapter))
    logger.info("Registered tool: kma_pre_warning")
