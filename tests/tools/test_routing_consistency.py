# SPDX-License-Identifier: Apache-2.0
"""T033/T034/T035 — Routing consistency CI gate (Epic #1634 FR-006/007/008/014/020/028).

Load-bearing governance test: boot-time validation of the tool registry.
See specs/1634-tool-system-wiring/contracts/routing-consistency.md for the
full invariant list + failure-message format.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing_index import (
    RoutingIndex,
)

REPO_ROOT = Path(__file__).parent.parent.parent
SRC_TOOLS = REPO_ROOT / "src" / "ummaya" / "tools"


@pytest.fixture(scope="module")
def live_registry() -> tuple[ToolRegistry, RoutingIndex]:
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    routing_index = register_all_tools(registry, executor)
    return registry, routing_index


# ---------------------------------------------------------------------------
# Invariant 1 — Primitive declared
# Every registered GovAPITool MUST have non-None primitive.
# Failure message format:
#   "<tool_id>: invariant 1 (primitive declared) — primitive=None on registered adapter"
# ---------------------------------------------------------------------------


class TestInvariant1PrimitiveDeclared:
    def test_all_registered_adapters_declare_primitive(self, live_registry):
        """Every adapter in the live registry has a non-None primitive field."""
        registry, _ = live_registry
        for tool_id, tool in registry._tools.items():
            assert tool.primitive is not None, (
                f"{tool_id}: invariant 1 (primitive declared) — "
                f"primitive=None on registered adapter"
            )

    def test_all_primitives_within_closed_enum(self, live_registry):
        """Every declared primitive is one of the active reserved primitives."""
        valid_primitives = frozenset({"find", "locate", "send", "check"})
        registry, _ = live_registry
        for tool_id, tool in registry._tools.items():
            assert tool.primitive in valid_primitives, (
                f"{tool_id}: primitive={tool.primitive!r} is outside the active primitive "
                f"closed set {valid_primitives}"
            )


# ---------------------------------------------------------------------------
# Invariant 2 — Ministry in closed enum
# Pydantic enforces at construction; verify build_routing_index observes this
# by checking every registered tool has a valid ministry value.
# ---------------------------------------------------------------------------


class TestInvariant2MinistryClosedEnum:
    def test_routing_index_reflects_valid_ministry_on_all_adapters(self, live_registry):
        """build_routing_index() indexes adapters whose ministry was already
        validated by Pydantic at construction — verify by_tool_id contains
        only tools with non-empty ministry strings.
        """
        _, routing_index = live_registry
        for tool_id, tool in routing_index.by_tool_id.items():
            assert isinstance(tool.ministry, str) and tool.ministry, (
                f"{tool_id}: ministry is empty or None in routing index"
            )


# ---------------------------------------------------------------------------
# Invariant 3 — adapter_mode declared in mock subtree (CI-only file-path inspection)
# Every GovAPITool constructed under src/ummaya/tools/mock/* MUST set
# adapter_mode="mock" explicitly.
# ---------------------------------------------------------------------------


class TestInvariant3MockAdapterMode:
    def test_mock_subtree_adapters_declare_adapter_mode(self):
        """Every GovAPITool constructor in the mock/ subtree declares adapter_mode='mock'.

        Note: Current mock/* modules use AdapterRegistration (not GovAPITool) directly,
        so this check is vacuously satisfied. The guard protects against future drift
        where a mock module instantiates a GovAPITool without the explicit mode flag.
        """
        mock_dir = SRC_TOOLS / "mock"
        violations: list[str] = []

        for py_file in mock_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            source = py_file.read_text()
            if "GovAPITool(" not in source:
                continue
            # For every GovAPITool constructor in this file, adapter_mode="mock" MUST appear.
            # Use a balanced-paren scanner — the mock lookup adapters introduced by
            # Spec 2296 contain nested AdapterRealDomainPolicy(...) calls, so a simple
            # `\([^)]+\)` regex truncates the constructor at the first inner ')'.
            for ctor_start in [m.end() for m in re.finditer(r"GovAPITool\s*\(", source)]:
                depth = 1
                idx = ctor_start
                while idx < len(source) and depth > 0:
                    if source[idx] == "(":
                        depth += 1
                    elif source[idx] == ")":
                        depth -= 1
                    idx += 1
                ctor_block = source[ctor_start - 1 : idx]
                if (
                    'adapter_mode="mock"' not in ctor_block
                    and "adapter_mode='mock'" not in ctor_block
                ):
                    violations.append(
                        f"{py_file.relative_to(REPO_ROOT)}: GovAPITool constructed without "
                        f"adapter_mode='mock' — invariant 3 (mock subtree adapter_mode declared)"
                    )

        assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# Invariant 4 — Unique tool_id
# No two registered adapters may share tool_id.
# ---------------------------------------------------------------------------


class TestInvariant4UniqueToolId:
    def test_tool_ids_unique(self, live_registry):
        """No duplicate tool_id exists in the live registry."""
        registry, _ = live_registry
        ids = list(registry._tools.keys())
        assert len(ids) == len(set(ids)), (
            f"Duplicate tool_ids detected: {[x for x in ids if ids.count(x) > 1]}"
        )

    def test_routing_index_by_tool_id_matches_registry(self, live_registry):
        """RoutingIndex.by_tool_id is consistent with the registry's tool set."""
        registry, routing_index = live_registry
        assert frozenset(registry._tools.keys()) == frozenset(routing_index.by_tool_id.keys()), (
            "RoutingIndex.by_tool_id diverges from registry._tools"
        )


# ---------------------------------------------------------------------------
# Invariant 5 (compute_permission_tier) + Invariant 6 (auth_type/auth_level)
# REMOVED in Epic δ #2295 — auth_level / is_irreversible / _AUTH_TYPE_LEVEL_MAPPING
# deleted from GovAPITool as Spec 033 UMMAYA-invented residue (Constitution § II).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Check 7 — Tool list closure
# The Python-side registered tool set matches the active closed set.
# LLM-visible primitive names (find/locate/send/check) and auxiliary
# tools live on the TUI side and are validated by `bun test` CI.
# ---------------------------------------------------------------------------


class TestCheck7ToolListClosure:
    """The Python-side registered tool set matches the 52-entry registry.

    Divergence from this set indicates either an unauthorized addition or
    an inadvertent removal — both are CI failures.
    """

    EXPECTED_REGISTERED_TOOL_IDS: frozenset[str] = frozenset(
        {
            "locate",
            "find",
            "kakao_address_search",
            "kakao_keyword_search",
            "kakao_coord_to_region",
            "juso_adm_cd_lookup",
            "sgis_adm_cd_lookup",
            "koroad_accident_search",
            "koroad_accident_hazard_search",
            "kma_weather_alert_status",
            "kma_current_observation",
            "kma_short_term_forecast",
            "kma_ultra_short_term_forecast",
            "kma_pre_warning",
            "kma_forecast_fetch",
            "nmc_emergency_search",
            "hira_hospital_search",
            "nfa_emergency_info_service",
            "mohw_welfare_eligibility_search",
            # Spec 2296 — Epic ε AX-infrastructure callable-channel reference
            # mock adapters for the read surfaces of OPAQUE administrative
            # domains. Per Constitution § II + delegation-flow-design.md § 12,
            # these are explicitly mocked under `mock_lookup_module_*` names
            # with the six transparency fields stamped.
            "mock_lookup_module_hometax_simplified",
            "mock_lookup_module_gov24_certificate",
            # Epic η #2298 FR-021 — primitive surfaces registered via
            # mvp_surface.py so the LLM sees them in
            # registry.export_core_tools_openai(). Required for the
            # citizen-OPAQUE chain (verify→lookup→submit) to be emittable.
            "check",
            "send",
            # Epic ζ #2297 path B (live smoke 2026-04-30) — 15 non-core mock
            # adapter wrappers bridged into the BM25 corpus by discovery_bridge
            # so lookup(mode="search") surfaces verify/submit
            # candidates alongside lookup-class adapters. is_core=False; not
            # in the primary LLM tool list.
            # 10 verify family wrappers
            "mock_verify_module_modid",
            "mock_verify_module_kec",
            "mock_verify_module_geumyung",
            "mock_verify_module_simple_auth",
            "mock_verify_module_any_id_sso",
            "mock_verify_gongdong_injeungseo",
            "mock_verify_geumyung_injeungseo",
            "mock_verify_ganpyeon_injeung",
            "mock_verify_mobile_id",
            "mock_verify_mydata",
            # 5 submit wrappers
            "mock_submit_module_hometax_taxreturn",
            "mock_submit_module_gov24_minwon",
            "mock_submit_module_public_mydata_action",
            "mock_traffic_fine_pay_v1",
            "mock_welfare_application_submit_v1",
            # Spec #2797 — direct-curl verified public-data find adapters.
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
        }
    )

    def test_registered_set_matches_expected(self, live_registry):
        """Registry tool set exactly matches the active closed set."""
        registry, _ = live_registry
        actual = frozenset(registry._tools.keys())
        assert actual == self.EXPECTED_REGISTERED_TOOL_IDS, (
            f"Registry drift: "
            f"missing={self.EXPECTED_REGISTERED_TOOL_IDS - actual}, "
            f"extra={actual - self.EXPECTED_REGISTERED_TOOL_IDS}"
        )


# ---------------------------------------------------------------------------
# Check 8 — CC dev tool absence
# Grep src/ummaya/tools/register_all.py for any of the 16 CC dev tool names.
# Fail-closed if found (FR-012 violation).
# ---------------------------------------------------------------------------


class TestCheck8CCDevToolAbsence:
    CC_DEV_TOOL_NAMES: tuple[str, ...] = (
        "BashTool",
        "FileEditTool",
        "FileReadTool",
        "FileWriteTool",
        "GlobTool",
        "GrepTool",
        "NotebookEditTool",
        "PowerShellTool",
        "LSPTool",
        "REPLTool",
        "ConfigTool",
        "EnterWorktreeTool",
        "ExitWorktreeTool",
        "EnterPlanModeTool",
        "ExitPlanModeTool",
        "MCPTool",
    )

    def test_register_all_has_no_cc_dev_tool_refs(self):
        """register_all.py must not reference any CC developer tooling."""
        source = (SRC_TOOLS / "register_all.py").read_text()
        violations = [name for name in self.CC_DEV_TOOL_NAMES if name in source]
        assert not violations, (
            f"CC dev tool(s) referenced in register_all.py — FR-012 violation. "
            f"Remove the import/registration: {violations}"
        )

    def test_tools_init_has_no_cc_dev_tool_refs(self):
        """src/ummaya/tools/__init__.py must not re-export CC developer tooling."""
        init_path = SRC_TOOLS / "__init__.py"
        if not init_path.exists():
            pytest.skip("src/ummaya/tools/__init__.py does not exist")
        source = init_path.read_text()
        violations = [name for name in self.CC_DEV_TOOL_NAMES if name in source]
        assert not violations, (
            f"CC dev tool(s) found in tools/__init__.py — FR-012 violation: {violations}"
        )


# ---------------------------------------------------------------------------
# Check 9 — Auxiliary tools not in GovAPITool registry (TUI-only, skip)
# ---------------------------------------------------------------------------


class TestCheck9AuxiliaryToolsAbsence:
    def test_auxiliary_tools_not_in_gov_api_registry(self):
        """Auxiliary tools (WebFetch, Calculator, etc.) are TUI-side only.
        Python GovAPITool registry must not contain them.
        This check is vacuously satisfied; TUI coverage is in `bun test` CI.
        """
        pytest.skip(
            "Auxiliary tools (WebFetch, Calculator, etc.) are registered on the "
            "TUI side only. Python-side validation is not applicable here — "
            "covered by `bun test` CI (Check 9 per contract § 3)."
        )


# ---------------------------------------------------------------------------
# Check 10 — Plugin namespace reservation
# If any registered tool_id starts with `plugin.`, enforce `plugin.<id>.<verb>`.
# ---------------------------------------------------------------------------


class TestCheck10PluginNamespace:
    _PLUGIN_PATTERN = re.compile(r"^plugin\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

    def test_plugin_prefixed_tool_ids_follow_pattern(self, live_registry):
        """Plugin-namespaced tool_ids must match 'plugin.<id>.<verb>' pattern."""
        registry, _ = live_registry
        violations = [
            tool_id
            for tool_id in registry._tools
            if tool_id.startswith("plugin.") and not self._PLUGIN_PATTERN.match(tool_id)
        ]
        assert not violations, (
            f"Plugin namespace violation(s): {violations} "
            f"— pattern must be 'plugin.<id>.<verb>' (C7 per migration tree)"
        )


# ---------------------------------------------------------------------------
# FR-028 — Composite-pattern detector
# Detect any adapter module that imports another adapter's _call/register/_fetch
# (composite pattern — removed per migration tree § L1-B B6).
# ---------------------------------------------------------------------------


class TestFR028CompositePatternDetector:
    """Detect composite adapters whose module imports another adapter's
    _call / register / _fetch symbol from a sibling adapter module.

    Implementation uses source-level regex rather than runtime importlib
    inspection to keep the check fast, deterministic, and free of import
    side-effects. The pattern matches cross-adapter imports of private
    callables only; intra-module self-imports are not flagged.
    """

    # Pattern: `from ummaya.tools.<pkg>.<mod> import <_call|register|_fetch>`
    _IMPORT_PATTERN = re.compile(
        r"from\s+(ummaya\.tools\.(?P<pkg>[^.\s]+)\.(?P<mod>[^\s]+))\s+"
        r"import\s+(?:_call|register|_fetch)",
        re.MULTILINE,
    )

    def test_no_composite_adapter_fans_out(self):
        """No adapter source file imports _call/register/_fetch from a sibling adapter.

        Composite pattern (prohibited by FR-028 / migration tree § L1-B B6):
          An adapter module A imports another adapter module B's private callable
          (_call/_fetch) to orchestrate a multi-adapter response internally.

        Excluded by design:
          - register_all.py: central coordinator; its imports of `register` are
            the canonical registration mechanism, NOT composite fan-out.
          - __init__.py: package-level re-exports.
          - __pycache__: bytecode artifacts.
          - composite/: deleted subtree.
        """
        violations: list[str] = []

        # Excluded filenames that are architecturally allowed to import register
        # functions from sibling adapter modules.
        excluded_stems = frozenset({"register_all", "mvp_surface"})

        for py_file in SRC_TOOLS.rglob("*.py"):
            # Skip deleted composite/ tree and __pycache__
            if "composite" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            # Skip __init__.py (re-exports) and the central coordinator
            if py_file.name == "__init__.py" or py_file.stem in excluded_stems:
                continue

            source = py_file.read_text()
            # Only check files that define or register a GovAPITool adapter
            if "GovAPITool(" not in source and "AdapterRegistration(" not in source:
                continue

            own_parent = py_file.parent.name  # e.g. "koroad", "kma"
            own_stem = py_file.stem  # e.g. "accident_hazard_search"

            for m in self._IMPORT_PATTERN.finditer(source):
                imported_pkg = m.group("pkg")
                imported_mod = m.group("mod")
                # Self-import: same package + same module stem → skip
                if imported_pkg == own_parent and imported_mod == own_stem:
                    continue
                # Cross-adapter import of a private callable → composite pattern
                violations.append(
                    f"{py_file.relative_to(REPO_ROOT)}: composite pattern — "
                    f"imports '{m.group(0).strip()}' from sibling adapter "
                    f"(FR-028 / migration tree § L1-B B6)"
                )

        assert not violations, "\n".join(violations)
