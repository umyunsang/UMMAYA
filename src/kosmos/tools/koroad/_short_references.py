# SPDX-License-Identifier: Apache-2.0
"""KOROAD siDo 17 광역시도 short reference constant for v4 llm_description section 3.

Source: /tmp/kosmos-domain-docs/koroad.txt § 3.2 siDo
2-digit wire codes for the 17 광역시도 used in KOROAD accident APIs.

Format: "서울=11 부산=12 ..." — compact inline table ≤ 200 tokens.
"""

from __future__ import annotations

# KOROAD_SIDO_SHORT_REFERENCE: 17 광역시도 → KOROAD 2-digit siDo wire code.
#
# Source: koroad.txt § 3.2 siDo (도로교통공단 교통사고분석시스템)
# These are the actual 2-digit codes — NOT the 4-digit 행정구역코드 (e.g. 1100 = wrong).
#
#   11 = 서울특별시
#   12 = 부산광역시
#   22 = 대구광역시
#   23 = 인천광역시
#   24 = 광주광역시
#   25 = 대전광역시
#   26 = 울산광역시
#   27 = 세종특별자치시
#   13 = 경기도
#   14 = 강원특별자치도
#   15 = 충청북도
#   16 = 충청남도
#   17 = 전북특별자치도
#   18 = 전라남도
#   19 = 경상북도
#   20 = 경상남도
#   21 = 제주특별자치도
KOROAD_SIDO_SHORT_REFERENCE: str = (
    "서울=11 부산=12 대구=22 인천=23 광주=24 "
    "대전=25 울산=26 세종=27 경기=13 강원=14 "
    "충북=15 충남=16 전북=17 전남=18 경북=19 경남=20 제주=21"
)


# Spec 2522 — KOROAD GugunCode 250+ 시군구 매핑. 사용자 디렉티브 "코드체계 노출".
# IntEnum name (e.g. SEOUL_GANGNAM=680) 영문 transliteration → K-EXAONE 가
# 시민 한국어 발화 ("강남구") 와 매칭 가능. Pydantic JSON schema 가 IntEnum
# name 을 standard export 안 하므로 description 에 인라인 필요.
def _build_gugun_reference() -> str:
    """GugunCode IntEnum 동적 dump. 새 GugunCode 추가 시 자동 update."""
    from kosmos.tools.koroad.code_tables import GugunCode

    pairs = []
    for member in GugunCode:
        # SEOUL_GANGNAM → "seoul gangnam=680" (lowercase, space-separated)
        readable = member.name.lower().replace("_", " ")
        pairs.append(f"{readable}={member.value}")
    return " / ".join(pairs)


KOROAD_GUGUN_REFERENCE: str = _build_gugun_reference()
