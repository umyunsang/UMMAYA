# Verified data.go.kr Adapter Wave

Feature: `specs/2798-data-go-kr-live-expansion`
Epic: #2832

This catalog page covers the direct-curl verified public-data wave plus the
approved follow-up APIs from the 2026-05-16 application batch. UMMAYA now
registers thirty live, read-only `find` adapters from this catalog. Each
included adapter has a saved successful probe under
`docs/api/data-go-kr-candidate-docs/<id>/probes/`; default tests replay those
fixtures and never call live public APIs.

## Included Adapters

| data.go.kr ID | tool_id | Source | Primitive | Env var | Evidence |
|---|---|---|---|---|---|
| `15043459` | `fsc_corporate_finance_summary` | 금융위원회 기업 재무요약 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15043459/probes/live-2026-05-16/corporate-finance-summary.body.json` |
| `15073861` | `airkorea_ctprvn_air_quality` | 에어코리아 시도별 실시간 대기질 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json` |
| `15091886` | `ftc_large_group_status` | 공정거래위원회 대규모기업집단 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15091886/probes/live-2026-05-16/ftc-large-group.body.xml` |
| `15091910` | `ftc_public_ym_list` | 공정거래위원회 사용 가능 공개년월 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15091910/probes/live-2026-05-16/ftc-public-ym.body.xml` |
| `15098529` | `tago_bus_route_search` | 국토교통부 TAGO 버스노선 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098529/probes/live-2026-05-16/tago-bus-route.body.xml` |
| `15098530` | `tago_bus_arrival_search` | 국토교통부 TAGO 버스도착 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml` |
| `15098533` | `tago_bus_location_search` | 국토교통부 TAGO 버스위치 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098533/probes/live-2026-05-16/tago-bus-location.body.xml` |
| `15098534` | `tago_bus_station_search` | 국토교통부 TAGO 버스정류소 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098534/probes/live-2026-05-16/tago-bus-station.body.xml` |
| `15101360` | `kepco_contract_power_usage` | 한국전력 계약종별 전력사용량 조회 | `find` | `UMMAYA_KEPCO_POWER_DATA_API_KEY` | `15101360/probes/live-2026-05-16/kepco-contract-type.body.json` |
| `15129394` | `pps_bid_public_info` | 조달청 나라장터 입찰공고 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15129394/probes/live-2026-05-27/pps-bid-construction-search.body.json` |
| `15134761` | `reb_real_estate_stat_table` | 한국부동산원 부동산 통계표 조회 | `find` | `UMMAYA_REB_REAL_ESTATE_STATS_API_KEY` | `15134761/probes/live-2026-05-16/reb-stat-table.body.json` |
| `15157485` | `bfc_funeral_area_fee` | 부산시설공단 장례식장 시설사용료 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15157485/probes/live-2026-05-16/funeral-area-list.body.json` |
| `15158680` | `kcue_finance_regional_tuition` | 대학알리미 지역별 등록금 현황 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml` |
| `15158684` | `kcue_student_regional_foreign` | 대학알리미 지역별 외국인 유학생 현황 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158684/probes/live-2026-05-16/student-regional-foreign.body.xml` |
| `15121954` | `moj_village_lawyer_lookup` | 법무부 마을변호사 지역별 현황 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15121954/probes/live-2026-05-16-direct-check/moj-village-lawyer-http.body` |
| `15073554` | `mois_facility_safety_info_lookup` | 행정안전부 안전정보 통합공개 시설 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15073554/probes/live-2026-05-16-direct-check/mois-facility-safety-search.body` |
| `15001699` | `hira_medical_institution_detail` | 건강보험심사평가원 의료기관 상세정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15001699/probes/live-2026-05-16-direct-check/hira-medical-detail.body` |
| `15155046` | `mois_emergency_call_box_lookup` | 행정안전부 안전비상벨 위치정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15155046/probes/live-2026-05-16-direct-check/emergency-call-box.body` |
| `15158794` | `djtc_subway_segment_fare_time_check` | 대전교통공사 역간 소요시간 거리 요금 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158794/probes/live-2026-05-16-direct-check/djtc-time-distance.body` |
| `15096040` | `gyeryong_assistive_device_charging_place_locate` | 계룡시 장애인 전동보장구 충전 장소 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15096040/probes/live-2026-05-16-direct-check/gyeryong-charger.body` |
| `15000652` | `nmc_aed_site_locate` | 국립중앙의료원 전국 AED 정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15000652/probes/live-2026-05-16-direct-check/nmc-aed-manage.body` |
| `15127779` | `mof_ocean_water_quality_check` | 해양수산부 실시간 해양수질 측정자료 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15127779/probes/live-2026-05-16-direct-check/ocean-water-quality.body` |
| `15075057` | `mfds_easy_drug_info_lookup` | 식품의약품안전처 의약품개요정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15075057/probes/live-2026-05-16-direct-check/mfds-easy-drug.body` |
| `15156780` | `mpm_public_job_lookup` | 인사혁신처 공공취업정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15156780/probes/live-2026-05-16-direct-check/mpm-public-job-g01.body` |
| `15129471` | `pps_shopping_mall_product_lookup` | 조달청 종합쇼핑몰 품목정보 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15129471/probes/live-2026-05-16-direct-check/pps-shopping-product.body` |
| `15158905` | `ksd_financial_term_lookup` | 한국예탁결제원 금융용어 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158905/probes/live-2026-05-16-direct-check/ksd-financial-term.body` |
| `15157820` | `mss_sme_support_notice_lookup` | 중소벤처기업부 중소기업 지원사업 공고 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15157820/probes/live-2026-05-16-direct-check/sme-support-announcement.body` |
| `15140950` | `ccourt_publication_documents` | 헌법재판소 발간자료 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15140950/probes/live-2026-05-16-direct-check/ccourt-publication.body` |
| `15149906` | `moj_stay_person_counter` | 법무부 체류외국인 현황 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15149906/probes/live-2026-05-16-blocker-resolution/moj-gateway-ServiceKey.body` |
| `15074634` | `msit_business_announcement_lookup` | 과학기술정보통신부 사업공고 조회 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15074634/probes/live-2026-05-16-blocker-resolution/msit-rawkey-ua-only.body` |

## Excluded From This Wave

| data.go.kr ID | Status | Handling |
|---|---|---|
| `15038392` | Approved key was recognized, but the legacy AcademyInfo finance endpoint returned service-access denial for the tested operation. | Deferred until provider entitlement or operation mapping is confirmed. |
| `15058923` | EKAPE animal trace endpoint returned the same unregistered-key envelope for approved and synthetic keys. | Deferred until provider-side approval state changes or a corrected endpoint is published. |
| `15063444` | Uiryeong shelter endpoint was reachable, but approved and synthetic keys returned the same unregistered-key envelope. | Deferred until a key-specific success probe exists. |

## Runtime Contract

- All catalog entries register as `GovAPITool` with `primitive="find"`,
  `adapter_mode="live"`, and `citizen_facing_gate="read-only"`.
- Default tests use fixture replay only; live public API calls are excluded from
  CI by policy.
- Direct runtime calls require the listed environment variables and route
  through `ToolExecutor.invoke()` or the `find` meta-tool.
- Parser output is normalized to `{"kind": "collection", "items": [...],
  "total_count": N}` so it passes the existing `LookupCollection` envelope.
- HTTP 4xx/5xx errors redact sensitive query parameters before the tool error
  is shown to the LLM or CLI user.
