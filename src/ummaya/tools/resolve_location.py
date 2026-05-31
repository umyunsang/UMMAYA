# SPDX-License-Identifier: Apache-2.0
"""locate facade coroutine — T023.

Single entry point for converting a natural-language place reference into
structured location data (coordinates, 10-digit 행정동 code, address, POI).

Legacy compatibility resolver chain: kakao → juso → sgis.
New LLM-visible calls should use concrete provider adapters from
``ummaya.tools.location_adapters``. The root ``locate({tool_id, params})``
shape is retained only for legacy transcripts and compatibility paths.

FR-002: Accepts ``query``, ``want``, and optional ``near`` anchor.
FR-003: Kakao / JUSO / SGIS are exposed as separate locate adapters; this
legacy façade is retained for old transcripts and direct unit tests.
FR-035: ``source`` field populated on every successful result.
FR-036: ``ResolveBundle`` carries per-backend provenance.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

import httpx

from ummaya.tools.kma.projection import KMADomainError, latlon_to_lcc
from ummaya.tools.models import (
    AddressResult,
    AdmCodeResult,
    CoordResult,
    POIResult,
    RegionResult,
    ResolveBundle,
    ResolveError,
    ResolveLocationInput,
    ResolveLocationOutput,
)

logger = logging.getLogger(__name__)


def _compact_match_text(value: str) -> str:
    """Normalize Korean/English location text for conservative relevance checks."""
    compact = re.sub(r"[^0-9a-zA-Z가-힣]+", "", value).lower()
    return compact.replace("특별", "").replace("광역", "").replace("대학교", "대")


def _keyword_doc_matches_query(query: str, doc: object) -> bool:
    """Guard Kakao keyword hits against unrelated top-result drift.

    Kakao keyword search is intentionally broad. For nonsense strings such as
    "존재하지않는주소" it may still return a popular POI; UMMAYA must surface
    not_found instead of treating that as a resolved citizen location.
    """
    normalized_query = _compact_match_text(query)
    if len(normalized_query) < 2:
        return False
    for attr in ("place_name", "address_name", "road_address_name"):
        value = getattr(doc, attr, None)
        if not isinstance(value, str):
            continue
        normalized_value = _compact_match_text(value)
        if len(normalized_value) < 2:
            continue
        if normalized_query in normalized_value or normalized_value in normalized_query:
            return True
    return False


async def _kakao_geocode(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CoordResult | AddressResult | POIResult | None:
    """Resolve a location to (Address | POI | Coord) via Kakao parallel fanout.

    Issues both ``search/address`` and ``search/keyword`` calls in parallel
    (see :func:`_kakao_coords` for the rationale on why fanout, not fallback)
    and merges the responses by deterministic priority:

      1. address response present → :class:`AddressResult` (carries
         structured road/jibun/postal-code fields).
      2. keyword response present → :class:`POIResult` (POI / landmark /
         business name + coordinates).
      3. neither present → ``None`` (caller surfaces ResolveError).

    The merge order reflects the semantic specificity of each response, not
    a primary/fallback preference: both calls already completed by the time
    the merge runs.
    """
    import asyncio  # noqa: PLC0415

    from ummaya.tools.geocoding.kakao_client import (  # noqa: PLC0415
        search_address,
        search_keyword,
    )

    async def _addr() -> AddressResult | CoordResult | None:
        try:
            result = await search_address(query, client=client)
            if not result.documents:
                return None
            doc = result.documents[0]
            try:
                lat = float(doc.y) if doc.y else None
                lon = float(doc.x) if doc.x else None
            except (ValueError, TypeError):
                lat = lon = None
            if lat is None or lon is None:
                return None
            addr_block = doc.road_address or doc.address
            road = doc.road_address.address_name if doc.road_address else None
            jibun = doc.address.address_name if doc.address else None
            if addr_block:
                return AddressResult(
                    kind="address",
                    road_address=road,
                    jibun_address=jibun,
                    postal_code=(doc.road_address.zone_no if doc.road_address else None),
                    source="kakao",
                )
            return _with_kma_grid(
                CoordResult(
                    kind="coords",
                    lat=lat,
                    lon=lon,
                    confidence=_confidence_from_total(result.meta.total_count),
                    source="kakao",
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("kakao address geocode failed for %r: %s", query, exc)
            return None

    async def _kw() -> POIResult | None:
        try:
            result = await search_keyword(query, client=client)
            if not result.documents:
                return None
            doc = result.documents[0]
            if not _keyword_doc_matches_query(query, doc):
                logger.info(
                    "kakao keyword geocode rejected unrelated top result for query=%r "
                    "place_name=%r",
                    query,
                    getattr(doc, "place_name", None),
                )
                return None
            try:
                lat = float(doc.y) if doc.y else None
                lon = float(doc.x) if doc.x else None
            except (ValueError, TypeError):
                lat = lon = None
            if lat is None or lon is None:
                return None
            return _poi_with_kma_grid(
                POIResult(
                    kind="poi",
                    name=doc.place_name,
                    category=doc.category_name,
                    lat=lat,
                    lon=lon,
                    source="kakao",
                    address_name=doc.address_name if isinstance(doc.address_name, str) else None,
                    road_address_name=(
                        doc.road_address_name if isinstance(doc.road_address_name, str) else None
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("kakao keyword geocode failed for %r: %s", query, exc)
            return None

    addr_result, kw_result = await asyncio.gather(_addr(), _kw())

    # Deterministic priority — NOT a fallback chain. The address result wins
    # when present because a non-empty address response means the query was
    # unambiguously a structured address (road/jibun + structured fields).
    # The keyword result fills the POI-only gap exposed when address is empty
    # (e.g. "동아대학교"). See _kakao_coords for the full rationale.
    if addr_result is not None:
        return addr_result
    return kw_result


def _confidence_from_total(total: int) -> Literal["high", "medium", "low"]:
    if total == 1:
        return "high"
    if total <= 3:
        return "medium"
    return "low"


def _with_kma_grid(coords: CoordResult) -> CoordResult:
    """Attach official KMA nx/ny grid coordinates when WGS-84 point is in domain."""
    try:
        nx, ny = latlon_to_lcc(coords.lat, coords.lon)
    except KMADomainError as exc:
        logger.debug("kma grid projection skipped: %s", exc)
        return coords
    return coords.model_copy(update={"nx": nx, "ny": ny})


def _poi_with_kma_grid(poi: POIResult) -> POIResult:
    """Attach official KMA nx/ny grid coordinates to POI results when possible."""
    try:
        nx, ny = latlon_to_lcc(poi.lat, poi.lon)
    except KMADomainError as exc:
        logger.debug("poi kma grid projection skipped: %s", exc)
        return poi
    return poi.model_copy(update={"nx": nx, "ny": ny})


def _adm_level_from_code(code: str) -> Literal["sido", "sigungu", "eupmyeondong"]:
    if code[2:].rstrip("0") == "":
        return "sido"
    if code[5:].rstrip("0") == "":
        return "sigungu"
    return "eupmyeondong"


async def _kakao_adm_cd_from_coords(
    coords: CoordResult,
    *,
    client: httpx.AsyncClient | None = None,
) -> AdmCodeResult | None:
    """Resolve a 10-digit legal/admin code from official Kakao coord2regioncode rows."""
    from ummaya.tools.geocoding.kakao_client import coord_to_region_code  # noqa: PLC0415

    try:
        result = await coord_to_region_code(lon=coords.lon, lat=coords.lat, client=client)
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("kakao coord2region adm_cd failed for %s,%s: %s", coords.lat, coords.lon, exc)
        return None

    if not result.documents:
        return None

    ordered = sorted(result.documents, key=lambda doc: 0 if doc.region_type == "B" else 1)
    doc = ordered[0]
    code = doc.code.strip()
    if len(code) != 10 or not code.isdigit():
        return None

    name = doc.address_name.strip() or " ".join(
        part
        for part in (
            doc.region_1depth_name,
            doc.region_2depth_name,
            doc.region_3depth_name,
            doc.region_4depth_name,
        )
        if part
    )
    return AdmCodeResult(
        kind="adm_cd",
        code=code,
        name=name,
        level=_adm_level_from_code(code),
        source="kakao",
    )


async def _kakao_region_from_coords(
    *,
    lat: float,
    lon: float,
    client: httpx.AsyncClient | None = None,
) -> RegionResult | None:
    """Resolve legal/admin region names from coordinates via Kakao coord2regioncode."""
    from ummaya.tools.geocoding.kakao_client import coord_to_region_code  # noqa: PLC0415

    result = await coord_to_region_code(lon=lon, lat=lat, client=client)
    if not result.documents:
        return None
    ordered = sorted(result.documents, key=lambda doc: 0 if doc.region_type == "B" else 1)
    doc = ordered[0]
    region_type: Literal["B", "H"] = "B" if doc.region_type == "B" else "H"
    return RegionResult(
        kind="region",
        region_type=region_type,
        address_name=doc.address_name,
        region_1depth_name=doc.region_1depth_name,
        region_2depth_name=doc.region_2depth_name,
        region_3depth_name=doc.region_3depth_name,
        region_4depth_name=doc.region_4depth_name,
        code=doc.code,
        x=doc.x,
        y=doc.y,
        source="kakao",
    )


async def _kakao_address_coords(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CoordResult | None:
    """Resolve coordinates via Kakao address endpoint (structured address only).

    Returns ``None`` when the query is not a structured address — Kakao's
    address endpoint emits an empty ``documents`` list for POI/landmark
    queries like "동아대학교". Use :func:`_kakao_keyword_coords` for those.
    """
    try:
        from ummaya.tools.geocoding.kakao_client import search_address  # noqa: PLC0415

        result = await search_address(query, client=client)
        if not result.documents:
            return None
        doc = result.documents[0]
        try:
            lat = float(doc.y) if doc.y else None
            lon = float(doc.x) if doc.x else None
        except (ValueError, TypeError):
            lat = lon = None
        if lat is None or lon is None:
            return None
        return _with_kma_grid(
            CoordResult(
                kind="coords",
                lat=lat,
                lon=lon,
                confidence=_confidence_from_total(result.meta.total_count),
                source="kakao",
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("kakao address coords failed for %r: %s", query, exc)
        return None


async def _kakao_keyword_coords(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CoordResult | None:
    """Resolve coordinates via Kakao keyword endpoint (POI / landmark / business).

    Returns ``None`` when no place matches. The keyword endpoint also accepts
    structured-address strings and returns the nearest POI's coordinates
    (≈centimeter offset from the address coordinate), so this is safe to call
    in parallel with :func:`_kakao_address_coords` and merge the results.
    """
    try:
        from ummaya.tools.geocoding.kakao_client import search_keyword  # noqa: PLC0415

        result = await search_keyword(query, client=client)
        if not result.documents:
            return None
        doc = result.documents[0]
        if not _keyword_doc_matches_query(query, doc):
            logger.info(
                "kakao keyword coords rejected unrelated top result for query=%r place_name=%r",
                query,
                getattr(doc, "place_name", None),
            )
            return None
        try:
            lat = float(doc.y) if doc.y else None
            lon = float(doc.x) if doc.x else None
        except (ValueError, TypeError):
            lat = lon = None
        if lat is None or lon is None:
            return None
        return _with_kma_grid(
            CoordResult(
                kind="coords",
                lat=lat,
                lon=lon,
                confidence=_confidence_from_total(result.meta.total_count),
                source="kakao",
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("kakao keyword coords failed for %r: %s", query, exc)
        return None


async def _kakao_coords(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> CoordResult | None:
    """Resolve coordinates via Kakao — parallel fanout across both endpoints.

    Kakao Local API splits its location semantic space into two endpoints:
    ``search/address.json`` covers structured addresses, ``search/keyword.json``
    covers POI / landmarks / businesses. Either dimension is empty for the
    other dimension's queries (verified live: "동아대학교" → address empty,
    keyword returns 부산 사하구 하단동; "테헤란로 152" → address returns the
    road point, keyword returns the same coordinates wrapped as the building
    POI). A wrapper that needs to handle both query types must therefore
    issue both calls.

    This is parallel fanout (``asyncio.gather``), NOT sequential fallback —
    both calls fire simultaneously, the merge applies a deterministic
    priority (address result wins when present, since it carries structured
    address fields by definition; keyword result fills the POI-only gap).
    Cost: 2× per-call traffic, capped at 2× of Kakao's 100k/day quota
    (separate pools per endpoint = effective 200k/day combined).

    Reference: PyKakao 1.x ``Local`` class
    (https://github.com/WooilJeong/PyKakao) which exposes the same six
    endpoints as six methods — the wrapper-side fanout is UMMAYA' addition
    on top of the byte-identical PyKakao surface so callers like
    ``_handle_chat_request`` see one coordinate result regardless of query
    dimension.
    """
    import asyncio  # noqa: PLC0415

    addr_result, kw_result = await asyncio.gather(
        _kakao_address_coords(query, client=client),
        _kakao_keyword_coords(query, client=client),
        return_exceptions=False,
    )

    # Deterministic priority — NOT a fallback chain. Both calls already
    # completed; the merge picks the most semantically appropriate result.
    # Address result wins when present because the address endpoint only
    # returns matches for genuinely structured-address queries; a hit there
    # means the query was unambiguously an address. Keyword result is used
    # when the query was a POI/landmark (address endpoint empty).
    if addr_result is not None:
        return addr_result
    return kw_result


async def _kakao_adm_cd(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> AdmCodeResult | None:
    """Spec 2522 T047 fix — Kakao b_code fallback for adm_cd path.

    JUSO/SGIS API 키가 없는 환경에서 adm_cd 를 못 받아 KOROAD chain 이
    fail 하던 회귀 (frames-gangnam-accident-fix3 evidence). Kakao Local API
    의 ``address.b_code`` (10-digit 법정동) 을 AdmCodeResult 로 매핑.
    Kakao 키만 있으면 광역시도 / 시군구 / 동 단위 모두 정상 동작.
    """
    try:
        from ummaya.tools.geocoding.kakao_client import search_address  # noqa: PLC0415

        result = await search_address(query, client=client)
        if not result.documents:
            return None
        doc = result.documents[0]
        b_code = (doc.address.b_code or "").strip() if doc.address else ""
        if not b_code or len(b_code) != 10:
            return None
        # doc.address 는 위에서 falsy guard 통과한 상태 — mypy narrowing 위해 assert
        assert doc.address is not None  # noqa: S101 — type narrowing for mypy
        name = (doc.address.address_name or query).strip()
        return AdmCodeResult(
            kind="adm_cd",
            code=b_code,
            name=name,
            level=_adm_level_from_code(b_code),
            source="kakao",
        )
    except (httpx.HTTPError, httpx.HTTPStatusError, ValueError) as exc:
        logger.debug("kakao adm_cd fallback failed for %r: %s", query, exc)
        return None
    except Exception as exc:  # noqa: BLE001 — Codex P1: UMMAYA_KAKAO_API_KEY 부재
        # 시 search_address() 가 ConfigurationError raise. JUSO/SGIS 도 없는
        # 환경에서 hard adapter fail 대신 graceful ResolveError 로 fallback.
        logger.debug("kakao adm_cd fallback config/unexpected error for %r: %s", query, exc)
        return None


async def _juso_adm_cd(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> AdmCodeResult | None:
    """Try to resolve 10-digit adm_cd via juso.go.kr API.

    Delegates to the shared ``geocoding.juso.lookup_adm_cd`` backend helper.
    Returns AdmCodeResult on success, None on failure/no result.
    """
    from ummaya.settings import settings  # noqa: PLC0415
    from ummaya.tools.geocoding.juso import lookup_adm_cd  # noqa: PLC0415

    confm_key = settings.juso_confm_key
    if not confm_key:
        logger.debug("juso: UMMAYA_JUSO_CONFM_KEY not set, skipping")
        return None

    result = await lookup_adm_cd(query, confm_key=confm_key, client=client)
    if result is None:
        return None

    return AdmCodeResult(
        kind="adm_cd",
        code=result["adm_cd"],
        name=result["name"],
        level=result["level"],  # type: ignore[arg-type]
        source="juso",
    )


async def _sgis_adm_cd(
    query: str,
    coords: CoordResult | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> AdmCodeResult | None:
    """Try to resolve 10-digit adm_cd via SGIS API.

    Delegates to the shared ``geocoding.sgis.lookup_adm_cd_by_coords`` backend
    helper.  Requires coordinates — returns None if not available.
    """
    if coords is None:
        logger.debug("sgis adm_cd: no coords available, skipping")
        return None

    from ummaya.settings import settings  # noqa: PLC0415
    from ummaya.tools.geocoding.sgis import lookup_adm_cd_by_coords  # noqa: PLC0415

    consumer_key = settings.sgis_key
    consumer_secret = settings.sgis_secret
    if not consumer_key or not consumer_secret:
        logger.debug("sgis: UMMAYA_SGIS_KEY/SECRET not set, skipping")
        return None

    result = await lookup_adm_cd_by_coords(
        lat=coords.lat,
        lon=coords.lon,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        client=client,
    )
    if result is None:
        return None

    return AdmCodeResult(
        kind="adm_cd",
        code=result["adm_cd"],
        name=result["name"],
        level=result["level"],  # type: ignore[arg-type]
        source="sgis",
    )


async def resolve_location(  # noqa: C901
    inp: ResolveLocationInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> (
    CoordResult
    | AdmCodeResult
    | AddressResult
    | POIResult
    | RegionResult
    | ResolveBundle
    | ResolveError
):
    """Resolve a natural-language place reference to structured location data.

    Deterministic resolver chain: kakao → juso → sgis.
    Short-circuits on the first non-error result.

    Args:
        inp: Validated ResolveLocationInput.
        client: Optional httpx.AsyncClient for test injection.

    Returns:
        One of the 6 ResolveLocationOutput variants.
    """
    query = inp.query.strip()
    want = inp.want

    if not query:
        return ResolveError(
            kind="error",
            reason="empty_query",
            message="Query must not be empty.",
        )

    logger.debug("locate: query=%r want=%s", query, want)

    # --- coords path ---
    if want == "coords":
        coords = await _kakao_coords(query, client=client)
        if coords:
            return _with_kma_grid(coords)
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Could not resolve coordinates for query {query!r}.",
        )

    # --- region path ---
    if want == "region":
        coords = await _kakao_coords(query, client=client)
        if coords is None:
            return ResolveError(
                kind="error",
                reason="not_found",
                message=f"Could not resolve coordinates for region query {query!r}.",
            )
        try:
            region = await _kakao_region_from_coords(
                lat=coords.lat,
                lon=coords.lon,
                client=client,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("kakao region resolution failed for %r: %s", query, exc)
            return ResolveError(
                kind="error",
                reason="upstream_unavailable",
                message=f"Kakao coord2regioncode backend unavailable: {exc}",
            )
        if region is not None:
            return region
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Could not resolve region metadata for query {query!r}.",
        )

    # --- adm_cd path ---
    if want == "adm_cd":
        # Spec 2522 T047 — ordered resolver chain.
        # JUSO (UMMAYA_JUSO_CONFM_KEY) → Kakao address.b_code →
        # Kakao coord2regioncode → SGIS (UMMAYA_SGIS_KEY).
        # The coord2regioncode leg covers POI/station queries where Kakao
        # search/address is intentionally empty but search/keyword returned
        # a WGS-84 point.
        adm = await _juso_adm_cd(query, client=client)
        if adm:
            return adm

        adm = await _kakao_adm_cd(query, client=client)
        if adm:
            return adm

        coords = await _kakao_coords(query, client=client)
        if coords:
            adm = await _kakao_adm_cd_from_coords(coords, client=client)
            if adm:
                return adm

        adm = await _sgis_adm_cd(query, coords=coords, client=client)
        if adm:
            return adm

        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Could not resolve administrative code for query {query!r}.",
        )

    # --- address path ---
    if want in ("road_address", "jibun_address"):
        geo = await _kakao_geocode(query, client=client)
        if geo and isinstance(geo, AddressResult):
            return geo
        # Try juso for canonical road address
        adm = await _juso_adm_cd(query, client=client)
        if adm is None:
            return ResolveError(
                kind="error",
                reason="not_found",
                message=f"Could not resolve address for query {query!r}.",
            )
        # adm.name is an administrative area name (e.g. "서울특별시 강남구"), not a
        # specific road or jibun address.  Returning it in road_address would
        # mislead callers, so we surface an honest not_found error instead.
        return ResolveError(
            kind="error",
            reason="not_found",
            message=(
                f"JUSO resolved only an administrative area ({adm.name!r}) for"
                f" query {query!r}, not a specific road or jibun address."
            ),
        )

    # --- poi path ---
    if want == "poi":
        # Was previously routed through search_address — a structural bug:
        # the address endpoint returns empty for POI queries like
        # "동아대학교", so every want='poi' call ended in not_found and the
        # LLM fell back to fabricated coordinates. Routing
        # through the keyword endpoint is the byte-correct PyKakao mapping
        # for POI queries.
        try:
            from ummaya.tools.geocoding.kakao_client import search_keyword  # noqa: PLC0415

            result = await search_keyword(query, client=client)
            if result.documents:
                doc = result.documents[0]
                if not _keyword_doc_matches_query(query, doc):
                    logger.info(
                        "poi resolution rejected unrelated top result for query=%r place_name=%r",
                        query,
                        getattr(doc, "place_name", None),
                    )
                    return ResolveError(
                        kind="error",
                        reason="not_found",
                        message=f"Could not resolve POI for query {query!r}.",
                    )
                try:
                    lat = float(doc.y) if doc.y else None
                    lon = float(doc.x) if doc.x else None
                except (ValueError, TypeError):
                    lat = lon = None
                if lat is not None and lon is not None:
                    return _poi_with_kma_grid(
                        POIResult(
                            kind="poi",
                            name=doc.place_name,
                            category=doc.category_name,
                            lat=lat,
                            lon=lon,
                            source="kakao",
                            address_name=(
                                doc.address_name if isinstance(doc.address_name, str) else None
                            ),
                            road_address_name=(
                                doc.road_address_name
                                if isinstance(doc.road_address_name, str)
                                else None
                            ),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("poi resolution failed for %r: %s", query, exc)

        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Could not resolve POI for query {query!r}.",
        )

    # --- coords_and_admcd (default MVP bundle) ---
    if want in ("coords_and_admcd", "all"):
        coords_bundle: CoordResult | None = None
        adm_bundle: AdmCodeResult | None = None
        address_result: AddressResult | None = None
        poi_result: POIResult | None = None
        region_result: RegionResult | None = None

        if want == "all":
            # Parallel fanout across Kakao's two location-semantic
            # dimensions: address endpoint (structured road/jibun fields)
            # and keyword endpoint (POI / landmark / business). Both calls
            # fire simultaneously via asyncio.gather; each result populates
            # the bundle slot it semantically owns (address → AddressResult,
            # keyword → POIResult, both → CoordResult). This is NOT a
            # primary/fallback pair — see _kakao_coords for the rationale.
            import asyncio  # noqa: PLC0415

            from ummaya.tools.geocoding.kakao_client import (  # noqa: PLC0415
                KakaoKeywordSearchResult,
                KakaoSearchResult,
                search_address,
                search_keyword,
            )

            async def _addr_call() -> KakaoSearchResult | None:
                try:
                    return await search_address(query, client=client)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("kakao address (all) failed for %r: %s", query, exc)
                    return None

            async def _kw_call() -> KakaoKeywordSearchResult | None:
                try:
                    return await search_keyword(query, client=client)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("kakao keyword (all) failed for %r: %s", query, exc)
                    return None

            kakao_addr, kakao_kw = await asyncio.gather(_addr_call(), _kw_call())

            # Address response → AddressResult + CoordResult.
            if kakao_addr is not None and getattr(kakao_addr, "documents", None):
                addr_doc = kakao_addr.documents[0]
                try:
                    lat = float(addr_doc.y) if addr_doc.y else None
                    lon = float(addr_doc.x) if addr_doc.x else None
                except (ValueError, TypeError):
                    lat = lon = None
                if lat is not None and lon is not None:
                    coords_bundle = _with_kma_grid(
                        CoordResult(
                            kind="coords",
                            lat=lat,
                            lon=lon,
                            confidence=_confidence_from_total(kakao_addr.meta.total_count),
                            source="kakao",
                        )
                    )
                if addr_doc.road_address or addr_doc.address:
                    address_result = AddressResult(
                        kind="address",
                        road_address=(
                            addr_doc.road_address.address_name if addr_doc.road_address else None
                        ),
                        jibun_address=(addr_doc.address.address_name if addr_doc.address else None),
                        postal_code=(
                            addr_doc.road_address.zone_no if addr_doc.road_address else None
                        ),
                        source="kakao",
                    )

            # Keyword response → POIResult; also populates coords_bundle when
            # the address endpoint produced no result (POI-only query like
            # "동아대학교"). Address coordinates always win when both fire
            # because structured-address matches are more specific.
            if kakao_kw is not None and getattr(kakao_kw, "documents", None):
                doc_kw = kakao_kw.documents[0]
                if not _keyword_doc_matches_query(query, doc_kw):
                    logger.info(
                        "kakao keyword (all) rejected unrelated top result for query=%r "
                        "place_name=%r",
                        query,
                        getattr(doc_kw, "place_name", None),
                    )
                    lat_kw = lon_kw = None
                else:
                    try:
                        lat_kw = float(doc_kw.y) if doc_kw.y else None
                        lon_kw = float(doc_kw.x) if doc_kw.x else None
                    except (ValueError, TypeError):
                        lat_kw = lon_kw = None
                if lat_kw is not None and lon_kw is not None:
                    if coords_bundle is None:
                        coords_bundle = _with_kma_grid(
                            CoordResult(
                                kind="coords",
                                lat=lat_kw,
                                lon=lon_kw,
                                confidence=_confidence_from_total(kakao_kw.meta.total_count),
                                source="kakao",
                            )
                        )
                    poi_result = _poi_with_kma_grid(
                        POIResult(
                            kind="poi",
                            name=doc_kw.place_name,
                            category=doc_kw.category_name,
                            lat=lat_kw,
                            lon=lon_kw,
                            source="kakao",
                            address_name=(
                                doc_kw.address_name
                                if isinstance(doc_kw.address_name, str)
                                else None
                            ),
                            road_address_name=(
                                doc_kw.road_address_name
                                if isinstance(doc_kw.road_address_name, str)
                                else None
                            ),
                        )
                    )
        else:
            coords_bundle = await _kakao_coords(query, client=client)
            if coords_bundle is not None:
                coords_bundle = _with_kma_grid(coords_bundle)

        # Resolve adm_cd through authoritative backends in declared order.
        adm_bundle = await _juso_adm_cd(query, client=client)
        if adm_bundle is None:
            adm_bundle = await _kakao_adm_cd(query, client=client)
        if adm_bundle is None and coords_bundle is not None:
            adm_bundle = await _kakao_adm_cd_from_coords(coords_bundle, client=client)
        if adm_bundle is None:
            adm_bundle = await _sgis_adm_cd(query, coords=coords_bundle, client=client)

        if coords_bundle is None and adm_bundle is None:
            return ResolveError(
                kind="error",
                reason="not_found",
                message=f"Could not resolve location for query {query!r}.",
            )

        if want == "all" and coords_bundle is not None:
            try:
                region_result = await _kakao_region_from_coords(
                    lat=coords_bundle.lat,
                    lon=coords_bundle.lon,
                    client=client,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("kakao region (all) failed for %r: %s", query, exc)
                return ResolveError(
                    kind="error",
                    reason="upstream_unavailable",
                    message=f"Kakao coord2regioncode backend unavailable: {exc}",
                )

        return ResolveBundle(
            kind="bundle",
            source="bundle",
            coords=coords_bundle,
            adm_cd=adm_bundle,
            address=address_result if want == "all" else None,
            poi=poi_result if want == "all" else None,
            region=region_result if want == "all" else None,
        )

    # Fallback for unrecognized want values (shouldn't reach here due to Pydantic)
    return ResolveError(
        kind="error",
        reason="invalid_query",
        message=f"Unsupported want={want!r}.",
    )


async def resolve_location_v4(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> ResolveLocationOutput | ResolveError:
    """Resolve a place query to the standardised v4 flat output — Spec 2522 US7 (T039).

    Guarantees all 4 required fields (lat, lon, b_code, address_name) via the
    Kakao Local API. JUSO / SGIS are NOT called — Kakao ``b_code`` field
    (행정동 코드) is populated directly from the Kakao response document.

    Returns:
        ``ResolveLocationOutput`` on success (source always "kakao").
        ``ResolveError`` with reason ``"not_found"`` when Kakao returns 0 results.
        ``ResolveError`` with reason ``"invalid_query"`` for an empty query.

    Evidence:
        /tmp/ummaya-evidence/geocoding-evidence.md — 4 scenarios (서울 강남구,
        부산, 제주특별자치도, 존재하지않는주소), Kakao-only, all fields present.
    """
    query = query.strip()
    if not query:
        return ResolveError(
            kind="error",
            reason="empty_query",
            message="Query must not be empty.",
        )

    logger.debug("resolve_location_v4: query=%r", query)

    try:
        from ummaya.tools.geocoding.kakao_client import search_address  # noqa: PLC0415

        result = await search_address(query, client=client)
    except Exception as exc:
        logger.debug("resolve_location_v4: kakao search failed for %r: %s", query, exc)
        return ResolveError(
            kind="error",
            reason="upstream_unavailable",
            message=f"Kakao geocoding backend unavailable: {exc}",
        )

    if not result.documents:
        return ResolveError(
            kind="error",
            reason="not_found",
            message=f"Could not resolve location for query {query!r}.",
        )

    doc = result.documents[0]

    # Extract lat / lon (Kakao uses x=lon, y=lat as strings)
    try:
        lat = float(doc.y)
        lon = float(doc.x)
    except (ValueError, TypeError):
        return ResolveError(
            kind="error",
            reason="upstream_unavailable",
            message="Kakao returned non-numeric coordinates.",
        )

    # Extract b_code — present in doc.address block; fall back to doc itself
    addr_block = doc.address
    b_code_raw: str | None = None
    if addr_block is not None:
        b_code_raw = getattr(addr_block, "b_code", None)
    if not b_code_raw:
        # Kakao sometimes puts b_code on the document root for REGION-type results
        b_code_raw = getattr(doc, "b_code", None)

    if not b_code_raw or len(b_code_raw) != 10 or not b_code_raw.isdigit():
        return ResolveError(
            kind="error",
            reason="upstream_unavailable",
            message=(
                f"Kakao response missing or invalid b_code for query {query!r}. Got: {b_code_raw!r}"
            ),
        )

    # address_name: prefer doc.address_name (populated for REGION/ROAD types)
    address_name: str = (
        doc.address_name or (addr_block.address_name if addr_block else None) or query
    )
    if not address_name:
        address_name = query

    # Confidence derived from total_count
    total = result.meta.total_count
    if total == 1:
        confidence: str = "high"
    elif total <= 3:
        confidence = "medium"
    else:
        confidence = "low"

    return ResolveLocationOutput(
        lat=lat,
        lon=lon,
        b_code=b_code_raw,
        address_name=address_name,
        confidence=confidence,  # type: ignore[arg-type]
        source="kakao",
    )


locate = resolve_location
