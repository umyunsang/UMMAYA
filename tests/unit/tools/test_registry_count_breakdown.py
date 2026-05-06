# SPDX-License-Identifier: Apache-2.0
"""T035 — Registry count breakdown assertion (SC-003).

Boots the registry and asserts the four-surface count breakdown from spec.md SC-003:
  - Main ToolRegistry: 40 entries (12 Live + 5 MVP-surface + 4 lookup mocks + 19 bridge wrappers)
  - kosmos.primitives.verify._VERIFY_ADAPTERS: 10 families
  - kosmos.primitives.submit._ADAPTER_REGISTRY: 5 families
  - kosmos.primitives.subscribe._SUBSCRIBE_ADAPTERS: 3 families

Test FAILS if any count is off-by-one.

Canonical counts from spec.md SC-003 and tasks.md Phase 0 research.
If these assertions fail with an unexpected count, REPORT the discrepancy —
do NOT silently adjust the expected values.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Main ToolRegistry count — 40 total
# ---------------------------------------------------------------------------
# Epic η #2298 — extended from 16 to 19 by adding `verify` / `submit` /
# `subscribe` to mvp_surface as `is_core=True` GovAPITool entries (FR-021).
# Without these, the LLM cannot emit the verify→lookup→submit chain because
# `registry.export_core_tools_openai()` only returned [resolve_location, lookup].
# The 3 new entries are the canonical primitives, not new agency adapters.

# Epic ζ #2297 path B (live smoke 2026-04-30 follow-up) — extended from 19 to 37
# by adding 18 non-core mock adapters via discovery_bridge:
#   - 10 verify family wrappers (mock_verify_module_{modid,kec,geumyung,
#     simple_auth,any_id_sso} + mock_verify_{gongdong,geumyung,ganpyeon,
#     mobile_id,mydata}_*)
#   - 6 submit wrappers (mock_submit_module_{hometax_taxreturn,gov24_minwon,
#     public_mydata_action} + mock_traffic_fine_pay_v1 +
#     mock_koroad_driver_fitness_reservation_v1 + mock_welfare_application_submit_v1)
#   - 3 subscribe wrappers (mock_cbs_disaster_v1 + mock_rest_pull_tick_v1 +
#     mock_rss_public_notices_v1)
# These wrappers are registered with is_core=False so the LLM's primary tool list
# stays at 5 primitives + lookup-class Live; they participate in lookup(mode="search")
# BM25 corpus so verify/submit/subscribe candidates surface for citizen queries
# (the gap that blocked η T011 + ζ T018 live smoke runs).
# CIV-001 real-use audit added one Gov24 lookup mock for the move-in dependent
# sequence, bringing the main registry to 38 while primitive sub-registries stayed
# unchanged.
# The 2026-05-05 full target-state real-use audit added one read-only national
# AX bundle discovery mock so opaque-but-policy-mandated domains still produce
# a lookup grounding step before privileged submit/subscribe routing.
# MOB-001 real-use audit added a KOROAD driver fitness-test reservation submit
# mock so mobility requests can produce a distinct reservation submit before
# traffic-fine payment / subscription.
_EXPECTED_MAIN_REGISTRY_COUNT = 40

_EXPECTED_MAIN_REGISTRY_BREAKDOWN = {
    "live_adapters": 12,  # 12 Live: koroad ×2, kma ×6, hira ×1, nfa ×1, nmc ×1, mohw ×1
    "mvp_surface": 2,  # lookup + resolve_location (main-verb surface)
    "lookup_mocks": 4,  # Hometax simplified + Gov24 certificate + move-in + AX bundle
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
    }
)

_EXPECTED_MVP_SURFACE_IDS = frozenset(
    {"lookup", "resolve_location", "verify", "submit", "subscribe"}
)

_EXPECTED_LOOKUP_MOCK_IDS = frozenset(
    {
        "mock_lookup_module_hometax_simplified",
        "mock_lookup_module_gov24_certificate",
        "mock_lookup_module_gov24_movein_sequence",
        "mock_lookup_module_national_ax_bundle",
    }
)


def test_main_registry_total_count() -> None:
    """Main ToolRegistry must have the canonical entry count after register_all_tools()."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

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
    """All 12 expected Live tool IDs must be registered in the main ToolRegistry."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

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
    """The 2 MVP-surface tool IDs (lookup, resolve_location) must be registered."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

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
    """The lookup mock IDs must be registered in the main ToolRegistry."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

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
# Verify sub-registry count — 10 families
# ---------------------------------------------------------------------------

_EXPECTED_VERIFY_COUNT = 10

_EXPECTED_VERIFY_FAMILIES = frozenset(
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
    }
)


def test_verify_adapter_registry_count() -> None:
    """kosmos.primitives.verify._VERIFY_ADAPTERS must have exactly 10 families."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

    actual = len(_VERIFY_ADAPTERS)
    assert actual == _EXPECTED_VERIFY_COUNT, (
        f"verify._VERIFY_ADAPTERS count mismatch: expected {_EXPECTED_VERIFY_COUNT}, "
        f"got {actual}. "
        f"Registered families: {sorted(_VERIFY_ADAPTERS.keys())}"
    )


def test_verify_adapter_registry_families() -> None:
    """All 10 expected verify family keys must be present in _VERIFY_ADAPTERS."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

    registered = frozenset(_VERIFY_ADAPTERS.keys())
    missing = _EXPECTED_VERIFY_FAMILIES - registered
    assert not missing, (
        f"Missing verify families in _VERIFY_ADAPTERS: {missing}. Registered: {sorted(registered)}"
    )

    extra = registered - _EXPECTED_VERIFY_FAMILIES
    assert not extra, (
        f"Unexpected extra verify families in _VERIFY_ADAPTERS: {extra}. "
        f"Expected only: {sorted(_EXPECTED_VERIFY_FAMILIES)}"
    )


def test_verify_digital_onepass_not_in_registry() -> None:
    """digital_onepass must NOT be in _VERIFY_ADAPTERS (FR-004 deletion guard)."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.verify import _VERIFY_ADAPTERS

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
# Submit sub-registry count — 6 adapters
# ---------------------------------------------------------------------------

_EXPECTED_SUBMIT_COUNT = 6

_EXPECTED_SUBMIT_IDS = frozenset(
    {
        # 3 existing / real-use mock submit adapters (retrofitted, pre-delegation)
        "mock_traffic_fine_pay_v1",
        "mock_koroad_driver_fitness_reservation_v1",
        "mock_welfare_application_submit_v1",
        # 3 new delegation-aware (Epic ε)
        "mock_submit_module_hometax_taxreturn",
        "mock_submit_module_gov24_minwon",
        "mock_submit_module_public_mydata_action",
    }
)


def test_submit_adapter_registry_count() -> None:
    """kosmos.primitives.submit._ADAPTER_REGISTRY must have exactly 6 entries."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.submit import _ADAPTER_REGISTRY

    actual = len(_ADAPTER_REGISTRY)
    assert actual == _EXPECTED_SUBMIT_COUNT, (
        f"submit._ADAPTER_REGISTRY count mismatch: expected {_EXPECTED_SUBMIT_COUNT}, "
        f"got {actual}. "
        f"Registered IDs: {sorted(_ADAPTER_REGISTRY.keys())}"
    )


def test_submit_adapter_registry_ids() -> None:
    """All 6 expected submit adapter IDs must be present in _ADAPTER_REGISTRY."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.submit import _ADAPTER_REGISTRY

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
# Subscribe sub-registry count — 3 adapters
# ---------------------------------------------------------------------------

_EXPECTED_SUBSCRIBE_COUNT = 3

_EXPECTED_SUBSCRIBE_IDS = frozenset(
    {
        "mock_cbs_disaster_v1",
        "mock_rest_pull_tick_v1",
        "mock_rss_public_notices_v1",
    }
)


def test_subscribe_adapter_registry_count() -> None:
    """kosmos.primitives.subscribe._SUBSCRIBE_ADAPTERS must have exactly 3 entries."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.subscribe import _SUBSCRIBE_ADAPTERS

    actual = len(_SUBSCRIBE_ADAPTERS)
    assert actual == _EXPECTED_SUBSCRIBE_COUNT, (
        f"subscribe._SUBSCRIBE_ADAPTERS count mismatch: expected {_EXPECTED_SUBSCRIBE_COUNT}, "
        f"got {actual}. "
        f"Registered IDs: {sorted(_SUBSCRIBE_ADAPTERS.keys())}"
    )


def test_subscribe_adapter_registry_ids() -> None:
    """All 3 expected subscribe adapter IDs must be present in _SUBSCRIBE_ADAPTERS."""
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.subscribe import _SUBSCRIBE_ADAPTERS

    registered = frozenset(_SUBSCRIBE_ADAPTERS.keys())
    missing = _EXPECTED_SUBSCRIBE_IDS - registered
    assert not missing, (
        f"Missing subscribe adapter IDs in _SUBSCRIBE_ADAPTERS: {missing}. "
        f"Registered: {sorted(registered)}"
    )

    extra = registered - _EXPECTED_SUBSCRIBE_IDS
    assert not extra, (
        f"Unexpected extra subscribe adapter IDs in _SUBSCRIBE_ADAPTERS: {extra}. "
        f"Expected only: {sorted(_EXPECTED_SUBSCRIBE_IDS)}"
    )


# ---------------------------------------------------------------------------
# Cross-surface summary — all four counts in one shot
# ---------------------------------------------------------------------------


def test_all_four_surface_counts_match_canonical() -> None:
    """Cross-surface guard: all four registry counts match the SC-003 canonical breakdown.

    This is the single-test summary that must stay green for SC-003 compliance.
    If it fails, run the individual count tests above to identify which surface drifted.
    """
    import kosmos.tools.mock  # noqa: F401 — trigger side-effect registration
    from kosmos.primitives.submit import _ADAPTER_REGISTRY as submit_reg  # noqa: N811
    from kosmos.primitives.subscribe import _SUBSCRIBE_ADAPTERS as subscribe_reg  # noqa: N811
    from kosmos.primitives.verify import _VERIFY_ADAPTERS as verify_reg  # noqa: N811
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.register_all import register_all_tools
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    counts = {
        "main_registry": len(registry),
        "verify_families": len(verify_reg),
        "submit_adapters": len(submit_reg),
        "subscribe_adapters": len(subscribe_reg),
    }
    expected = {
        # Epic η #2298 FR-021 — main_registry extended from 16 to 19 by adding
        # verify / submit / subscribe primitive surfaces to mvp_surface so the
        # LLM sees them in registry.export_core_tools_openai().
        # Epic ζ #2297 path B (live smoke 2026-04-30) — main_registry extended
        # from 19 to 37 by discovery_bridge bridging 18 non-core mock adapters,
        # then to 38 by adding the Gov24 move-in dependent-sequence lookup mock,
        # then to 39 by adding the national AX bundle grounding lookup mock,
        # then to 40 by adding the KOROAD fitness reservation submit mock
        # (10 verify + 6 submit + 3 subscribe family wrappers) into the BM25
        # corpus so lookup(mode="search") surfaces them. is_core=False so the
        # primary LLM tool list stays at 5 primitives + lookup-class Live.
        "main_registry": 40,
        "verify_families": 10,
        "submit_adapters": 6,
        "subscribe_adapters": 3,
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
