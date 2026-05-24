---
title: "Live Adapters"
description: "按用户问题整理既有 Live adapter 与新验证的 public-data adapter。"
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

本页不是三十个新 API 的清单，而是当前 Live surface 的阅读入口：把既有 Live adapters 和新验证的 public-data adapters 按用户能提出的问题重新整理。

当前 registry evidence 区分 42 个 live `find` adapters、5 个 live `locate` provider adapters，以及 4 个 main primitive surfaces：`find`、`locate`、`check`、`send`。新 wave 在既有 KMA、KOROAD、HIRA、NMC、NFA、MOHW live surface 之上，新增了 30 个经过 approval、direct call、fixture replay 验证的 read-only public-data adapters。

## 本次更新意味着什么

新的 public-data wave 让 UMMAYA 可以把更多生活行政查询问题路由到同一个 `find` primitive。除了 weather 和 hospital lookup，现在还覆盖 bus data、air quality、AED、emergency call box、drug summary、public jobs、SME support notices、procurement、real-estate statistics、university statistics、power-usage statistics、legal/public records 等数据。

Live 表示 read-only lookup 具有 callable channel 和 credential path。它不表示 UMMAYA 可以完成 protected submissions、payments、identity checks、certificate issuance、tax filing 或其他 binding official actions。除非有 live authority 和 receipt evidence，否则这些 workflow 必须保持 Mock 或 Handoff。

## Live Adapter Groups

| 用户问题组 | 对应 tool IDs | 示例 prompt |
|---|---|---|
| Weather、air quality、disaster、safety | `kma_current_observation`, `kma_forecast_fetch`, `kma_pre_warning`, `kma_short_term_forecast`, `kma_ultra_short_term_forecast`, `kma_weather_alert_status`, `airkorea_ctprvn_air_quality`, `mois_facility_safety_info_lookup`, `mois_emergency_call_box_lookup` | "检查今天首尔空气质量和天气警报", "查找附近 emergency call boxes 或 safety facilities" |
| Emergency healthcare、hospitals、AED、welfare guidance | `hira_hospital_search`, `hira_medical_institution_detail`, `nmc_emergency_search`, `nmc_aed_site_locate`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search`, `mfds_easy_drug_info_lookup`, `gyeryong_assistive_device_charging_place_locate` | "查找附近 AED 位置", "查询这个药品概况", "确认 public welfare guidance" |
| Transit、bus、road、subway | `koroad_accident_search`, `koroad_accident_hazard_search`, `tago_bus_route_search`, `tago_bus_arrival_search`, `tago_bus_location_search`, `tago_bus_station_search`, `djtc_subway_segment_fare_time_check` | "查找 bus arrival information", "告诉我大田地铁两站之间的时间和票价" |
| Jobs、business、procurement、support programs | `mpm_public_job_lookup`, `mss_sme_support_notice_lookup`, `msit_business_announcement_lookup`, `pps_bid_public_info`, `pps_shopping_mall_product_lookup`, `fsc_corporate_finance_summary`, `ksd_financial_term_lookup` | "查找 SME support notices", "确认 public jobs 和 procurement notices" |
| Civic statistics、legal help、public records | `moj_village_lawyer_lookup`, `moj_stay_person_counter`, `ccourt_publication_documents`, `ftc_large_group_status`, `ftc_public_ym_list`, `reb_real_estate_stat_table`, `bfc_funeral_area_fee`, `kcue_finance_regional_tuition`, `kcue_student_regional_foreign`, `kepco_contract_power_usage`, `mof_ocean_water_quality_check` | "查找 village lawyer status", "确认 real-estate statistics", "查询 university tuition statistics" |
| Address 与 administrative-area resolution | `juso_adm_cd_lookup`, `kakao_address_search`, `kakao_coord_to_region`, `kakao_keyword_search`, `sgis_adm_cd_lookup` | "把这个地址转换成行政洞代码", "根据地点解析 location context" |

这张表是 user-task view。canonical tool ID list、schema path 和 permission tier 请以 [Adapter Matrix](/ch/coverage/adapter-matrix/) 与 `docs/api/README.md` 为准。

## 仍保持 Deferred

已批准候选 `15038392`、`15058923`、`15063444` 不能作为 Live adapter 宣传。它们仍需要 provider entitlement、endpoint mapping 或 key-specific success evidence。只有成功 probe 证明 callable shape 后，才可从 Deferred 升级。

## Evidence Trail

`docs/api/verified-data-go-kr/README.md` 记录每个 included adapter、data.go.kr ID、env var 和 saved probe path。默认测试只 replay saved fixtures，不调用 live public APIs。实际 runtime call 需要相应 `UMMAYA_*` environment variables，并通过 `find` meta-tool 或 `ToolExecutor.invoke()` 执行。

docs-site 的 machine-readable adapter metadata 会合并 `docs/api/README.md` catalog rows 和 individual adapter spec front matter。新增 Live adapter 后，运行 `npm run docs:generate` 与 `npm run docs:check`，确保 prose、generated JSON 和 `llms.txt` 保持一致。
