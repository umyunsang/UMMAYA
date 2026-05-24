# SPDX-License-Identifier: Apache-2.0
"""KMA ultra-short-term current observation adapter (초단기실황 관측).

The KMA getUltraSrtNcst endpoint returns observations as a list of pivot rows,
where each row has a ``{category, obsrValue}`` pair rather than returning a flat
object.  This module flattens those rows into a single ``KmaCurrentObservationOutput``
model via ``_pivot_rows_to_output``.

Special case: RN1 (1-hour precipitation) can arrive as the string ``"-"`` when
no precipitation has been measured.  The ``rn1`` field validator normalises that
sentinel — along with ``None`` and ``""`` — to ``0.0`` so downstream consumers
always receive a numeric value.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

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

_OPERATION = "getUltraSrtNcst"
_BASE_URL = f"{KMA_API_HUB_VILAGE_FCST_BASE_URL}/{_OPERATION}"
_NO_DATA_RESULT_CODE = "03"
_MAX_OBSERVATION_SLOT_ATTEMPTS = 6

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class KmaCurrentObservationInput(BaseModel):
    """Input parameters for the KMA ultra-short-term current observation API."""

    model_config = ConfigDict(frozen=True)

    base_date: str = Field(
        ...,
        description=(
            "관측 기준 날짜 (YYYYMMDD format, no separator). "
            "오늘 날짜 사용. Example: 20260430. "
            "시스템 프롬프트의 '오늘 날짜' context 를 그대로 사용."
        ),
    )
    base_time: str = Field(
        ...,
        description=(
            "관측 기준 시각 (HHMM format, 24-hour, no separator). "
            "직전 정시로 내림 (예: 14:35 → 1400). 매 시각 10분 이후 호출. "
            "Example: 1400 (오후 2시 관측), 0900 (오전 9시 관측)."
        ),
    )

    nx: int = Field(
        ...,
        ge=1,
        le=149,
        description=(
            "KMA grid X coordinate (1-149). 시도/시군구 명칭이 아닌 KMA 격자 좌표. "
            "Obtain via a coordinate-producing locate adapter which returns nx/ny "
            "verbatim. Example: 서울 종로구 = 60, 부산 사하구 = 96."
        ),
    )
    ny: int = Field(
        ...,
        ge=1,
        le=253,
        description=(
            "KMA grid Y coordinate (1-253). nx와 함께 locate 으로 받음. "
            "Example: 서울 종로구 = 127, 부산 사하구 = 73."
        ),
    )
    num_of_rows: int = Field(
        default=10,
        ge=1,
        description="결과 행 수 (default 10). 보통 기본값 사용.",
    )
    page_no: int = Field(
        default=1,
        ge=1,
        description="페이지 번호 (1-based, default 1). 보통 기본값 사용.",
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
    def _normalize_base_time(cls, v: str) -> str:
        """Round down to the nearest hour to avoid 'data not ready' errors."""
        if not re.fullmatch(r"\d{4}", v):
            raise ValueError(f"base_time must be HHMM, got {v!r}")
        return v[:2] + "00"


class KmaCurrentObservationOutput(BaseModel):
    """Flat observation record produced by pivoting KMA category rows."""

    model_config = ConfigDict(frozen=True)

    base_date: str
    """Observation date YYYYMMDD."""

    base_time: str
    """Observation time HHMM."""

    nx: int
    """Grid X coordinate."""

    ny: int
    """Grid Y coordinate."""

    t1h: float | None = None
    """Temperature in degrees Celsius."""

    rn1: float = 0.0
    """1-hour accumulated precipitation in millimetres (0.0 when no precipitation)."""

    uuu: float | None = None
    """East-west wind component in m/s (positive = eastward)."""

    vvv: float | None = None
    """North-south wind component in m/s (positive = northward)."""

    wsd: float | None = None
    """Wind speed in m/s."""

    reh: float | None = None
    """Relative humidity in percent."""

    pty: int = 0
    """Precipitation type code.

    0=none, 1=rain, 2=rain+snow, 3=snow, 5=drizzle, 6=drizzle+snow, 7=snow flurry.
    """

    vec: float | None = None
    """Wind direction in degrees (0–360, meteorological convention)."""

    @field_validator("rn1", mode="before")
    @classmethod
    def _normalize_rn1(cls, v: object) -> float:
        """Normalise sentinel precipitation values to 0.0.

        The KMA API uses ``"-"`` to indicate that no precipitation was observed.
        This validator converts ``"-"``, ``None``, and ``""`` to ``0.0`` so that
        all consumers receive a numeric value.
        """
        if v is None or v == "" or v == "-":
            return 0.0
        return float(v)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_items(raw: object) -> list[dict[str, object]]:
    """Coerce the KMA items payload into a plain list of dicts.

    The KMA API returns ``items.item`` as either a list (multiple rows) or a
    single dict (one row).  An empty / missing value yields an empty list.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    return []


def _pivot_rows_to_output(items: list[dict[str, object]]) -> KmaCurrentObservationOutput:
    """Pivot a list of KMA observation rows into a flat output model.

    Each row in *items* is expected to contain:
    ``baseDate``, ``baseTime``, ``nx``, ``ny``, ``category``, ``obsrValue``.

    Recognised categories: T1H, RN1, UUU, VVV, WSD, REH, PTY, VEC.
    Unknown categories are silently ignored.

    Args:
        items: List of raw row dicts from the API ``items.item`` field.

    Returns:
        A fully populated ``KmaCurrentObservationOutput`` instance.
    """
    first = items[0]
    base_date = str(first["baseDate"])
    base_time = str(first["baseTime"])
    nx = int(str(first["nx"]))
    ny = int(str(first["ny"]))

    category_map: dict[str, object] = {}
    for row in items:
        cat = str(row["category"]).upper()
        val = row["obsrValue"]
        category_map[cat] = val

    def _opt_float(key: str) -> float | None:
        raw = category_map.get(key)
        if raw is None or raw == "" or raw == "-":
            return None
        return float(str(raw))

    return KmaCurrentObservationOutput(
        base_date=base_date,
        base_time=base_time,
        nx=nx,
        ny=ny,
        t1h=_opt_float("T1H"),
        rn1=category_map.get("RN1", 0.0),  # type: ignore[arg-type]  # field_validator normalises
        uuu=_opt_float("UUU"),
        vvv=_opt_float("VVV"),
        wsd=_opt_float("WSD"),
        reh=_opt_float("REH"),
        pty=int(str(category_map.get("PTY", 0))),
        vec=_opt_float("VEC"),
    )


def _previous_observation_slot(base_date: str, base_time: str) -> tuple[str, str]:
    """Return the previous hourly KMA observation slot."""
    hour = int(base_time[:2])
    if hour > 0:
        return base_date, f"{hour - 1:02d}00"

    base_day = datetime.strptime(base_date, "%Y%m%d").replace(tzinfo=UTC)
    prev_day = base_day - timedelta(days=1)
    return prev_day.strftime("%Y%m%d"), "2300"


def _candidate_observation_slots(
    base_date: str,
    base_time: str,
    *,
    max_attempts: int = _MAX_OBSERVATION_SLOT_ATTEMPTS,
) -> list[tuple[str, str]]:
    """Return current and prior hourly slots for KMA NO_DATA recovery."""
    slots: list[tuple[str, str]] = []
    current_date = base_date
    current_time = base_time
    for _ in range(max_attempts):
        slots.append((current_date, current_time))
        current_date, current_time = _previous_observation_slot(current_date, current_time)
    return slots


def _is_retryable_no_data_error(exc: ToolExecutionError) -> bool:
    """Return true for KMA data-not-ready responses worth retrying backward."""
    message = str(exc)
    return (
        f"resultCode='{_NO_DATA_RESULT_CODE}'" in message
        or "resultMsg='NO_DATA'" in message
        or "empty items list" in message
    )


def _parse_response(payload: dict[str, object]) -> KmaCurrentObservationOutput:
    """Parse a full KMA getUltraSrtNcst response envelope.

    Args:
        payload: Decoded JSON dict from the API.

    Returns:
        A validated ``KmaCurrentObservationOutput``.

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
                tool_id="kma_current_observation",
                message=(f"KMA API error: resultCode={result_code!r} resultMsg={result_msg!r}"),
            )

        body = cast(dict[str, object], response["body"])
        items_container = cast(dict[str, object], body["items"])
        raw_items = items_container["item"]
        items = _normalize_items(raw_items)

        if not items:
            raise ToolExecutionError(
                tool_id="kma_current_observation",
                message="KMA API returned an empty items list.",
            )

        return _pivot_rows_to_output(items)

    except ToolExecutionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ToolExecutionError(
            tool_id="kma_current_observation",
            message=f"Unexpected KMA response structure: {exc}",
            cause=exc,
        ) from exc


# ---------------------------------------------------------------------------
# Adapter callable
# ---------------------------------------------------------------------------


async def _call(  # noqa: C901
    params: KmaCurrentObservationInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch ultra-short-term current observations from the KMA API.

    Args:
        params: Validated input parameters.
        client: Optional injected ``httpx.AsyncClient`` (for testing).

    Returns:
        A plain dict matching ``KmaCurrentObservationOutput`` field names.

    Raises:
        ConfigurationError: If ``UMMAYA_KMA_API_HUB_AUTH_KEY`` is not set.
        ToolExecutionError: On HTTP errors or unexpected API response shapes.
    """
    endpoint = resolve_vilage_fcst_endpoint(_OPERATION)

    logger.debug(
        "KMA observation request: base_date=%s base_time=%s nx=%d ny=%d",
        params.base_date,
        params.base_time,
        params.nx,
        params.ny,
    )

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=30.0)

    try:
        assert client is not None  # noqa: S101 — guaranteed by branch above
        no_data_slots: list[str] = []
        for base_date, base_time in _candidate_observation_slots(
            params.base_date,
            params.base_time,
        ):
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

            response = await client.get(
                endpoint.url,
                params=query_params,
            )
            response.raise_for_status()

            payload = decode_response_payload(response)
            try:
                output = _parse_response(payload)
            except ToolExecutionError as exc:
                if not _is_retryable_no_data_error(exc):
                    raise
                no_data_slots.append(f"{base_date} {base_time}: {exc}")
                continue

            logger.info(
                "KMA observation retrieved: base_date=%s base_time=%s nx=%d ny=%d t1h=%s",
                output.base_date,
                output.base_time,
                output.nx,
                output.ny,
                output.t1h,
            )
            return output.model_dump()

        attempted = ", ".join(no_data_slots)
        raise ToolExecutionError(
            tool_id="kma_current_observation",
            message=(
                "KMA API returned no observation data for the requested slot or prior slots. "
                f"attempted={attempted}"
            ),
        )

    except (ToolExecutionError, ConfigurationError):
        raise
    except httpx.HTTPStatusError as exc:
        raise ToolExecutionError(
            tool_id="kma_current_observation",
            message=f"HTTP error from KMA API: {summarize_http_status_error(exc)}",
            cause=exc,
        ) from exc
    except httpx.RequestError as exc:
        raise ToolExecutionError(
            tool_id="kma_current_observation",
            message=f"Network error reaching KMA API: {exc}",
            cause=exc,
        ) from exc
    except KmaPayloadDecodeError as exc:
        raise ToolExecutionError(
            tool_id="kma_current_observation",
            message=f"Unable to decode KMA API response: {exc}",
            cause=exc,
        ) from exc
    finally:
        if own_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

KMA_CURRENT_OBSERVATION_TOOL = GovAPITool(
    id="kma_current_observation",
    name_ko="초단기실황 관측 조회",
    ministry="KMA",
    category=["기상", "실황", "관측"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaCurrentObservationInput,
    output_schema=KmaCurrentObservationOutput,
    llm_description=build_description_v4(
        purpose=(
            "기상청 초단기실황 (getUltraSrtNcst) — 현재 시각 기준 실제 관측값 "
            "(기온 T1H / 강수 RN1 / 습도 REH / 풍속 WSD / 풍향 VEC / 강수형태 PTY). "
            "시민이 '지금 기온' / '현재 비 와' / '오늘 날씨 어때' 묻는 경우 첫 호출."
        ),
        input_quirk=(
            "nx/ny 는 locate 결과의 KMA 격자 X/Y를 그대로 복사. "
            "base_date=YYYYMMDD, base_time=HH00. "
            "시스템 프롬프트의 '현재 KST 시각'을 기준으로 직전 정시 사용; "
            "정시 +10분 전이면 한 시간 더 이전이 안정. NO_DATA 시 이전 시간 자동 재시도. "
            "XML is the official default wire format; resultCode '00'=정상."
        ),
        short_reference=kma_grid_short_reference(),
        domain_quirk=(
            "매 정시 +10분 이후 호출. 14:05 호출 → base_time='1300', "
            "14:25 호출 → base_time='1400'. "
            "RN1='-' 는 강수 없음(0.0). HTTP 200 이어도 resultCode != '00' 이면 에러. "
            "VEC(풍향, 도): 0=북, 90=동, 180=남, 270=서. 16방위 매핑 — "
            "N(348.75-11.25), NNE(11.25-33.75), NE(33.75-56.25), ENE(56.25-78.75), "
            "E(78.75-101.25), ESE(101.25-123.75), SE(123.75-146.25), SSE(146.25-168.75), "
            "S(168.75-191.25), SSW(191.25-213.75), SW(213.75-236.25), WSW(236.25-258.75), "
            "W(258.75-281.25), WNW(281.25-303.75), NW(303.75-326.25), NNW(326.25-348.75). "
            "vec=271 → W(서풍), vec=315 → NW(북서풍). 추측 금지."
        ),
        self_contained_decl=(
            "REQUIRED: nx/ny 입력 필수. 지역명 ('동아대학교', '부산 사하구 다대1동') 은 "
            "locate(kakao_keyword_search 또는 kakao_address_search)로 nx/ny 받은 후 "
            "본 도구 호출. ORDERING: turn1=locate adapter, turn2=이 도구. 좌표 추측 금지."
        ),
    ),
    search_hint=(
        "현재 날씨 기온 강수 습도 풍속 초단기실황 관측 "
        "current weather temperature precipitation humidity wind observation"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 현재 날씨 관측 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=600,
    rate_limit_per_minute=10,
    is_core=True,
    primitive="find",
    trigger_examples=[
        "지금 서울 기온",
        "현재 풍속",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register the KMA current observation tool and its adapter.

    Args:
        registry: The central ``ToolRegistry`` to add the tool to.
        executor: The ``ToolExecutor`` to bind the adapter function to.
    """
    from ummaya.tools.executor import AdapterFn

    registry.register(KMA_CURRENT_OBSERVATION_TOOL)

    # SWAP/llm-provider(2521): wrap the flat KmaCurrentObservationOutput dict
    # into a LookupRecord envelope so envelope.normalize()'s 5-variant
    # LookupOutput validator (kind=record/collection/timeseries/error/search)
    # accepts it. Citizen-visible symptom without this wrap: "Response
    # processing failed" — LLM never sees real weather data, retries lookup
    # in confusion (probe-traced 2026-05-01).
    async def _kma_observation_adapter(inp: BaseModel) -> dict[str, Any]:
        # AdapterFn is BaseModel; dispatcher narrows by tool_id, so runtime
        # type is always KmaCurrentObservationInput. cast for mypy strict.
        raw = await _call(cast("KmaCurrentObservationInput", inp))
        return {"kind": "record", "item": raw}

    executor.register_adapter("kma_current_observation", cast(AdapterFn, _kma_observation_adapter))
    logger.info("Registered tool: kma_current_observation")
