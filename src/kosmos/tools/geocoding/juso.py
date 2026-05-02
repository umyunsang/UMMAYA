# SPDX-License-Identifier: Apache-2.0
"""JUSO.go.kr backend helper for administrative code (adm_cd) lookup.

This module is a *backend-only* helper consumed by ``resolve_location``.
It is NOT exposed as an LLM-visible tool (FR-003).

The adm-code lookup logic was previously inlined in
``kosmos.tools.resolve_location._juso_adm_cd``.  It is moved here in
spec/022-mvp-main-tool US4 (T050) to keep the geocoding package cohesive
and to allow direct unit-testing of the backend method.
"""

from __future__ import annotations

import logging

import httpx

from kosmos.tools._outbound_trace import traced_async_client

logger = logging.getLogger(__name__)

_JUSO_API_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"


async def lookup_adm_cd(
    query: str,
    *,
    confm_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict[str, str] | None:
    """Resolve a free-text Korean address to a 10-digit adm_cd via juso.go.kr.

    Backend method — not exposed as an LLM tool.

    Args:
        query: Free-text Korean address string (e.g. "서울특별시 강남구").
        confm_key: JUSO API confirm key (``KOSMOS_JUSO_CONFM_KEY``).
        client: Optional injected ``httpx.AsyncClient`` for testing.

    Returns:
        Dict with keys ``adm_cd``, ``name``, ``level``, ``source="juso"``
        on success.  Returns ``None`` on no-result, network error, or
        API error — callers should fall through to the next resolver.
    """
    params = {
        "confmKey": confm_key,
        "currentPage": "1",
        "countPerPage": "1",
        "keyword": query,
        "resultType": "json",
    }

    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client(timeout=10.0) if own_client else client  # type: ignore[assignment]

    try:
        resp = await _client.get(_JUSO_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", {})
        juso_list = results.get("juso", [])

        if not juso_list:
            logger.debug("juso: no results for query=%r", query)
            return None

        item = juso_list[0]
        adm_cd = item.get("admCd", "")
        if not adm_cd or len(adm_cd) != 10:
            logger.debug("juso: admCd missing or wrong length: %r", adm_cd)
            return None

        road_addr = item.get("roadAddr", "")
        sgg_nm = (item.get("siNm", "") + " " + item.get("sggNm", "")).strip()
        name = sgg_nm or road_addr

        # Determine granularity level from adm_cd trailing zeros
        if adm_cd.endswith("00000000"):
            level = "sido"
        elif adm_cd.endswith("0000"):
            level = "sigungu"
        else:
            level = "eupmyeondong"

        return {
            "adm_cd": adm_cd,
            "name": name,
            "level": level,
            "source": "juso",
        }

    except Exception as exc:
        logger.warning(
            "juso.lookup_adm_cd failed (query_len=%d): %s",
            len(query),
            type(exc).__name__,
            exc_info=True,
        )
        return None

    finally:
        if own_client:
            await _client.aclose()
