# SPDX-License-Identifier: Apache-2.0
"""Tests for locate primitive adapter routing semantics."""

from __future__ import annotations

import pytest

from ummaya.tools.geocoding.kakao_client import (
    KakaoAddressDocument,
    KakaoAddressResult,
    KakaoSearchMeta,
    KakaoSearchResult,
)
from ummaya.tools.location_adapters import (
    KakaoCoordToRegionInput,
    KakaoKeywordSearchInput,
    SgisAdmCdLookupInput,
    _kakao_keyword_search,
    canonical_admin_area_query,
    should_route_keyword_query_to_address,
)
from ummaya.tools.models import ResolveBundle


def test_admin_area_keyword_query_is_detected() -> None:
    assert should_route_keyword_query_to_address("부산 사하구 다대1동")
    assert should_route_keyword_query_to_address("사하구 하단동에서")
    assert should_route_keyword_query_to_address("부산 사하구")
    assert not should_route_keyword_query_to_address("다대포해수욕장")
    assert not should_route_keyword_query_to_address("동아대학교 승학캠퍼스")


def test_canonical_admin_area_query_strips_location_suffix() -> None:
    assert canonical_admin_area_query("부산 사하구 다대1동에서") == "부산 사하구 다대1동"
    assert canonical_admin_area_query("사하구 하단동 근처") == "사하구 하단동"


def test_reverse_geocode_inputs_reject_rounded_coordinate_pairs() -> None:
    with pytest.raises(ValueError, match="do not round"):
        KakaoCoordToRegionInput(lat=35, lon=129)

    with pytest.raises(ValueError, match="do not round"):
        SgisAdmCdLookupInput(lat=35, lon=129)


@pytest.mark.asyncio
async def test_kakao_keyword_admin_area_query_uses_address_search(monkeypatch) -> None:
    async def _fake_search_address(query: str) -> KakaoSearchResult:
        assert query == "부산 사하구 다대1동"
        return KakaoSearchResult(
            meta=KakaoSearchMeta(total_count=1, pageable_count=1, is_end=True),
            documents=[
                KakaoAddressDocument(
                    address_name="부산 사하구 다대1동",
                    x="128.971316010861",
                    y="35.0591517638253",
                    address=KakaoAddressResult(
                        address_name="부산 사하구 다대1동",
                        region_1depth_name="부산",
                        region_2depth_name="사하구",
                        region_3depth_name="다대1동",
                    ),
                    road_address=None,
                )
            ],
        )

    monkeypatch.setattr("ummaya.tools.geocoding.kakao_client.search_address", _fake_search_address)

    result = await _kakao_keyword_search(KakaoKeywordSearchInput(query="부산 사하구 다대1동에서"))

    assert isinstance(result, ResolveBundle)
    assert result.coords is not None
    assert result.coords.lat == 35.0591517638253
    assert result.coords.lon == 128.971316010861
