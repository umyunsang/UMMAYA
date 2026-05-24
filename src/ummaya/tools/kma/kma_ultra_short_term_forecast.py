# SPDX-License-Identifier: Apache-2.0
"""KMA ultra-short-term forecast adapter (초단기예보 조회).

Wraps the ``getUltraSrtFcst`` endpoint from the Korea Meteorological Administration
(기상청) via the KMA API Hub ``authKey`` surface.
Returns forecast items for the next 6 hours; the live API canonicalizes requested
HHMM times to the published baseTime carried in response rows.

Wire format quirks handled by this module:
  - Single-item response returns ``item`` as a dict (not array) — normalized to list.
  - XML is the official default; JSON is requested only when explicitly selected.
  - ``resultCode != "00"`` is always an error regardless of HTTP 200.
  - Wire fields use camelCase; output model fields use snake_case.
  - base_time accepts HHMM; KMA may canonicalize it to the nearest published
    baseTime in the response.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ummaya.tools._description_template import build_description_v4
from ummaya.tools._outbound_trace import traced_async_client
from ummaya.tools.errors import ConfigurationError, ToolExecutionError
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.kma.grid_coords import kma_grid_short_reference
from ummaya.tools.kma.kma_short_term_forecast import (
    ForecastItem,
    KmaShortTermForecastOutput,
    _normalize_items,
)
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

_OPERATION = "getUltraSrtFcst"
_BASE_URL = f"{KMA_API_HUB_VILAGE_FCST_BASE_URL}/{_OPERATION}"

# ---------------------------------------------------------------------------
# Input model (output reuses ForecastItem / KmaShortTermForecastOutput)
# ---------------------------------------------------------------------------


class KmaUltraShortTermForecastInput(BaseModel):
    """Input parameters for the KMA ultra-short-term forecast (초단기예보) API."""

    model_config = ConfigDict(frozen=True)

    base_date: str = Field(..., description="발표 날짜 (YYYYMMDD). 보통 오늘. Example: 20260430.")
    base_time: str = Field(
        ...,
        description=(
            "조회 기준 시각 (HHMM format). Official guide examples use HH30 and "
            "call after HH:45 KST. KMA live API may canonicalize a non-HH30 "
            "request to the actually published baseTime in the response."
        ),
    )
    nx: int = Field(
        ...,
        ge=1,
        le=149,
        description="KMA 격자 X (1-149). locate 으로 받아 그대로 전달.",
    )
    ny: int = Field(
        ...,
        ge=1,
        le=253,
        description="KMA 격자 Y (1-253). nx 와 함께 locate 으로 받음.",
    )
    num_of_rows: int = Field(
        default=60,
        ge=1,
        description="결과 행 수 (default 60 = 6시간 × ~10 카테고리). 보통 기본값.",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1).",
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
        """Validate that base_time is in HHMM format."""
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError(f"base_time must be HHMM, got {v!r}")
        hour = int(v[:2])
        minute = int(v[2:])
        if hour > 23 or minute > 59:
            raise ValueError(f"base_time must be a valid HHMM clock time, got {v!r}")
        return v


# Output reuses the same output model as short-term forecast
KmaUltraShortTermForecastOutput = KmaShortTermForecastOutput


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_response(payload: dict[str, object]) -> KmaUltraShortTermForecastOutput:
    """Parse a full KMA getUltraSrtFcst response envelope.

    Args:
        payload: Decoded JSON dict from the API.

    Returns:
        A validated ``KmaUltraShortTermForecastOutput``.

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
                tool_id="kma_ultra_short_term_forecast",
                message=(f"KMA API error: resultCode={result_code!r} resultMsg={result_msg!r}"),
            )

        body = cast(dict[str, object], response["body"])
        total_count = int(str(body.get("totalCount", 0)))

        raw_items_container = body.get("items", {})
        if not raw_items_container or isinstance(raw_items_container, str):
            return KmaUltraShortTermForecastOutput(total_count=total_count, items=[])

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

        return KmaUltraShortTermForecastOutput(total_count=total_count, items=parsed_items)

    except ToolExecutionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolExecutionError(
            tool_id="kma_ultra_short_term_forecast",
            message=f"Unexpected KMA ultra-short-term forecast response structure: {exc}",
            cause=exc,
        ) from exc


# ---------------------------------------------------------------------------
# Adapter callable
# ---------------------------------------------------------------------------


async def _call(
    params: KmaUltraShortTermForecastInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch ultra-short-term forecast data from the KMA getUltraSrtFcst API.

    Args:
        params: Validated input parameters.
        client: Optional injected ``httpx.AsyncClient`` (for testing).

    Returns:
        A plain dict matching ``KmaUltraShortTermForecastOutput`` field names.

    Raises:
        ConfigurationError: If ``UMMAYA_KMA_API_HUB_AUTH_KEY`` is not set.
        ToolExecutionError: On HTTP errors or unexpected API response shapes.
    """
    endpoint = resolve_vilage_fcst_endpoint(_OPERATION)

    query_params: dict[str, str | int] = {
        endpoint.auth_query_param: endpoint.api_key,
        "base_date": params.base_date,
        "base_time": params.base_time,
        "nx": params.nx,
        "ny": params.ny,
        "numOfRows": params.num_of_rows,
        "pageNo": params.page_no,
    }
    query_params = apply_format_params(query_params, params.data_type)

    logger.debug(
        "KMA ultra-short-term forecast request: base_date=%s base_time=%s nx=%d ny=%d",
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
        response = await client.get(endpoint.url, params=query_params)
        response.raise_for_status()

        payload = decode_response_payload(response)
        output = _parse_response(payload)

        logger.info(
            "KMA ultra-short-term forecast retrieved: base_date=%s base_time=%s "
            "nx=%d ny=%d items=%d",
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
            tool_id="kma_ultra_short_term_forecast",
            message=(
                "HTTP error from KMA ultra-short-term forecast API: "
                f"{summarize_http_status_error(exc)}"
            ),
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id="kma_ultra_short_term_forecast",
            message=f"Network error reaching KMA ultra-short-term forecast API: {exc}",
            cause=exc,
        ) from exc
    except KmaPayloadDecodeError as exc:
        raise ToolExecutionError(
            tool_id="kma_ultra_short_term_forecast",
            message=f"Unable to decode KMA ultra-short-term forecast API response: {exc}",
            cause=exc,
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

KMA_ULTRA_SHORT_TERM_FORECAST_TOOL = GovAPITool(
    id="kma_ultra_short_term_forecast",
    name_ko="초단기예보 조회",
    llm_description=build_description_v4(
        purpose=(
            "기상청 초단기예보 (getUltraSrtFcst) — 향후 6시간 시간대별 "
            "기온 T1H / 강수 RN1 / 하늘 SKY / 풍속 WSD 예보. "
            "시민이 '한 두 시간 후 비 와' / '지금 직후 날씨' 묻는 경우. "
            "3일 예보는 kma_short_term_forecast 사용."
        ),
        input_quirk=(
            "nx (1-149), ny (1-253) Lambert 5 km 격자. "
            "base_date=YYYYMMDD (오늘). "
            "base_time=HHMM format; prefer the latest HH30 slot after HH:45 KST. "
            "Use the system prompt's 현재 KST 시각 hint to select that slot. "
            "KMA may canonicalize a non-HH30 request to the published baseTime. "
            "Use the response item's base_time as the authoritative issued time."
        ),
        short_reference=kma_grid_short_reference(),
        domain_quirk=(
            "초단기예보는 빈번히 갱신되며 응답 baseTime 이 요청 base_time 과 다를 수 있음. "
            "resultCode string '00'=정상. "
            "HTTP 200 이어도 resultCode != '00' 이면 에러. XML is the official default."
        ),
        self_contained_decl=(
            "REQUIRED: nx/ny 입력 필수. 지역명 ('동아대학교', '부산 사하구 다대1동') 은 "
            "locate(kakao_keyword_search 또는 kakao_address_search)로 nx/ny 받은 후 "
            "본 도구 호출. ORDERING: turn1=locate adapter, turn2=이 도구. 좌표 추측 금지."
        ),
    ),
    ministry="KMA",
    category=["기상", "예보", "초단기예보"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaUltraShortTermForecastInput,
    output_schema=KmaUltraShortTermForecastOutput,
    search_hint=(
        "초단기예보 단기예보 6시간예보 기온 강수 하늘상태 습도 풍속 "
        "ultra-short-term forecast 6-hour weather temperature precipitation sky wind"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 초단기예보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=600,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="find",
    trigger_examples=[
        "한 시간 뒤 서울 비 와?",
        "지금 비 그칠까",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register the KMA ultra-short-term forecast tool and its adapter.

    Args:
        registry: The central ``ToolRegistry`` to add the tool to.
        executor: The ``ToolExecutor`` to bind the adapter function to.
    """
    from ummaya.tools.executor import AdapterFn

    registry.register(KMA_ULTRA_SHORT_TERM_FORECAST_TOOL)

    async def _kma_ultra_short_term_adapter(inp: BaseModel) -> dict[str, object]:
        raw = await _call(cast("KmaUltraShortTermForecastInput", inp))
        return {"kind": "record", "item": raw}

    executor.register_adapter(
        "kma_ultra_short_term_forecast",
        cast(AdapterFn, _kma_ultra_short_term_adapter),
    )
    logger.info("Registered tool: kma_ultra_short_term_forecast")
