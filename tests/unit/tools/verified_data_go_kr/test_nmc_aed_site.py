# SPDX-License-Identifier: Apache-2.0
"""NMC AED adapter post-processing tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ummaya.tools.verified_data_go_kr.nmc_aed_site import NmcAedSiteInput, handle

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "docs/api/data-go-kr-candidate-docs/15000652/probes/live-2026-05-16-direct-check"
    / "nmc-aed-manage.body"
)


@pytest.mark.asyncio
async def test_nmc_aed_site_sorts_by_origin_distance_when_available() -> None:
    """AED records carry WGS-84 coords, so a place-origin query should sort by distance."""

    result = await handle(
        NmcAedSiteInput(
            q0="서울특별시",
            q1="종로구",
            page_no=1,
            num_of_rows=5,
            origin_lat=37.5769780711,
            origin_lon=126.9768154242,
        ),
        fixture_body=FIXTURE.read_bytes(),
    )

    first_record = result["items"][0]["record"]
    assert first_record["org"] == "경복궁관리소"
    assert first_record["buildPlace"] == "흥례문"
    assert first_record["distance_km"] == 0.0
    assert first_record["distance_unit"] == "km"
