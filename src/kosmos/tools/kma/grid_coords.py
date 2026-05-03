# SPDX-License-Identifier: Apache-2.0
"""KMA (Korea Meteorological Administration) grid coordinate lookup tables and conversions.

Maps Korean region names (Korean or Romanized) to KMA 5 km grid (nx, ny) points
used by the ultra-short-term observation API (getUltraSrtNcst).

Grid system: Lambert Conformal Conic projection, 5 km resolution.
Reference: KMA VilageFcstInfoService_2.0 API technical guide.
"""

from __future__ import annotations

from kosmos.tools.kma.projection import latlon_to_lcc

# REGION_TO_GRID: maps region name strings to (nx, ny) KMA grid tuples.
# Keys include both Korean and common Romanized names for broad matching.
# All values sourced from the official KMA grid coordinate lookup table.
REGION_TO_GRID: dict[str, tuple[int, int]] = {
    # --- Metropolitan cities and provinces (centroids) ---
    "서울": (61, 126),
    "Seoul": (61, 126),
    "서울특별시": (61, 126),
    "부산": (98, 76),
    "Busan": (98, 76),
    "부산광역시": (98, 76),
    "대구": (89, 90),
    "Daegu": (89, 90),
    "대구광역시": (89, 90),
    "인천": (55, 124),
    "Incheon": (55, 124),
    "인천광역시": (55, 124),
    "광주": (58, 74),
    "Gwangju": (58, 74),
    "광주광역시": (58, 74),
    "대전": (67, 100),
    "Daejeon": (67, 100),
    "대전광역시": (67, 100),
    "울산": (102, 84),
    "Ulsan": (102, 84),
    "울산광역시": (102, 84),
    "세종": (66, 103),
    "Sejong": (66, 103),
    "세종특별자치시": (66, 103),
    "경기": (60, 120),
    "Gyeonggi": (60, 120),
    "경기도": (60, 120),
    "강원": (73, 134),
    "Gangwon": (73, 134),
    "강원도": (73, 134),
    "강원특별자치도": (73, 134),
    "충북": (69, 107),
    "Chungbuk": (69, 107),
    "충청북도": (69, 107),
    "충남": (68, 100),
    "Chungnam": (68, 100),
    "충청남도": (68, 100),
    "전북": (63, 89),
    "Jeonbuk": (63, 89),
    "전라북도": (63, 89),
    "전북특별자치도": (63, 89),
    "전남": (51, 67),
    "Jeonnam": (51, 67),
    "전라남도": (51, 67),
    "경북": (89, 106),
    "Gyeongbuk": (89, 106),
    "경상북도": (89, 106),
    "경남": (91, 77),
    "Gyeongnam": (91, 77),
    "경상남도": (91, 77),
    "제주": (52, 38),
    "Jeju": (52, 38),
    "제주특별자치도": (52, 38),
    # --- Major districts in Seoul ---
    "강남": (61, 125),
    "강남구": (61, 125),
    "Gangnam": (61, 125),
    "서초": (61, 124),
    "서초구": (61, 124),
    "Seocho": (61, 124),
    "송파": (62, 124),
    "송파구": (62, 124),
    "마포": (59, 127),
    "마포구": (59, 127),
    "종로": (60, 127),
    "종로구": (60, 127),
    "용산": (60, 126),
    "용산구": (60, 126),
    "노원": (61, 130),
    "노원구": (61, 130),
    # --- Other major cities ---
    "수원": (60, 121),
    "Suwon": (60, 121),
    "성남": (63, 124),
    "Seongnam": (63, 124),
    "고양": (57, 128),
    "Goyang": (57, 128),
    "용인": (64, 119),
    "Yongin": (64, 119),
    "창원": (90, 77),
    "Changwon": (90, 77),
    "전주": (63, 89),
    "Jeonju": (63, 89),
    "청주": (69, 106),
    "Cheongju": (69, 106),
    "춘천": (73, 134),
    "Chuncheon": (73, 134),
    "포항": (102, 94),
    "Pohang": (102, 94),
    "천안": (63, 110),
    "Cheonan": (63, 110),
}


def kma_grid_short_reference() -> str:
    """Return a compact inline table of 17 Korean metropolitan regions → KMA (nx, ny) grids.

    Extracts the 17 canonical 광역시도 centroids from REGION_TO_GRID and formats
    them as a single-line table suitable for embedding in a GovAPITool.llm_description
    section 3 (short_reference).  Token budget: ≤ 200 tokens.

    Returns:
        A string of the form "서울=(61,126) 부산=(98,76) ..."
    """
    # Canonical 17 광역시도 keys (한글 short name order)
    _SIDO_KEYS: list[str] = [
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
    ]
    parts = [f"{k}=({REGION_TO_GRID[k][0]},{REGION_TO_GRID[k][1]})" for k in _SIDO_KEYS]
    return " ".join(parts)


def lookup_grid(region: str) -> tuple[int, int]:
    """Look up the KMA grid (nx, ny) for a named Korean region.

    Attempts an exact match against the REGION_TO_GRID table.
    The lookup is case-sensitive; normalize the input before calling if needed.

    Args:
        region: Korean or Romanized region name (e.g., "서울", "Busan", "강남구").

    Returns:
        A ``(nx, ny)`` tuple of KMA grid coordinates.

    Raises:
        ValueError: If ``region`` does not appear in the lookup table.
    """
    try:
        return REGION_TO_GRID[region]
    except KeyError:
        known = sorted(REGION_TO_GRID.keys())
        raise ValueError(
            f"Unknown region {region!r}. Known regions ({len(known)} total): {known[:10]}..."
        ) from None


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """Convert WGS-84 (latitude, longitude) to KMA 5 km Lambert Conformal Conic grid (nx, ny).

    Uses the official KMA VilageFcstInfoService_2.0 projection parameters:
      - Earth radius Re = 6371.00877 km
      - Grid resolution = 5.0 km
      - Standard latitudes slat1 = 30.0°, slat2 = 60.0°
      - Reference longitude olon = 126.0°, reference latitude olat = 38.0°
      - Grid origin xo = 43, yo = 136 (in grid units from the projection origin)

    Args:
        lat: Latitude in decimal degrees (WGS-84).
        lon: Longitude in decimal degrees (WGS-84).

    Returns:
        A ``(nx, ny)`` tuple of integer KMA grid coordinates.
    """
    return latlon_to_lcc(lat, lon)
