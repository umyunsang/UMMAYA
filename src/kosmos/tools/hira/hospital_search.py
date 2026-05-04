# SPDX-License-Identifier: Apache-2.0
"""HIRA hospital search adapter — T054.

Wraps the ``getHospBasisList`` endpoint from HIRA
(건강보험심사평가원, Health Insurance Review and Assessment Service).

Input: WGS84 coordinates (xPos, yPos) + radius in meters.
Output: LookupCollection of hospital records.

Endpoint: https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList

FR-021: Accepts (xPos, yPos, radius) — native coord+radius spatial input.
FR-023: Ships happy-path AND error-path tests with recorded fixtures.
FR-024: Fail-closed defaults (non-auth tool — read-only gate per Epic δ #2295,
        is_concurrency_safe=True, cache_ttl_seconds=0).
FR-037: Adapter is an async coroutine.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools._description_template import build_description_v4
from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ToolExecutionError, _require_env
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"

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
            "Search radius in meters. Maximum 10 000 m. "
            "Default 2 000 m (2 km). Increase only if initial results are empty."
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


# ---------------------------------------------------------------------------
# Async adapter handler
# ---------------------------------------------------------------------------


async def handle(
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

    logger.debug(
        "hira_hospital_search: xPos=%.5f yPos=%.5f radius=%d page=%d rows=%d",
        inp.xPos,
        inp.yPos,
        inp.radius,
        inp.pageNo,
        inp.numOfRows,
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
        "within a WGS84 coordinate radius. Returns hospital name, address, phone, "
        "institution type, and distance. Use for: nearby hospitals, clinics, healthcare."
    ),
    input_quirk=(
        "xPos = longitude (lon, 124–132 WGS84 decimal degrees) — agency naming convention. "
        "yPos = latitude (lat, 33–39 WGS84 decimal degrees) — agency naming convention. "
        "Always obtain xPos/yPos from resolve_location(want='coords') before calling. "
        "radius default 2000 m (max 10000 m). Increase if results are empty."
    ),
    short_reference=(
        "No 17-region table needed — HIRA accepts lat/lon directly (no grid conversion). "
        "Unlike KMA, no nx/ny grid step is required. "
        "Response fields: yadmNm (name), addr, telno, clCdNm (type), ykiho (ID), distance."
    ),
    domain_quirk=(
        "JSON format requires '_type=json' (underscore prefix). "
        "'type=json' and 'dataType=JSON' are silently ignored — API returns XML. "
        "Response 'distance' is a high-precision decimal string, not a float. "
        "Response coord fields are uppercase: XPos/YPos (capital X and Y)."
    ),
    self_contained_decl=(
        "Self-contained: call resolve_location(want='coords') first, then this tool. "
        "No follow-up tool required for basic hospital listing. "
        "Use ykiho for HIRA detail queries. "
        "Do not guess coordinates — always resolve from user-supplied location text."
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
        "이비인후과 추천",
        "야간 진료 병원",
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
