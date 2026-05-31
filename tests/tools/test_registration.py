# SPDX-License-Identifier: Apache-2.0
"""Tests for central tool registration entry point (T039)."""

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry


class TestToolRegistration:
    """Verify register_all_tools() wires all adapters correctly."""

    def test_registers_all_tools(self) -> None:
        """All tools are registered after calling register_all_tools.

        Count history (Epic #507):
          T049  —2 (address_to_region, address_to_grid removed)
          Stage 3 (T033/T048/T056)  +3 (nmc_emergency_search,
            kma_forecast_fetch, hira_hospital_search)
          Phase 2 (spec 029)  +2 (nfa_emergency_info_service,
            mohw_welfare_eligibility_search)
        Total: 15 (= 2 MVP core + 8 legacy adapters + 3 seed adapters + 2 Phase 2 stubs).
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        # Spec 2296 SC-003: 12 Live + 2 MVP-surface (resolve_location, lookup)
        # + 2 lookup mocks (mock_lookup_module_hometax_simplified,
        # mock_lookup_module_gov24_certificate) = 16
        # Epic η #2298 FR-021: + 2 primitive surfaces (verify, submit) = 18.
        # Required so the LLM can emit the
        # citizen-OPAQUE chain via OpenAI tool_calls schema.
        # Epic ζ #2297 path B (live smoke 2026-04-30): + 15 non-core mock
        # adapter wrappers (10 verify + 5 submit via discovery_bridge) = 33.
        # Locate adapter split: + 5 first-class locate provider adapters
        # (Kakao address/keyword/coord-region, JUSO adm_cd, SGIS adm_cd) = 38.
        # Spec #2797 verified public-data wave: + 14 direct-curl verified
        # data.go.kr/LINK adapters = 52.
        # Spec #2798 live expansion: + 16 approved data.go.kr adapters = 68.
        # Spec #2799 KFTC OpenGiro: + 2 fixture-backed send adapters = 70.
        # Spec #2800 KMA APIHub structured typ02/openApi wrappers: +77 active
        # plus 5 non-structured URL wrappers and TAGO route-station lookup =
        # 153. Upstream-unavailable, retired, and approval-pending APIHub
        # operations stay cataloged but are not registered as callable tools.
        # is_core=False so the LLM's primary tool list stays at active
        # primitives + lookup-class; these participate in
        # lookup(mode="search") BM25 corpus only.
        assert len(registry) == 153

    def test_tool_ids_present(self) -> None:
        """Each expected tool_id is in the registry.

        Note: address_to_region and address_to_grid were removed in T049 (Epic
        #507).  Administrative code and grid resolution are now backend-only
        (juso/sgis helpers and latlon_to_lcc respectively).
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        expected = {
            # MVP LLM-visible core surface (T028)
            "locate",
            "find",
            # Locate provider adapters
            "kakao_address_search",
            "kakao_keyword_search",
            "kakao_coord_to_region",
            "juso_adm_cd_lookup",
            "sgis_adm_cd_lookup",
            # Adapters
            "koroad_accident_search",
            "koroad_accident_hazard_search",
            "kma_weather_alert_status",
            "kma_current_observation",
            # Stage 3 seed adapters (Epic #507)
            "nmc_emergency_search",
            "kma_forecast_fetch",
            "hira_hospital_search",
            # Phase 2 adapters (spec 029)
            "nfa_emergency_info_service",
            "mohw_welfare_eligibility_search",
            # Spec #2797 verified public-data adapters
            "fsc_corporate_finance_summary",
            "airkorea_ctprvn_air_quality",
            "ftc_large_group_status",
            "ftc_public_ym_list",
            "tago_bus_route_search",
            "tago_bus_arrival_search",
            "tago_bus_location_search",
            "tago_bus_station_search",
            "kepco_contract_power_usage",
            "pps_bid_public_info",
            "reb_real_estate_stat_table",
            "bfc_funeral_area_fee",
            "kcue_finance_regional_tuition",
            "kcue_student_regional_foreign",
            # Spec #2798 additional approved public-data adapters
            "moj_village_lawyer_lookup",
            "mois_facility_safety_info_lookup",
            "hira_medical_institution_detail",
            "mois_emergency_call_box_lookup",
            "djtc_subway_segment_fare_time_check",
            "gyeryong_assistive_device_charging_place_locate",
            "nmc_aed_site_locate",
            "mof_ocean_water_quality_check",
            "mfds_easy_drug_info_lookup",
            "mpm_public_job_lookup",
            "pps_shopping_mall_product_lookup",
            "ksd_financial_term_lookup",
            "mss_sme_support_notice_lookup",
            "ccourt_publication_documents",
            "moj_stay_person_counter",
            "msit_business_announcement_lookup",
            # Spec #2799 KFTC OpenGiro send adapters
            "mock_kftc_opengiro_bill_send_v1",
            "mock_kftc_opengiro_payment_send_v1",
            # Spec #2800 KMA APIHub structured + URL adapters
            "kma_apihub_url_air_metar_decoded",
            "kma_apihub_vilage_fcst_info_service_2_0_get_vilage_fcst",
            "kma_apihub_vilage_fcst_info_service_2_0_get_ultra_srt_fcst",
        }
        for tool_id in expected:
            assert tool_id in registry, f"{tool_id} not found in registry"

    def test_adapters_bound(self) -> None:
        """Each adapter tool has a corresponding adapter in the executor.

        Note: resolve_location and lookup are core surface tools — they are
        handled directly by the orchestrator and do NOT have executor adapters.
        Note: address_to_region and address_to_grid were removed in T049 (Epic
        #507) — they are no longer LLM-visible tools.
        """
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        expected = {
            "koroad_accident_search",
            "koroad_accident_hazard_search",
            "kma_weather_alert_status",
            "kma_current_observation",
            # Stage 3 seed adapters (Epic #507)
            "nmc_emergency_search",
            "kma_forecast_fetch",
            "hira_hospital_search",
            # Phase 2 adapters (spec 029)
            "nfa_emergency_info_service",
            "mohw_welfare_eligibility_search",
            # Spec #2797 verified public-data adapters
            "fsc_corporate_finance_summary",
            "airkorea_ctprvn_air_quality",
            "ftc_large_group_status",
            "ftc_public_ym_list",
            "tago_bus_route_search",
            "tago_bus_arrival_search",
            "tago_bus_location_search",
            "tago_bus_station_search",
            "kepco_contract_power_usage",
            "pps_bid_public_info",
            "reb_real_estate_stat_table",
            "bfc_funeral_area_fee",
            "kcue_finance_regional_tuition",
            "kcue_student_regional_foreign",
            # Spec #2798 additional approved public-data adapters
            "moj_village_lawyer_lookup",
            "mois_facility_safety_info_lookup",
            "hira_medical_institution_detail",
            "mois_emergency_call_box_lookup",
            "djtc_subway_segment_fare_time_check",
            "gyeryong_assistive_device_charging_place_locate",
            "nmc_aed_site_locate",
            "mof_ocean_water_quality_check",
            "mfds_easy_drug_info_lookup",
            "mpm_public_job_lookup",
            "pps_shopping_mall_product_lookup",
            "ksd_financial_term_lookup",
            "mss_sme_support_notice_lookup",
            "ccourt_publication_documents",
            "moj_stay_person_counter",
            "msit_business_announcement_lookup",
            # Spec #2800 KMA APIHub structured + URL adapters
            "kma_apihub_url_air_metar_decoded",
            "kma_apihub_vilage_fcst_info_service_2_0_get_vilage_fcst",
            "kma_apihub_vilage_fcst_info_service_2_0_get_ultra_srt_fcst",
        }
        for tool_id in expected:
            assert tool_id in executor._adapters, f"No adapter for {tool_id}"

    def test_no_import_errors(self) -> None:
        """register_all_tools completes without import errors."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        # Should not raise
        register_all_tools(registry, executor)

    def test_core_tools_include_mvp_surface(self) -> None:
        """resolve_location and lookup must appear in core_tools() (T028, FR-001)."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        core_ids = {t.id for t in registry.core_tools()}
        assert "locate" in core_ids
        assert "find" in core_ids

    def test_idempotent_fails_on_duplicate(self) -> None:
        """Calling register_all_tools twice raises DuplicateToolError."""
        from ummaya.tools.errors import DuplicateToolError

        registry = ToolRegistry()
        executor = ToolExecutor(registry)
        register_all_tools(registry, executor)
        with pytest.raises(DuplicateToolError):
            register_all_tools(registry, executor)
