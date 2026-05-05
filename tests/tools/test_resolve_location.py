# SPDX-License-Identifier: Apache-2.0
"""Integration tests for resolve_location facade — T019.

Mocks all geocoding backend calls (kakao, juso, sgis).
No live API calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kosmos.tools.models import (
    AddressResult,
    AdmCodeResult,
    CoordResult,
    POIResult,
    ResolveBundle,
    ResolveError,
    ResolveLocationInput,
)
from kosmos.tools.resolve_location import resolve_location

# ---------------------------------------------------------------------------
# Shared mock return values
# ---------------------------------------------------------------------------

_COORD = CoordResult(
    kind="coords",
    lat=37.5665,
    lon=126.9780,
    confidence="high",
    source="kakao",
)
_ADM = AdmCodeResult(
    kind="adm_cd",
    code="1168000000",
    name="강남구",
    level="sigungu",
    source="juso",
)
_ADDRESS = AddressResult(
    kind="address",
    road_address="서울 강남구 테헤란로 152",
    jibun_address=None,
    postal_code=None,
    source="kakao",
)
_POI = POIResult(
    kind="poi",
    name="강남역",
    category="지하철역",
    lat=37.4979,
    lon=127.0276,
    source="kakao",
)


# ---------------------------------------------------------------------------
# want="coords"
# ---------------------------------------------------------------------------


class TestResolveCoords:
    @pytest.mark.asyncio
    async def test_returns_coord_result_on_kakao_success(self):
        inp = ResolveLocationInput(query="서울 강남구", want="coords")
        with patch(
            "kosmos.tools.resolve_location._kakao_coords",
            new=AsyncMock(return_value=_COORD),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, CoordResult)
        assert result.lat == pytest.approx(37.5665)

    @pytest.mark.asyncio
    async def test_returns_error_when_kakao_fails(self):
        inp = ResolveLocationInput(query="존재하지않는장소", want="coords")
        with patch(
            "kosmos.tools.resolve_location._kakao_coords",
            new=AsyncMock(return_value=None),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)
        assert result.reason == "not_found"


# ---------------------------------------------------------------------------
# want="adm_cd"
# ---------------------------------------------------------------------------


class TestResolveAdmCd:
    @pytest.mark.asyncio
    async def test_juso_short_circuits(self):
        inp = ResolveLocationInput(query="서울 강남구", want="adm_cd")
        with (
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=_ADM),
            ),
            patch(
                "kosmos.tools.resolve_location._kakao_coords",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kosmos.tools.resolve_location._sgis_adm_cd",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, AdmCodeResult)
        assert result.code == "1168000000"

    @pytest.mark.asyncio
    async def test_falls_back_to_sgis_when_juso_and_kakao_fail(self):
        # Spec 2522 T047 — chain 재정렬 (juso → kakao_b_code → sgis).
        # SGIS 까지 fallback 도달하려면 _juso_adm_cd + _kakao_adm_cd 모두 None.
        sgis_adm = AdmCodeResult(
            kind="adm_cd", code="1168000000", name="강남구", level="sigungu", source="sgis"
        )
        inp = ResolveLocationInput(query="서울 강남구", want="adm_cd")
        with (
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kosmos.tools.resolve_location._kakao_adm_cd",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kosmos.tools.resolve_location._kakao_coords",
                new=AsyncMock(return_value=_COORD),
            ),
            patch(
                "kosmos.tools.resolve_location._sgis_adm_cd",
                new=AsyncMock(return_value=sgis_adm),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, AdmCodeResult)
        assert result.source == "sgis"

    @pytest.mark.asyncio
    async def test_error_when_all_backends_fail(self):
        inp = ResolveLocationInput(query="알수없는장소", want="adm_cd")
        with (
            patch("kosmos.tools.resolve_location._juso_adm_cd", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._kakao_adm_cd", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._kakao_coords", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._sgis_adm_cd", new=AsyncMock(return_value=None)),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)
        assert result.reason == "not_found"


# ---------------------------------------------------------------------------
# want="road_address"
# ---------------------------------------------------------------------------


class TestResolveAddress:
    @pytest.mark.asyncio
    async def test_kakao_address_success(self):
        inp = ResolveLocationInput(query="서울 강남구 테헤란로 152", want="road_address")
        with (
            patch(
                "kosmos.tools.resolve_location._kakao_geocode",
                new=AsyncMock(return_value=_ADDRESS),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, AddressResult)
        assert result.road_address is not None

    @pytest.mark.asyncio
    async def test_falls_back_to_juso_when_kakao_fails(self):
        # When Kakao fails and JUSO only resolves an administrative area name,
        # the facade must return ResolveError rather than a misleading AddressResult
        # with an admin area name in the road_address field.
        inp = ResolveLocationInput(query="서울 강남구 테헤란로 152", want="road_address")
        juso_adm = AdmCodeResult(
            kind="adm_cd",
            code="1168000000",
            name="서울특별시 강남구 테헤란로 152",
            level="sigungu",
            source="juso",
        )
        with (
            patch(
                "kosmos.tools.resolve_location._kakao_geocode",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=juso_adm),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)
        assert result.reason == "not_found"
        assert "administrative area" in result.message

    @pytest.mark.asyncio
    async def test_error_when_all_fail(self):
        inp = ResolveLocationInput(query="알수없는주소", want="jibun_address")
        with (
            patch("kosmos.tools.resolve_location._kakao_geocode", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._juso_adm_cd", new=AsyncMock(return_value=None)),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)
        assert result.reason == "not_found"


# ---------------------------------------------------------------------------
# want="poi"
# ---------------------------------------------------------------------------


class TestResolvePOI:
    @pytest.mark.asyncio
    async def test_poi_success(self):
        # POI path now uses Kakao keyword endpoint (search_keyword), not the
        # address endpoint. Address endpoint returns empty for POI queries
        # like "강남역" / "동아대학교"; routing want='poi' through it was a
        # structural bug retired in the keyword-fanout fix. Mock the keyword
        # response shape (place_name + category_name + x/y).
        mock_doc = MagicMock()
        mock_doc.y = "37.4979"
        mock_doc.x = "127.0276"
        mock_doc.place_name = "강남역"
        mock_doc.category_name = "교통,수송 > 지하철역"
        mock_doc.address_name = "서울 강남구 역삼동"
        mock_doc.road_address_name = "서울 강남구 강남대로 396"

        mock_result = MagicMock()
        mock_result.documents = [mock_doc]
        mock_result.meta.total_count = 1

        inp = ResolveLocationInput(query="강남역", want="poi")
        with patch(
            "kosmos.tools.geocoding.kakao_client.search_keyword",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, POIResult)
        assert result.name == "강남역"
        assert result.category == "교통,수송 > 지하철역"

    @pytest.mark.asyncio
    async def test_poi_no_documents_returns_error(self):
        inp = ResolveLocationInput(query="알수없는POI", want="poi")
        mock_result = MagicMock()
        mock_result.documents = []
        mock_result.meta.total_count = 0

        with patch(
            "kosmos.tools.geocoding.kakao_client.search_keyword",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)
        assert result.reason == "not_found"


# ---------------------------------------------------------------------------
# want="coords_and_admcd" (default bundle)
# ---------------------------------------------------------------------------


class TestResolveCoordsAndAdmCd:
    @pytest.mark.asyncio
    async def test_full_bundle(self):
        inp = ResolveLocationInput(query="서울 강남구", want="coords_and_admcd")
        with (
            patch(
                "kosmos.tools.resolve_location._kakao_coords",
                new=AsyncMock(return_value=_COORD),
            ),
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=_ADM),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveBundle)
        assert result.coords is not None
        assert result.adm_cd is not None

    @pytest.mark.asyncio
    async def test_partial_bundle_coords_only(self):
        inp = ResolveLocationInput(query="서울 강남구", want="coords_and_admcd")
        with (
            patch(
                "kosmos.tools.resolve_location._kakao_coords",
                new=AsyncMock(return_value=_COORD),
            ),
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kosmos.tools.resolve_location._sgis_adm_cd",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await resolve_location(inp)
        # coords alone is enough to return a bundle
        assert isinstance(result, ResolveBundle)
        assert result.coords is not None
        assert result.adm_cd is None

    @pytest.mark.asyncio
    async def test_error_when_both_fail(self):
        inp = ResolveLocationInput(query="알수없는곳", want="coords_and_admcd")
        with (
            patch("kosmos.tools.resolve_location._kakao_coords", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._juso_adm_cd", new=AsyncMock(return_value=None)),
            patch("kosmos.tools.resolve_location._sgis_adm_cd", new=AsyncMock(return_value=None)),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveError)

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        """FR-T019: empty query must short-circuit before any backend calls."""
        inp = ResolveLocationInput(query="   ", want="coords_and_admcd")
        result = await resolve_location(inp)
        # strip() makes it empty
        assert isinstance(result, ResolveError)
        assert result.reason == "empty_query"


# ---------------------------------------------------------------------------
# want="all"
# ---------------------------------------------------------------------------


class TestResolveAll:
    @pytest.mark.asyncio
    async def test_all_bundle_includes_address_and_poi(self):
        # want="all" now fans out across both Kakao endpoints in parallel
        # (asyncio.gather): search_address populates AddressResult +
        # CoordResult; search_keyword populates POIResult. The address
        # coordinates win when both fire because structured-address matches
        # are more specific. See _kakao_coords for the rationale.
        inp = ResolveLocationInput(query="강남역", want="all")

        # search_address response — must use plain Mocks (not AsyncMock) for
        # nested attribute bags to avoid Pydantic serialising coroutines.
        mock_road_address = MagicMock()
        mock_road_address.address_name = "서울 강남구 테헤란로 152"
        mock_road_address.zone_no = "06236"

        mock_addr_doc = MagicMock()
        mock_addr_doc.y = "37.4979"
        mock_addr_doc.x = "127.0276"
        mock_addr_doc.address_name = "강남역"
        mock_addr_doc.road_address = mock_road_address
        mock_addr_doc.address = None

        mock_addr_result = MagicMock()
        mock_addr_result.documents = [mock_addr_doc]
        mock_addr_result.meta.total_count = 1

        # search_keyword response — POIResult fields (place_name + category_name).
        mock_kw_doc = MagicMock()
        mock_kw_doc.y = "37.4979"
        mock_kw_doc.x = "127.0276"
        mock_kw_doc.place_name = "강남역 2호선"
        mock_kw_doc.category_name = "교통,수송 > 지하철역"
        mock_kw_doc.address_name = "서울 강남구 역삼동"

        mock_kw_result = MagicMock()
        mock_kw_result.documents = [mock_kw_doc]
        mock_kw_result.meta.total_count = 1

        with (
            patch(
                "kosmos.tools.resolve_location._juso_adm_cd",
                new=AsyncMock(return_value=_ADM),
            ),
            patch(
                "kosmos.tools.geocoding.kakao_client.search_address",
                new=AsyncMock(return_value=mock_addr_result),
            ),
            patch(
                "kosmos.tools.geocoding.kakao_client.search_keyword",
                new=AsyncMock(return_value=mock_kw_result),
            ),
        ):
            result = await resolve_location(inp)
        assert isinstance(result, ResolveBundle)
        assert result.coords is not None
        assert result.address is not None
        assert result.address.road_address == "서울 강남구 테헤란로 152"
        assert result.poi is not None
        assert result.poi.name == "강남역 2호선"
        assert result.poi.category == "교통,수송 > 지하철역"
