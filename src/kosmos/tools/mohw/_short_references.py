# SPDX-License-Identifier: Apache-2.0
"""MOHW 생애주기(life_array) 7-enum short reference constant for v4 llm_description section 3.

Source: /tmp/kosmos-domain-docs/mohw_codes.txt § 코드표 (생애주기)
7 life-stage enum codes for the MOHW welfare eligibility search API (lifeArray wire param).

Format: "001=영유아 / 002=아동 ..." — compact inline table ≤ 80 tokens.
"""

from __future__ import annotations

# MOHW_LIFE_STAGE_SHORT_REFERENCE: 7 life-stage enum → MOHW wire code.
#
# Source: mohw_codes.txt § 코드표 (생애주기)
# Wire param name: lifeArray (camelCase; LLM input field name: life_array → snake_case)
#
#   001 = 영유아   (infants and toddlers, 0-6세)
#   002 = 아동     (children, 7-12세)
#   003 = 청소년   (youth, 13-18세)
#   004 = 청년     (young adults, 19-34세)
#   005 = 중장년   (middle-aged, 35-64세)
#   006 = 노년     (elderly, 65세+)
#   007 = 임신·출산 (pregnancy and childbirth)
MOHW_LIFE_STAGE_SHORT_REFERENCE: str = (
    "001=영유아 / 002=아동 / 003=청소년 / 004=청년 / 005=중장년 / 006=노년 / 007=임신·출산"
)
