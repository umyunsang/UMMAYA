# SPDX-License-Identifier: Apache-2.0
"""Kakao Local API HTTP client for address + POI geocoding.

Wraps two of Kakao Local API's six endpoints:
  - ``GET /v2/local/search/address.json`` — structured address (도로명/지번)
  - ``GET /v2/local/search/keyword.json`` — POI / landmark / business name

The two endpoints cover Kakao's two location-semantic dimensions; they are
NOT a primary/fallback pair. The address endpoint returns empty for POI
queries like "동아대학교", and the keyword endpoint returns the nearest POI
when given a structured address string. Callers that only know "the user
gave a free-form location query" need to issue both calls in parallel and
merge — see :func:`kosmos.tools.resolve_location._kakao_coords_fanout`.

This file is the source-of-truth shape mirror; it does not synthesise any
business logic. Reference: PyKakao 1.x ``Local`` class
(`https://github.com/WooilJeong/PyKakao`), which exposes the same six
endpoints as six methods on a single facade — the industry-standard
Korean wrapper for this API. KOSMOS originally shipped only
``search_address`` (Spec 022); ``search_keyword`` is added here to close
the POI-coverage gap captured in
``specs/integration-verification/donga-univ-poi-bug/``.

Authentication: REST API key via ``Authorization: KakaoAK {key}`` header.
Key source: ``KOSMOS_KAKAO_API_KEY`` environment variable.

Error mapping (all propagated directly for recovery classifier):
  - HTTP 401  → :exc:`httpx.HTTPStatusError` (auth_expired)
  - HTTP 429  → :exc:`httpx.HTTPStatusError` (rate_limit)
  - timeout   → :exc:`httpx.TimeoutException`
  - other 4xx/5xx → :exc:`httpx.HTTPStatusError`
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ConfigurationError, _require_env

logger = logging.getLogger(__name__)

_ADDRESS_BASE_URL = "https://dapi.kakao.com/v2/local/search/address.json"
_KEYWORD_BASE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
# Retained for backwards compatibility with callers that imported the
# original module-level constant; aliases the address endpoint.
_BASE_URL = _ADDRESS_BASE_URL
_DEFAULT_TIMEOUT = 5.0  # seconds


# ---------------------------------------------------------------------------
# Pydantic v2 response models
# ---------------------------------------------------------------------------


class KakaoRoadAddressResult(BaseModel):
    """Road address (도로명주소) portion of a Kakao address document."""

    model_config = ConfigDict(frozen=True)

    address_name: str
    """Full road address string."""

    region_1depth_name: str
    """Province (시도) name, e.g. "서울특별시"."""

    region_2depth_name: str
    """District (구군) name, e.g. "강남구"."""

    region_3depth_name: str = ""
    """Sub-district (읍면동) name."""

    road_name: str = ""
    """Road name."""

    underground_yn: str = "N"
    """Whether underground (Y/N)."""

    main_building_no: str = ""
    """Main building number."""

    sub_building_no: str = ""
    """Sub building number."""

    building_name: str = ""
    """Building name."""

    zone_no: str = ""
    """Postal zone code."""

    x: str = ""
    """Longitude as string."""

    y: str = ""
    """Latitude as string."""


class KakaoAddressDocument(BaseModel):
    """A single address document returned by the Kakao search/address endpoint."""

    model_config = ConfigDict(frozen=True)

    address_name: str
    """Full resolved address string."""

    address_type: str = ""
    """Type of address: REGION, ROAD_ADDR, REGION_ADDR, etc."""

    x: str
    """Longitude (경도) as string."""

    y: str
    """Latitude (위도) as string."""

    address: KakaoAddressResult | None = None
    """Legacy address result block (구주소)."""

    road_address: KakaoRoadAddressResult | None = None
    """Road address block (도로명주소); preferred when available."""


class KakaoAddressResult(BaseModel):
    """Legacy address (구주소) portion of a Kakao address document."""

    model_config = ConfigDict(frozen=True)

    address_name: str
    """Full legacy address string."""

    region_1depth_name: str
    """Province (시도) name."""

    region_2depth_name: str
    """District (구군) name."""

    region_3depth_name: str = ""
    """Sub-district (읍면동) name."""

    mountain_yn: str = "N"
    """Whether mountain address (Y/N)."""

    main_address_no: str = ""
    """Main address number."""

    sub_address_no: str = ""
    """Sub address number."""

    b_code: str = ""
    """10-digit 법정동 코드 (행정동 code). Spec 2522 US7 T039."""

    h_code: str = ""
    """10-digit 행정동 코드. Parallel code used for administrative hierarchy lookups."""

    x: str = ""
    """Longitude as string."""

    y: str = ""
    """Latitude as string."""


# Re-attach forward reference now that KakaoAddressResult is defined
KakaoAddressDocument.model_rebuild()


class KakaoSearchMeta(BaseModel):
    """Metadata returned alongside Kakao address search results."""

    model_config = ConfigDict(frozen=True)

    total_count: int = Field(default=0, ge=0)
    """Total number of documents matching the query."""

    pageable_count: int = Field(default=0, ge=0)
    """Number of results the API will paginate through."""

    is_end: bool = True
    """Whether this is the last page of results."""


class KakaoSearchResult(BaseModel):
    """Top-level response envelope from the Kakao address search API."""

    model_config = ConfigDict(frozen=True)

    meta: KakaoSearchMeta
    """Pagination metadata."""

    documents: list[KakaoAddressDocument]
    """Matched address documents (empty list when no match)."""


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


async def search_address(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> KakaoSearchResult:
    """Search Kakao Local API for a Korean address string.

    Args:
        query: Free-form Korean address to geocode (e.g. "서울특별시 강남구 테헤란로").
        client: Optional injected ``httpx.AsyncClient`` for testing.

    Returns:
        A :class:`KakaoSearchResult` with matched documents (may be empty).

    Raises:
        ConfigurationError: If ``KOSMOS_KAKAO_API_KEY`` is not set.
        ConfigurationError: If ``KOSMOS_KAKAO_API_KEY`` is not set.
        httpx.TimeoutException: On request timeout.
        httpx.HTTPStatusError: On HTTP 4xx/5xx responses (including 401
            auth-expired and 429 rate-limit).  Propagated directly so
            the recovery classifier can recognise and route them.
        httpx.RequestError: On connection-level failures.
    """
    api_key = _require_env("KOSMOS_KAKAO_API_KEY")

    headers = {
        "Authorization": f"KakaoAK {api_key}",
        "Accept": "application/json",
    }
    request_params: dict[str, str | int] = {"query": query, "size": 2}

    logger.debug("Kakao address search: query=%r", query)

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=_DEFAULT_TIMEOUT)

    try:
        assert client is not None
        response = await client.get(_BASE_URL, headers=headers, params=request_params)

        # Let httpx.HTTPStatusError propagate for ALL status codes (including
        # 401 auth-expired, 429 rate-limit) so the recovery classifier can
        # recognise them directly without unwrapping ToolExecutionError.
        response.raise_for_status()

        payload: dict[str, Any] = response.json()
        result = KakaoSearchResult(**payload)

        logger.debug(
            "Kakao address search returned %d document(s)",
            result.meta.total_count,
        )
        return result

    except ConfigurationError:
        raise
    # Let httpx exceptions (TimeoutException, HTTPStatusError, RequestError)
    # propagate directly so the recovery classifier can recognise them.
    finally:
        if own_client and client is not None:
            await client.aclose()


# ---------------------------------------------------------------------------
# Pydantic v2 models — keyword (POI) endpoint
# ---------------------------------------------------------------------------


class KakaoPlaceDocument(BaseModel):
    """A single place document returned by the Kakao search/keyword endpoint.

    Field set is intentionally narrower than ``KakaoAddressDocument`` because
    the keyword endpoint's response does not carry the structured
    address/road_address sub-blocks. Callers that need structured address
    fields should also issue a search/address call and merge — see
    :func:`kosmos.tools.resolve_location._kakao_coords_fanout`.
    """

    model_config = ConfigDict(frozen=True)

    id: str = ""
    """Kakao place id."""

    place_name: str
    """POI / business / landmark name (e.g. "동아대학교 승학캠퍼스")."""

    category_name: str = ""
    """Category breadcrumb (e.g. "교육,학문 > 학교 > 대학교")."""

    category_group_code: str = ""
    """Category group code (e.g. "SC4" for school)."""

    category_group_name: str = ""
    """Human-readable category group name (e.g. "학교")."""

    phone: str = ""
    """Place phone number, may be empty."""

    address_name: str = ""
    """Jibun-format address string (구주소)."""

    road_address_name: str = ""
    """Road-format address string (도로명주소), may be empty."""

    x: str
    """Longitude (경도) as string."""

    y: str
    """Latitude (위도) as string."""

    place_url: str = ""
    """Kakao Map detail page URL."""

    distance: str = ""
    """Distance from search anchor in meters, present only when x/y supplied."""


class KakaoKeywordSearchResult(BaseModel):
    """Top-level response envelope from the Kakao keyword search API.

    Mirrors :class:`KakaoSearchResult` so callers can consume both endpoints
    through structurally compatible code paths (``meta.total_count`` +
    ``documents`` iteration), even though the document shapes differ.
    """

    model_config = ConfigDict(frozen=True)

    meta: KakaoSearchMeta
    documents: list[KakaoPlaceDocument]


async def search_keyword(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> KakaoKeywordSearchResult:
    """Search Kakao Local API for a Korean POI / landmark / business name.

    The keyword endpoint covers the POI half of Kakao's location semantic
    space: queries that name a place rather than describe a structured
    address (e.g. "동아대학교", "스타벅스 강남역점", "남대문"). For
    structured-address queries, prefer :func:`search_address`; the two
    endpoints are NOT a primary/fallback pair, and a wrapper that needs
    both should call them in parallel and merge.

    Args:
        query: Free-form Korean place name to search for.
        client: Optional injected ``httpx.AsyncClient`` for testing.

    Returns:
        A :class:`KakaoKeywordSearchResult` with matched place documents
        (may be empty when no place matches the query).

    Raises: same as :func:`search_address`.
    """
    api_key = _require_env("KOSMOS_KAKAO_API_KEY")

    headers = {
        "Authorization": f"KakaoAK {api_key}",
        "Accept": "application/json",
    }
    request_params: dict[str, str | int] = {"query": query, "size": 2}

    logger.debug("Kakao keyword search: query=%r", query)

    own_client = client is None
    if own_client:
        client = traced_async_client(timeout=_DEFAULT_TIMEOUT)

    try:
        assert client is not None
        response = await client.get(_KEYWORD_BASE_URL, headers=headers, params=request_params)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        result = KakaoKeywordSearchResult(**payload)
        logger.debug(
            "Kakao keyword search returned %d document(s)", result.meta.total_count
        )
        return result
    except ConfigurationError:
        raise
    finally:
        if own_client and client is not None:
            await client.aclose()
