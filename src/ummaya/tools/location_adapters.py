# SPDX-License-Identifier: Apache-2.0
"""Locate primitive adapters.

Each provider endpoint is exposed as a separate ``GovAPITool`` bound to the
``locate`` primitive. The root ``locate`` tool stays a thin envelope:

    locate({"tool_id": "<adapter>", "params": {...}})

This keeps provider semantics in adapter descriptions and schemas instead of
pre-processing citizen queries inside the primitive dispatcher.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from ummaya.settings import settings
from ummaya.tools.kma.projection import KMADomainError, latlon_to_lcc
from ummaya.tools.models import (
    AdapterRealDomainPolicy,
    AddressResult,
    AdmCodeResult,
    CoordResult,
    GovAPITool,
    POIResult,
    RegionResult,
    ResolveBundle,
    ResolveError,
)

logger = logging.getLogger(__name__)


class _LocateOutput(RootModel[object]):
    """Opaque locate output wrapper for registry metadata export."""


class KakaoAddressSearchInput(BaseModel):
    """Kakao Local ``search/address`` input."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Structured Korean road/jibun address or administrative place text. "
            "Use for addresses such as '서울 강남구 테헤란로 152' or '부산 사하구 하단동'."
        ),
    )


class KakaoKeywordSearchInput(BaseModel):
    """Kakao Local ``search/keyword`` input."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Korean POI, campus, landmark, station, hospital, or business name. "
            "Use for named places such as '동아대학교 승학캠퍼스', '강남역', '서울대병원'."
        ),
    )


class KakaoCoordToRegionInput(BaseModel):
    """Kakao Local ``coord2regioncode`` input."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90, description="Latitude returned by a prior locate adapter.")
    lon: float = Field(ge=-180, le=180, description="Longitude returned by a prior locate adapter.")


class JusoAdmCdLookupInput(BaseModel):
    """JUSO address-link administrative code lookup input."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=200,
        description="Korean road/jibun address text for JUSO admCd lookup.",
    )


class SgisAdmCdLookupInput(BaseModel):
    """SGIS reverse-geocode administrative code lookup input."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90, description="Latitude returned by a prior locate adapter.")
    lon: float = Field(ge=-180, le=180, description="Longitude returned by a prior locate adapter.")


def _provider_policy(provider: str, url: str) -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url=url,
        real_classification_text=f"{provider} public location API privacy/policy citation.",
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 5, 13, tzinfo=UTC),
    )


def _adm_level_from_code(code: str) -> str:
    if code[2:].rstrip("0") == "":
        return "sido"
    if code[5:].rstrip("0") == "":
        return "sigungu"
    return "eupmyeondong"


def _coord_with_grid(lat: float, lon: float, *, confidence: str = "medium") -> CoordResult:
    nx: int | None = None
    ny: int | None = None
    try:
        nx, ny = latlon_to_lcc(lat, lon)
    except KMADomainError as exc:
        logger.debug("KMA grid projection skipped for %s,%s: %s", lat, lon, exc)
    return CoordResult(
        kind="coords",
        lat=lat,
        lon=lon,
        nx=nx,
        ny=ny,
        confidence=confidence,  # type: ignore[arg-type]
        source="kakao",
    )


def _kma_grid_or_none(lat: float, lon: float) -> tuple[int | None, int | None]:
    try:
        return latlon_to_lcc(lat, lon)
    except KMADomainError as exc:
        logger.debug("KMA grid projection skipped for %s,%s: %s", lat, lon, exc)
        return None, None


def _confidence(total: int) -> str:
    if total == 1:
        return "high"
    if total <= 3:
        return "medium"
    return "low"


async def _kakao_address_search(inp: KakaoAddressSearchInput) -> ResolveBundle | ResolveError:
    from ummaya.tools.geocoding.kakao_client import search_address

    result = await search_address(inp.query)
    if not result.documents:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Kakao address search returned no result for {inp.query!r}.",
        )

    doc = result.documents[0]
    try:
        lat = float(doc.y)
        lon = float(doc.x)
    except (TypeError, ValueError):
        return ResolveError(
            kind="error",
            reason="invalid_query",
            message=f"Kakao address result had invalid coordinates for {inp.query!r}.",
        )

    road = doc.road_address.address_name if doc.road_address else None
    jibun = doc.address.address_name if doc.address else None
    address = AddressResult(
        kind="address",
        road_address=road,
        jibun_address=jibun,
        postal_code=(doc.road_address.zone_no if doc.road_address else None),
        source="kakao",
    )
    coords = _coord_with_grid(lat, lon, confidence=_confidence(result.meta.total_count))

    adm_cd: AdmCodeResult | None = None
    b_code = (doc.address.b_code or "").strip() if doc.address else ""
    if len(b_code) == 10 and b_code.isdigit():
        adm_cd = AdmCodeResult(
            kind="adm_cd",
            code=b_code,
            name=(doc.address.address_name or inp.query).strip() if doc.address else inp.query,
            level=_adm_level_from_code(b_code),  # type: ignore[arg-type]
            source="kakao",
        )

    return ResolveBundle(
        kind="bundle",
        source="bundle",
        coords=coords,
        adm_cd=adm_cd,
        address=address,
    )


async def _kakao_keyword_search(inp: KakaoKeywordSearchInput) -> POIResult | ResolveError:
    from ummaya.tools.geocoding.kakao_client import search_keyword

    result = await search_keyword(inp.query)
    if not result.documents:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Kakao keyword search returned no result for {inp.query!r}.",
        )

    doc = result.documents[0]
    try:
        lat = float(doc.y)
        lon = float(doc.x)
    except (TypeError, ValueError):
        return ResolveError(
            kind="error",
            reason="invalid_query",
            message=f"Kakao keyword result had invalid coordinates for {inp.query!r}.",
        )

    nx, ny = _kma_grid_or_none(lat, lon)
    return POIResult(
        kind="poi",
        name=doc.place_name,
        category=doc.category_name,
        lat=lat,
        lon=lon,
        nx=nx,
        ny=ny,
        source="kakao",
        address_name=doc.address_name if isinstance(doc.address_name, str) else None,
        road_address_name=doc.road_address_name if isinstance(doc.road_address_name, str) else None,
    )


async def _kakao_coord_to_region(inp: KakaoCoordToRegionInput) -> RegionResult | ResolveError:
    from ummaya.tools.geocoding.kakao_client import coord_to_region_code

    result = await coord_to_region_code(lon=inp.lon, lat=inp.lat)
    if not result.documents:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Kakao coord2regioncode returned no result for {inp.lat},{inp.lon}.",
        )

    doc = sorted(result.documents, key=lambda item: 0 if item.region_type == "B" else 1)[0]
    if len(doc.code.strip()) != 10 or not doc.code.strip().isdigit():
        return ResolveError(
            kind="error",
            reason="invalid_query",
            message=f"Kakao coord2regioncode returned invalid code {doc.code!r}.",
        )

    return RegionResult(
        kind="region",
        region_type=doc.region_type,  # type: ignore[arg-type]
        address_name=doc.address_name,
        region_1depth_name=doc.region_1depth_name,
        region_2depth_name=doc.region_2depth_name,
        region_3depth_name=doc.region_3depth_name,
        region_4depth_name=doc.region_4depth_name,
        code=doc.code.strip(),
        x=doc.x,
        y=doc.y,
        source="kakao",
    )


async def _juso_adm_cd_lookup(inp: JusoAdmCdLookupInput) -> AdmCodeResult | ResolveError:
    from ummaya.tools.geocoding.juso import lookup_adm_cd

    if not settings.juso_confm_key:
        return ResolveError(
            kind="error",
            reason="upstream_unavailable",
            message="UMMAYA_JUSO_CONFM_KEY is not configured.",
        )

    result = await lookup_adm_cd(inp.query, confm_key=settings.juso_confm_key)
    if result is None:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"JUSO admCd lookup returned no result for {inp.query!r}.",
        )

    return AdmCodeResult(
        kind="adm_cd",
        code=result["adm_cd"],
        name=result["name"],
        level=result["level"],  # type: ignore[arg-type]
        source="juso",
    )


async def _sgis_adm_cd_lookup(inp: SgisAdmCdLookupInput) -> AdmCodeResult | ResolveError:
    from ummaya.tools.geocoding.sgis import lookup_adm_cd_by_coords

    if not settings.sgis_key or not settings.sgis_secret:
        return ResolveError(
            kind="error",
            reason="upstream_unavailable",
            message="UMMAYA_SGIS_KEY/UMMAYA_SGIS_SECRET are not configured.",
        )

    result = await lookup_adm_cd_by_coords(
        lat=inp.lat,
        lon=inp.lon,
        consumer_key=settings.sgis_key,
        consumer_secret=settings.sgis_secret,
    )
    if result is None:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"SGIS adm_cd lookup returned no result for {inp.lat},{inp.lon}.",
        )

    return AdmCodeResult(
        kind="adm_cd",
        code=result["adm_cd"],
        name=result["name"],
        level=result["level"],  # type: ignore[arg-type]
        source="sgis",
    )


KAKAO_ADDRESS_SEARCH_TOOL = GovAPITool(
    id="kakao_address_search",
    name_ko="카카오 주소 검색",
    ministry="UMMAYA",
    category=["locate", "kakao", "address", "geocode"],
    endpoint="https://dapi.kakao.com/v2/local/search/address.json",
    auth_type="api_key",
    input_schema=KakaoAddressSearchInput,
    output_schema=_LocateOutput,
    llm_description=(
        "Locate adapter for Kakao Local search/address. Use for structured road or "
        "jibun addresses and administrative district text. Returns a bundle containing "
        "address, coordinates, KMA nx/ny when in domain, and Kakao b_code when present. "
        "Call as locate({tool_id:'kakao_address_search', params:{query:'...'}})."
    ),
    search_hint=(
        "locate 위치 주소 도로명 지번 행정동 좌표 geocode kakao address "
        "서울 강남구 부산 사하구 테헤란로"
    ),
    policy=_provider_policy("Kakao", "https://www.kakao.com/policy/privacy"),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    primitive="locate",
)

KAKAO_KEYWORD_SEARCH_TOOL = GovAPITool(
    id="kakao_keyword_search",
    name_ko="카카오 장소 키워드 검색",
    ministry="UMMAYA",
    category=["locate", "kakao", "poi", "geocode"],
    endpoint="https://dapi.kakao.com/v2/local/search/keyword.json",
    auth_type="api_key",
    input_schema=KakaoKeywordSearchInput,
    output_schema=_LocateOutput,
    llm_description=(
        "Locate adapter for Kakao Local search/keyword. Use for named places, campuses, "
        "stations, landmarks, hospitals, businesses, and POIs such as '동아대학교 승학캠퍼스' "
        "or '강남역'. Returns POI name/category, WGS-84 lat/lon, and KMA nx/ny "
        "when in domain. If a downstream adapter needs q0/q1 region names, follow with "
        "locate({tool_id:'kakao_coord_to_region', params:{lat:<lat>, lon:<lon>}})."
    ),
    search_hint=(
        "locate 위치 장소 키워드 POI 랜드마크 캠퍼스 역 병원 좌표 kakao keyword "
        "동아대 동아대학교 승학캠퍼스 강남역 서울대병원"
    ),
    policy=_provider_policy("Kakao", "https://www.kakao.com/policy/privacy"),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    primitive="locate",
)

KAKAO_COORD_TO_REGION_TOOL = GovAPITool(
    id="kakao_coord_to_region",
    name_ko="카카오 좌표-지역 변환",
    ministry="UMMAYA",
    category=["locate", "kakao", "region", "reverse-geocode"],
    endpoint="https://dapi.kakao.com/v2/local/geo/coord2regioncode.json",
    auth_type="api_key",
    input_schema=KakaoCoordToRegionInput,
    output_schema=_LocateOutput,
    llm_description=(
        "Locate adapter for Kakao coord2regioncode. Use after a coordinate-producing "
        "locate adapter when a downstream public API needs region_1depth_name/q0, "
        "region_2depth_name/q1, or a 10-digit legal/admin code. "
        "Call as locate({tool_id:'kakao_coord_to_region', params:{lat:<lat>, lon:<lon>}})."
    ),
    search_hint=("locate 지역 시도 시군구 행정동 법정동 q0 q1 coord2region reverse geocode kakao"),
    policy=_provider_policy("Kakao", "https://www.kakao.com/policy/privacy"),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    primitive="locate",
)

JUSO_ADM_CD_LOOKUP_TOOL = GovAPITool(
    id="juso_adm_cd_lookup",
    name_ko="도로명주소 행정코드 조회",
    ministry="UMMAYA",
    category=["locate", "juso", "adm_cd", "address"],
    endpoint="https://business.juso.go.kr/addrlink/addrLinkApi.do",
    auth_type="api_key",
    input_schema=JusoAdmCdLookupInput,
    output_schema=_LocateOutput,
    llm_description=(
        "Locate adapter for JUSO addrlink admCd lookup. Use when a downstream adapter "
        "specifically needs a 10-digit adm_cd from a Korean road/jibun address. "
        "Requires UMMAYA_JUSO_CONFM_KEY."
    ),
    search_hint="locate 주소 행정동 adm_cd admCd juso 도로명주소 법정동 코드",
    policy=_provider_policy("JUSO", "https://www.juso.go.kr/addrlink/devAddrLinkRequestGuide.do"),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    primitive="locate",
)

SGIS_ADM_CD_LOOKUP_TOOL = GovAPITool(
    id="sgis_adm_cd_lookup",
    name_ko="SGIS 좌표 행정코드 조회",
    ministry="UMMAYA",
    category=["locate", "sgis", "adm_cd", "reverse-geocode"],
    endpoint="https://sgisapi.mods.go.kr/OpenAPI3/addr/rgeocodewgs84.json",
    auth_type="api_key",
    input_schema=SgisAdmCdLookupInput,
    output_schema=_LocateOutput,
    llm_description=(
        "Locate adapter for SGIS reverse geocoding. Use after a coordinate-producing "
        "locate adapter when a downstream adapter needs a 10-digit adm_cd. "
        "Requires UMMAYA_SGIS_KEY and UMMAYA_SGIS_SECRET."
    ),
    search_hint="locate sgis 좌표 역지오코딩 행정동 adm_cd 통계청 region reverse geocode",
    policy=_provider_policy("SGIS", "https://sgis.kostat.go.kr/view/newhelp/api_help_10_0"),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    primitive="locate",
)


def register(registry: object, executor: object) -> None:
    """Register locate adapters in the central ToolRegistry and ToolExecutor."""

    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    adapter_pairs: list[tuple[GovAPITool, Any]] = [
        (KAKAO_ADDRESS_SEARCH_TOOL, _kakao_address_search),
        (KAKAO_KEYWORD_SEARCH_TOOL, _kakao_keyword_search),
        (KAKAO_COORD_TO_REGION_TOOL, _kakao_coord_to_region),
        (JUSO_ADM_CD_LOOKUP_TOOL, _juso_adm_cd_lookup),
        (SGIS_ADM_CD_LOOKUP_TOOL, _sgis_adm_cd_lookup),
    ]
    for tool, adapter in adapter_pairs:
        registry.register(tool)
        executor.register_adapter(tool.id, adapter)
        logger.info("Registered locate adapter: %s", tool.id)


__all__ = [
    "KAKAO_ADDRESS_SEARCH_TOOL",
    "KAKAO_KEYWORD_SEARCH_TOOL",
    "KAKAO_COORD_TO_REGION_TOOL",
    "JUSO_ADM_CD_LOOKUP_TOOL",
    "SGIS_ADM_CD_LOOKUP_TOOL",
    "register",
]
