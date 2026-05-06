# SPDX-License-Identifier: Apache-2.0
"""KOROAD accident hazard search adapter — T025.

Wraps the ``getRestFrequentzoneLg`` endpoint from KOROAD.
Input: 10-digit adm_cd + year (integer).
Output: LookupCollection of hazard spots.

Internal codebook maps the first 5 digits of ``adm_cd`` to KOROAD
``siDo`` + ``guGun`` codes, with year-aware 2023 quirks:
  - 강원 42 → 51 (강원특별자치도, 2023+)
  - 전북 45 → 52 (전북특별자치도, 2023+)
  - 부천시 (41192) split into sub-gu codes (191/193/195) for pre-2023 data,
    unified as 192 for 2023+ (FR-018, FR-019).

FR-018: ``input_schema`` registered with adm_cd pattern + year.
FR-019: 2023 code quirks encapsulated here (not in resolve_location).
FR-037: Adapter is an async coroutine.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools._outbound_trace import traced_async_client
from kosmos.tools.errors import ToolExecutionError, _require_env
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool

logger = logging.getLogger(__name__)

_BASE_URL = "https://apis.data.go.kr/B552061/frequentzoneLg/getRestFrequentzoneLg"

# ---------------------------------------------------------------------------
# Input schema (T025 — adm_cd + year)
# ---------------------------------------------------------------------------


class AccidentHazardSearchInput(BaseModel):
    """Input schema for koroad_accident_hazard_search.

    Uses a 10-digit 행정동 code (adm_cd) and a calendar year to look up
    the KOROAD accident hazard spots for that municipality.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    adm_cd: str = Field(
        pattern=r"^[0-9]{10}$",
        description=(
            "10-digit 행정동 administrative code. "
            "Obtain from resolve_location(want='adm_cd'). "
            "Example: '1111000000' for 서울특별시 종로구."
        ),
    )
    year: int = Field(
        ge=2019,
        le=2100,
        description=(
            "Calendar year for the accident dataset. "
            "2023+ uses 강원특별자치도(51)/전북특별자치도(52) codes automatically. "
            "Example: 2024."
        ),
    )


# ---------------------------------------------------------------------------
# Year-code mapping (2023 quirks — FR-019)
# ---------------------------------------------------------------------------

# GANGWON_NEW_CODE_YEAR = 2023 (42 → 51)
_GANGWON_NEW_YEAR = 2023
# JEONBUK_NEW_CODE_YEAR = 2023 (45 → 52)
_JEONBUK_NEW_YEAR = 2023

# Maps first-2-digit sido prefix → (old_sido_code, new_sido_code, cutover_year)
# where new code applies for year >= cutover_year
_SIDO_REMAP: dict[str, tuple[int, int, int]] = {
    "42": (42, 51, _GANGWON_NEW_YEAR),  # 강원
    "51": (51, 51, 0),  # 강원특별자치도 (already new)
    "45": (45, 52, _JEONBUK_NEW_YEAR),  # 전북
    "52": (52, 52, 0),  # 전북특별자치도 (already new)
}

# 5-digit prefix → sido code for all provinces
_PREFIX5_TO_SIDO: dict[str, int] = {
    "11000": 11,  # 서울특별시
    "11110": 11,  # 서울 종로구
    "11140": 11,  # 서울 중구
    "11170": 11,  # 서울 용산구
    "11200": 11,  # 서울 성동구
    "11215": 11,  # 서울 광진구
    "11230": 11,  # 서울 동대문구
    "11260": 11,  # 서울 중랑구
    "11290": 11,  # 서울 성북구
    "11305": 11,  # 서울 강북구
    "11320": 11,  # 서울 도봉구
    "11350": 11,  # 서울 노원구
    "11380": 11,  # 서울 은평구
    "11410": 11,  # 서울 서대문구
    "11440": 11,  # 서울 마포구
    "11470": 11,  # 서울 양천구
    "11500": 11,  # 서울 강서구
    "11530": 11,  # 서울 구로구
    "11545": 11,  # 서울 금천구
    "11560": 11,  # 서울 영등포구
    "11590": 11,  # 서울 동작구
    "11620": 11,  # 서울 관악구
    "11650": 11,  # 서울 서초구
    "11680": 11,  # 서울 강남구
    "11710": 11,  # 서울 송파구
    "11740": 11,  # 서울 강동구
    "26000": 26,  # 부산광역시
    "26110": 26,
    "26140": 26,
    "26170": 26,
    "26200": 26,
    "26230": 26,
    "26260": 26,
    "26290": 26,
    "26320": 26,
    "26350": 26,
    "26380": 26,
    "26410": 26,
    "26440": 26,
    "26470": 26,
    "26500": 26,
    "26530": 26,
    "26710": 26,
    "27000": 27,  # 대구광역시
    "27110": 27,
    "27140": 27,
    "27170": 27,
    "27200": 27,
    "27230": 27,
    "27260": 27,
    "27290": 27,
    "27710": 27,
    "28000": 28,  # 인천광역시
    "28110": 28,
    "28140": 28,
    "28177": 28,
    "28185": 28,
    "28200": 28,
    "28237": 28,
    "28245": 28,
    "28259": 28,
    "28261": 28,
    "28710": 28,
    "28720": 28,
    "29000": 29,  # 광주광역시
    "29110": 29,
    "29140": 29,
    "29155": 29,
    "29170": 29,
    "29200": 29,
    "30000": 30,  # 대전광역시
    "30110": 30,
    "30140": 30,
    "30170": 30,
    "30200": 30,
    "30230": 30,
    "31000": 31,  # 울산광역시
    "31110": 31,
    "31140": 31,
    "31170": 31,
    "31200": 31,
    "31710": 31,
    "36000": 36,  # 세종특별자치시
    "36110": 36,
    "41000": 41,  # 경기도
    "41111": 41,
    "41113": 41,
    "41115": 41,
    "41117": 41,
    "41131": 41,
    "41133": 41,
    "41135": 41,
    "41150": 41,
    "41171": 41,
    "41173": 41,
    # 부천시: historical split 191/193/195 → unified 192 for 2023+
    # adm_cd prefix 41192 covers unified 부천시
    "41191": 41,  # 원미구 (pre-2023)
    "41192": 41,  # 부천시 통합 (2023+)
    "41193": 41,  # 소사구 (pre-2023)
    "41195": 41,  # 오정구 (pre-2023)
    "41210": 41,
    "41220": 41,
    "41250": 41,
    "41271": 41,
    "41273": 41,
    "41281": 41,
    "41285": 41,
    "41287": 41,
    "41290": 41,
    "41390": 41,
    "41461": 41,
    "41463": 41,
    "41465": 41,
    "41480": 41,
    "41500": 41,
    "41550": 41,
    "41570": 41,
    "41590": 41,
    "41610": 41,
    "41630": 41,
    "41670": 41,
    "41680": 41,
    "41820": 41,
    "41830": 41,
    "41840": 41,
    "42000": 42,  # 강원도 (legacy pre-2023)
    "42110": 42,
    "42120": 42,
    "42130": 42,
    "42150": 42,
    "42160": 42,
    "42170": 42,
    "42180": 42,
    "42190": 42,
    "42210": 42,
    "42720": 42,
    "42730": 42,
    "42750": 42,
    "42760": 42,
    "42770": 42,
    "42780": 42,
    "42790": 42,
    "42800": 42,
    "42810": 42,
    "42820": 42,
    "43000": 43,  # 충청북도
    "43110": 43,
    "43130": 43,
    "43140": 43,
    "43150": 43,
    "43720": 43,
    "43730": 43,
    "43740": 43,
    "43745": 43,
    "43750": 43,
    "43760": 43,
    "43770": 43,
    "43780": 43,
    "44000": 44,  # 충청남도
    "44110": 44,
    "44130": 44,
    "44140": 44,
    "44150": 44,
    "44160": 44,
    "44720": 44,
    "44725": 44,
    "44730": 44,
    "44740": 44,
    "44745": 44,
    "44750": 44,
    "44760": 44,
    "44770": 44,
    "44800": 44,
    "45000": 45,  # 전라북도 (legacy pre-2023)
    "45110": 45,
    "45130": 45,
    "45140": 45,
    "45150": 45,
    "45720": 45,
    "45730": 45,
    "45740": 45,
    "45750": 45,
    "45760": 45,
    "45770": 45,
    "45780": 45,
    "45790": 45,
    "45800": 45,
    "46000": 46,  # 전라남도
    "46110": 46,
    "46720": 46,
    "46730": 46,
    "46740": 46,
    "46750": 46,
    "46760": 46,
    "46770": 46,
    "46780": 46,
    "46790": 46,
    "46800": 46,
    "46810": 46,
    "46820": 46,
    "46830": 46,
    "46840": 46,
    "47000": 47,  # 경상북도
    "47110": 47,
    "47115": 47,
    "47130": 47,
    "47140": 47,
    "47150": 47,
    "47720": 47,
    "47725": 47,
    "47730": 47,
    "47740": 47,
    "47745": 47,
    "47750": 47,
    "47755": 47,
    "47760": 47,
    "47770": 47,
    "47780": 47,
    "47790": 47,
    "47800": 47,
    "47810": 47,
    "47820": 47,
    "47830": 47,
    "47840": 47,
    "48000": 48,  # 경상남도
    "48110": 48,
    "48125": 48,
    "48127": 48,
    "48129": 48,
    "48131": 48,
    "48133": 48,
    "48720": 48,
    "48725": 48,
    "48730": 48,
    "48740": 48,
    "48745": 48,
    "48750": 48,
    "48760": 48,
    "48770": 48,
    "48780": 48,
    "48790": 48,
    "48800": 48,
    "48810": 48,
    "48820": 48,
    "48830": 48,
    "50000": 50,  # 제주특별자치도
    "50110": 50,
    "50130": 50,
    "51000": 51,  # 강원특별자치도 (2023+)
    "51110": 51,
    "51120": 51,
    "51130": 51,
    "51140": 51,
    "51150": 51,
    "51155": 51,
    "51160": 51,
    "51170": 51,
    "51180": 51,
    "51720": 51,
    "51730": 51,
    "51750": 51,
    "51760": 51,
    "51770": 51,
    "51780": 51,
    "51790": 51,
    "51800": 51,
    "51810": 51,
    "51820": 51,
    "52000": 52,  # 전북특별자치도 (2023+)
    "52110": 52,
    "52113": 52,
    "52130": 52,
    "52140": 52,
    "52150": 52,
    "52720": 52,
    "52730": 52,
    "52740": 52,
    "52750": 52,
    "52760": 52,
    "52770": 52,
    "52780": 52,
    "52790": 52,
    "52800": 52,
}

# 5-digit prefix → gugun code for each sido
_PREFIX5_TO_GUGUN: dict[str, int] = {
    # Seoul
    "11110": 110,
    "11140": 140,
    "11170": 170,
    "11200": 200,
    "11215": 215,
    "11230": 230,
    "11260": 260,
    "11290": 290,
    "11305": 305,
    "11320": 320,
    "11350": 350,
    "11380": 380,
    "11410": 410,
    "11440": 440,
    "11470": 470,
    "11500": 500,
    "11530": 530,
    "11545": 545,
    "11560": 560,
    "11590": 590,
    "11620": 620,
    "11650": 650,
    "11680": 680,
    "11710": 710,
    "11740": 740,
    # Busan
    "26110": 110,
    "26140": 140,
    "26170": 170,
    "26200": 200,
    "26230": 230,
    "26260": 260,
    "26290": 290,
    "26320": 320,
    "26350": 350,
    "26380": 380,
    "26410": 410,
    "26440": 440,
    "26470": 470,
    "26500": 500,
    "26530": 530,
    "26710": 710,
    # Daegu
    "27110": 110,
    "27140": 140,
    "27170": 170,
    "27200": 200,
    "27230": 230,
    "27260": 260,
    "27290": 290,
    "27710": 710,
    # Incheon
    "28110": 110,
    "28140": 140,
    "28177": 177,
    "28185": 185,
    "28200": 200,
    "28237": 237,
    "28245": 245,
    "28259": 259,
    "28261": 261,
    "28710": 710,
    "28720": 720,
    # Gwangju
    "29110": 110,
    "29140": 140,
    "29155": 155,
    "29170": 170,
    "29200": 200,
    # Daejeon
    "30110": 110,
    "30140": 140,
    "30170": 170,
    "30200": 200,
    "30230": 230,
    # Ulsan
    "31110": 110,
    "31140": 140,
    "31170": 170,
    "31200": 200,
    "31710": 710,
    # Sejong (no gugun)
    "36110": 0,
    # Gyeonggi
    "41111": 111,
    "41113": 113,
    "41115": 115,
    "41117": 117,
    "41131": 131,
    "41133": 133,
    "41135": 135,
    "41150": 150,
    "41171": 171,
    "41173": 173,
    "41191": 191,  # 부천 원미구 pre-2023
    "41192": 192,  # 부천시 통합 2023+ (unified code)
    "41193": 193,  # 부천 소사구 pre-2023
    "41195": 195,  # 부천 오정구 pre-2023
    "41210": 210,
    "41220": 220,
    "41250": 250,
    "41271": 271,
    "41273": 273,
    "41281": 281,
    "41285": 285,
    "41287": 287,
    "41290": 290,
    "41390": 390,
    "41461": 461,
    "41463": 463,
    "41465": 465,
    "41480": 480,
    "41500": 500,
    "41550": 550,
    "41570": 570,
    "41590": 590,
    "41610": 610,
    "41630": 630,
    "41670": 670,
    "41680": 680,
    "41820": 820,
    "41830": 830,
    "41840": 840,
    # Gangwon (legacy 42)
    "42110": 110,
    "42120": 120,
    "42130": 130,
    "42150": 150,
    "42160": 160,
    "42170": 170,
    "42180": 180,
    "42190": 190,
    "42210": 210,
    "42720": 720,
    "42730": 730,
    "42750": 750,
    "42760": 760,
    "42770": 770,
    "42780": 780,
    "42790": 790,
    "42800": 800,
    "42810": 810,
    "42820": 820,
    # Chungbuk 43
    "43110": 110,
    "43130": 130,
    "43140": 140,
    "43150": 150,
    "43720": 720,
    "43730": 730,
    "43740": 740,
    "43745": 745,
    "43750": 750,
    "43760": 760,
    "43770": 770,
    "43780": 780,
    # Chungnam 44
    "44110": 110,
    "44130": 130,
    "44140": 140,
    "44150": 150,
    "44160": 160,
    "44720": 720,
    "44725": 725,
    "44730": 730,
    "44740": 740,
    "44745": 745,
    "44750": 750,
    "44760": 760,
    "44770": 770,
    "44800": 800,
    # Jeonbuk legacy 45
    "45110": 110,
    "45130": 130,
    "45140": 140,
    "45150": 150,
    "45720": 720,
    "45730": 730,
    "45740": 740,
    "45750": 750,
    "45760": 760,
    "45770": 770,
    "45780": 780,
    "45790": 790,
    "45800": 800,
    # Jeonnam 46
    "46110": 110,
    "46720": 720,
    "46730": 730,
    "46740": 740,
    "46750": 750,
    "46760": 760,
    "46770": 770,
    "46780": 780,
    "46790": 790,
    "46800": 800,
    "46810": 810,
    "46820": 820,
    "46830": 830,
    "46840": 840,
    # Gyeongbuk 47
    "47110": 110,
    "47115": 115,
    "47130": 130,
    "47140": 140,
    "47150": 150,
    "47720": 720,
    "47725": 725,
    "47730": 730,
    "47740": 740,
    "47745": 745,
    "47750": 750,
    "47755": 755,
    "47760": 760,
    "47770": 770,
    "47780": 780,
    "47790": 790,
    "47800": 800,
    "47810": 810,
    "47820": 820,
    "47830": 830,
    "47840": 840,
    # Gyeongnam 48
    "48110": 110,
    "48125": 125,
    "48127": 127,
    "48129": 129,
    "48131": 131,
    "48133": 133,
    "48720": 720,
    "48725": 725,
    "48730": 730,
    "48740": 740,
    "48745": 745,
    "48750": 750,
    "48760": 760,
    "48770": 770,
    "48780": 780,
    "48790": 790,
    "48800": 800,
    "48810": 810,
    "48820": 820,
    "48830": 830,
    # Jeju 50
    "50110": 110,
    "50130": 130,
    # Gangwon new 51
    "51110": 110,
    "51120": 120,
    "51130": 130,
    "51140": 140,
    "51150": 150,
    "51155": 155,
    "51160": 160,
    "51170": 170,
    "51180": 180,
    "51720": 720,
    "51730": 730,
    "51750": 750,
    "51760": 760,
    "51770": 770,
    "51780": 780,
    "51790": 790,
    "51800": 800,
    "51810": 810,
    "51820": 820,
    # Jeonbuk new 52
    "52110": 110,
    "52113": 113,
    "52130": 130,
    "52140": 140,
    "52150": 150,
    "52720": 720,
    "52730": 730,
    "52740": 740,
    "52750": 750,
    "52760": 760,
    "52770": 770,
    "52780": 780,
    "52790": 790,
    "52800": 800,
}

# SearchYearCd values indexed by year (general/지자체별 category)
_YEAR_TO_SEARCH_CD: dict[int, str] = {
    2024: "2025119",
    2023: "2024056",
    2022: "2023026",
    2021: "2022046",
    2020: "2022046",  # fallback to oldest available
    2019: "2022046",
}


def _adm_cd_to_sido_gugun(adm_cd: str, year: int) -> tuple[int, int]:
    """Map a 10-digit adm_cd + year to (sido_code, gugun_code).

    Applies year-aware 2023 quirks for 강원/전북 and 부천시 split.

    Args:
        adm_cd: 10-digit administrative code.
        year: Calendar year of the dataset query.

    Returns:
        (sido_code, gugun_code) integers for the KOROAD API.

    Raises:
        ValueError: If adm_cd cannot be mapped to a valid KOROAD code pair.
    """
    prefix5 = adm_cd[:5]

    sido = _PREFIX5_TO_SIDO.get(prefix5)
    if sido is None:
        # Fallback: use first 2 digits as sido
        prefix2 = adm_cd[:2]
        sido = int(prefix2)

    # Apply 2023 code remapping for Gangwon and Jeonbuk
    sido_str = str(sido).zfill(2)
    if sido_str in _SIDO_REMAP:
        old_code, new_code, cutover_year = _SIDO_REMAP[sido_str]
        if year >= cutover_year and cutover_year > 0:
            sido = new_code
        elif year < cutover_year and cutover_year > 0:
            sido = old_code

    gugun = _PREFIX5_TO_GUGUN.get(prefix5)
    if gugun is None:
        # Fallback: use 3rd-4th digits as gugun*10 (rough)
        gugun = int(adm_cd[2:5]) if len(adm_cd) >= 5 else 0

    # 부천시 split quirk: pre-2023 uses 191/193/195, 2023+ uses 192
    if sido == 41 and prefix5 in ("41191", "41193", "41195") and year >= 2023:
        gugun = 192  # unified 부천시 code
    elif sido == 41 and prefix5 == "41192" and year < 2023:
        gugun = 191  # fallback to 원미구 for pre-2023

    return sido, gugun


def _get_search_year_cd(year: int) -> str:
    """Return the best SearchYearCd string for a given calendar year."""
    if year in _YEAR_TO_SEARCH_CD:
        return _YEAR_TO_SEARCH_CD[year]
    if year > 2024:
        return _YEAR_TO_SEARCH_CD[2024]  # use latest available
    return _YEAR_TO_SEARCH_CD[2021]  # oldest available


# ---------------------------------------------------------------------------
# geom_json strip helper (T036)
# ---------------------------------------------------------------------------


def _strip_geom_json(item: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *item* with the ``geom_json`` field removed.

    The KOROAD ``getRestFrequentzoneLg`` response embeds a GeoJSON Polygon
    string (~500 characters per record) in every item.  This field is not
    actionable by the LLM (it can't render or reason over raw Polygon WKT)
    and inflates the context window unnecessarily.

    This helper is applied to every item before building the output dict so
    that only human-readable fields (coordinates, counts, names) reach the LLM.

    Args:
        item: A single raw item dict from the KOROAD wire response.

    Returns:
        A shallow copy of *item* without the ``geom_json`` key.  All other
        fields are preserved unchanged.
    """
    stripped = dict(item)
    stripped.pop("geom_json", None)
    return stripped


# ---------------------------------------------------------------------------
# Async adapter handler
# ---------------------------------------------------------------------------


async def handle(
    inp: AccidentHazardSearchInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Invoke the KOROAD accident hazard endpoint and return a LookupCollection dict.

    FR-037: This is an async coroutine.
    FR-018: Returns LookupCollection with spot_nm, tot_dth_cnt, geom_json.

    Args:
        inp: Validated AccidentHazardSearchInput.
        client: Optional httpx.AsyncClient for test injection.

    Returns:
        A dict suitable for envelope normalization into LookupCollection.

    Raises:
        ConfigurationError: If KOSMOS_DATA_GO_KR_API_KEY is not set.
        RuntimeError: On upstream API errors.
    """
    api_key = _require_env("KOSMOS_DATA_GO_KR_API_KEY")

    try:
        sido, gugun = _adm_cd_to_sido_gugun(inp.adm_cd, inp.year)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Cannot map adm_cd={inp.adm_cd!r} to KOROAD codes: {exc}") from exc

    search_year_cd = _get_search_year_cd(inp.year)

    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "searchYearCd": search_year_cd,
        "siDo": sido,
        "guGun": gugun,
        "numOfRows": 10,
        "pageNo": 1,
        "type": "json",
    }

    logger.debug(
        "koroad_accident_hazard_search: adm_cd=%s year=%d → sido=%d gugun=%d searchYearCd=%s",
        inp.adm_cd,
        inp.year,
        sido,
        gugun,
        search_year_cd,
    )

    own_client = client is None
    _client: httpx.AsyncClient = traced_async_client(timeout=30.0) if own_client else client  # type: ignore[assignment]

    try:
        response = await _client.get(_BASE_URL, params=params)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "xml" in content_type.lower() and "json" not in content_type.lower():
            raise ToolExecutionError(
                "koroad_accident_hazard_search",
                f"KOROAD API returned XML instead of JSON (Content-Type: {content_type!r}).",
            )

        raw: dict[str, Any] = response.json()
    finally:
        if own_client:
            await _client.aclose()

    result_code = str(raw.get("resultCode", ""))
    result_msg = str(raw.get("resultMsg", "Unknown"))

    if result_code == "03":
        # NODATA_ERROR — return empty collection
        return {
            "kind": "collection",
            "items": [],
            "total_count": 0,
        }

    if result_code != "00":
        raise ToolExecutionError(
            "koroad_accident_hazard_search",
            f"KOROAD API error: code={result_code!r} msg={result_msg!r}",
        )

    total_count = int(raw.get("totalCount", 0))
    raw_items = raw.get("items", {})

    item_list: list[dict[str, Any]] = []
    if raw_items and not isinstance(raw_items, str):
        raw_item = raw_items.get("item", [])
        if isinstance(raw_item, dict):
            item_list = [raw_item]
        elif isinstance(raw_item, list):
            item_list = raw_item

    items = [
        {
            "spot_nm": item.get("spot_nm", ""),
            "tot_dth_cnt": item.get("dth_dnv_cnt", 0),
            "spot_cd": item.get("spot_cd", ""),
            "sido_sgg_nm": item.get("sido_sgg_nm", ""),
            "occrrnc_cnt": item.get("occrrnc_cnt", 0),
            "caslt_cnt": item.get("caslt_cnt", 0),
            "la_crd": item.get("la_crd"),
            "lo_crd": item.get("lo_crd"),
        }
        for item in (_strip_geom_json(raw_item) for raw_item in item_list)
    ]

    return {
        "kind": "collection",
        "items": items,
        "total_count": total_count,
    }


# ---------------------------------------------------------------------------
# Tool definition and registration helper (T027)
# ---------------------------------------------------------------------------

# Output schema placeholder — the handler returns LookupCollection-shaped dicts.
# We reuse AccidentHazardSearchInput for input_schema; output_schema is
# declared using a lightweight placeholder model so that GovAPITool is valid.


class _AccidentHazardSearchOutput(RootModel[dict[str, Any]]):
    """Placeholder output schema for GovAPITool registration."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


KOROAD_ACCIDENT_HAZARD_SEARCH_TOOL = GovAPITool(
    id="koroad_accident_hazard_search",
    name_ko="교통사고 위험지점 조회 (행정동 코드)",
    ministry="KOROAD",
    category=["교통안전", "사고통계", "위험지역"],
    endpoint=_BASE_URL,
    auth_type="api_key",
    input_schema=AccidentHazardSearchInput,
    output_schema=_AccidentHazardSearchOutput,
    llm_description=(
        # Section 1 — what this tool does
        "Query the KOROAD accident hazard spot dataset by 10-digit 행정동 administrative code "
        "and calendar year. Returns a ranked list of accident-prone locations (spots) with "
        "coordinates, occurrence counts, and casualty counts for the specified municipality "
        "and year. "
        # Section 2 — mandatory prerequisite
        "ORDERING RULE: call resolve_location(want='adm_cd') FIRST to obtain the 10-digit "
        "adm_cd before invoking this tool — never guess or construct adm_cd from memory. "
        # Section 3 — wire format notes
        "[WIRE FORMAT] Input accepts a 10-digit adm_cd (e.g. '1168000000' for 강남구) and "
        "an integer year. The adapter internally maps year → searchYearCd and adm_cd → "
        "2-digit siDo + 3-digit guGun codes (including 2023+ 강원/전북 quirks). "
        "geom_json fields (~500 char Polygon strings) are stripped from all output items "
        "to reduce context window usage. "
        # Section 4 — when to use this tool vs koroad_accident_search
        "Prefer this tool over koroad_accident_search when the caller already has a "
        "10-digit adm_cd from resolve_location — it accepts the adm_cd directly and "
        "handles all siDo/guGun mapping internally. "
        # Section 5 — trigger examples
        "Use this when a user asks about traffic danger zones, accident hotspots, "
        "어린이 보호구역 사고 다발, 스쿨존 사고 위험 구역, or road safety at a specific "
        "location in Korea."
    ),
    search_hint=(
        "교통사고 위험지점 안전취약지점 사고다발구역 행정동코드 연도별 사고지점 "
        "accident hazard spot dangerous zone adm_cd year traffic safety Korea"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.koroad.or.kr/main/web/policy/data_use.do",
        real_classification_text="도로교통공단 공공데이터 이용약관 — 교통사고 위험지점 데이터 비상업적 공공 이용 허가",  # TODO: verify URL  # noqa: E501
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=3600,
    rate_limit_per_minute=10,
    is_core=False,
    # Spec 031 T032/T033 dual-axis fields — None during pre-v1.2 compatibility window FR-028
    primitive="lookup",
    published_tier_minimum=None,
    nist_aal_hint=None,
    trigger_examples=[
        "어린이 보호구역 사고 다발",
        "스쿨존 사고 위험 구역",
    ],
)


def register(registry: object, executor: object) -> None:
    """Register KOROAD accident hazard search tool and its adapter.

    Args:
        registry: A ToolRegistry instance.
        executor: A ToolExecutor instance.
    """
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)
    assert isinstance(executor, ToolExecutor)

    async def _adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, AccidentHazardSearchInput)
        return await handle(inp)

    registry.register(KOROAD_ACCIDENT_HAZARD_SEARCH_TOOL)
    executor.register_adapter("koroad_accident_hazard_search", _adapter)
    logger.info("Registered tool: koroad_accident_hazard_search")
