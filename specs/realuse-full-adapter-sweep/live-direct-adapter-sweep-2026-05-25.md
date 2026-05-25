# Live Direct Adapter Sweep - 2026-05-25

Generated: `2026-05-25T21:51:20.819899+09:00`

Scope: live adapters only; `mock_` adapters, root primitive wrappers, and `send`/`check` side-effect surfaces excluded.

## Summary

- `pass`: 122
- `upstream_error`: 3

## Failures / Non-Pass

- `kma_apihub_amm_iwxxm_service_get_metar`: `upstream_error` - Adapter 'kma_apihub_amm_iwxxm_service_get_metar' raised an exception during upstream call. Detail: ToolExecutionError: KMA APIHub error: operation='AmmIwxxmService/getMetar' resultCode='01' resultMsg='APPLICATION_ERROR'.
- `moj_stay_person_counter`: `upstream_error` - Adapter 'moj_stay_person_counter' raised an exception during upstream call. Detail: HTTPStatusError: Server error '502 Bad Gateway' for url 'http://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter?Service
- `moj_village_lawyer_lookup`: `upstream_error` - Adapter 'moj_village_lawyer_lookup' raised an exception during upstream call. Detail: HTTPStatusError: Server error '502 Bad Gateway' for url 'http://apis.data.go.kr/1270000/mojmabyun/mabyun?serviceKey=***&pageNo=1&numOf

## Follow-Up Probes

- `moj_village_lawyer_lookup`: direct `curl` after the sweep returned HTTP 200 XML on both HTTP and HTTPS gateway URLs, `resultCode=0`, `totalCount=3008`. A sequential `ToolExecutor.invoke()` retry returned `LookupCollection`, `total_count=3008`.
- `moj_stay_person_counter`: direct `curl` after the sweep returned HTTP 200 XML on both HTTP and HTTPS gateway URLs, `resultCode=0`, `totalCount=3`. A sequential `ToolExecutor.invoke()` retry returned `LookupCollection`, `total_count=3`.
- `kma_apihub_amm_iwxxm_service_get_metar`: direct `curl` against the official KMA APIHub URL returned HTTP 200 XML but API payload `resultCode=01`, `resultMsg=APPLICATION_ERROR` for `RKSI`, `RKSS`, and `RKPK`. This remains an upstream APIHub response, not an adapter schema failure.

## Passes

- `airkorea_ctprvn_air_quality` (KECO/find): pass total=40
- `bfc_funeral_area_fee` (BFC/find): pass total=4
- `ccourt_publication_documents` (CCOURT/find): pass total=5
- `djtc_subway_segment_fare_time_check` (DJTC/find): pass total=1
- `fsc_corporate_finance_summary` (FSC/find): pass total=2
- `ftc_large_group_status` (FTC/find): pass total=71
- `ftc_public_ym_list` (FTC/find): pass total=1
- `gyeryong_assistive_device_charging_place_locate` (GYERYONG/find): pass total=7
- `hira_hospital_search` (HIRA/find): pass total=306
- `hira_medical_institution_detail` (HIRA/find): pass total=0
- `juso_adm_cd_lookup` (UMMAYA/locate): pass
- `kakao_address_search` (UMMAYA/locate): pass
- `kakao_coord_to_region` (UMMAYA/locate): pass
- `kakao_keyword_search` (UMMAYA/locate): pass
- `kcue_finance_regional_tuition` (KCUE/find): pass total=20
- `kcue_student_regional_foreign` (KCUE/find): pass total=20
- `kepco_contract_power_usage` (KEPCO/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2aapps_all` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2aapps_area` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2acla_all` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2acla_area` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2acld_all` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2acld_area` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2adcoew_all` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2adcoew_area` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2afog_all` (KMA/find): pass total=1
- `kma_apihub_cloud_satlit_info_service_get_gk2afog_area` (KMA/find): pass total=1
- `kma_apihub_eqk_info_service_get_eqk_msg` (KMA/find): pass total=1
- `kma_apihub_eqk_info_service_get_eqk_msg_list` (KMA/find): pass total=1
- `kma_apihub_kimmodel_info_service_get_kimldaps_unis_all` (KMA/find): pass total=0
- `kma_apihub_kimmodel_info_service_get_kimldaps_unis_area` (KMA/find): pass total=0
- `kma_apihub_kimmodel_info_service_get_kimrdaps_unis_all` (KMA/find): pass total=0
- `kma_apihub_kimmodel_info_service_get_kimrdaps_unis_area` (KMA/find): pass total=0
- `kma_apihub_sea_mtly_info_service_get_buoy_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_buoy_mm_sumry` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_buoy_mm_sumry2` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_daily_buoy` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_daily_lhaws` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_daily_wave_buoy` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_lhaws_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_lhaws_mm_sumry` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_lhaws_mm_sumry2` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_note` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_obs_open_year` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_wave_buoy_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_wave_buoy_mm_sumry` (KMA/find): pass total=1
- `kma_apihub_sea_mtly_info_service_get_wave_buoy_mm_sumry2` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_air_note` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_daily_air_data` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_daily_wthr_data` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_mm_sumry` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_mm_sumry2` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_note` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_get_sfc_stn_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sfc_mtly_info_service_getr_air_stn_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_air_stn_info` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_air_stn_info2` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_air_stn_info3` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_avg_ta_anamaly` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_note` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_rn_anamaly` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_sfc_stn_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_stn_phnmn_data` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_stn_phnmn_data2` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_stn_phnmn_data3` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_typhoon_list` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_year_sumry` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_get_year_sumry2` (KMA/find): pass total=1
- `kma_apihub_sfc_yearly_info_service_getr_air_stn_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_max_wind` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_note` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_std_isbrsf_value` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_ta_hm_level` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_upp_lst_tbl` (KMA/find): pass total=1
- `kma_apihub_upp_mtly_info_service_get_wind_level` (KMA/find): pass total=1
- `kma_apihub_vilage_fcst_info_service_2_0_get_fcst_version` (KMA/find): pass total=1
- `kma_apihub_vilage_fcst_info_service_2_0_get_ultra_srt_fcst` (KMA/find): pass total=60
- `kma_apihub_vilage_fcst_info_service_2_0_get_ultra_srt_ncst` (KMA/find): pass total=8
- `kma_apihub_vilage_fcst_info_service_2_0_get_vilage_fcst` (KMA/find): pass total=1016
- `kma_apihub_vilage_fcst_msg_service_get_land_fcst` (KMA/find): pass total=9
- `kma_apihub_vilage_fcst_msg_service_get_sea_fcst` (KMA/find): pass total=9
- `kma_apihub_vilage_fcst_msg_service_get_wthr_situation` (KMA/find): pass total=1
- `kma_apihub_wthr_radar_info_service_get_comp_cappi_qcd_all` (KMA/find): pass total=1
- `kma_apihub_wthr_radar_info_service_get_comp_cappi_qcd_area` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_ir_all` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_ir_area` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_nr_all` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_nr_area` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_sw_all` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_sw_area` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_vi_all` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_vi_area` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_wv_all` (KMA/find): pass total=1
- `kma_apihub_wthr_satlit_info_service_get_gk2a_wv_area` (KMA/find): pass total=1
- `kma_current_observation` (KMA/find): pass
- `kma_forecast_fetch` (KMA/find): pass
- `kma_pre_warning` (KMA/find): pass total=8
- `kma_short_term_forecast` (KMA/find): pass total=1016
- `kma_ultra_short_term_forecast` (KMA/find): pass total=60
- `kma_weather_alert_status` (KMA/find): pass total=8
- `koroad_accident_hazard_search` (KOROAD/find): pass total=3
- `koroad_accident_search` (KOROAD/find): pass total=None
- `ksd_financial_term_lookup` (KSD/find): pass total=26
- `mfds_easy_drug_info_lookup` (MFDS/find): pass total=7
- `mof_ocean_water_quality_check` (MOF/find): pass total=294857
- `mohw_welfare_eligibility_search` (MOHW/find): pass total=72
- `mois_emergency_call_box_lookup` (MOIS/find): pass total=22464
- `mois_facility_safety_info_lookup` (MOIS/find): pass total=43913
- `mpm_public_job_lookup` (MPM/find): pass total=57121
- `msit_business_announcement_lookup` (MSIT/find): pass total=4129
- `mss_sme_support_notice_lookup` (MSS/find): pass total=200
- `nfa_emergency_info_service` (NFA/find): pass total=1351
- `nmc_aed_site_locate` (NMC/find): pass total=484
- `nmc_emergency_search` (NMC/find): pass total=1
- `pps_bid_public_info` (PPS/find): pass total=1
- `pps_shopping_mall_product_lookup` (PPS/find): pass total=0
- `reb_real_estate_stat_table` (REB/find): pass total=738
- `sgis_adm_cd_lookup` (UMMAYA/locate): pass
- `tago_bus_arrival_search` (MOLIT/find): pass total=4
- `tago_bus_location_search` (MOLIT/find): pass total=5
- `tago_bus_route_search` (MOLIT/find): pass total=17
- `tago_bus_station_search` (MOLIT/find): pass total=1
