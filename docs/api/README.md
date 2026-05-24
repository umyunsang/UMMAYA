# UMMAYA API Catalog

This directory documents every active adapter registered with UMMAYA at the close of the Claude Code → Korean public-service harness migration (Initiative #1631, Epic P6 #1637), the direct-curl verified public-data waves from Epics #2797 and #2832, and the KMA APIHub structured expansion from Spec #2800. Active adapters span Korean ministries, public corporations, and public-infrastructure endpoints: live `find` adapters call `data.go.kr`, KMA APIHub, or provider LINK APIs, live `locate` adapters wrap provider-specific geocoding APIs, and mock `send`/`check` adapters replay public-spec-mirrored fixtures. Subscription adapters are intentionally deferred until UMMAYA has an app/push-notification runtime.

The catalog is intended for three audiences:

- **Citizen developers** (and external plugin contributors) discovering what UMMAYA already ships.
- **Release validators** confirming the registered surface against documentation.
- **Maintainers** keeping schemas in sync with `src/ummaya/tools/` source.

Every adapter spec follows the seven-section template in [`specs/1637-p6-docs-smoke/contracts/adapter-spec-template.md`](../../specs/1637-p6-docs-smoke/contracts/adapter-spec-template.md): YAML front matter (`tool_id` · `primitive` · `tier` · `permission_tier`) followed by Overview · Envelope · Search hints · Endpoint · Permission tier rationale · Worked example · Constraints. JSON Schema Draft 2020-12 exports for every adapter live under [`schemas/`](./schemas/) and are produced deterministically by [`scripts/build_schemas.py`](../../scripts/build_schemas.py).

Provider portfolio notes that are broader than one active adapter live next to
the catalog. The current KFTC portfolio analysis is
[`kftc-openapi-portfolio.md`](./kftc-openapi-portfolio.md); it maps the full
KFTC OpenAPI service surface to UMMAYA primitives and records approval/testbed
gates before future adapter specs are opened. The endpoint-by-endpoint KFTC
developer-site inventory is
[`kftc-openapi-endpoint-inventory.md`](./kftc-openapi-endpoint-inventory.md).
The deeper section-by-section debug report is
[`kftc-openapi-56-section-debug-report.md`](./kftc-openapi-56-section-debug-report.md);
it records the scroll-verified KFTC OpenAPI sidebar routes, direct probe
outcomes, root-cause classifications, and the UMMAYA adapter treatment for each
route.

The KMA APIHub structured catalog is grouped under
[`kma/apihub_structured_adapters.md`](./kma/apihub_structured_adapters.md). It
wraps 85 `typ02/openApi` operations as generated `kma_apihub_*` `find`
adapters with individual JSON Schema files under [`schemas/`](./schemas/).
They are grouped here to keep the index readable; the generated schema
filenames and stable `tool_id` values are the source of truth for individual
operations.

## How to use this catalog

1. **Find an adapter** — scan Matrix A (by source) when the ministry is known, Matrix B (by primitive) when the verb (`find` / `locate` / `send` / `check`) is known. Both matrices are sorted alphabetically by `tool_id`.
2. **Read the spec** — open the linked Markdown file. The seven mandatory sections give classification, envelope reference, bilingual search hints, endpoint, permission rationale, worked example, and constraints.
3. **Consume the schema** — the JSON Schema file linked from each row is Draft 2020-12 and validates against any generic schema validator. Re-run `python scripts/build_schemas.py --check` to verify the on-disk schemas still match the source Pydantic models.

## Matrix A — adapters by source

| Source | tool_id | Primitive | Tier | Permission | Spec | Schema |
|---|---|---|---|---|---|---|
| KOROAD | `koroad_accident_search` | `find` | live | 1 | [koroad/accident_search.md](./koroad/accident_search.md) | [koroad_accident_search.json](./schemas/koroad_accident_search.json) |
| KOROAD | `koroad_accident_hazard_search` | `find` | live | 1 | [koroad/accident_hazard_search.md](./koroad/accident_hazard_search.md) | [koroad_accident_hazard_search.json](./schemas/koroad_accident_hazard_search.json) |
| KMA | `kma_current_observation` | `find` | live | 1 | [kma/current_observation.md](./kma/current_observation.md) | [kma_current_observation.json](./schemas/kma_current_observation.json) |
| KMA | `kma_short_term_forecast` | `find` | live | 1 | [kma/short_term_forecast.md](./kma/short_term_forecast.md) | [kma_short_term_forecast.json](./schemas/kma_short_term_forecast.json) |
| KMA | `kma_ultra_short_term_forecast` | `find` | live | 1 | [kma/ultra_short_term_forecast.md](./kma/ultra_short_term_forecast.md) | [kma_ultra_short_term_forecast.json](./schemas/kma_ultra_short_term_forecast.json) |
| KMA | `kma_weather_alert_status` | `find` | live | 1 | [kma/weather_alert_status.md](./kma/weather_alert_status.md) | [kma_weather_alert_status.json](./schemas/kma_weather_alert_status.json) |
| KMA | `kma_pre_warning` | `find` | live | 1 | [kma/pre_warning.md](./kma/pre_warning.md) | [kma_pre_warning.json](./schemas/kma_pre_warning.json) |
| KMA | `kma_forecast_fetch` | `find` | live | 1 | [kma/forecast_fetch.md](./kma/forecast_fetch.md) | [kma_forecast_fetch.json](./schemas/kma_forecast_fetch.json) |
| KMA APIHub | `kma_apihub_*` (85 generated adapters) | `find` | live | 1 | [kma/apihub_structured_adapters.md](./kma/apihub_structured_adapters.md) | [`kma_apihub_*.json`](./schemas/) |
| HIRA | `hira_hospital_search` | `find` | live | 1 | [hira/hospital_search.md](./hira/hospital_search.md) | [hira_hospital_search.json](./schemas/hira_hospital_search.json) |
| NMC | `nmc_emergency_search` | `find` | live | 3 | [nmc/emergency_search.md](./nmc/emergency_search.md) | [nmc_emergency_search.json](./schemas/nmc_emergency_search.json) |
| NFA119 | `nfa_emergency_info_service` | `find` | live | 1 | [nfa119/emergency_info_service.md](./nfa119/emergency_info_service.md) | [nfa_emergency_info_service.json](./schemas/nfa_emergency_info_service.json) |
| MOHW | `mohw_welfare_eligibility_search` | `find` | live | 1 | [mohw/welfare_eligibility_search.md](./mohw/welfare_eligibility_search.md) | [mohw_welfare_eligibility_search.json](./schemas/mohw_welfare_eligibility_search.json) |
| FSC | `fsc_corporate_finance_summary` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [fsc_corporate_finance_summary.json](./schemas/fsc_corporate_finance_summary.json) |
| KECO / AirKorea | `airkorea_ctprvn_air_quality` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [airkorea_ctprvn_air_quality.json](./schemas/airkorea_ctprvn_air_quality.json) |
| FTC | `ftc_large_group_status` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [ftc_large_group_status.json](./schemas/ftc_large_group_status.json) |
| FTC | `ftc_public_ym_list` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [ftc_public_ym_list.json](./schemas/ftc_public_ym_list.json) |
| MOLIT / TAGO | `tago_bus_route_search` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [tago_bus_route_search.json](./schemas/tago_bus_route_search.json) |
| MOLIT / TAGO | `tago_bus_arrival_search` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [tago_bus_arrival_search.json](./schemas/tago_bus_arrival_search.json) |
| MOLIT / TAGO | `tago_bus_location_search` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [tago_bus_location_search.json](./schemas/tago_bus_location_search.json) |
| MOLIT / TAGO | `tago_bus_station_search` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [tago_bus_station_search.json](./schemas/tago_bus_station_search.json) |
| KEPCO | `kepco_contract_power_usage` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [kepco_contract_power_usage.json](./schemas/kepco_contract_power_usage.json) |
| PPS | `pps_bid_public_info` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [pps_bid_public_info.json](./schemas/pps_bid_public_info.json) |
| REB | `reb_real_estate_stat_table` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [reb_real_estate_stat_table.json](./schemas/reb_real_estate_stat_table.json) |
| BFC | `bfc_funeral_area_fee` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [bfc_funeral_area_fee.json](./schemas/bfc_funeral_area_fee.json) |
| KCUE | `kcue_finance_regional_tuition` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [kcue_finance_regional_tuition.json](./schemas/kcue_finance_regional_tuition.json) |
| KCUE | `kcue_student_regional_foreign` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [kcue_student_regional_foreign.json](./schemas/kcue_student_regional_foreign.json) |
| CCOURT | `ccourt_publication_documents` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [ccourt_publication_documents.json](./schemas/ccourt_publication_documents.json) |
| DJTC | `djtc_subway_segment_fare_time_check` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [djtc_subway_segment_fare_time_check.json](./schemas/djtc_subway_segment_fare_time_check.json) |
| Gyeryong | `gyeryong_assistive_device_charging_place_locate` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [gyeryong_assistive_device_charging_place_locate.json](./schemas/gyeryong_assistive_device_charging_place_locate.json) |
| HIRA | `hira_medical_institution_detail` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [hira_medical_institution_detail.json](./schemas/hira_medical_institution_detail.json) |
| KSD | `ksd_financial_term_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [ksd_financial_term_lookup.json](./schemas/ksd_financial_term_lookup.json) |
| MFDS | `mfds_easy_drug_info_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mfds_easy_drug_info_lookup.json](./schemas/mfds_easy_drug_info_lookup.json) |
| MOF | `mof_ocean_water_quality_check` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mof_ocean_water_quality_check.json](./schemas/mof_ocean_water_quality_check.json) |
| MOIS | `mois_emergency_call_box_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mois_emergency_call_box_lookup.json](./schemas/mois_emergency_call_box_lookup.json) |
| MOIS | `mois_facility_safety_info_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mois_facility_safety_info_lookup.json](./schemas/mois_facility_safety_info_lookup.json) |
| MOJ | `moj_stay_person_counter` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [moj_stay_person_counter.json](./schemas/moj_stay_person_counter.json) |
| MOJ | `moj_village_lawyer_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [moj_village_lawyer_lookup.json](./schemas/moj_village_lawyer_lookup.json) |
| MPM | `mpm_public_job_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mpm_public_job_lookup.json](./schemas/mpm_public_job_lookup.json) |
| MSIT | `msit_business_announcement_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [msit_business_announcement_lookup.json](./schemas/msit_business_announcement_lookup.json) |
| MSS | `mss_sme_support_notice_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [mss_sme_support_notice_lookup.json](./schemas/mss_sme_support_notice_lookup.json) |
| NMC | `nmc_aed_site_locate` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [nmc_aed_site_locate.json](./schemas/nmc_aed_site_locate.json) |
| PPS | `pps_shopping_mall_product_lookup` | `find` | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) | [pps_shopping_mall_product_lookup.json](./schemas/pps_shopping_mall_product_lookup.json) |
| Mock — Check | `mock_verify_digital_onepass` | `check` | mock | 2 | [verify/digital_onepass.md](./verify/digital_onepass.md) | [mock_verify_digital_onepass.json](./schemas/mock_verify_digital_onepass.json) |
| Mock — Check | `mock_verify_mobile_id` | `check` | mock | 2 | [verify/mobile_id.md](./verify/mobile_id.md) | [mock_verify_mobile_id.json](./schemas/mock_verify_mobile_id.json) |
| Mock — Check | `mock_verify_gongdong_injeungseo` | `check` | mock | 3 | [verify/gongdong_injeungseo.md](./verify/gongdong_injeungseo.md) | [mock_verify_gongdong_injeungseo.json](./schemas/mock_verify_gongdong_injeungseo.json) |
| Mock — Check | `mock_verify_geumyung_injeungseo` | `check` | mock | 2 | [verify/geumyung_injeungseo.md](./verify/geumyung_injeungseo.md) | [mock_verify_geumyung_injeungseo.json](./schemas/mock_verify_geumyung_injeungseo.json) |
| Mock — Check | `mock_verify_ganpyeon_injeung` | `check` | mock | 2 | [verify/ganpyeon_injeung.md](./verify/ganpyeon_injeung.md) | [mock_verify_ganpyeon_injeung.json](./schemas/mock_verify_ganpyeon_injeung.json) |
| Mock — Check | `mock_verify_mydata` | `check` | mock | 2 | [verify/mydata.md](./verify/mydata.md) | [mock_verify_mydata.json](./schemas/mock_verify_mydata.json) |
| Mock — Send | `mock_kftc_opengiro_bill_send_v1` | `send` | mock | 2 | [submit/kftc_opengiro.md](./submit/kftc_opengiro.md) | [mock_kftc_opengiro_bill_send_v1.json](./schemas/mock_kftc_opengiro_bill_send_v1.json) |
| Mock — Send | `mock_kftc_opengiro_payment_send_v1` | `send` | mock | 2 | [submit/kftc_opengiro.md](./submit/kftc_opengiro.md) | [mock_kftc_opengiro_payment_send_v1.json](./schemas/mock_kftc_opengiro_payment_send_v1.json) |
| Mock — Send | `mock_traffic_fine_pay_v1` | `send` | mock | 2 | [submit/traffic_fine_pay.md](./submit/traffic_fine_pay.md) | [mock_traffic_fine_pay_v1.json](./schemas/mock_traffic_fine_pay_v1.json) |
| Mock — Send | `mock_welfare_application_submit_v1` | `send` | mock | 2 | [submit/welfare_application.md](./submit/welfare_application.md) | [mock_welfare_application_submit_v1.json](./schemas/mock_welfare_application_submit_v1.json) |
| Geocoding | `juso_adm_cd_lookup` | `locate` | live | 1 | [locate/index.md](./locate/index.md) | [juso_adm_cd_lookup.json](./schemas/juso_adm_cd_lookup.json) |
| Geocoding | `kakao_address_search` | `locate` | live | 1 | [locate/index.md](./locate/index.md) | [kakao_address_search.json](./schemas/kakao_address_search.json) |
| Geocoding | `kakao_coord_to_region` | `locate` | live | 1 | [locate/index.md](./locate/index.md) | [kakao_coord_to_region.json](./schemas/kakao_coord_to_region.json) |
| Geocoding | `kakao_keyword_search` | `locate` | live | 1 | [locate/index.md](./locate/index.md) | [kakao_keyword_search.json](./schemas/kakao_keyword_search.json) |
| Geocoding | `sgis_adm_cd_lookup` | `locate` | live | 1 | [locate/index.md](./locate/index.md) | [sgis_adm_cd_lookup.json](./schemas/sgis_adm_cd_lookup.json) |

## Matrix B — adapters by primitive

### `find` (127 live ministry, public-data, and KMA APIHub adapters)

| tool_id | Source | Tier | Permission | Spec |
|---|---|---|---|---|
| `airkorea_ctprvn_air_quality` | KECO / AirKorea | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `bfc_funeral_area_fee` | BFC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `ccourt_publication_documents` | CCOURT | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `djtc_subway_segment_fare_time_check` | DJTC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `fsc_corporate_finance_summary` | FSC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `ftc_large_group_status` | FTC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `ftc_public_ym_list` | FTC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `gyeryong_assistive_device_charging_place_locate` | Gyeryong | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `hira_hospital_search` | HIRA | live | 1 | [hira/hospital_search.md](./hira/hospital_search.md) |
| `hira_medical_institution_detail` | HIRA | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `kcue_finance_regional_tuition` | KCUE | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `kcue_student_regional_foreign` | KCUE | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `kepco_contract_power_usage` | KEPCO | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `kma_current_observation` | KMA | live | 1 | [kma/current_observation.md](./kma/current_observation.md) |
| `kma_forecast_fetch` | KMA | live | 1 | [kma/forecast_fetch.md](./kma/forecast_fetch.md) |
| `kma_pre_warning` | KMA | live | 1 | [kma/pre_warning.md](./kma/pre_warning.md) |
| `kma_short_term_forecast` | KMA | live | 1 | [kma/short_term_forecast.md](./kma/short_term_forecast.md) |
| `kma_ultra_short_term_forecast` | KMA | live | 1 | [kma/ultra_short_term_forecast.md](./kma/ultra_short_term_forecast.md) |
| `kma_weather_alert_status` | KMA | live | 1 | [kma/weather_alert_status.md](./kma/weather_alert_status.md) |
| `kma_apihub_*` (85 generated adapters) | KMA APIHub | live | 1 | [kma/apihub_structured_adapters.md](./kma/apihub_structured_adapters.md) |
| `koroad_accident_hazard_search` | KOROAD | live | 1 | [koroad/accident_hazard_search.md](./koroad/accident_hazard_search.md) |
| `koroad_accident_search` | KOROAD | live | 1 | [koroad/accident_search.md](./koroad/accident_search.md) |
| `ksd_financial_term_lookup` | KSD | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mfds_easy_drug_info_lookup` | MFDS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mof_ocean_water_quality_check` | MOF | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mohw_welfare_eligibility_search` | MOHW | live | 1 | [mohw/welfare_eligibility_search.md](./mohw/welfare_eligibility_search.md) |
| `mois_emergency_call_box_lookup` | MOIS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mois_facility_safety_info_lookup` | MOIS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `moj_stay_person_counter` | MOJ | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `moj_village_lawyer_lookup` | MOJ | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mpm_public_job_lookup` | MPM | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `msit_business_announcement_lookup` | MSIT | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `mss_sme_support_notice_lookup` | MSS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `nfa_emergency_info_service` | NFA119 | live | 1 | [nfa119/emergency_info_service.md](./nfa119/emergency_info_service.md) |
| `nmc_aed_site_locate` | NMC | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `nmc_emergency_search` | NMC | live | 3 (gated) | [nmc/emergency_search.md](./nmc/emergency_search.md) |
| `pps_bid_public_info` | PPS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `pps_shopping_mall_product_lookup` | PPS | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `reb_real_estate_stat_table` | REB | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `tago_bus_arrival_search` | MOLIT / TAGO | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `tago_bus_location_search` | MOLIT / TAGO | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `tago_bus_route_search` | MOLIT / TAGO | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |
| `tago_bus_station_search` | MOLIT / TAGO | live | 1 | [verified-data-go-kr/README.md](./verified-data-go-kr/README.md) |

### `locate` (5 provider adapters)

| tool_id | Source | Tier | Permission | Spec |
|---|---|---|---|---|
| `juso_adm_cd_lookup` | JUSO address-link | live | 1 | [locate/index.md](./locate/index.md) |
| `kakao_address_search` | Kakao Local address search | live | 1 | [locate/index.md](./locate/index.md) |
| `kakao_coord_to_region` | Kakao Local coord2regioncode | live | 1 | [locate/index.md](./locate/index.md) |
| `kakao_keyword_search` | Kakao Local keyword search | live | 1 | [locate/index.md](./locate/index.md) |
| `sgis_adm_cd_lookup` | SGIS reverse geocoding | live | 1 | [locate/index.md](./locate/index.md) |

### `send` (4 entries)

| tool_id | Source | Tier | Permission | Spec |
|---|---|---|---|---|
| `mock_kftc_opengiro_bill_send_v1` | KFTC OpenGiro bill service (mock) | mock | 2 | [submit/kftc_opengiro.md](./submit/kftc_opengiro.md) |
| `mock_kftc_opengiro_payment_send_v1` | KFTC OpenGiro payment service (mock) | mock | 2 | [submit/kftc_opengiro.md](./submit/kftc_opengiro.md) |
| `mock_traffic_fine_pay_v1` | data.go.kr (mock) | mock | 2 | [submit/traffic_fine_pay.md](./submit/traffic_fine_pay.md) |
| `mock_welfare_application_submit_v1` | KFTC MyData (mock) | mock | 2 | [submit/welfare_application.md](./submit/welfare_application.md) |

### `check` (6 entries)

| tool_id | Family | Tier | Permission | Spec |
|---|---|---|---|---|
| `mock_verify_digital_onepass` | 디지털원패스 | mock | 2 | [verify/digital_onepass.md](./verify/digital_onepass.md) |
| `mock_verify_ganpyeon_injeung` | 간편인증 | mock | 2 | [verify/ganpyeon_injeung.md](./verify/ganpyeon_injeung.md) |
| `mock_verify_geumyung_injeungseo` | 금융인증서 | mock | 2 | [verify/geumyung_injeungseo.md](./verify/geumyung_injeungseo.md) |
| `mock_verify_gongdong_injeungseo` | 공동인증서 | mock | 3 | [verify/gongdong_injeungseo.md](./verify/gongdong_injeungseo.md) |
| `mock_verify_mobile_id` | 모바일 신분증 | mock | 2 | [verify/mobile_id.md](./verify/mobile_id.md) |
| `mock_verify_mydata` | 마이데이터 | mock | 2 | [verify/mydata.md](./verify/mydata.md) |

## Meta surface — `find`

The `find` meta-tool is the LLM's primary entry point for public-service read operations. It is fetch-only: the backend performs adapter discovery internally and injects candidate `tool_id` values into the system prompt, then the model calls `find({tool_id, params})`. Its active JSON Schema export is [`schemas/find.json`](./schemas/find.json).

For implementation details see [`src/ummaya/tools/lookup.py`](../../src/ummaya/tools/lookup.py) and the BM25 + dense hybrid retrieval backend under [`src/ummaya/tools/retrieval/`](../../src/ummaya/tools/retrieval/).

## Meta surface — `locate`

The `locate` meta-tool is the LLM's provider-specific entry point for public location resolution. The model chooses one of the injected locate adapter IDs and calls `locate({tool_id, params})`. Its active JSON Schema export is [`schemas/locate.json`](./schemas/locate.json), and the provider adapter schemas are listed in Matrix A.

For implementation details see [`src/ummaya/tools/location_adapters.py`](../../src/ummaya/tools/location_adapters.py) and backend helpers under [`src/ummaya/tools/geocoding/`](../../src/ummaya/tools/geocoding/).

## Conventions

- **English source text only** in all spec files. Korean appears only inside the bilingual "Search hints" section and inside Korean conversation snippets within "Worked example" — per [`AGENTS.md § Hard rules`](../../AGENTS.md) and [`Spec 1637 FR-021`](../../specs/1637-p6-docs-smoke/spec.md).
- **Permission tier classification** follows [Spec 033 (Permission v2 Spectrum)](../../specs/033-permission-v2-spectrum/spec.md). Tier 1 is fail-open public data, Tier 2 requires AAL2 identity, Tier 3 requires AAL3 plus gate.
- **Mock public-spec citations** are mandatory: every Mock-tier adapter cites a public document, URL, or KISA/government standard per memory `feedback_mock_evidence_based`.
- **Fail-closed defaults** (Constitution Principle II) are inherited from the source Pydantic envelopes — see each adapter's "Constraints" section for the explicit fail-closed rendering.
- **No new runtime dependencies** were introduced for this catalog (Spec 1637 FR-022); `scripts/build_schemas.py` uses stdlib + Pydantic v2 only.

## Out of scope for this catalog

- External plugin adapters published under `ummaya-plugin-store/<repo>` carry their own `README.ko.md` per the Spec 1636 plugin DX. Their docs live in the plugin repo, not here.
- OPAQUE-tier mock stubs (`barocert/`, `npki_crypto/`, `omnione/` placeholder packages) have no entries here per the [Mock-vs-Scenario rule](../scenarios/README.md) — they belong in `docs/scenarios/`.
- Live API regression coverage is `@pytest.mark.live` skipped by default; this catalog documents fixture-replay behavior only.
