# SPDX-License-Identifier: Apache-2.0
"""KMA short-term forecast fetch adapter — kma_forecast_fetch (T046).

Wraps the ``getVilageFcst`` endpoint from the Korea Meteorological Administration
(기상청) via the shared data.go.kr service key.

Input: (lat, lon) coordinates + base_date + base_time.
Internally projects (lat, lon) → (nx, ny) via Lambert Conformal Conic before
calling the upstream API.

Returns a ``LookupTimeseries`` with one point per forecast hour, each carrying:
  timestamp_iso  — forecast target as ISO-8601 string (KST, no tz offset)
  temperature_c  — TMP [°C] as float, or None
  pop_pct        — POP [%] as int, or None
  precipitation_mm — PCP string (e.g. "강수없음", "1.0mm") or None
  sky_code       — SKY code string ("1"=맑음, "3"=구름많음, "4"=흐림) or None
  interval       — always "hour"

FR-027 to FR-031 (spec/022-mvp-main-tool/spec.md).

Registration:
  Call ``register(registry)`` at application startup to make this tool
  discoverable.  Do NOT call from register_all.py — Stage 3 (T048) does that.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import LookupErrorReason, _require_env
from kosmos.tools.kma.projection import KMADomainError, latlon_to_lcc
from kosmos.tools.models import (  # noqa: A004
    AdapterRealDomainPolicy,
    GovAPITool,
    LookupError,  # noqa: A004 — domain-specific Pydantic model, intentional shadow
    LookupTimeseries,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

_VALID_BASE_TIMES: frozenset[str] = frozenset(
    {"0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"}
)

# ---------------------------------------------------------------------------
# Input schema (Pydantic v2 strict — no Any)
# ---------------------------------------------------------------------------


class KmaForecastFetchInput(BaseModel):
    """Input parameters for the kma_forecast_fetch adapter.

    The adapter converts (lat, lon) internally to KMA grid (nx, ny) using
    Lambert Conformal Conic projection — callers must NOT supply nx/ny.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    lat: float = Field(
        ge=-90,
        le=90,
        description=(
            "WGS-84 latitude of the target location, in decimal degrees. "
            "For Korean locations this is typically 33–38. "
            "Obtain from resolve_location(want='coords')."
        ),
    )
    lon: float = Field(
        ge=-180,
        le=180,
        description=(
            "WGS-84 longitude of the target location, in decimal degrees. "
            "For Korean locations this is typically 126–130. "
            "Obtain from resolve_location(want='coords')."
        ),
    )
    base_date: str = Field(
        pattern=r"^\d{8}$",
        description=(
            "Forecast base date in YYYYMMDD format, e.g. '20260416'. "
            "Use today's date or yesterday if today's data is not yet published."
        ),
    )
    base_time: str = Field(
        description=(
            "Forecast base time in HHMM format. "
            "Must be one of: 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 (KST). "
            "Data is published approximately 10 minutes after each base time."
        ),
    )


# ---------------------------------------------------------------------------
# Internal response parsing helpers
# ---------------------------------------------------------------------------


def _build_timestamp_iso(fcst_date: str, fcst_time: str) -> str:
    """Combine YYYYMMDD + HHMM into a naive ISO-8601 string (KST)."""
    # fcst_date = "20260416", fcst_time = "0900"
    return f"{fcst_date[:4]}-{fcst_date[4:6]}-{fcst_date[6:8]}T{fcst_time[:2]}:{fcst_time[2:]}:00"


def _parse_forecast_items(
    item_list: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Aggregate raw KMA item list into per-hour points.

    KMA returns one row per (fcstDate, fcstTime, category) triplet.
    We group by (fcstDate, fcstTime) and extract the semantic fields.

    Args:
        item_list: Raw list of item dicts from the KMA API response.

    Returns:
        List of point dicts (one per forecast hour), sorted by timestamp.
    """
    # Map (fcstDate, fcstTime) → {category: value}
    slots: dict[tuple[str, str], dict[str, str]] = {}

    for row in item_list:
        if not isinstance(row, dict):
            continue
        fcst_date = str(row.get("fcstDate", ""))
        fcst_time = str(row.get("fcstTime", ""))
        category = str(row.get("category", ""))
        value = str(row.get("fcstValue", ""))
        if fcst_date and fcst_time and category:
            slots.setdefault((fcst_date, fcst_time), {})[category] = value

    points: list[dict[str, object]] = []
    for (fcst_date, fcst_time), cats in sorted(slots.items()):
        tmp = cats.get("TMP")
        pop = cats.get("POP")
        pcp = cats.get("PCP")
        sky = cats.get("SKY")

        point: dict[str, object] = {
            "timestamp_iso": _build_timestamp_iso(fcst_date, fcst_time),
            "temperature_c": float(tmp) if tmp is not None else None,
            "pop_pct": int(pop) if pop is not None else None,
            "precipitation_mm": pcp if pcp is not None else None,
            "sky_code": sky if sky is not None else None,
            "interval": "hour",
        }
        points.append(point)

    return points


def _normalize_items(raw: object) -> list[dict[str, object]]:
    """Coerce KMA items.item payload to a list of dicts (handles dict vs list)."""
    if not raw:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    logger.warning("kma_forecast_fetch: unexpected items type %s; treating as empty", type(raw))
    return []


# ---------------------------------------------------------------------------
# Core async handler
# ---------------------------------------------------------------------------


async def _fetch(
    inp: KmaForecastFetchInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> LookupTimeseries | LookupError:
    """Invoke the KMA getVilageFcst endpoint and return a LookupTimeseries.

    Args:
        inp: Validated KmaForecastFetchInput.
        client: Optional injected ``httpx.AsyncClient`` for testing.

    Returns:
        LookupTimeseries on success, LookupError on domain/upstream errors.
    """
    import uuid
    from datetime import datetime

    # Validate base_time before touching the network
    if inp.base_time not in _VALID_BASE_TIMES:
        return LookupError(
            kind="error",
            reason=LookupErrorReason.invalid_params,
            message=(
                f"base_time {inp.base_time!r} is not a valid KMA forecast base time. "
                f"Must be one of: {', '.join(sorted(_VALID_BASE_TIMES))}."
            ),
        )

    # Project coordinates to KMA grid
    try:
        nx, ny = latlon_to_lcc(inp.lat, inp.lon)
    except KMADomainError as exc:
        return LookupError(
            kind="error",
            reason=LookupErrorReason.out_of_domain,
            message=str(exc),
        )

    logger.debug(
        "kma_forecast_fetch: lat=%.4f lon=%.4f → nx=%d ny=%d base_date=%s base_time=%s",
        inp.lat,
        inp.lon,
        nx,
        ny,
        inp.base_date,
        inp.base_time,
    )

    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    query_params: dict[str, str | int] = {
        "serviceKey": api_key,
        "base_date": inp.base_date,
        "base_time": inp.base_time,
        "nx": nx,
        "ny": ny,
        "numOfRows": 290,
        "pageNo": 1,
        "dataType": "JSON",
        "_type": "json",
    }

    own_client = client is None
    # Spec 2521 (2026-05-01) — switch to the traced client so the verbose
    # tool view in the TUI can surface request/response JSON for the
    # outbound data.go.kr call. When no capture scope is open (unit tests
    # invoking ``_fetch`` directly) the hook is a no-op.
    _client: httpx.AsyncClient = (
        traced_async_client(timeout=30.0) if own_client else client  # type: ignore[assignment]
    )

    request_id = str(uuid.uuid4())
    t_start = datetime.now(tz=UTC)

    try:
        response = await _client.get(_BASE_URL, params=query_params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            return LookupError(
                kind="error",
                reason=LookupErrorReason.upstream_unavailable,
                message=(
                    f"KMA API returned XML instead of JSON "
                    f"(content-type={content_type!r}). "
                    "Check KOSMOS_DATA_GO_KR_API_KEY validity."
                ),
            )

        payload: dict[str, Any] = response.json()

    except httpx.HTTPStatusError as exc:
        return LookupError(
            kind="error",
            reason=LookupErrorReason.upstream_unavailable,
            message=f"HTTP error from KMA forecast API: {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        return LookupError(
            kind="error",
            reason=LookupErrorReason.timeout,
            message=f"Network error reaching KMA forecast API: {exc}",
            retryable=True,
        )
    finally:
        if own_client:
            await _client.aclose()

    # Parse envelope
    try:
        resp_body = payload["response"]
        header = resp_body["header"]
        result_code = str(header["resultCode"])
        result_msg = str(header.get("resultMsg", ""))
    except (KeyError, TypeError) as exc:
        return LookupError(
            kind="error",
            reason=LookupErrorReason.upstream_unavailable,
            message=f"Unexpected KMA response structure: {exc}",
        )

    if result_code != "00":
        return LookupError(
            kind="error",
            reason=LookupErrorReason.upstream_unavailable,
            message=f"KMA API error: resultCode={result_code!r} resultMsg={result_msg!r}",
            upstream_code=result_code,
            upstream_message=result_msg,
        )

    body = resp_body.get("body", {})
    raw_items_container = body.get("items", {})
    if not raw_items_container or isinstance(raw_items_container, str):
        item_list: list[dict[str, object]] = []
    else:
        raw_items = raw_items_container.get("item")
        item_list = _normalize_items(raw_items)

    points = _parse_forecast_items(item_list)

    elapsed_ms = int((datetime.now(tz=UTC) - t_start).total_seconds() * 1000)

    from kosmos.tools.models import LookupMeta

    meta = LookupMeta(
        source="kma_forecast_fetch",
        fetched_at=t_start,
        request_id=request_id,
        elapsed_ms=elapsed_ms,
    )

    return LookupTimeseries(
        kind="timeseries",
        points=points,
        interval="hour",
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------

_PLACEHOLDER_INPUT = KmaForecastFetchInput


class _ForecastFetchOutput(BaseModel):
    """Placeholder output schema for GovAPITool registration.

    Actual output is LookupTimeseries (handled by envelope layer).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    kind: str = "timeseries"


KMA_FORECAST_FETCH_TOOL = GovAPITool(
    id="kma_forecast_fetch",
    name_ko="단기예보 조회 (좌표 입력)",
    ministry="KMA",
    category=["기상", "예보", "단기예보", "좌표"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=KmaForecastFetchInput,
    output_schema=_ForecastFetchOutput,
    llm_description=(
        "Fetch a KMA short-term weather forecast (단기예보, ~3 days) for a location "
        "given as WGS-84 coordinates (lat, lon). "
        "Always call resolve_location(want='coords') first to obtain lat/lon. "
        "Returns hourly time-series with temperature, precipitation probability, "
        "precipitation amount, and sky condition. "
        "base_time must be one of: 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 (KST)."
    ),
    search_hint="단기예보 날씨 기온 강수 short-term weather forecast temperature precipitation",
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.kma.go.kr/data/policy.html",
        real_classification_text="기상청 공공데이터 이용약관 — 기상예보 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
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
        "오늘 서울 날씨 알려줘",
        "내일 부산 비 와?",
        "주말 제주 날씨",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper (DO NOT call from register_all.py — Stage 3 / T048)
# ---------------------------------------------------------------------------


def register(registry: object) -> None:
    """Register kma_forecast_fetch in the tool registry.

    NOTE: This function intentionally takes only ``registry`` (not ``executor``)
    because the adapter is invoked through the MVP lookup facade which calls
    ``_fetch`` directly via the registry look-up.  If the executor pattern is
    needed, callers can bind it separately.

    Do NOT call this from ``register_all.py``.  Stage 3 (T048) does that.

    Args:
        registry: A ``ToolRegistry`` instance.
    """
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    registry.register(KMA_FORECAST_FETCH_TOOL)
    logger.info("Registered tool: kma_forecast_fetch")
