# SPDX-License-Identifier: Apache-2.0
"""KMA station-based short reference constants for v4 llm_description section 3.

Source: /tmp/kosmos-domain-docs/kma_asos.txt § 첨부 지점 코드
One representative ASOS station per 17 광역시도 (the most central / well-known station).

Format: "서울=108 부산=159 ..." — compact inline table ≤ 200 tokens.
"""

from __future__ import annotations

# KMA_STATION_SHORT_REFERENCE: 17 광역시도 representative ASOS station codes.
#
# Mapping rationale (one station per 시도):
#   108 = 서울 (Seoul Gwanaksan)         서울특별시
#   159 = 부산 (Busan)                   부산광역시
#   143 = 대구 (Daegu)                   대구광역시
#   112 = 인천 (Incheon)                 인천광역시
#   156 = 광주 (Gwangju)                 광주광역시
#   133 = 대전 (Daejeon)                 대전광역시
#   152 = 울산 (Ulsan)                   울산광역시
#   239 = 세종 (Sejong)                  세종특별자치시
#   119 = 수원 (Suwon — 경기 대표)        경기도
#   105 = 강릉 (Gangneung — 강원 대표)    강원특별자치도
#   131 = 청주 (Cheongju — 충북 대표)     충청북도
#   232 = 천안 (Cheonan — 충남 대표)      충청남도
#   146 = 전주 (Jeonju — 전북 대표)       전북특별자치도
#   165 = 목포 (Mokpo — 전남 대표)        전라남도
#   138 = 포항 (Pohang — 경북 대표)       경상북도
#   155 = 창원 (Changwon — 경남 대표)     경상남도
#   184 = 제주 (Jeju)                    제주특별자치도
KMA_STATION_SHORT_REFERENCE: str = (
    "서울=108 부산=159 대구=143 인천=112 광주=156 "
    "대전=133 울산=152 세종=239 경기(수원)=119 강원(강릉)=105 "
    "충북(청주)=131 충남(천안)=232 전북(전주)=146 전남(목포)=165 "
    "경북(포항)=138 경남(창원)=155 제주=184"
)
