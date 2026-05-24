---
title: "Live Adapters"
description: "既存 Live adapter と新しく検証された public-data adapter を user question 別に整理します。"
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

この page は三十個の新 API list ではなく、現在の Live surface を読むための map です。既存 Live adapters と新しく verified された public-data adapters を、users が聞ける question で grouped します。

現在の registry evidence は 42 個の live `find` adapters、5 個の live `locate` provider adapters、そして 4 個の main primitive surfaces（`find`、`locate`、`check`、`send`）を区別します。新 wave は、既存の KMA、KOROAD、HIRA、NMC、NFA、MOHW live surface の上に、approval、direct call、fixture replay で確認された 30 個の read-only public-data adapters を追加しました。

## 何が変わったか

新しい public-data wave により、UMMAYA はより広い everyday administrative lookup questions を同じ `find` primitive へ route できます。weather と hospital lookup だけでなく、bus data、air quality、AED、emergency call box、drug summary、public jobs、SME support notices、procurement、real-estate statistics、university statistics、power-usage statistics、legal/public records まで扱えます。

Live は read-only lookup に callable channel と credential path があるという意味です。protected submissions、payments、identity checks、certificate issuance、tax filing、その他 binding official actions を完了できるという意味ではありません。live authority と receipt evidence がない workflow は Mock または Handoff に残す必要があります。

## Live Adapter Groups

| User question group | Matching tool IDs | Example prompts |
|---|---|---|
| Weather、air quality、disaster、safety | `kma_current_observation`, `kma_forecast_fetch`, `kma_pre_warning`, `kma_short_term_forecast`, `kma_ultra_short_term_forecast`, `kma_weather_alert_status`, `airkorea_ctprvn_air_quality`, `mois_facility_safety_info_lookup`, `mois_emergency_call_box_lookup` | "今日のソウルの大気質と weather alerts を確認して", "近くの emergency call boxes や safety facilities を探して" |
| Emergency healthcare、hospitals、AED、welfare guidance | `hira_hospital_search`, `hira_medical_institution_detail`, `nmc_emergency_search`, `nmc_aed_site_locate`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search`, `mfds_easy_drug_info_lookup`, `gyeryong_assistive_device_charging_place_locate` | "近くの AED locations を探して", "この drug summary を調べて", "public welfare guidance を確認して" |
| Transit、bus、road、subway | `koroad_accident_search`, `koroad_accident_hazard_search`, `tago_bus_route_search`, `tago_bus_arrival_search`, `tago_bus_location_search`, `tago_bus_station_search`, `djtc_subway_segment_fare_time_check` | "bus arrival information を探して", "大田地下鉄の二駅間の時間と fare を教えて" |
| Jobs、business、procurement、support programs | `mpm_public_job_lookup`, `mss_sme_support_notice_lookup`, `msit_business_announcement_lookup`, `pps_bid_public_info`, `pps_shopping_mall_product_lookup`, `fsc_corporate_finance_summary`, `ksd_financial_term_lookup` | "SME support notices を探して", "public jobs と procurement notices を確認して" |
| Civic statistics、legal help、public records | `moj_village_lawyer_lookup`, `moj_stay_person_counter`, `ccourt_publication_documents`, `ftc_large_group_status`, `ftc_public_ym_list`, `reb_real_estate_stat_table`, `bfc_funeral_area_fee`, `kcue_finance_regional_tuition`, `kcue_student_regional_foreign`, `kepco_contract_power_usage`, `mof_ocean_water_quality_check` | "village lawyer status を探して", "real-estate statistics を確認して", "university tuition statistics を調べて" |
| Address and administrative-area resolution | `juso_adm_cd_lookup`, `kakao_address_search`, `kakao_coord_to_region`, `kakao_keyword_search`, `sgis_adm_cd_lookup` | "この住所を行政洞コードへ変換して", "場所を location context に resolve して" |

この table は user-task view です。canonical tool ID list、schema paths、permission tiers は [Adapter Matrix](/jg/coverage/adapter-matrix/) と `docs/api/README.md` を基準に確認します。

## Deferred のままのもの

Approved candidates `15038392`、`15058923`、`15063444` は Live adapters として advertise しません。provider entitlement、endpoint mapping、または key-specific success evidence がまだ必要です。successful probe が callable shape を証明するまでは Deferred のままです。

## Evidence Trail

`docs/api/verified-data-go-kr/README.md` は included adapter、data.go.kr ID、env var、saved probe path を記録します。default tests は saved fixtures を replay し、live public APIs を call しません。runtime calls には listed `UMMAYA_*` environment variables が必要で、`find` meta-tool または `ToolExecutor.invoke()` を通ります。

docs-site の machine-readable adapter metadata は、`docs/api/README.md` catalog rows と individual adapter spec front matter を merge して生成されます。Live adapter を追加した後は `npm run docs:generate` と `npm run docs:check` を実行し、prose、generated JSON、`llms.txt` が同じ事実を示すようにします。
