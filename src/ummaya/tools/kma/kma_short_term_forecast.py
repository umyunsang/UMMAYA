# SPDX-License-Identifier: Apache-2.0
"""KMA short-term forecast adapter (단기예보 조회).

Wraps the ``getVilageFcst`` endpoint from the Korea Meteorological Administration
(기상청) via the KMA API Hub ``authKey`` surface.
Returns a list of forecast items covering approximately 3 days ahead, published
8 times a day at 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 KST.

Wire format quirks handled by this module:
  - Single-item response returns ``item`` as a dict (not array) — normalized to list.
  - XML is the official default; JSON is requested only when explicitly selected.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
  - Wire fields use camelCase; output model fields use snake_case.
  - PCP / SNO values may be strings like "30.0~50.0mm" — stored as-is.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ummaya.tools._description_template import build_description_v4
from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.grid_coords import kma_grid_short_reference
from ummaya.tools.kma.response_payload import (
    KmaPayloadDecodeError,
    apply_format_params,
    decode_response_payload,
    summarize_http_status_error,
)
from ummaya.tools.kma.vilage_fcst_endpoint import (
    KMA_API_HUB_VILAGE_FCST_BASE_URL,
    resolve_vilage_fcst_endpoint,
)
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_SEOUL_TZ = ZoneInfo("Asia/Seoul")
_OPERATION = "getVilageFcst"
_BASE_URL = f"{KMA_API_HUB_VILAGE_FCST_BASE_URL}/{_OPERATION}"

# Valid base times for the short-term forecast service (KST)
_BASE_TIME_ORDER: tuple[str, ...] = (
    "0200",
    "0500",
    "0800",
    "1100",
    "1400",
    "1700",
    "2000",
    "2300",
)
_VALID_BASE_TIMES = frozenset(_BASE_TIME_ORDER)
_NO_DATA_RESULT_CODE = "03"
_MAX_BASE_SLOT_ATTEMPTS = 9
_RECENT_BASE_SLOT_RETENTION_DAYS = 3

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class KmaShortTermForecastInput(BaseModel):
    """Input parameters for the KMA short-term forecast (단기예보) API."""

    model_config = ConfigDict(frozen=True)

    base_date: str = Field(
        ...,
        description=("예보 발표 날짜 (YYYYMMDD). 보통 오늘. Do not copy sample dates."),
    )
    base_time: str = Field(
        ...,
        description=(
            "예보 발표 시각 (HHMM, 24-hour, no separator). "
            "유효 값 8개: 0200 / 0500 / 0800 / 1100 / 1400 / 1700 / 2000 / 2300. "
            "각 발표 시각의 약 +10분 후 데이터 안정. 현재 시각의 직전 발표 시각 사용."
        ),
    )
    nx: int = Field(
        ...,
        ge=1,
        le=149,
        description=(
            "KMA 격자 X 좌표 (1-149). locate adapter 결과의 coords.nx 를 "
            "그대로 전달. Do not substitute a memorized city example."
        ),
    )
    ny: int = Field(
        ...,
        ge=1,
        le=253,
        description=(
            "KMA 격자 Y 좌표 (1-253). nx 와 함께 locate 으로 받음. "
            "Do not substitute a memorized city example."
        ),
    )
    num_of_rows: int = Field(
        default=290,
        ge=1,
        description=("결과 행 수 (default 290 = 1 격자 단기예보 full dataset). 보통 기본값 사용."),
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1). 보통 기본값.",
    )
    data_type: Literal["JSON", "XML"] = Field(
        default="XML",
        description="응답 형식. XML is the official default; JSON is available if requested.",
    )

    @field_validator("base_date")
    @classmethod
    def _validate_base_date(cls, v: str) -> str:
        if not re.fullmatch(r"\d{8}", v):
            raise ValueError(f"base_date must be YYYYMMDD, got {v!r}")
        return v

    @field_validator("base_time")
    @classmethod
    def _validate_base_time(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError(f"base_time must be HHMM, got {v!r}")
        if v not in _VALID_BASE_TIMES:
            raise ValueError(f"base_time must be one of {sorted(_VALID_BASE_TIMES)}, got {v!r}")
        return v


class ForecastItem(BaseModel):
    """A single forecast data point from the KMA short-term or ultra-short-term API."""

    model_config = ConfigDict(frozen=True)

    base_date: str
    """Base date of the forecast publication in YYYYMMDD format."""

    base_time: str
    """Base time of the forecast publication in HHMM format."""

    fcst_date: str
    """Forecast target date in YYYYMMDD format."""

    fcst_time: str
    """Forecast target time in HHMM format."""

    nx: int
    """Grid X coordinate."""

    ny: int
    """Grid Y coordinate."""

    category: str
    """Forecast category code.

    Examples: TMP (temperature), SKY (sky condition), PTY (precipitation type),
    POP (precipitation probability), REH (humidity), WSD (wind speed),
    UUU (east-west wind), VVV (north-south wind), VEC (wind direction),
    WAV (wave height), PCP (precipitation amount), SNO (snowfall),
    TMN (minimum temperature), TMX (maximum temperature).
    """

    fcst_value: str
    """Forecast value as a string (numeric values or code strings like '30.0~50.0mm')."""


class KmaShortTermForecastOutput(BaseModel):
    """Output from the kma_short_term_forecast tool."""

    model_config = ConfigDict(frozen=True)

    total_count: int
    """Total number of forecast items available for this query."""

    items: list[ForecastItem]
    """Forecast items for the requested page."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_items(raw: object) -> list[dict[str, object]]:
    """Coerce the KMA items payload into a plain list of dicts.

    The KMA API returns ``items.item`` as either a list (multiple rows) or a
    single dict (one row).  An empty / missing value yields an empty list.

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
        return [row for row in raw if isinstance(row, dict)]
    logger.warning("Unexpected items type %s from KMA forecast API; treating as empty", type(raw))
    return []


def _previous_base_slot(base_date: str, base_time: str) -> tuple[str, str]:
    """Return the previous KMA short-term forecast publication slot."""
    idx = _BASE_TIME_ORDER.index(base_time)
    if idx > 0:
        return base_date, _BASE_TIME_ORDER[idx - 1]

    base_day = datetime.strptime(base_date, "%Y%m%d").replace(tzinfo=_SEOUL_TZ)
    prev_day = base_day - timedelta(days=1)
    return prev_day.strftime("%Y%m%d"), _BASE_TIME_ORDER[-1]


def _candidate_base_slots(
    base_date: str,
    base_time: str,
    *,
    max_attempts: int = _MAX_BASE_SLOT_ATTEMPTS,
) -> list[tuple[str, str]]:
    """Return the requested and prior KMA base slots for NO_DATA recovery."""
    slots: list[tuple[str, str]] = []
    current_date = base_date
    current_time = base_time
    for _ in range(max_attempts):
        slots.append((current_date, current_time))
        current_date, current_time = _previous_base_slot(current_date, current_time)
    return slots


def _latest_published_base_slot(
    *,
    now: datetime | None = None,
    publication_lag_minutes: int = 10,
) -> tuple[str, str]:
    """Return the latest short-term forecast slot expected to be published."""
    kst_now = now.astimezone(_SEOUL_TZ) if now is not None else datetime.now(_SEOUL_TZ)
    stable_now = kst_now - timedelta(minutes=publication_lag_minutes)
    past_times = [
        base_time for base_time in _BASE_TIME_ORDER if int(base_time[:2]) <= stable_now.hour
    ]
    if past_times:
        return stable_now.strftime("%Y%m%d"), past_times[-1]

    prev_day = stable_now - timedelta(days=1)
    return prev_day.strftime("%Y%m%d"), _BASE_TIME_ORDER[-1]


def _coerce_future_base_slot(
    base_date: str,
    base_time: str,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Clamp a future or unpublished request to the latest published KMA slot."""
    latest_date, latest_time = _latest_published_base_slot(now=now)
    requested_key = (base_date, base_time)
    latest_key = (latest_date, latest_time)
    if requested_key > latest_key:
        return latest_key
    return requested_key


def _coerce_recent_base_slot(
    base_date: str,
    base_time: str,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Clamp stale, invalid, future, or unpublished requests to the latest published slot."""
    latest_date, latest_time = _latest_published_base_slot(now=now)
    latest_dt = _base_slot_datetime(latest_date, latest_time)
    try:
        requested_dt = _base_slot_datetime(base_date, base_time)
    except ValueError:
        return latest_date, latest_time
    earliest_dt = latest_dt - timedelta(days=_RECENT_BASE_SLOT_RETENTION_DAYS)
    if requested_dt < earliest_dt or requested_dt > latest_dt:
        return latest_date, latest_time
    return base_date, base_time


def _base_slot_datetime(base_date: str, base_time: str) -> datetime:
    parsed = datetime.strptime(f"{base_date}{base_time}", "%Y%m%d%H%M")
    return parsed.replace(tzinfo=_SEOUL_TZ)


def _is_no_data_error(exc: ToolExecutionError) -> bool:
    """Return True when a KMA ToolExecutionError is resultCode=03/NO_DATA."""
    message = str(exc)
    return f"resultCode={_NO_DATA_RESULT_CODE!r}" in message or "resultMsg='NO_DATA'" in message


def _parse_response(payload: dict[str, object]) -> KmaShortTermForecastOutput:
    """Parse a full KMA getVilageFcst response envelope.

    Args:
        payload: Decoded JSON dict from the API.

    Returns:
        A validated ``KmaShortTermForecastOutput``.

    Raises:
        ToolExecutionError: If the API returned a non-zero result code or the
            response structure is unexpected.
    """
    try:
        response = cast(dict[str, object], payload["response"])
        header = cast(dict[str, object], response["header"])
        result_code: str = str(header["resultCode"])
        result_msg: str = str(header.get("resultMsg", ""))

        if result_code != "00":
            raise ToolExecutionError(
                tool_id="kma_short_term_forecast",
                message=(f"KMA API error: resultCode={result_code!r} resultMsg={result_msg!r}"),
            )

        body = cast(dict[str, object], response["body"])
        total_count = int(str(body.get("totalCount", 0)))

        raw_items_container = body.get("items", {})
        if not raw_items_container or isinstance(raw_items_container, str):
            return KmaShortTermForecastOutput(total_count=total_count, items=[])

        items_container = cast(dict[str, object], raw_items_container)
        raw_items = items_container.get("item")
        item_dicts = _normalize_items(raw_items)

        parsed_items: list[ForecastItem] = []
        for row in item_dicts:
            parsed_items.append(
                ForecastItem(
                    base_date=str(row["baseDate"]),
                    base_time=str(row["baseTime"]),
                    fcst_date=str(row["fcstDate"]),
                    fcst_time=str(row["fcstTime"]),
                    nx=int(str(row["nx"])),
                    ny=int(str(row["ny"])),
                    category=str(row["category"]),
                    fcst_value=str(row["fcstValue"]),
                )
            )

        return KmaShortTermForecastOutput(total_count=total_count, items=parsed_items)

    except ToolExecutionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=f"Unexpected KMA short-term forecast response structure: {exc}",
            cause=exc,
        ) from exc


# ---------------------------------------------------------------------------
# Adapter callable
# ---------------------------------------------------------------------------


async def _call(  # noqa: C901
    params: KmaShortTermForecastInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch short-term forecast data from the KMA getVilageFcst API.

    Args:
        params: Validated input parameters.
        client: Optional injected ``httpx.AsyncClient`` (for testing).

    Returns:
        A plain dict matching ``KmaShortTermForecastOutput`` field names.

    Raises:
        ConfigurationError: If ``UMMAYA_KMA_API_HUB_AUTH_KEY`` is not set.
        ToolExecutionError: On HTTP errors or unexpected API response shapes.
    """
    endpoint = resolve_vilage_fcst_endpoint(_OPERATION)

    initial_base_date, initial_base_time = _coerce_recent_base_slot(
        params.base_date,
        params.base_time,
    )
    candidate_slots = _candidate_base_slots(initial_base_date, initial_base_time)
    no_data_slots: list[str] = []

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        for base_date, base_time in candidate_slots:
            query_params: dict[str, str | int] = {
                endpoint.auth_query_param: endpoint.api_key,
                "base_date": base_date,
                "base_time": base_time,
                "nx": params.nx,
                "ny": params.ny,
                "numOfRows": params.num_of_rows,
                "pageNo": params.page_no,
            }
            query_params = apply_format_params(query_params, params.data_type)

            logger.debug(
                "KMA short-term forecast request: base_date=%s base_time=%s nx=%d ny=%d",
                base_date,
                base_time,
                params.nx,
                params.ny,
            )

            response = await client.get(endpoint.url, params=query_params)
            response.raise_for_status()

            payload = decode_response_payload(response)
            try:
                output = _parse_response(payload)
            except ToolExecutionError as exc:
                if _is_no_data_error(exc):
                    no_data_slots.append(f"{base_date} {base_time}: {exc}")
                    continue
                raise

            if output.items:
                logger.info(
                    "KMA short-term forecast retrieved: base_date=%s base_time=%s "
                    "nx=%d ny=%d items=%d",
                    base_date,
                    base_time,
                    params.nx,
                    params.ny,
                    len(output.items),
                )
                return output.model_dump()

            no_data_slots.append(f"{base_date} {base_time}: empty item list")

        attempted = ", ".join(no_data_slots)
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=(
                "KMA API returned no forecast data for the requested slot or prior slots. "
                f"attempted={attempted}"
            ),
        )

    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=(
                f"HTTP error from KMA short-term forecast API: {summarize_http_status_error(exc)}"
            ),
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=f"Network error reaching KMA short-term forecast API: {exc}",
            cause=exc,
        ) from exc
    except KmaPayloadDecodeError as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=f"Unable to decode KMA short-term forecast API response: {exc}",
            cause=exc,
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

KMA_SHORT_TERM_FORECAST_TOOL = GovAPITool(
    id="kma_short_term_forecast",
    name_ko="단기예보 조회",
    ministry="KMA",
    category=["기상", "예보", "단기예보"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaShortTermForecastInput,
    output_schema=KmaShortTermForecastOutput,
    llm_description=build_description_v4(
        purpose=(
            "기상청 단기예보 (getVilageFcst) — 향후 약 3일 시간대별 "
            "기온 TMP / 강수확률 POP / 하늘 SKY / 습도 REH / 풍속 WSD / 강수 PCP 예보. "
            "시민이 '내일 날씨' / '주말 비 올까' / '이번 주 기온' 묻는 경우 호출."
        ),
        input_quirk=(
            "nx (1-149), ny (1-253) Lambert 5 km 격자. "
            "base_date=YYYYMMDD (오늘). "
            "base_time 유효값 8개: 0200/0500/0800/1100/1400/1700/2000/2300 (KST). "
            "발표 후 ~10분 데이터 안정. 시스템 프롬프트 '현재 KST 시각' 의 "
            "직전 정시 사용. base_time 추측 금지."
        ),
        short_reference=kma_grid_short_reference(),
        domain_quirk=(
            "PCP / SNO 값 string ('강수없음', '1.0mm', '30.0~50.0mm'). "
            "resultCode string '00'=정상, '03'=데이터없음. "
            "HTTP 200 이어도 resultCode != '00' 이면 에러."
        ),
        self_contained_decl=(
            "REQUIRED: nx/ny 입력 필수. 지역명 ('동아대학교', '부산 사하구 다대1동') 은 "
            "locate(kakao_keyword_search 또는 kakao_address_search)로 nx/ny 받은 후 "
            "본 도구 호출. ORDERING: turn1=locate adapter, turn2=이 도구. 좌표 추측 금지."
        ),
    ),
    search_hint=(
        "단기예보 날씨예보 기온 강수확률 하늘상태 습도 풍속 풍향 "
        "short-term forecast weather temperature precipitation sky humidity wind"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 단기예보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=1800,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="find",
    trigger_examples=[
        "내일부터 3일 서울 날씨",
        "이번 주 서울 비 예보",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register the KMA short-term forecast tool and its adapter.

    Args:
        registry: The central ``ToolRegistry`` to add the tool to.
        executor: The ``ToolExecutor`` to bind the adapter function to.
    """
    from ummaya.tools.executor import AdapterFn

    registry.register(KMA_SHORT_TERM_FORECAST_TOOL)

    # SWAP/llm-provider(2521): wrap forecast output as LookupRecord so
    # envelope.normalize() accepts it (5-variant LookupOutput discriminator).
    async def _kma_stf_adapter(inp: BaseModel) -> dict[str, object]:
        # AdapterFn signature is BaseModel; the dispatcher narrows by
        # tool_id before invoking, so the runtime type is always
        # KmaShortTermForecastInput.  cast keeps mypy --strict happy
        # without a defensive isinstance() at the hot path.
        raw = await _call(cast("KmaShortTermForecastInput", inp))
        return {"kind": "record", "item": raw}

    executor.register_adapter("kma_short_term_forecast", cast(AdapterFn, _kma_stf_adapter))
    logger.info("Registered tool: kma_short_term_forecast")
