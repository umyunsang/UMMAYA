# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_EXPLICIT_TOOL_ID_RE = re.compile(
    r"(?:tool_id|adapter|도구)\s*[:=]\s*`?([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)`?",
    re.IGNORECASE,
)
_ARTIFACT_ID_RE = re.compile(
    r"\b(?:artifact|source|working|derivative|render|viewport)-[A-Za-z0-9_-]+\b"
)
_DOCUMENT_PATH_RE = re.compile(
    r"(?:^|[\s:'\"(])((?:~|/|[A-Za-z]:\\|\.{1,2}/)?[^\s:'\"]*"
    r"\.(?:hwpx|hwp|docx|pdf|xlsx|pptx))\b",
    re.IGNORECASE,
)
_DOCUMENT_FORMAT_RE = re.compile(r"\b(hwpx|hwp|docx|pdf|xlsx|pptx)\b", re.IGNORECASE)
_DOCUMENT_INTENT_RE = re.compile(
    r"(문서|공문서|양식|서식|파일|작성|저장|렌더|미리보기|변경사항|"
    r"\bdiff\b|\bcompact\b|\bdocument\b|\bfile\b|\bform\b|\brender\b|\bsave\b|\bwrite\b)",
    re.IGNORECASE,
)
_DOCUMENT_WRITE_INTENT_RE = re.compile(
    r"(작성|수정|편집|채우|채워|입력|변경|저장|write|edit|fill|apply|save)",
    re.IGNORECASE,
)
_DOCUMENT_LOCAL_HINT_RE = re.compile(
    r"(다운로드|downloads?|폴더|파일|양식|서식|활동일지|신청서|등본|증명서)",
    re.IGNORECASE,
)
_COORDINATE_PAIR_RE = re.compile(
    r"(?P<lat>[+-]?\d{1,2}(?:\.\d+)?)\s*,\s*(?P<lon>[+-]?\d{2,3}(?:\.\d+)?)"
)
_POI_LOCATION_RE = re.compile(
    r"(근처|주변|인근|가까운|역|터미널|공항|캠퍼스|대학교|대학|해수욕장|시장|공원|랜드마크)"
)
_ADMIN_LOCATION_RE = re.compile(
    r"(?:[가-힣]{2,}(?:시|군|구|동|읍|면)\b|[가-힣0-9]{2,}(?<!으)(?:로|길)\b)"
)
_PUBLIC_DATA_OPERATION_RE = re.compile(
    r"\b(getSurfaceChart|getAuxillaryChart|SEA\d{4}|FinancesService|"
    r"StudentService|WthrChartInfoService)\b",
    re.IGNORECASE,
)
_KMA_GIMHAE_AIRPORT_RE = re.compile(r"(김해(?:공항)?|Gimhae|RKPK)", re.IGNORECASE)
_KMA_GIMPO_AIRPORT_RE = re.compile(r"(김포(?:공항)?|Gimpo|RKSS)", re.IGNORECASE)
_KMA_AIRPORT_AVIATION_RE = re.compile(
    r"(AMOS|METAR|SPECI|RVR|항공기상|공항기상|활주로|runway|aviation|"
    r"비행기|항공편|비행편|이륙|착륙|결항|지연|운항|뜰\s*만|뜨나|뜰\s*수|"
    r"flight|take\s*off|landing|delay|cancel)",
    re.IGNORECASE,
)
_KMA_EXPLICIT_METAR_RE = re.compile(r"(\bMETAR\b|\bSPECI\b|해독자료)", re.IGNORECASE)
_KMA_RUNWAY_AREA_RE = re.compile(
    r"(AMOS|활주로|RVR|runway|시정|visibility|공항기상관측|매분)",
    re.IGNORECASE,
)
_KMA_ANALYSIS_CHART_RE = re.compile(
    r"(분석일기도|지상일기도|보조일기도|WthrChartInfoService|getSurfaceChart|"
    r"getAuxillaryChart|synoptic\s+chart)",
    re.IGNORECASE,
)
_KMA_ANALYSIS_DATA_RE = re.compile(
    r"(분석자료|이미\s*분석|고해상도\s*격자|객관분석|AWS\s*객관|지도\s*자료|"
    r"일기도|분석일기도|비구름|바람\s*흐름|날씨\s*흐름|공식\s*기상자료|전국\s*날씨|"
    r"synoptic|weather\s*chart|objective\s*analysis|high[-\s]?resolution|grid)",
    re.IGNORECASE,
)
_KMA_ANALYSIS_MAP_RE = re.compile(
    r"(일기도|분석일기도|지도\s*자료|비구름|바람\s*흐름|날씨\s*흐름|전국\s*날씨|"
    r"synoptic|weather\s*chart)",
    re.IGNORECASE,
)
_KMA_ANALYSIS_POINT_RE = re.compile(
    r"(주변|근처|특정지점|좌표|위도|경도|\blat\b|\blon\b|공항\s*주변)",
    re.IGNORECASE,
)
_KMA_LIFESTYLE_WEATHER_RE = re.compile(
    r"(날씨|현재\s*기상|실황|관측|예보|기온|습도|풍속|지금\s*비|"
    r"비\s*(?:와|오|올|내리)|우산|강수|소나기|산책|퇴근|"
    r"current\s+weather|forecast|rain|umbrella|precipitation|temperature)",
    re.IGNORECASE,
)
_EMERGENCY_RE = re.compile(r"(응급|응급실|응급의료|\bemergency\b|\ber\b)", re.IGNORECASE)
_IMPLICIT_EMERGENCY_RE = re.compile(
    r"(사람이\s*(?:쓰러|쓰러졌|쓰러져)|의식(?:을)?\s*(?:잃|없)|"
    r"갑자기\s*쓰러|쓰러진\s*사람|위급|심정지|호흡(?:이)?\s*없|"
    r"collapsed|unconscious|cardiac\s*arrest)",
    re.IGNORECASE,
)
_AED_RE = re.compile(r"(\bAED\b|자동심장충격기|자동제세동기|제세동기)", re.IGNORECASE)
_TRAFFIC_HAZARD_RE = re.compile(
    r"(교통사고|사고\s*위험|사고다발|위험\s*(?:구간|도로|지점)|어린이보호구역|보호구역|"
    r"도로\s*구간|accident|hazard|hotspot)",
    re.IGNORECASE,
)
_TRAFFIC_HAZARD_SPECIFIC_RE = re.compile(
    r"(사고\s*위험|위험\s*(?:구간|도로|지점)|어린이보호구역|보호구역|스쿨존|"
    r"도로\s*구간|행정동코드|adm_cd|hazard|hotspot)",
    re.IGNORECASE,
)
_MOF_OCEAN_WATER_QUALITY_RE = re.compile(
    r"(해양\s*수질|해양수질|수질\s*자동\s*측정|용존산소|\bpH\b|"
    r"water\s+quality|ocean\s+water)",
    re.IGNORECASE,
)
_PPS_BID_RE = re.compile(r"(입찰|나라장터|조달청|\bbid\b|procurement|tender)", re.IGNORECASE)
_PPS_SHOPPING_RE = re.compile(
    r"(종합\s*쇼핑몰|쇼핑몰|공공\s*조달\s*물품|조달\s*물품|계약\s*물품|"
    r"물품\s*(?:검색|조회)|물품\s*관련|shopping\s*mall|product\s*(?:lookup|search))",
    re.IGNORECASE,
)
_AIRKOREA_AIR_QUALITY_RE = re.compile(
    r"(미세먼지|초미세먼지|초미세|대기질|대기오염|공기질|마스크|"
    r"pm\s*2\.?5|pm\s*10|air\s*korea|airkorea|air\s*quality|airquality)",
    re.IGNORECASE,
)
_DJTC_SUBWAY_SEGMENT_RE = re.compile(
    r"((대전|DJTC|대전교통공사|도시철도|지하철).*(역간|소요시간|거리|운임|요금)|"
    r"(역간|소요시간|거리|운임|요금).*(대전|DJTC|대전교통공사|도시철도|지하철))",
    re.IGNORECASE,
)
_INTERCITY_PUBLIC_TRANSPORT_RE = re.compile(
    r"(?!.*(?:교통사고|사고\s*위험|사고다발|위험\s*(?:구간|도로|지점)|도로교통공단|KOROAD|accident|hazard))"
    r"(?=.*(?:대중\s*교통|교통편|교통\s*수단|고속\s*버스|시외\s*버스|버스|열차|기차|KTX|SRT|철도|지하철))"
    r"(?:서울|인천|대전|대구|광주|부산|울산|세종|수원|성남|고양|용인|청주|천안|전주|"
    r"포항|창원|김해|진주|여수|순천|목포|강릉|춘천|원주|제주|서귀포)"
    r"[^\n]{0,24}(?:에서|부터)[^\n]{0,80}"
    r"(?:서울|인천|대전|대구|광주|부산|울산|세종|수원|성남|고양|용인|청주|천안|전주|"
    r"포항|창원|김해|진주|여수|순천|목포|강릉|춘천|원주|제주|서귀포)"
    r"[^\n]{0,24}(?:까지|로|으로|도착|이동|가는)",
    re.IGNORECASE,
)
_KCUE_REGIONAL_RE = re.compile(
    r"(대학알리미|대학정보공시|학교구분코드|schl[_\s-]?div[_\s-]?cd|KCUE|"
    r"지역별\s*(등록금|재정)|외국인\s*유학생|foreign\s+student|international\s+student)",
    re.IGNORECASE,
)
_KCUE_REGIONAL_FINANCE_RE = re.compile(
    r"(지역별\s*(등록금|재정)|등록금\s*(현황|지역별)?|tuition|finance)",
    re.IGNORECASE,
)
_KCUE_REGIONAL_FOREIGN_STUDENT_RE = re.compile(
    r"(외국인\s*유학생|유학생\s*현황|foreign\s+student|international\s+student)",
    re.IGNORECASE,
)
_HIRA_MEDICAL_DETAIL_RE = re.compile(
    r"((병원|의료기관|의원).*(상세|진료과|진료과목|진료시간|주차)|"
    r"(상세|진료시간|주차|응급실).*(병원|의료기관|의원)|ykiho|detail)",
    re.IGNORECASE,
)
_HIRA_HOSPITAL_SEARCH_RE = re.compile(
    r"((병원|의료기관|의원|내과|소아과|이비인후과|피부과|정형외과|가정의학과|진료과)."
    r"*(근처|주변|인근|가까운|전화|주소|찾|검색|조회)|"
    r"(근처|주변|인근|가까운|전화|주소|찾|검색|조회).*"
    r"(병원|의료기관|의원|내과|소아과|이비인후과|피부과|정형외과|가정의학과|진료과)|"
    r"hospital\s+search|clinic\s+search|medical\s+institution)",
    re.IGNORECASE,
)
_MOIS_EMERGENCY_CALL_BOX_RE = re.compile(
    r"(안전\s*비상벨|비상벨|긴급\s*신고함|긴급신고함|방범벨|"
    r"emergency\s+call\s+box)",
    re.IGNORECASE,
)
_GYERYONG_ASSISTIVE_CHARGER_RE = re.compile(
    r"((전동보장구|전동\s*휠체어|보장구|장애인).*(충전|충전소|충전장소)|"
    r"(충전|충전소|충전장소).*(전동보장구|전동\s*휠체어|보장구|장애인)|"
    r"계룡시?.*(충전소|충전\s*장소))",
    re.IGNORECASE,
)
_CREDENTIAL_RE = re.compile(
    r"(간편인증|본인인증|모바일\s*신분증|공동인증서|금융인증서|인증서|"
    r"delegation|consent|verify|login|로그인|동의)",
    re.IGNORECASE,
)
_SIDE_EFFECT_RE = re.compile(
    r"(신청|제출|신고|송신|납부|결제|발급|저장|수정|편집|채우|"
    r"submit|send|pay|issue|save|write|edit|fill|apply)",
    re.IGNORECASE,
)
_SUBMIT_SIDE_EFFECT_RE = re.compile(r"(신청|제출|신고|submit|send|apply)", re.IGNORECASE)
_PAYMENT_SIDE_EFFECT_RE = re.compile(r"(납부|결제|pay)", re.IGNORECASE)
