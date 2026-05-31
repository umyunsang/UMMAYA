# SPDX-License-Identifier: Apache-2.0
"""Manifest for direct-curl verified public-data adapters."""

from __future__ import annotations

from datetime import UTC, datetime

from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec

_LAST_VERIFIED = datetime(2026, 5, 16, tzinfo=UTC)
_LAST_VERIFIED_2026_05_28 = datetime(2026, 5, 28, tzinfo=UTC)
_DATA_GO_KR_KEY = "UMMAYA_DATA_GO_KR_API_KEY"


def _data_go_policy(dataset_id: str) -> str:
    return f"https://www.data.go.kr/data/{dataset_id}/openapi.do"


VERIFIED_DATA_GO_KR_ADAPTERS: tuple[VerifiedAdapterSpec, ...] = (
    VerifiedAdapterSpec(
        dataset_id="15043459",
        tool_id="fsc_corporate_finance_summary",
        module_name="fsc_corporate_finance",
        name_ko="금융위원회 기업 재무요약 조회",
        ministry="FSC",
        category=["finance", "corporate", "public-data"],
        endpoint="https://apis.data.go.kr/1160100/service/GetFinaStatInfoService_V2/getSummFinaStat_V2",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
            "crno": "crno",
            "biz_year": "bizYear",
        },
        static_query_params={"resultType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15043459/probes/live-2026-05-16/corporate-finance-summary.body.json",
        policy_url=_data_go_policy("15043459"),
        policy_text="공공데이터포털 인증키 기반 금융위원회 기업 재무정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15043459 기업 재무정보 금융위원회 corporate finance crno bizYear find",
        llm_description=(
            "법인등록번호(crno)와 사업연도(biz_year)로 "
            "금융위원회 기업 재무요약 공개 데이터를 조회한다."
        ),
        trigger_examples=["이 법인의 2019년 재무요약 조회해줘"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15073861",
        tool_id="airkorea_ctprvn_air_quality",
        module_name="airkorea_air_quality",
        name_ko="에어코리아 시도별 실시간 대기질 조회",
        ministry="KECO",
        category=["environment", "air-quality", "public-data"],
        endpoint="https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "sido_name": "sidoName",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
            "ver": "ver",
        },
        static_query_params={"returnType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json",
        policy_url=_data_go_policy("15073861"),
        policy_text="공공데이터포털 인증키 기반 한국환경공단 에어코리아 대기오염정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15073861 AirKorea 에어코리아 대기오염 시도별 대기질 미세먼지 "
            "sidoName 서울 부산 경기 find"
        ),
        llm_description=(
            "짧은 시도명(sido_name: 서울, 부산, 경기 등)으로 에어코리아 시도별 "
            "실시간 측정소 대기질 공개 데이터를 조회한다. 부산광역시처럼 긴 행정명은 "
            "AirKorea 계약상 부산으로 줄여 호출한다."
        ),
        trigger_examples=["서울 대기질 측정소 데이터 조회해줘"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15091886",
        tool_id="ftc_large_group_status",
        module_name="ftc_large_group",
        name_ko="공정거래위원회 대규모기업집단 조회",
        ministry="FTC",
        category=["corporate", "fair-trade", "public-data"],
        endpoint="https://apis.data.go.kr/1130000/appnGroupSttusList/appnGroupSttusListApi",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "presentn_year": "presentnYear",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        record_tag="appnGroupSttus",
        evidence_path="docs/api/data-go-kr-candidate-docs/15091886/probes/live-2026-05-16/ftc-large-group.body.xml",
        policy_url=_data_go_policy("15091886"),
        policy_text="공공데이터포털 인증키 기반 공정거래위원회 대규모기업집단 현황 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15091886 공정위 대규모기업집단 상호출자제한집단 FTC large group find",
        llm_description="공개년월(presentn_year) 기준 공정위 지정 대규모기업집단 현황을 조회한다.",
        trigger_examples=["2021년 5월 대규모기업집단 목록 조회해줘"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15091910",
        tool_id="ftc_public_ym_list",
        module_name="ftc_public_ym",
        name_ko="공정거래위원회 사용 가능 공개년월 조회",
        ministry="FTC",
        category=["corporate", "fair-trade", "public-data"],
        endpoint="https://apis.data.go.kr/1130000/publicYmList/publicYmListApi",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "job_se_code": "jobSeCode",
            "presentn_year": "presentnYear",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        record_tag="publicYm",
        evidence_path="docs/api/data-go-kr-candidate-docs/15091910/probes/live-2026-05-16/ftc-public-ym.body.xml",
        policy_url=_data_go_policy("15091910"),
        policy_text="공공데이터포털 인증키 기반 공정거래위원회 공개년월 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15091910 공정위 공개년월 사용가능 공개년월 FTC public ym find",
        llm_description=(
            "업무구분코드(job_se_code)와 연도(presentn_year)로 사용 가능한 공개년월을 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15098529",
        tool_id="tago_bus_route_search",
        module_name="tago_bus_route",
        name_ko="국토교통부 TAGO 버스노선 조회",
        ministry="MOLIT",
        category=["transport", "bus", "public-data"],
        endpoint="https://apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteNoList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "city_code": "cityCode",
            "route_no": "routeNo",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15098529/probes/live-2026-05-16/tago-bus-route.body.xml",
        policy_url=_data_go_policy("15098529"),
        policy_text="공공데이터포털 인증키 기반 국토교통부 TAGO 버스노선정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15098529 TAGO 버스노선 cityCode routeNo bus route find",
        llm_description=(
            "Search official TAGO bus route data by city_code and citizen-visible "
            "route_no. Use this before tago_bus_location_search when route_id is "
            "unknown."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15098530",
        tool_id="tago_bus_arrival_search",
        module_name="tago_bus_arrival",
        name_ko="국토교통부 TAGO 버스도착 조회",
        ministry="MOLIT",
        category=["transport", "bus", "public-data"],
        endpoint="https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "city_code": "cityCode",
            "node_id": "nodeId",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml",
        policy_url=_data_go_policy("15098530"),
        policy_text="공공데이터포털 인증키 기반 국토교통부 TAGO 버스도착정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15098530 TAGO 버스도착 정류소 nodeId routeno routeid arrival bus find",
        llm_description=(
            "Search official TAGO bus-arrival predictions by city_code and node_id. "
            "If the citizen gives a stop name such as 부산역 instead of node_id, call "
            "tago_bus_station_search first and reuse its nodeid. If the citizen names "
            "a route such as 1001, pass route_no as an optional client-side filter "
            "against the returned TAGO routeno field; use route_id from "
            "tago_bus_route_search when the route number is ambiguous."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15098529",
        tool_id="tago_bus_route_station_search",
        module_name="tago_bus_route_station",
        name_ko="국토교통부 TAGO 노선별 경유정류소 조회",
        ministry="MOLIT",
        category=["transport", "bus", "public-data"],
        endpoint="https://apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteAcctoThrghSttnList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "city_code": "cityCode",
            "route_id": "routeId",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15098529/probes/live-2026-05-28/tago-bus-route-station.body.xml",
        policy_url=_data_go_policy("15098529"),
        policy_text="공공데이터포털 인증키 기반 국토교통부 TAGO 버스노선정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED_2026_05_28,
        search_hint=("15098529 TAGO 노선별 경유정류소 routeId nodenm nodeid nodeord bus stop find"),
        llm_description=(
            "Search the official TAGO route-station list by city_code and route_id. "
            "For a citizen query that combines a route number and place, call "
            "tago_bus_route_search to get route_id, then call this tool with node_nm "
            "as a client-side filter against returned nodenm values. Use the matching "
            "nodeid with tago_bus_arrival_search and include route_no or route_id."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15098533",
        tool_id="tago_bus_location_search",
        module_name="tago_bus_location",
        name_ko="국토교통부 TAGO 버스위치 조회",
        ministry="MOLIT",
        category=["transport", "bus", "public-data"],
        endpoint="https://apis.data.go.kr/1613000/BusLcInfoInqireService/getRouteAcctoBusLcList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "city_code": "cityCode",
            "route_id": "routeId",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15098533/probes/live-2026-05-16/tago-bus-location.body.xml",
        policy_url=_data_go_policy("15098533"),
        policy_text="공공데이터포털 인증키 기반 국토교통부 TAGO 버스위치정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15098533 TAGO 버스위치 routeId bus location find",
        llm_description=(
            "Search official TAGO bus-location data by city_code and route_id. "
            "Use tago_bus_route_search first when the citizen gives only a route number."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15098534",
        tool_id="tago_bus_station_search",
        module_name="tago_bus_station",
        name_ko="국토교통부 TAGO 버스정류소 조회",
        ministry="MOLIT",
        category=["transport", "bus", "public-data"],
        endpoint="https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getSttnNoList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "city_code": "cityCode",
            "node_nm": "nodeNm",
            "node_no": "nodeNo",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15098534/probes/live-2026-05-16/tago-bus-station.body.xml",
        policy_url=_data_go_policy("15098534"),
        policy_text="공공데이터포털 인증키 기반 국토교통부 TAGO 버스정류소정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15098534 TAGO 버스정류소 nodeNm nodeNo station find",
        llm_description=(
            "Search official TAGO bus-stop data by city_code, stop-name fragment "
            "(node_nm), or stop number (node_no). For bus-arrival questions with a "
            "named place or stop, call this before tago_bus_arrival_search to obtain nodeid."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15101360",
        tool_id="kepco_contract_power_usage",
        module_name="kepco_power_usage",
        name_ko="한국전력 계약종별 전력사용량 조회",
        ministry="KEPCO",
        category=["energy", "utility", "public-data"],
        endpoint="https://bigdata.kepco.co.kr/openapi/v1/powerUsage/contractType.do",
        env_var="UMMAYA_KEPCO_POWER_DATA_API_KEY",
        auth_query_param="apiKey",
        response_format="json",
        query_param_map={
            "year": "year",
            "month": "month",
            "metro_cd": "metroCd",
            "city_cd": "cityCd",
            "cntr_cd": "cntrCd",
        },
        static_query_params={"returnType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15101360/probes/live-2026-05-16/kepco-contract-type.body.json",
        policy_url="https://bigdata.kepco.co.kr/cmsmain.do?scode=S01&pcode=000493&pstate=cntr&redirect=Y",
        policy_text="한국전력 전력데이터 개방포털 인증키 기반 계약종별 전력사용량 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15101360 KEPCO 한전 계약종별 전력사용량 power usage cntrCd find",
        llm_description=(
            "연월과 지역/계약종별 코드로 한국전력 계약종별 전력사용량 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15129394",
        tool_id="pps_bid_public_info",
        module_name="pps_bid_public_info",
        name_ko="조달청 나라장터 입찰공고 조회",
        ministry="PPS",
        category=["procurement", "bid", "public-data"],
        endpoint="https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkPPSSrch",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
            "inqry_div": "inqryDiv",
            "inqry_bgn_dt": "inqryBgnDt",
            "inqry_end_dt": "inqryEndDt",
            "bid_ntce_nm": "bidNtceNm",
            "ntce_instt_nm": "ntceInsttNm",
            "dminstt_nm": "dminsttNm",
            "prtcpt_lmt_rgn_nm": "prtcptLmtRgnNm",
            "indstryty_nm": "indstrytyNm",
        },
        static_query_params={"type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15129394/probes/live-2026-05-27/pps-bid-construction-search.body.json",
        policy_url=_data_go_policy("15129394"),
        policy_text="공공데이터포털 인증키 기반 조달청 나라장터 입찰공고정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15129394 조달청 나라장터 입찰공고 검색조건 공사조회 전기공사 부산시 "
            "공고게시일시 개찰일시 inqryBgnDt inqryEndDt bidNtceNm ntceInsttNm "
            "dminsttNm prtcptLmtRgnNm cnstrtsiteRgnNm region_name indstrytyNm "
            "bid public procurement construction find"
        ),
        llm_description=(
            "Wraps official PPS operation getBidPblancListInfoCnstwkPPSSrch, "
            "the construction-bid search-condition endpoint. Use it for ordinary "
            "citizen list searches such as '이번 주 부산시 전기공사 입찰'. "
            "Fill inqry_bgn_dt and inqry_end_dt as YYYYMMDDHHMM. Use inqry_div='1' "
            "for posted-this-week questions and '2' for bid-opening-date questions. "
            "Keep each upstream call within a 31-day-or-smaller date window; split "
            "broader citizen ranges across multiple calls instead of sending one "
            "over-broad request. "
            "Use bid_ntce_nm for notice keywords such as 전기공사, prtcpt_lmt_rgn_nm "
            "for official participation-limit region restrictions such as 부산광역시, "
            "region_name for UMMAYA client-side filtering against documented PPS "
            "response fields such as cnstrtsiteRgnNm/ntceInsttNm/dminsttNm, and "
            "indstryty_nm for license/industry names such as 전기공사업. Do not "
            "invent notice-number detail inputs for list-search questions; this "
            "adapter no longer exposes the bid-notice-number detail path."
        ),
        trigger_examples=["이번 주 부산시 전기공사 입찰 올라온 거 있어?"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15134761",
        tool_id="reb_real_estate_stat_table",
        module_name="reb_real_estate_stats",
        name_ko="한국부동산원 부동산 통계표 조회",
        ministry="REB",
        category=["real-estate", "statistics", "public-data"],
        endpoint="https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do",
        env_var="UMMAYA_REB_REAL_ESTATE_STATS_API_KEY",
        auth_query_param="KEY",
        response_format="json",
        query_param_map={"statbl_id": "STATBL_ID", "p_index": "pIndex", "p_size": "pSize"},
        static_query_params={"Type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15134761/probes/live-2026-05-16/reb-stat-table.body.json",
        policy_url="https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do",
        policy_text="한국부동산원 R-ONE OpenAPI 인증키 기반 부동산통계 조회 서비스.",
        last_verified=_LAST_VERIFIED,
        search_hint="15134761 한국부동산원 REB R-ONE 부동산통계 통계표 find",
        llm_description=(
            "한국부동산원 R-ONE 부동산 통계표 목록을 조회한다. 통계표 ID(statbl_id)는 선택 필터다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15157485",
        tool_id="bfc_funeral_area_fee",
        module_name="bfc_funeral_cost",
        name_ko="부산시설공단 장례식장 시설사용료 조회",
        ministry="BFC",
        category=["funeral", "fee", "public-data"],
        endpoint="https://apis.data.go.kr/B552587/FuneralCostsService_v2/getFCAreaList_v2",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={"page_no": "pageNo", "num_of_rows": "numOfRows"},
        static_query_params={"resultType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15157485/probes/live-2026-05-16/funeral-area-list.body.json",
        policy_url=_data_go_policy("15157485"),
        policy_text="공공데이터포털 인증키 기반 부산시설공단 장례비산출 정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15157485 부산시설공단 장례비 장례식장 시설사용료 funeral fee find",
        llm_description="부산시설공단 장례비산출 서비스의 시설사용료 목록을 조회한다.",
        trigger_examples=["부산 장례식장 시설사용료 조회해줘"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15158680",
        tool_id="kcue_finance_regional_tuition",
        module_name="kcue_finance_status",
        name_ko="대학알리미 지역별 등록금 현황 조회",
        ministry="KCUE",
        category=["education", "university", "public-data"],
        endpoint="https://apis.data.go.kr/B340014/FinancesService/getRegionalTuitionCrntSt",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "schl_div_cd": "schlDivCd",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml",
        policy_url=_data_go_policy("15158680"),
        policy_text=(
            "공공데이터포털 인증키 기반 한국대학교육협의회 대학알리미 재정 현황 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint="15158680 대학알리미 재정 등록금 지역별 KCUE tuition finance find",
        llm_description=(
            "학교구분코드(schl_div_cd)로 대학알리미 지역별 등록금 현황 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15158684",
        tool_id="kcue_student_regional_foreign",
        module_name="kcue_student_status",
        name_ko="대학알리미 지역별 외국인 유학생 현황 조회",
        ministry="KCUE",
        category=["education", "university", "public-data"],
        endpoint="https://apis.data.go.kr/B340014/StudentService/getRegionalForeignStudentCrntSt",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "schl_div_cd": "schlDivCd",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15158684/probes/live-2026-05-16/student-regional-foreign.body.xml",
        policy_url=_data_go_policy("15158684"),
        policy_text=(
            "공공데이터포털 인증키 기반 한국대학교육협의회 대학정보공시 학생 현황 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint="15158684 대학알리미 학생 외국인 유학생 지역별 KCUE student foreign find",
        llm_description=(
            "학교구분코드(schl_div_cd)로 "
            "대학알리미 지역별 외국인 유학생 현황 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15121954",
        tool_id="moj_village_lawyer_lookup",
        module_name="moj_village_lawyer",
        name_ko="법무부 마을변호사 지역별 현황 조회",
        ministry="MOJ",
        category=["legal-aid", "justice", "public-data"],
        endpoint="http://apis.data.go.kr/1270000/mojmabyun/mabyun",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={"page_no": "pageNo", "num_of_rows": "numOfRows"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15121954/probes/live-2026-05-16-direct-check/moj-village-lawyer-http.body",
        policy_url=_data_go_policy("15121954"),
        policy_text="공공데이터포털 인증키 기반 법무부 마을변호사 지역별 현황 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15121954 법무부 마을변호사 지역별 무료 법률상담 lawyer legal aid find",
        llm_description="마을변호사와 지역 담당 공무원 배정 현황 공개 데이터를 조회한다.",
        trigger_examples=["우리 동네 마을변호사 찾아줘"],
    ),
    VerifiedAdapterSpec(
        dataset_id="15073554",
        tool_id="mois_facility_safety_info_lookup",
        module_name="mois_facility_safety",
        name_ko="행정안전부 안전정보 통합공개 시설 조회",
        ministry="MOIS",
        category=["safety", "facility", "public-data"],
        endpoint="https://apis.data.go.kr/1741000/FcltsSafetyInfoService2025/getFcltsInfoSearch_4",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "fclts_nm": "fclts_nm",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"resultType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15073554/probes/live-2026-05-16-direct-check/mois-facility-safety-search.body",
        policy_url=_data_go_policy("15073554"),
        policy_text="공공데이터포털 인증키 기반 행정안전부 안전정보 통합공개 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15073554 행안부 안전정보 시설 안전점검 호텔 시설물 safety facility find",
        llm_description=(
            "시설명(fclts_nm)으로 행정안전부 안전정보 통합공개 시설 기본정보를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15001699",
        tool_id="hira_medical_institution_detail",
        module_name="hira_medical_institution",
        name_ko="건강보험심사평가원 의료기관 상세정보 조회",
        ministry="HIRA",
        category=["health", "hospital", "public-data"],
        endpoint="https://apis.data.go.kr/B551182/MadmDtlInfoService2.7/getDtlInfo2.7",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={"ykiho": "ykiho", "page_no": "pageNo", "num_of_rows": "numOfRows"},
        static_query_params={"_type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15001699/probes/live-2026-05-16-direct-check/hira-medical-detail.body",
        policy_url=_data_go_policy("15001699"),
        policy_text=(
            "공공데이터포털 인증키 기반 건강보험심사평가원 의료기관별 상세정보 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15001699 HIRA 의료기관 상세정보 병원 상세 진료과 진료과목 응급실 "
            "주차 진료시간 ykiho hospital detail specialty find"
        ),
        llm_description=(
            "암호화 요양기호(ykiho)로 의료기관 세부정보와 "
            "응급실/주차/진료시간/진료과목 공개 데이터를 조회한다. "
            "일반 병원명·지역 검색에는 hira_hospital_search를 먼저 쓰고, "
            "상세정보나 진료과목 확인에는 이 어댑터를 이어서 쓴다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15155046",
        tool_id="mois_emergency_call_box_lookup",
        module_name="mois_emergency_call_box",
        name_ko="행정안전부 안전비상벨 위치정보 조회",
        ministry="MOIS",
        category=["safety", "location", "public-data"],
        endpoint="https://apis.data.go.kr/1741000/emergency_call_box_info/info",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "road_address": "cond[LCTN_ROAD_NM_ADDR::LIKE]",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"returnType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15155046/probes/live-2026-05-16-direct-check/emergency-call-box.body",
        policy_url=_data_go_policy("15155046"),
        policy_text="공공데이터포털 인증키 기반 행정안전부 안전비상벨 위치정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15155046 행안부 안전비상벨 비상벨 긴급신고함 위치 경찰연계 "
            "방범 emergency call box safety bell find"
        ),
        llm_description=(
            "도로명주소 조각으로 안전비상벨·비상벨·긴급신고함 설치 위치와 "
            "관리기관 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15158794",
        tool_id="djtc_subway_segment_fare_time_check",
        module_name="djtc_subway_segment",
        name_ko="대전교통공사 역간 소요시간 거리 요금 조회",
        ministry="DJTC",
        category=["transport", "subway", "public-data"],
        endpoint="https://apis.data.go.kr/B554695/TimeDistSVC/getTimeDist01",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={"strstnno": "strstnno", "endstnno": "endstnno"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15158794/probes/live-2026-05-16-direct-check/djtc-time-distance.body",
        policy_url=_data_go_policy("15158794"),
        policy_text="공공데이터포털 인증키 기반 대전교통공사 역간 소요시간 거리 요금 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15158794 대전교통공사 지하철 역간 소요시간 거리 요금 subway fare time find",
        llm_description=(
            "대전 도시철도 출발역/도착역 번호로 거리, 요금, 소요시간 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15096040",
        tool_id="gyeryong_assistive_device_charging_place_locate",
        module_name="gyeryong_assistive_charger",
        name_ko="계룡시 장애인 전동보장구 충전 장소 조회",
        ministry="GYERYONG",
        category=["accessibility", "welfare", "public-data"],
        endpoint="https://apis.data.go.kr/5580000/dspsnElectrAsstnDeviceElctcPlaceService/getdspsnElectrAsstnDeviceElctcPlace",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "current_page": "currentPage",
            "per_page": "perPage",
            "indoor_outdoor": "INDOOR_OTDR",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15096040/probes/live-2026-05-16-direct-check/gyeryong-charger.body",
        policy_url=_data_go_policy("15096040"),
        policy_text="공공데이터포털 인증키 기반 계룡시 장애인 전동보장구 충전 장소 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15096040 계룡시 전동휠체어 전동보장구 보장구 충전소 충전 장소 "
            "장애인 실내 accessibility charger find"
        ),
        llm_description=(
            "계룡시 장애인 전동보장구·전동휠체어 충전소/충전 장소, "
            "위치, 이용 가능 시간 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15000652",
        tool_id="nmc_aed_site_locate",
        module_name="nmc_aed_site",
        name_ko="국립중앙의료원 전국 AED 정보 조회",
        ministry="NMC",
        category=["health", "emergency", "public-data"],
        endpoint="https://apis.data.go.kr/B552657/AEDInfoInqireService/getEgytAedManageInfoInqire",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "q0": "Q0",
            "q1": "Q1",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15000652/probes/live-2026-05-16-direct-check/nmc-aed-manage.body",
        policy_url=_data_go_policy("15000652"),
        policy_text=(
            "공공데이터포털 인증키 기반 국립중앙의료원 전국 자동심장충격기 정보 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15000652 국립중앙의료원 AED 자동심장충격기 자동제세동기 "
            "응급실 주변 시도 시군구 q0 q1 find"
        ),
        llm_description=(
            "시도(q0)와 시군구(q1)로 전국 AED 설치 위치와 이용 가능 시간 공개 데이터를 "
            "조회한다. 시민이 '응급실이나 AED', '응급실/AED', '자동심장충격기'를 같이 "
            "묻는 경우 nmc_emergency_search 결과만으로 AED를 답하지 말고, 이 find "
            "어댑터를 별도 호출한다. q0/q1은 좌표가 아니라 공식 지역 필터다. "
            "origin_lat/origin_lon은 업스트림 파라미터가 아니라 응답 WGS84 좌표를 "
            "거리순으로 정렬하기 위한 선택 필드다. 예: "
            "부산역 근처는 locate 후 부산광역시/동구 또는 중구 지역 필터로 본 도구를 "
            "추가 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15127779",
        tool_id="mof_ocean_water_quality_check",
        module_name="mof_ocean_water_quality",
        name_ko="해양수산부 실시간 해양수질 측정자료 조회",
        ministry="MOF",
        category=["environment", "marine", "public-data"],
        endpoint="https://apis.data.go.kr/1192000/OceansWemoObvpRtmInfoService/OceansWemoObvpRtmInfo",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "station_code": "rtm_wq_wtch_sta_cd",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"_type": "xml"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15127779/probes/live-2026-05-16-direct-check/ocean-water-quality.body",
        policy_url=_data_go_policy("15127779"),
        policy_text=(
            "공공데이터포털 인증키 기반 해양수산부 실시간 해양수질자동측정망 측정자료 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint="15127779 해양수산부 해양수질 pH 용존산소 관측소 SEA3003 water quality find",
        llm_description=(
            "관측소 코드(station_code)로 해양수질 자동측정망 측정자료 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15075057",
        tool_id="mfds_easy_drug_info_lookup",
        module_name="mfds_easy_drug_info",
        name_ko="식품의약품안전처 의약품개요정보 조회",
        ministry="MFDS",
        category=["health", "drug", "public-data"],
        endpoint="http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="ServiceKey",
        response_format="json",
        query_param_map={
            "item_name": "itemName",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15075057/probes/live-2026-05-16-direct-check/mfds-easy-drug.body",
        policy_url=_data_go_policy("15075057"),
        policy_text=(
            "공공데이터포털 인증키 기반 식품의약품안전처 의약품개요정보(e약은요) 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint="15075057 식약처 e약은요 의약품 효능 복용법 주의사항 타이레놀 drug find",
        llm_description=(
            "의약품명(item_name)으로 식약처 e약은요 효능, 복용법, 주의사항 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15156780",
        tool_id="mpm_public_job_lookup",
        module_name="mpm_public_job",
        name_ko="인사혁신처 공공취업정보 조회",
        ministry="MPM",
        category=["labor", "public-job", "public-data"],
        endpoint="https://apis.data.go.kr/1760000/PblJobService/getList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "pblanc_ty": "Pblanc_ty",
            "instt_se": "Instt_se",
            "sort_order": "Sort_order",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15156780/probes/live-2026-05-16-direct-check/mpm-public-job-g01.body",
        policy_url=_data_go_policy("15156780"),
        policy_text="공공데이터포털 인증키 기반 인사혁신처 공공취업정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15156780 인사혁신처 공공취업 국가공무원 채용 공고 public job find",
        llm_description=(
            "공고유형, 기관구분, 정렬방향으로 공공취업 공고 목록 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15129471",
        tool_id="pps_shopping_mall_product_lookup",
        module_name="pps_shopping_mall_product",
        name_ko="조달청 종합쇼핑몰 품목정보 조회",
        ministry="PPS",
        category=["procurement", "catalog", "public-data"],
        endpoint="https://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getShoppingMallPrdctInfoList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "inqry_div": "inqryDiv",
            "prdct_clsfc_no_nm": "prdctClsfcNoNm",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15129471/probes/live-2026-05-16-direct-check/pps-shopping-product.body",
        policy_url=_data_go_policy("15129471"),
        policy_text="공공데이터포털 인증키 기반 조달청 종합쇼핑몰 품목정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint=(
            "15129471 조달청 나라장터 종합쇼핑몰 품목 의자 공급업체 procurement product find"
        ),
        llm_description=(
            "조회구분과 품명/분류명으로 나라장터 종합쇼핑몰 품목 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15158905",
        tool_id="ksd_financial_term_lookup",
        module_name="ksd_financial_term",
        name_ko="한국예탁결제원 금융용어 조회",
        ministry="KSD",
        category=["finance", "terminology", "public-data"],
        endpoint="https://apis.data.go.kr/B552481/FnTermSvc/getFinancialTermMeaning",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={"term": "term", "page_no": "pageNo", "num_of_rows": "numOfRows"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15158905/probes/live-2026-05-16-direct-check/ksd-financial-term.body",
        policy_url=_data_go_policy("15158905"),
        policy_text="공공데이터포털 인증키 기반 한국예탁결제원 금융용어조회서비스 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15158905 한국예탁결제원 금융용어 증권 주식 용어사전 KSD term find",
        llm_description="금융용어(term)로 한국예탁결제원 금융용어사전 공개 데이터를 조회한다.",
    ),
    VerifiedAdapterSpec(
        dataset_id="15157820",
        tool_id="mss_sme_support_notice_lookup",
        module_name="mss_sme_support_notice",
        name_ko="중소벤처기업부 중소기업 지원사업 공고 조회",
        ministry="MSS",
        category=["sme", "support", "public-data"],
        endpoint="https://apis.data.go.kr/1421000/bizinfo/pblancBsnsService",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "hashtags": "hashtags",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"dataType": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15157820/probes/live-2026-05-16-direct-check/sme-support-announcement.body",
        policy_url=_data_go_policy("15157820"),
        policy_text=(
            "공공데이터포털 인증키 기반 중소벤처기업부 중소기업 지원사업 공고 조회 OpenAPI."
        ),
        last_verified=_LAST_VERIFIED,
        search_hint="15157820 중소벤처기업부 중소기업 지원사업 공고 소상공인 창업 MSS find",
        llm_description=(
            "해시태그(hashtags)로 중소기업과 소상공인 지원사업 공고 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15140950",
        tool_id="ccourt_publication_documents",
        module_name="ccourt_publication_documents",
        name_ko="헌법재판소 발간자료 조회",
        ministry="CCOURT",
        category=["law", "publication", "public-data"],
        endpoint="https://apis.data.go.kr/9750000/PubDocsService/getSerialPublicationList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={"title": "title", "page_no": "pageNo", "num_of_rows": "numOfRows"},
        static_query_params={"type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15140950/probes/live-2026-05-16-direct-check/ccourt-publication.body",
        policy_url=_data_go_policy("15140950"),
        policy_text="공공데이터포털 인증키 기반 헌법재판소 발간자료 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15140950 헌법재판소 발간자료 헌법 판례집 논총 publication find",
        llm_description=(
            "제목(title)으로 헌법재판소 주요 연속간행물 발간자료 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15149906",
        tool_id="moj_stay_person_counter",
        module_name="moj_stay_person_counter",
        name_ko="법무부 체류외국인 현황 조회",
        ministry="MOJ",
        category=["immigration", "statistics", "public-data"],
        endpoint="http://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="ServiceKey",
        response_format="xml",
        query_param_map={
            "search_ym": "searchYm",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15149906/probes/live-2026-05-16-blocker-resolution/moj-gateway-ServiceKey.body",
        policy_url=_data_go_policy("15149906"),
        policy_text="공공데이터포털 인증키 기반 법무부 체류외국인 현황 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15149906 법무부 체류외국인 장단기 체류 통계 immigration stay person find",
        llm_description=(
            "검색연월(search_ym)로 법무부 체류외국인 구분별 집계 공개 데이터를 조회한다."
        ),
    ),
    VerifiedAdapterSpec(
        dataset_id="15074634",
        tool_id="msit_business_announcement_lookup",
        module_name="msit_business_announcement",
        name_ko="과학기술정보통신부 사업공고 조회",
        ministry="MSIT",
        category=["science", "notice", "public-data"],
        endpoint="http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="xml",
        query_param_map={
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
            "return_type": "returnType",
        },
        request_headers={
            "User-Agent": "Mozilla/5.0 UMMAYA-live-probe/2026-05-16",
            "Accept": "application/xml,text/xml,*/*",
        },
        evidence_path="docs/api/data-go-kr-candidate-docs/15074634/probes/live-2026-05-16-blocker-resolution/msit-rawkey-ua-only.body",
        policy_url=_data_go_policy("15074634"),
        policy_text="공공데이터포털 인증키 기반 과학기술정보통신부 사업공고 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15074634 과기정통부 사업공고 연구기획 AI허브 첨부파일 MSIT announcement find",
        llm_description=(
            "과학기술정보통신부 사업공고 제목, 상세 URL, 담당부서, 첨부파일 공개 데이터를 조회한다."
        ),
    ),
)

_BY_TOOL_ID = {spec.tool_id: spec for spec in VERIFIED_DATA_GO_KR_ADAPTERS}


def require_spec(tool_id: str) -> VerifiedAdapterSpec:
    """Return the manifest entry for *tool_id*."""

    return _BY_TOOL_ID[tool_id]
