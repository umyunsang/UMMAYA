# SPDX-License-Identifier: Apache-2.0
"""Unit tests for SGIS backend response parsing.

These are mocked schema fixtures, not production fallback data. Production code
uses the live SGIS HTTP response and never returns these static values.
"""

from __future__ import annotations

import httpx
import pytest

from ummaya.tools.geocoding.sgis import lookup_adm_cd_by_coords

SGIS_WGS84_SCHEMA_FIXTURE = {
    "result": [
        {
            "sido_cd": "21",
            "sido_nm": "부산광역시",
            "sgg_cd": "100",
            "sgg_nm": "사하구",
            "emdong_cd": "570",
            "emdong_nm": "하단2동",
            "full_addr": "부산광역시 사하구 하단2동",
        }
    ],
    "errCd": 0,
    "errMsg": "Success",
}


@pytest.mark.asyncio
async def test_lookup_adm_cd_by_coords_parses_wgs84_reverse_geocode_response(
    respx_mock,
) -> None:
    respx_mock.get("https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {"accessToken": "token"},
                "errCd": 0,
                "errMsg": "Success",
            },
        )
    )
    respx_mock.get("https://sgisapi.mods.go.kr/OpenAPI3/addr/rgeocodewgs84.json").mock(
        return_value=httpx.Response(
            200,
            json=SGIS_WGS84_SCHEMA_FIXTURE,
        )
    )

    result = await lookup_adm_cd_by_coords(
        35.1154,
        128.9685,
        consumer_key="key",
        consumer_secret="secret",
    )

    assert result == {
        "adm_cd": "2110057000",
        "name": "부산광역시 사하구 하단2동",
        "level": "eupmyeondong",
        "source": "sgis",
    }


@pytest.mark.asyncio
async def test_lookup_adm_cd_by_coords_retries_transient_sgis_connect_timeout(
    respx_mock,
) -> None:
    auth_route = respx_mock.get("https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json")
    auth_route.side_effect = [
        httpx.ConnectTimeout("transient"),
        httpx.Response(200, json={"result": {"accessToken": "token"}}),
    ]
    respx_mock.get("https://sgisapi.mods.go.kr/OpenAPI3/addr/rgeocodewgs84.json").mock(
        return_value=httpx.Response(200, json=SGIS_WGS84_SCHEMA_FIXTURE)
    )

    result = await lookup_adm_cd_by_coords(
        35.1154,
        128.9685,
        consumer_key="key",
        consumer_secret="secret",
    )

    assert result is not None
    assert result["adm_cd"] == "2110057000"
    assert auth_route.call_count == 2
