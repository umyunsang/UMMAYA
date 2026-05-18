# SPDX-License-Identifier: Apache-2.0
"""T035 — Registry count breakdown assertion (SC-003).

Boots the registry and asserts the active count breakdown from spec.md SC-003:
  - Main ToolRegistry: 68 entries
  - ummaya.primitives.verify._VERIFY_ADAPTERS: 10 families
  - ummaya.primitives.submit._ADAPTER_REGISTRY: 5 families

Test FAILS if any count is off-by-one.

Canonical counts from spec.md SC-003 and tasks.md Phase 0 research.
If these assertions fail with an unexpected count, REPORT the discrepancy —
do NOT silently adjust the expected values.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Main ToolRegistry count — 68 total
# ---------------------------------------------------------------------------
# Epic η #2298 — extended from 16 to 18 by adding `check` / `send`
# to mvp_surface as `is_core=True` GovAPITool entries (FR-021).
# Without these, the LLM cannot emit the check→find→send chain because
# `registry.export_core_tools_openai()` only returned [locate, find].
# The 3 new entries are the canonical primitives, not new agency adapters.

# Epic ζ #2297 path B (live smoke 2026-04-30 follow-up) — extended from 18 to 33
# by adding 15 non-core mock adapters via discovery_bridge:
#   - 10 verify family wrappers (mock_verify_module_{modid,kec,geumyung,
#     simple_auth,any_id_sso} + mock_verify_{gongdong,geumyung,ganpyeon,
#     mobile_id,mydata}_*)
#   - 5 submit wrappers (mock_submit_module_{hometax_taxreturn,gov24_minwon,
#     public_mydata_action} + mock_traffic_fine_pay_v1 + mock_welfare_application_submit_v1)
# These wrappers are registered with is_core=False so the LLM's primary tool list
# stays at active primitives + find-class Live; they participate in find(mode="search")
# BM25 corpus so verify/submit candidates surface for citizen queries
# (the gap that blocked η T011 + ζ T018 live smoke runs).
# Agentic locate refactor — extended from 33 to 38 by registering five
# provider-specific locate adapters instead of hiding them behind a fused
# locate primitive.
# Spec #2797 — extended from 38 to 52 by registering fourteen direct-curl
# verified public-data adapters under src/ummaya/tools/verified_data_go_kr/.
# Spec #2798 — extended from 52 to 68 by registering sixteen additional
# approved live public-data adapters from the 2026-05-16 direct evidence batch.
# Spec live-mobileid-check — extended from 68 to 69 by registering one explicit
# live MobileID check adapter.
_EXPECTED_MAIN_REGISTRY_COUNT = 69

_EXPECTED_MAIN_REGISTRY_BREAKDOWN = {
    "live_adapters": 43,  # 12 existing Live + 30 verified public-data + 1 MobileID check
    "mvp_surface": 4,  # find + locate + check + send (main-verb surface)
    "locate_adapters": 5,  # kakao/juso/provider-specific locate adapters
    "lookup_mocks": 2,  # mock_lookup_module_hometax_simplified + mock_lookup_module_gov24_certificate  # noqa: E501
}

_EXPECTED_LIVE_TOOL_IDS = frozenset(
    {
        "koroad_accident_hazard_search",
        "koroad_accident_search",
        "kma_current_observation",
        "kma_forecast_fetch",
        "kma_pre_warning",
        "kma_short_term_forecast",
        "kma_ultra_short_term_forecast",
        "kma_weather_alert_status",
        "hira_hospital_search",
        "nfa_emergency_info_service",
        "nmc_emergency_search",
        "mohw_welfare_eligibility_search",
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
        "live_verify_mobile_id",
    }
)

_EXPECTED_MVP_SURFACE_IDS = frozenset({"find", "locate", "check", "send"})

_EXPECTED_LOOKUP_MOCK_IDS = frozenset(
    {
        "mock_lookup_module_hometax_simplified",
        "mock_lookup_module_gov24_certificate",
    }
)


def test_main_registry_total_count() -> None:
    """Main ToolRegistry must have exactly 68 entries after register_all_tools()."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    actual = len(registry)
    assert actual == _EXPECTED_MAIN_REGISTRY_COUNT, (
        f"Main ToolRegistry count mismatch: expected {_EXPECTED_MAIN_REGISTRY_COUNT}, "
        f"got {actual}. "
        f"Registered tool IDs: {sorted(registry._tools.keys())}"
    )


def test_main_registry_live_tool_ids_present() -> None:
    """All 42 expected Live tool IDs must be registered in the main ToolRegistry."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    registered_ids = frozenset(registry._tools.keys())
    missing = _EXPECTED_LIVE_TOOL_IDS - registered_ids
    assert not missing, (
        f"Missing Live tool IDs in main ToolRegistry: {missing}. "
        f"Registered: {sorted(registered_ids)}"
    )


def test_main_registry_mvp_surface_ids_present() -> None:
    """The 4 MVP-surface tool IDs (find, locate, check, send) must be registered."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    registered_ids = frozenset(registry._tools.keys())
    missing = _EXPECTED_MVP_SURFACE_IDS - registered_ids
    assert not missing, (
        f"Missing MVP-surface tool IDs in main ToolRegistry: {missing}. "
        f"Registered: {sorted(registered_ids)}"
    )


def test_main_registry_lookup_mock_ids_present() -> None:
    """The 2 new lookup mock IDs must be registered in the main ToolRegistry."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    registered_ids = frozenset(registry._tools.keys())
    missing = _EXPECTED_LOOKUP_MOCK_IDS - registered_ids
    assert not missing, (
        f"Missing lookup mock IDs in main ToolRegistry: {missing}. "
        f"Registered: {sorted(registered_ids)}"
    )


# ---------------------------------------------------------------------------
# Verify sub-registry count — 10 family adapters + 1 explicit live tool adapter
# ---------------------------------------------------------------------------

_EXPECTED_VERIFY_COUNT = 11

_EXPECTED_VERIFY_ADAPTER_KEYS = frozenset(
    {
        # 5 existing (retrofitted)
        "ganpyeon_injeung",
        "geumyung_injeungseo",
        "gongdong_injeungseo",
        "mobile_id",
        "mydata",
        # 5 new (Epic ε)
        "simple_auth_module",
        "modid",
        "kec",
        "geumyung_module",
        "any_id_sso",
        # Explicit live tool adapter sharing family=mobile_id.
        "live_verify_mobile_id",
    }
)


def test_verify_adapter_registry_count() -> None:
    """ummaya.primitives.verify._VERIFY_ADAPTERS must have the canonical adapter keys."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    actual = len(_VERIFY_ADAPTERS)
    assert actual == _EXPECTED_VERIFY_COUNT, (
        f"verify._VERIFY_ADAPTERS count mismatch: expected {_EXPECTED_VERIFY_COUNT}, "
        f"got {actual}. "
        f"Registered families: {sorted(_VERIFY_ADAPTERS.keys())}"
    )


def test_verify_adapter_registry_families() -> None:
    """All expected verify adapter keys must be present in _VERIFY_ADAPTERS."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    registered = frozenset(_VERIFY_ADAPTERS.keys())
    missing = _EXPECTED_VERIFY_ADAPTER_KEYS - registered
    assert not missing, (
        f"Missing verify families in _VERIFY_ADAPTERS: {missing}. Registered: {sorted(registered)}"
    )

    extra = registered - _EXPECTED_VERIFY_ADAPTER_KEYS
    assert not extra, (
        f"Unexpected extra verify families in _VERIFY_ADAPTERS: {extra}. "
        f"Expected only: {sorted(_EXPECTED_VERIFY_ADAPTER_KEYS)}"
    )


def test_verify_digital_onepass_not_in_registry() -> None:
    """digital_onepass must NOT be in _VERIFY_ADAPTERS (FR-004 deletion guard)."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    for family_key in _VERIFY_ADAPTERS:
        assert "digital_onepass" not in family_key, (
            f"FR-004 violation: digital_onepass found in _VERIFY_ADAPTERS "
            f"under key {family_key!r}. It must be deleted."
        )
        assert "onepass" not in family_key, (
            f"FR-004 violation: 'onepass' found in _VERIFY_ADAPTERS key {family_key!r}. "
            f"It must be deleted."
        )


# ---------------------------------------------------------------------------
# Submit sub-registry count — 5 adapters
# ---------------------------------------------------------------------------

_EXPECTED_SUBMIT_COUNT = 5

_EXPECTED_SUBMIT_IDS = frozenset(
    {
        # 2 existing (retrofitted, pre-delegation)
        "mock_traffic_fine_pay_v1",
        "mock_welfare_application_submit_v1",
        # 3 new delegation-aware (Epic ε)
        "mock_submit_module_hometax_taxreturn",
        "mock_submit_module_gov24_minwon",
        "mock_submit_module_public_mydata_action",
    }
)


def test_submit_adapter_registry_count() -> None:
    """ummaya.primitives.submit._ADAPTER_REGISTRY must have exactly 5 entries."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.submit import _ADAPTER_REGISTRY

    actual = len(_ADAPTER_REGISTRY)
    assert actual == _EXPECTED_SUBMIT_COUNT, (
        f"submit._ADAPTER_REGISTRY count mismatch: expected {_EXPECTED_SUBMIT_COUNT}, "
        f"got {actual}. "
        f"Registered IDs: {sorted(_ADAPTER_REGISTRY.keys())}"
    )


def test_submit_adapter_registry_ids() -> None:
    """All 5 expected submit adapter IDs must be present in _ADAPTER_REGISTRY."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.submit import _ADAPTER_REGISTRY

    registered = frozenset(_ADAPTER_REGISTRY.keys())
    missing = _EXPECTED_SUBMIT_IDS - registered
    assert not missing, (
        f"Missing submit adapter IDs in _ADAPTER_REGISTRY: {missing}. "
        f"Registered: {sorted(registered)}"
    )

    extra = registered - _EXPECTED_SUBMIT_IDS
    assert not extra, (
        f"Unexpected extra submit adapter IDs in _ADAPTER_REGISTRY: {extra}. "
        f"Expected only: {sorted(_EXPECTED_SUBMIT_IDS)}"
    )


# ---------------------------------------------------------------------------
# Cross-surface summary — active counts in one shot
# ---------------------------------------------------------------------------


def test_all_active_surface_counts_match_canonical() -> None:
    """Cross-surface guard: active registry counts match the SC-003 canonical breakdown.

    This is the single-test summary that must stay green for SC-003 compliance.
    If it fails, run the individual count tests above to identify which surface drifted.
    """
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.submit import _ADAPTER_REGISTRY as submit_reg  # noqa: N811
    from ummaya.primitives.verify import _VERIFY_ADAPTERS as verify_reg  # noqa: N811
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    counts = {
        "main_registry": len(registry),
        "verify_families": len(verify_reg),
        "submit_adapters": len(submit_reg),
    }
    expected = {
        # Epic η #2298 FR-021 — main_registry extended from 16 to 18 by adding
        # verify / submit primitive surfaces to mvp_surface so the
        # LLM sees them in registry.export_core_tools_openai().
        # Epic ζ #2297 path B (live smoke 2026-04-30) — main_registry extended
        # from 18 to 33 by discovery_bridge bridging 15 non-core mock adapters
        # (10 verify + 5 submit family wrappers) into the BM25
        # corpus so find(mode="search") surfaces them. is_core=False so the
        # primary LLM tool list stays at active primitives + find-class Live.
        # Locate-provider adapters add five first-class registry entries.
        # Spec #2798 adds sixteen approved live data.go.kr adapters, bringing
        # the main ToolRegistry from 52 to 68. The MobileID live check adds one
        # more adapter key and one more ToolRegistry entry.
        "main_registry": 69,
        "verify_families": 11,
        "submit_adapters": 5,
    }

    failures = []
    for surface, exp in expected.items():
        actual = counts[surface]
        if actual != exp:
            failures.append(f"  {surface}: expected {exp}, got {actual}")

    assert not failures, (
        "SC-003 canonical count breakdown mismatch:\n"
        + "\n".join(failures)
        + f"\n\nFull counts: {counts}"
    )
