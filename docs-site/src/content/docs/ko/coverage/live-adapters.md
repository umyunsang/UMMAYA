---
title: "Live Adapter 현황"
description: "기존 Live adapter와 새로 검증된 public-data adapter를 사용자 질문 기준으로 정리합니다."
llm_index: true
audience:
  - considering_user
  - public_sector_evaluator
  - adapter_author
  - maintainer
source_of_truth:
  - docs/api/README.md
  - docs/api/verified-data-go-kr/README.md
  - tests/unit/tools/test_registry_count_breakdown.py
  - specs/2798-data-go-kr-live-expansion/
---

이 페이지는 "30개 API 목록"이 아니라, 기존 Live adapter와 새로 추가된 Live adapter를 함께 읽기 위한 현황판입니다. 사용자는 여기서 어떤 질문이 실제 조회 도구로 이어질 수 있는지 보고, evaluator는 그 claim이 어떤 catalog와 evidence에 연결되는지 확인합니다.

현재 registry evidence는 42개의 live `find` adapter, 5개의 live `locate` provider adapter, 4개의 main primitive surface(`find`, `locate`, `check`, `send`)를 구분합니다. 새 wave는 승인·직접 호출·fixture replay까지 확인된 30개의 read-only public-data adapter이고, 기존 KMA/KOROAD/HIRA/NMC/NFA/MOHW live surface 위에 붙었습니다.

## 이번 업데이트의 의미

새로 추가된 public-data wave는 UMMAYA가 "공공 데이터 조회"를 더 넓은 생활 행정 질문으로 연결할 수 있게 합니다. 날씨와 병원처럼 이미 있던 lookup뿐 아니라, 버스, 대기질, AED, 비상벨, 의약품, 공공채용, 중소기업 지원사업, 조달, 부동산 통계, 대학 현황, 전력 사용량, 법률·공공기록 조회까지 같은 `find` primitive로 노출됩니다.

Live라는 말은 read-only 조회가 실제 callable channel과 credential path를 갖는다는 뜻입니다. 신청, 결제, 신분확인, 증명서 발급, 세금 신고처럼 구속력 있는 행위가 완료된다는 뜻은 아닙니다. 그런 workflow는 여전히 Mock 또는 Handoff로 표시되어야 합니다.

## Live Adapter Groups

| 사용자 질문 묶음 | 대응 가능한 tool IDs | 사용자가 물을 수 있는 예 |
|---|---|---|
| 날씨, 대기질, 재난·안전 | `kma_current_observation`, `kma_forecast_fetch`, `kma_pre_warning`, `kma_short_term_forecast`, `kma_ultra_short_term_forecast`, `kma_weather_alert_status`, `airkorea_ctprvn_air_quality`, `mois_facility_safety_info_lookup`, `mois_emergency_call_box_lookup` | "오늘 서울 미세먼지와 기상특보 확인해줘", "근처 비상벨이나 안전시설을 찾아줘" |
| 응급의료, 병원, AED, 복지 안내 | `hira_hospital_search`, `hira_medical_institution_detail`, `nmc_emergency_search`, `nmc_aed_site_locate`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search`, `mfds_easy_drug_info_lookup`, `gyeryong_assistive_device_charging_place_locate` | "근처 AED 위치 알려줘", "의약품 개요정보를 찾아줘", "복지 자격 안내를 확인해줘" |
| 교통, 버스, 도로, 지하철 | `koroad_accident_search`, `koroad_accident_hazard_search`, `tago_bus_route_search`, `tago_bus_arrival_search`, `tago_bus_location_search`, `tago_bus_station_search`, `djtc_subway_segment_fare_time_check` | "버스 도착 정보를 찾아줘", "대전 지하철 두 역 사이 소요시간과 요금 알려줘" |
| 일자리, 기업, 조달, 지원사업 | `mpm_public_job_lookup`, `mss_sme_support_notice_lookup`, `msit_business_announcement_lookup`, `pps_bid_public_info`, `pps_shopping_mall_product_lookup`, `fsc_corporate_finance_summary`, `ksd_financial_term_lookup` | "중소기업 지원사업 공고 찾아줘", "공공취업정보와 조달 입찰공고를 확인해줘" |
| 생활 통계, 법률, 공공기록 | `moj_village_lawyer_lookup`, `moj_stay_person_counter`, `ccourt_publication_documents`, `ftc_large_group_status`, `ftc_public_ym_list`, `reb_real_estate_stat_table`, `bfc_funeral_area_fee`, `kcue_finance_regional_tuition`, `kcue_student_regional_foreign`, `kepco_contract_power_usage`, `mof_ocean_water_quality_check` | "마을변호사 현황 찾아줘", "부동산 통계표를 확인해줘", "대학 등록금 현황을 찾아줘" |
| 주소와 행정구역 해석 | `juso_adm_cd_lookup`, `kakao_address_search`, `kakao_coord_to_region`, `kakao_keyword_search`, `sgis_adm_cd_lookup` | "이 주소를 행정동 코드로 바꿔줘", "주변 장소를 기준으로 위치를 resolve해줘" |

이 표는 사용자 task 기준으로 묶은 view입니다. 전체 canonical list, schema path, permission tier는 [Adapter Matrix](/ko/coverage/adapter-matrix/)와 `docs/api/README.md`를 기준으로 확인합니다.

## Deferred로 남은 것

승인된 후보 중 `15038392`, `15058923`, `15063444`는 아직 Live adapter로 홍보하지 않습니다. 승인 key가 있어도 provider entitlement, endpoint mapping, key-specific success probe가 확인되지 않았기 때문입니다. 이 세 건은 문서에서 "곧 가능"처럼 쓰면 안 되고, deferred evidence가 해결된 뒤에만 Live로 승격됩니다.

## Evidence Trail

Live public-data wave는 `docs/api/verified-data-go-kr/README.md`에 포함 adapter, data.go.kr ID, env var, saved probe path를 기록합니다. 기본 테스트는 live channel을 다시 호출하지 않고 saved fixture를 replay합니다. 실제 runtime 호출은 필요한 `UMMAYA_*` env var가 있을 때 `find` meta-tool 또는 `ToolExecutor.invoke()`를 통해 이루어집니다.

문서사이트의 machine-readable adapter metadata는 `docs/api/README.md`의 catalog row와 개별 spec front matter를 병합해 생성됩니다. 따라서 새 Live adapter를 추가한 뒤에는 `npm run docs:generate`와 `npm run docs:check`로 prose, generated JSON, `llms.txt`가 같은 사실을 말하는지 확인해야 합니다.
