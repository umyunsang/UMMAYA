# SPDX-License-Identifier: Apache-2.0
"""KMA weather alert status adapter.

Wraps the ``getWthrWrnList`` endpoint from the Korea Meteorological Administration
(기상청) via the shared data.go.kr service key.
Returns the current list of active weather warnings and watches for all regions.

Wire format quirks handled by this module:
  - Single-item response returns ``item`` as a dict (not array) — normalized to list.
  - XML is the default; JSON is requested via ``_type=json`` and ``dataType=JSON``.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
  - Items with ``cancel == 1`` are cancelled alerts and must be filtered out.
  - Wire fields use camelCase; output model fields use snake_case.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ConfigurationError, ToolExecutionError, _require_env  # noqa: F401
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KMA API endpoint constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnList"

# Mapping from wire camelCase field names to snake_case model field names
_FIELD_MAP: dict[str, str] = {
    "stnId": "stn_id",
    "tmFc": "tm_fc",
    "tmEf": "tm_ef",
    "tmSeq": "tm_seq",
    "areaCode": "area_code",
    "areaName": "area_name",
    "warnVar": "warn_var",
    "warnStress": "warn_stress",
    "cancel": "cancel",
    "command": "command",
    "warFc": "warn_fc",
}


# ---------------------------------------------------------------------------
# Pydantic v2 I/O Models
# ---------------------------------------------------------------------------


class KmaWeatherAlertStatusInput(BaseModel):
    """Input parameters for the kma_weather_alert_status tool."""

    model_config = ConfigDict(frozen=True)

    num_of_rows: int = Field(
        default=2000,
        ge=1,
        description="결과 행 수 (default 2000, 한 페이지에 전국 모든 특보 포함).",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1).",
    )
    data_type: Literal["JSON", "XML"] = Field(
        default="JSON",
        description="응답 형식 (JSON 권장).",
    )


class WeatherWarning(BaseModel):
    """A single active weather warning or watch from KMA getWthrWrnList.

    The wire response is inconsistent: some responses return the full 11-field
    schema, others return only a compact ``{stnId, tmFc, tmSeq}`` triple
    (observed live on 2026-04-14).  All fields other than ``stn_id`` and
    ``tm_fc`` are therefore Optional; consumers should handle ``None``.
    ``tm_fc`` arrives as int (e.g. ``202604141000``) in some responses and is
    coerced to the canonical YYYYMMDDHHMI string.
    """

    model_config = ConfigDict(frozen=True)

    stn_id: str
    """Station/region ID."""

    tm_fc: str
    """Announcement time in YYYYMMDDHHMI format (coerced from int if needed)."""

    tm_ef: str | None = None
    """Effective time in YYYYMMDDHHMI format (absent in compact responses)."""

    tm_seq: int = 0
    """Sequence number within the announcement."""

    area_code: str | None = None
    """Warning zone code (e.g. 'S1151300')."""

    area_name: str | None = None
    """Korean warning zone name (e.g. '서울')."""

    warn_var: int | None = None
    """Warning type code.
    1=강풍, 2=호우, 3=한파, 4=건조, 5=해일, 6=태풍, 7=대설, 8=황사, 11=폭염.
    """

    warn_stress: int | None = None
    """Severity code. 0=주의보 (watch), 1=경보 (warning)."""

    cancel: int = 0
    """Cancellation flag. 0=active, 1=cancelled."""

    command: int | None = None
    """Command code from KMA."""

    warn_fc: int | None = None
    """Warning forecast flag."""

    @field_validator("tm_fc", "tm_ef", mode="before")
    @classmethod
    def _coerce_time_to_str(cls, v: object) -> object:
        """KMA occasionally emits tmFc/tmEf as int; coerce to string."""
        if isinstance(v, int):
            return str(v)
        return v


class KmaWeatherAlertStatusOutput(BaseModel):
    """Output from the kma_weather_alert_status tool."""

    model_config = ConfigDict(frozen=True)

    total_count: int
    """Count of active (non-cancelled) warnings."""

    warnings: list[WeatherWarning]
    """Active warnings only (cancel=0)."""


# ---------------------------------------------------------------------------
# Response normalization helpers
# ---------------------------------------------------------------------------


def _normalize_items(items: object) -> list[dict[str, Any]]:
    """Normalize the ``items.item`` value from KMA wire response.

    The KMA API returns:
    - A list of dicts when multiple results are found.
    - A single dict (not wrapped in a list) when exactly one result is found.
    - An empty string, None, or missing key when no results are found.

    This function normalizes all three cases to a plain Python list.

    Args:
        items: The raw value of ``response.body.items.item`` (or similar).

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
    logger.warning("Unexpected items type %s from KMA API; treating as empty", type(items))
    return []


def _parse_response(raw: dict[str, Any]) -> KmaWeatherAlertStatusOutput:
    """Parse the full KMA JSON response body into a KmaWeatherAlertStatusOutput.

    Filters out cancelled alerts (cancel=1) before building the output.

    Args:
        raw: Parsed JSON dict from the KMA API.

    Returns:
        Validated KmaWeatherAlertStatusOutput with only active (non-cancelled) warnings.

    Raises:
        ToolExecutionError: If resultCode is not "00".
    """
    header = raw.get("response", {}).get("header", {})
    result_code = str(header.get("resultCode", ""))
    result_msg = str(header.get("resultMsg", "Unknown error"))

    # code "03" means NO_DATA — no active weather alerts exist.  This is a
    # legitimate empty result, not an error (common when no weather events).
    if result_code == "03":
        logger.info("KMA weather alert: no active alerts (resultCode=03)")
        return KmaWeatherAlertStatusOutput(total_count=0, warnings=[])

    if result_code != "00":
        raise ToolExecutionError(
            "kma_weather_alert_status",
            f"KMA API returned error: code={result_code!r} msg={result_msg!r}",
        )

    body = raw.get("response", {}).get("body", {})

    # items may be {"item": [...]} or {"item": {}} or "" or missing
    raw_items = body.get("items", {})
    if isinstance(raw_items, str) or not raw_items:
        item_list: list[dict[str, Any]] = []
    else:
        raw_item = raw_items.get("item", [])
        item_list = _normalize_items(raw_item)

    # Map wire camelCase fields to snake_case and filter out cancelled alerts
    active_warnings: list[WeatherWarning] = []
    for wire_item in item_list:
        mapped = {_FIELD_MAP[k]: v for k, v in wire_item.items() if k in _FIELD_MAP}
        if mapped.get("cancel") == 1:
            continue
        active_warnings.append(WeatherWarning(**mapped))

    return KmaWeatherAlertStatusOutput(
        total_count=len(active_warnings),
        warnings=active_warnings,
    )


# ---------------------------------------------------------------------------
# Async adapter function
# ---------------------------------------------------------------------------


async def _call(
    inp: KmaWeatherAlertStatusInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Async adapter for kma_weather_alert_status.

    Fetches current weather alert data from the KMA getWthrWrnList endpoint.
    Handles JSON vs. XML content-type guard, error code mapping, and response parsing.
    Cancelled alerts (cancel=1) are automatically excluded from the output.

    Args:
        inp: Validated input parameters.
        client: Optional httpx.AsyncClient for test injection. If None, a new
                client is created for this call.

    Returns:
        A plain dict matching KmaWeatherAlertStatusOutput schema.

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

    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client() if own_client else client  # type: ignore[assignment]
    assert _client is not None  # narrow: either injected or freshly created above

    try:
        logger.debug(
            "Calling KMA getWthrWrnList: numOfRows=%s pageNo=%s",
            inp.num_of_rows,
            inp.page_no,
        )
        response = await _client.get(_BASE_URL, params=params, timeout=30.0)
        response.raise_for_status()

        # XML fallback guard: some data.go.kr endpoints ignore _type=json
        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "kma_weather_alert_status",
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

KMA_WEATHER_ALERT_STATUS_TOOL = GovAPITool(
    id="kma_weather_alert_status",
    name_ko="기상특보 현황 조회",
    llm_description=(
        "기상청 기상특보 현황 — **현재 발효 중**인 호우경보 / 폭염주의보 / 한파특보 / "
        "태풍주의보 등 전국 활성 특보 목록. 시민이 '지금 경보 발효 중' / '호우 경보 떠 있어' / "
        "'태풍 어디까지 와' 같은 즉시 위험 정보를 묻는 경우. **사전 경보** (앞으로 발효 예정) 는 "
        "kma_pre_warning 사용. parameters 모두 default 사용 — 매개변수 추측 불필요."
    ),
    ministry="KMA",
    category=["기상", "특보", "경보"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaWeatherAlertStatusInput,
    output_schema=KmaWeatherAlertStatusOutput,
    search_hint=(
        "기상특보 기상경보 태풍 호우 대설 한파 폭염 강풍 "
        "weather warning alert typhoon heavy rain snow cold wave heat wind"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 기상경보 현황 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="lookup",
    trigger_examples=[
        "현재 발효 중인 특보",
        "서울 폭염주의보 있나",
    ],
)


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register KMA weather alert status tool and its adapter.

    Args:
        registry: The central ``ToolRegistry`` to add the tool to.
        executor: The ``ToolExecutor`` to bind the adapter function to.
    """
    from typing import cast

    from kosmos.tools.executor import AdapterFn

    registry.register(KMA_WEATHER_ALERT_STATUS_TOOL)
    executor.register_adapter("kma_weather_alert_status", cast(AdapterFn, _call))
    logger.info("Registered tool: kma_weather_alert_status")
