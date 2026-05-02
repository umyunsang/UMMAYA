# SPDX-License-Identifier: Apache-2.0
"""KMA short-term forecast adapter (단기예보 조회).

Wraps the ``getVilageFcst`` endpoint from the Korea Meteorological Administration
(기상청) via the shared data.go.kr service key.
Returns a list of forecast items covering approximately 3 days ahead, published
8 times a day at 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 KST.

Wire format quirks handled by this module:
  - Single-item response returns ``item`` as a dict (not array) — normalized to list.
  - XML is the default; JSON is requested via ``_type=json`` and ``dataType=JSON``.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
  - Wire fields use camelCase; output model fields use snake_case.
  - PCP / SNO values may be strings like "30.0~50.0mm" — stored as-is.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ConfigurationError, ToolExecutionError, _require_env
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool
from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# Valid base times for the short-term forecast service (KST)
_VALID_BASE_TIMES = frozenset({"0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"})

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class KmaShortTermForecastInput(BaseModel):
    """Input parameters for the KMA short-term forecast (단기예보) API."""

    model_config = ConfigDict(frozen=True)

    base_date: str = Field(
        ...,
        description=("예보 발표 날짜 (YYYYMMDD). 보통 오늘. Example: 20260430."),
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
            "KMA 격자 X 좌표 (1-149). resolve_location(query='<지역>') 으로 받아 "
            "그대로 전달. 예: 서울 종로구=60, 부산 사하구=96."
        ),
    )
    ny: int = Field(
        ...,
        ge=1,
        le=253,
        description=(
            "KMA 격자 Y 좌표 (1-253). nx 와 함께 resolve_location 으로 받음. "
            "예: 서울 종로구=127, 부산 사하구=73."
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
        default="JSON",
        description="응답 형식. JSON 권장 (default).",
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


def _parse_response(payload: dict[str, object]) -> KmaShortTermForecastOutput:
    """Parse a full KMA getVilageFcst JSON response.

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


async def _call(
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
        ConfigurationError: If ``KOSMOS_DATA_GO_KR_API_KEY`` is not set.
        ToolExecutionError: On HTTP errors or unexpected API response shapes.
    """
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    if params.data_type == "XML":
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message="XML data_type is not supported; use JSON.",
        )

    query_params: dict[str, str | int] = {
        "serviceKey": api_key,
        "base_date": params.base_date,
        "base_time": params.base_time,
        "nx": params.nx,
        "ny": params.ny,
        "numOfRows": params.num_of_rows,
        "pageNo": params.page_no,
        "dataType": params.data_type,
        "_type": "json",
    }

    logger.debug(
        "KMA short-term forecast request: base_date=%s base_time=%s nx=%d ny=%d",
        params.base_date,
        params.base_time,
        params.nx,
        params.ny,
    )

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101
        response = await client.get(_BASE_URL, params=query_params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                tool_id="kma_short_term_forecast",
                message=(
                    f"Unexpected XML response from KMA API "
                    f"(content-type={content_type!r}). "
                    "Check serviceKey validity."
                ),
            )

        payload: dict[str, object] = response.json()
        output = _parse_response(payload)

        logger.info(
            "KMA short-term forecast retrieved: base_date=%s base_time=%s nx=%d ny=%d items=%d",
            params.base_date,
            params.base_time,
            params.nx,
            params.ny,
            len(output.items),
        )
        return output.model_dump()

    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=f"HTTP error from KMA short-term forecast API: {exc.response.status_code}",
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id="kma_short_term_forecast",
            message=f"Network error reaching KMA short-term forecast API: {exc}",
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
    llm_description=(
        "기상청 단기예보 — 향후 약 3일 (오늘 / 내일 / 모레) 시간대별 기온 / 강수확률 / "
        "하늘 상태 / 습도 / 풍속 / 풍향 예보. 시민이 '내일 날씨' / '주말 비 올까' / "
        "'다음주 기온' 같은 미래 예보를 묻는 경우 호출.\n\n"
        "**ORDERING RULE**: 시민 발화에 위치명이 있으면 "
        "**먼저 resolve_location(query='<지역명>')** 호출 → nx/ny 받아서 이 도구에 전달. "
        "base_date / base_time 은 KMA 발표 시각 기준 "
        "(02/05/08/11/14/17/20/23시 발표) — 보통 직전 발표 시각 사용."
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
    primitive="lookup",
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
    from kosmos.tools.executor import AdapterFn

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
