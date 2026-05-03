# SPDX-License-Identifier: Apache-2.0
"""NFA 119 시도소방재난본부 17개 short reference constant for v4 llm_description section 3.

Source: /tmp/kosmos-domain-docs/nfa_station.csv — unique 시도본부 values.
One entry per 광역시도 (full official Korean names used as wire values).

Format: inline list ≤ 200 tokens — suitable for embedding in llm_description section 3.

Note: The 1145-row station detail table (individual 소방서/안전센터) is NOT inlined here
— LLM context budget does not support full station enumeration.  The 시도본부 names
are sufficient for citizen queries like "강남소방서 구급통계" (LLM resolves 강남 → 서울특별시).
"""

from __future__ import annotations

# NFA_HQ_SHORT_REFERENCE: 17 시도소방재난본부 official Korean names.
#
# Source: /tmp/kosmos-domain-docs/nfa_station.csv unique 시도본부 column values.
# These are the exact wire strings expected by the NFA 119 API `sidoHqOgidNm` param.
#
# Canonical list (17개):
#   서울특별시소방재난본부
#   부산광역시소방재난본부
#   대구광역시소방재난본부
#   인천광역시소방재난본부
#   광주광역시소방재난본부
#   대전광역시소방재난본부
#   울산광역시소방재난본부
#   세종특별자치시소방본부
#   경기도소방재난본부
#   강원특별자치도소방본부
#   충청북도소방본부
#   충청남도소방본부
#   전북특별자치도소방본부
#   전라남도소방본부
#   경상북도소방본부
#   경상남도소방본부
#   제주특별자치도소방안전본부
NFA_HQ_SHORT_REFERENCE: str = (
    "서울특별시소방재난본부 / 부산광역시소방재난본부 / 대구광역시소방재난본부 / "
    "인천광역시소방재난본부 / 광주광역시소방재난본부 / 대전광역시소방재난본부 / "
    "울산광역시소방재난본부 / 세종특별자치시소방본부 / 경기도소방재난본부 / "
    "강원특별자치도소방본부 / 충청북도소방본부 / 충청남도소방본부 / "
    "전북특별자치도소방본부 / 전라남도소방본부 / 경상북도소방본부 / "
    "경상남도소방본부 / 제주특별자치도소방안전본부"
)
