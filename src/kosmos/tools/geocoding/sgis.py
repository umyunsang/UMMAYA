# SPDX-License-Identifier: Apache-2.0
"""SGIS (통계청 공간정보서비스) backend helper for administrative code lookup.

This module is a *backend-only* helper consumed by ``resolve_location``.
It is NOT exposed as an LLM-visible tool (FR-003).

SGIS provides coordinate-to-region (역지오코딩) via its rgeocode endpoint,
which maps (lon, lat) to an 8-digit 행정동 code that we pad to 10 digits.

The adm-code lookup logic was previously inlined in
``kosmos.tools.resolve_location._sgis_adm_cd``.  It is moved here in
spec/022-mvp-main-tool US4 (T050) to keep the geocoding package cohesive
and to allow direct unit-testing of the backend method.
"""

from __future__ import annotations

import logging

import httpx

from kosmos.tools._outbound_trace import traced_async_client

logger = logging.getLogger(__name__)

_SGIS_AUTH_URL = "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json"
_SGIS_RGEOCODE_URL = "https://sgisapi.kostat.go.kr/OpenAPI3/addr/rgeocode.json"


async def lookup_adm_cd_by_coords(
    lat: float,
    lon: float,
    *,
    consumer_key: str,
    consumer_secret: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str] | None:
    """Resolve (lat, lon) to a 10-digit adm_cd via SGIS coord-to-region API.

    Backend method — not exposed as an LLM tool.

    Two-step process:
      1. Obtain short-lived SGIS access token.
      2. Call rgeocode with (lon, lat) to get 행정동 code.

    Args:
        lat: WGS-84 latitude.
        lon: WGS-84 longitude.
        consumer_key: SGIS API consumer key (``KOSMOS_SGIS_KEY``).
        consumer_secret: SGIS API consumer secret (``KOSMOS_SGIS_SECRET``).
        client: Optional injected ``httpx.AsyncClient`` for testing.

    Returns:
        Dict with keys ``adm_cd``, ``name``, ``level``, ``source="sgis"``
        on success.  Returns ``None`` on any error — callers should fall
        through to the next resolver.
    """
    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client(timeout=10.0) if own_client else client  # type: ignore[assignment]

    try:
        # Step 1: Obtain access token
        token_resp = await _client.get(
            _SGIS_AUTH_URL,
            params={
                "consumer_key": consumer_key,
                "consumer_secret": consumer_secret,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token: str = token_data.get("result", {}).get("accessToken", "")
        if not access_token:
            logger.debug("sgis: authentication returned empty accessToken")
            return None

        # Step 2: Coordinate to region lookup
        coord_resp = await _client.get(
            _SGIS_RGEOCODE_URL,
            params={
                "accessToken": access_token,
                "x_coor": str(lon),
                "y_coor": str(lat),
                "addr_type": "20",  # 행정동
            },
        )
        coord_resp.raise_for_status()
        coord_data = coord_resp.json()

        result_list = coord_data.get("result", [])
        if not result_list:
            logger.debug("sgis: rgeocode returned empty result for lat=%s lon=%s", lat, lon)
            return None

        item = result_list[0]
        adm_cd_raw = str(item.get("adm_cd", ""))
        if not adm_cd_raw or len(adm_cd_raw) < 8:
            logger.debug("sgis: adm_cd missing or too short: %r", adm_cd_raw)
            return None

        # SGIS returns 8-digit code; pad to 10 digits
        adm_cd = adm_cd_raw.ljust(10, "0")[:10]
        adm_nm = str(item.get("adm_nm", ""))

        if adm_cd.endswith("00000000"):
            level = "sido"
        elif adm_cd.endswith("0000"):
            level = "sigungu"
        else:
            level = "eupmyeondong"

        return {
            "adm_cd": adm_cd,
            "name": adm_nm,
            "level": level,
            "source": "sgis",
        }

    except Exception as exc:
        logger.warning(
            "sgis.lookup_adm_cd_by_coords failed (coords_provided=True): %s",
            type(exc).__name__,
            exc_info=True,
        )
        return None

    finally:
        if own_client:
            await _client.aclose()
