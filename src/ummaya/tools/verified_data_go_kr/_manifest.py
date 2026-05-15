# SPDX-License-Identifier: Apache-2.0
"""Manifest for direct-curl verified public-data adapters."""

from __future__ import annotations

from datetime import UTC, datetime

from ummaya.tools.verified_data_go_kr._models import VerifiedAdapterSpec

_LAST_VERIFIED = datetime(2026, 5, 16, tzinfo=UTC)
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
        search_hint="15073861 AirKorea 에어코리아 대기오염 시도별 대기질 미세먼지 find",
        llm_description=(
            "시도명(sido_name)으로 에어코리아 시도별 실시간 측정소 대기질 공개 데이터를 조회한다."
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
            "도시코드(city_code)와 노선번호(route_no)로 TAGO 버스노선 공개 데이터를 조회한다."
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
        search_hint="15098530 TAGO 버스도착 정류소 nodeId arrival bus find",
        llm_description=(
            "도시코드(city_code)와 정류소 ID(node_id)로 TAGO 버스도착 예정 정보를 조회한다."
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
        llm_description="도시코드(city_code)와 노선 ID(route_id)로 TAGO 버스 위치 정보를 조회한다.",
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
            "도시코드(city_code), 정류소명(node_nm), "
            "정류소번호(node_no)로 TAGO 정류소 정보를 조회한다."
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
        endpoint="https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc",
        env_var=_DATA_GO_KR_KEY,
        auth_query_param="serviceKey",
        response_format="json",
        query_param_map={
            "inqry_div": "inqryDiv",
            "bid_ntce_no": "bidNtceNo",
            "page_no": "pageNo",
            "num_of_rows": "numOfRows",
        },
        static_query_params={"type": "json"},
        evidence_path="docs/api/data-go-kr-candidate-docs/15129394/probes/live-2026-05-16/pps-bid-service.body.json",
        policy_url=_data_go_policy("15129394"),
        policy_text="공공데이터포털 인증키 기반 조달청 나라장터 입찰공고정보 조회 OpenAPI.",
        last_verified=_LAST_VERIFIED,
        search_hint="15129394 조달청 나라장터 입찰공고 bid public info find",
        llm_description=(
            "조회구분(inqry_div)과 입찰공고번호(bid_ntce_no)로 "
            "나라장터 입찰공고 공개 데이터를 조회한다."
        ),
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
)

_BY_TOOL_ID = {spec.tool_id: spec for spec in VERIFIED_DATA_GO_KR_ADAPTERS}


def require_spec(tool_id: str) -> VerifiedAdapterSpec:
    """Return the manifest entry for *tool_id*."""

    return _BY_TOOL_ID[tool_id]
