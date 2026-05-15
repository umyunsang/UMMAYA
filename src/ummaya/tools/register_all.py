# SPDX-License-Identifier: Apache-2.0
"""Central registration entry point for all UMMAYA government API tools.

Call ``register_all_tools(registry, executor)`` once at application startup
to register every available tool adapter and its executor binding.

NOTE (T049 / Epic #507): ``address_to_region`` and ``address_to_grid`` were
removed in User Story 4. Administrative code and coordinate resolution are now
first-class ``locate`` adapters in the central registry (Kakao/JUSO/SGIS).
Grid coordinate projection is exposed through coordinate-producing locate
adapter results and still uses ``latlon_to_lcc()`` internally.

NOTE (Stage 3 / T033, T048, T056): Three seed adapters added to the registry:
``nmc_emergency_search`` (Layer 3 gated stub), ``kma_forecast_fetch`` (short-term
forecast via LCC-projected grid), and ``hira_hospital_search`` (hospital search
by radius).  All three are discoverable via ``lookup(mode="search")`` and
invocable via ``lookup(mode="fetch")``.

NOTE (Epic #1634 P3 / T010b + T011): The composite adapter ``road_risk_score``
was removed per migration tree § L1-B B6 (``Composite 제거 · LLM primitive
chain``). The LLM is expected to compose risk-assessment responses by chaining
``lookup(mode="fetch")`` against the three underlying adapters
(``koroad_accident_search``, ``kma_weather_alert_status``,
``kma_current_observation``). Post-removal registered count is 14 (down from 15).
``build_routing_index()`` is called at the end of registration and fails boot
with ``SystemExit(78)`` (``EX_CONFIG``) if any adapter is misconfigured per
``specs/1634-tool-system-wiring/contracts/routing-consistency.md § 5``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing_index import (
    RoutingIndex,
    RoutingValidationError,
    build_routing_index,
)

logger = logging.getLogger(__name__)


def register_all_tools(registry: ToolRegistry, executor: ToolExecutor) -> RoutingIndex:
    """Register all available government API tool adapters.

    Registers the following 52 tools in order after discovery bridging and
    Spec #2797 verified public-data expansion:
      1. locate — MVP LLM core surface: location resolution (is_core=True)
      2. lookup — MVP LLM core surface: adapter discovery + invocation (is_core=True)
      3. koroad_accident_search — KOROAD accident hotspot search (by enum codes)
      4. koroad_accident_hazard_search — KOROAD accident hazard search (by adm_cd)
      5. kma_weather_alert_status — KMA weather alert status
      6. kma_current_observation — KMA ultra-short-term current observation
      7. kma_short_term_forecast — KMA short-term forecast (단기예보)
      8. kma_ultra_short_term_forecast — KMA ultra-short-term forecast (초단기예보)
      9. kma_pre_warning — KMA weather pre-warning list (기상예비특보목록)
     10. nmc_emergency_search — NMC emergency room bed availability (Layer 3 gated)
     11. kma_forecast_fetch — KMA short-term forecast by (lat, lon) → LCC grid
     12. hira_hospital_search — HIRA hospital search by coordinates + radius
     13. nfa_emergency_info_service — NFA EMS statistics (Phase 2, Layer 3 gated stub)
     14. mohw_welfare_eligibility_search — SSIS welfare service list (Phase 2, real XML handler — T025)
     15-28. verified_data_go_kr — fourteen direct-curl verified public-data adapters
     29. mock_lookup_module_hometax_simplified — Hometax simplified data (Mock, Epic ε T028)
     30. mock_lookup_module_gov24_certificate — Gov24 certificate lookup (Mock, Epic ε T029)

    After registration, ``build_routing_index()`` validates every adapter against
    the six invariants in ``contracts/routing-consistency.md § 2``. Violations
    cause ``SystemExit(78)`` (``EX_CONFIG``) at boot — fail-closed per
    Constitution § II.

    Args:
        registry: The central ToolRegistry to add tools to.
        executor: The ToolExecutor to bind adapter functions to.

    Returns:
        ``RoutingIndex`` partitioned by primitive, consumed by
        ``lookup(mode="search")`` for primitive-filtered ranking.

    Raises:
        DuplicateToolError: If any tool id is already registered (i.e., this
            function is called a second time on the same registry).
        SystemExit(78): If ``build_routing_index()`` rejects any adapter
            (invariant violation — see routing-consistency.md).
    """
    from ummaya.tools.hira.hospital_search import register as reg_hira
    from ummaya.tools.kma.forecast_fetch import (
        KMA_FORECAST_FETCH_TOOL,
        KmaForecastFetchInput,
    )
    from ummaya.tools.kma.forecast_fetch import (
        _fetch as kma_forecast_fetch_adapter,
    )
    from ummaya.tools.kma.kma_current_observation import register as reg_kma_obs
    from ummaya.tools.kma.kma_pre_warning import register as reg_kma_pre_warning
    from ummaya.tools.kma.kma_short_term_forecast import register as reg_kma_stf
    from ummaya.tools.kma.kma_ultra_short_term_forecast import register as reg_kma_ustf
    from ummaya.tools.kma.kma_weather_alert_status import register as reg_kma_alert
    from ummaya.tools.koroad.accident_hazard_search import register as reg_koroad_hazard
    from ummaya.tools.koroad.koroad_accident_search import register as reg_koroad
    from ummaya.tools.location_adapters import register as reg_locate
    from ummaya.tools.mock.lookup_module_gov24_certificate import (
        register as reg_mock_gov24_cert,
    )
    from ummaya.tools.mock.lookup_module_hometax_simplified import (
        register as reg_mock_hometax_simplified,
    )
    from ummaya.tools.mohw.welfare_eligibility_search import register as reg_mohw
    from ummaya.tools.mvp_surface import register_mvp_surface
    from ummaya.tools.nfa119.emergency_info_service import register as reg_nfa
    from ummaya.tools.nmc.emergency_search import register as reg_nmc
    from ummaya.tools.verified_data_go_kr import register as reg_verified_data_go_kr

    # Register MVP LLM-visible core surface first (FR-001, SC-003)
    register_mvp_surface(registry)
    import ummaya.tools.mock  # noqa: F401 — registers all mock surfaces in production

    # Locate provider endpoints are first-class adapters under the central
    # registry. They use ToolExecutor.invoke_raw() because their output union is
    # ResolveLocationOutput, not LookupOutput.
    reg_locate(registry, executor)

    reg_koroad(registry, executor)
    reg_koroad_hazard(registry, executor)
    reg_kma_alert(registry, executor)
    reg_kma_obs(registry, executor)
    reg_kma_stf(registry, executor)
    reg_kma_ustf(registry, executor)
    reg_kma_pre_warning(registry, executor)
    # road_risk_score (composite) removed per Epic #1634 FR-027 (migration tree § L1-B B6).

    # Seed adapters for MVP Main-Tool (Epic #507, Stage 3)
    reg_nmc(registry, executor)  # T033 — NMC (Layer 3 gated stub)
    reg_hira(registry, executor)  # T056 — HIRA hospital search

    # T048 — KMA forecast_fetch: register tool + bind executor adapter.
    # The module's register(registry) only covers the registry; the executor
    # binding lives here so _fetch is reachable via lookup(mode="fetch").
    registry.register(KMA_FORECAST_FETCH_TOOL)

    async def _kma_forecast_fetch_adapter(inp: BaseModel) -> dict[str, Any]:
        assert isinstance(inp, KmaForecastFetchInput)
        result = await kma_forecast_fetch_adapter(inp)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    executor.register_adapter("kma_forecast_fetch", _kma_forecast_fetch_adapter)
    logger.info("Registered tool: kma_forecast_fetch")

    # Phase 2 adapters (spec 029 — NFA 119 + MOHW SSIS, Layer 3 gated stubs)
    reg_nfa(registry, executor)  # T014 — NFA EMS statistics (interface-only)
    reg_mohw(registry, executor)  # T025 — MOHW welfare eligibility search (real XML handler)

    # Spec #2797 — direct-curl verified public-data adapters. These are real
    # read-only find adapters backed by saved live-probe fixtures and direct
    # HTTP handlers; newly applied but not-yet-authorized candidates stay out.
    reg_verified_data_go_kr(registry, executor)

    # Epic ε #2296 T028/T029 — New lookup mock GovAPITools (main ToolRegistry,
    # not per-primitive sub-registry — lookup adapters use BM25 discovery).
    reg_mock_hometax_simplified(registry, executor)  # T028 — Hometax simplified data
    reg_mock_gov24_cert(registry, executor)  # T029 — Gov24 certificate lookup

    # Epic ζ #2297 path B (live smoke 2026-04-30 follow-up) — bridge per-primitive
    # registries (verify/submit) into the main ToolRegistry's BM25 corpus
    # so `lookup(mode="search", query="…")` can surface verify/submit
    # candidates alongside lookup-class adapters. Without this bridge the citizen
    # tax-return chain never starts because BM25 returns empty for "종합소득세 신고".
    from ummaya.tools.discovery_bridge import bridge_per_primitive_registries

    bridge_count = bridge_per_primitive_registries(registry)
    logger.info(
        "discovery_bridge: bridged %d non-core mock adapters into BM25 corpus",
        bridge_count,
    )

    logger.info("All %d tools registered successfully", len(registry))

    # Epic #1634 P3 / T011 — fail-closed routing validation.
    # build_routing_index() walks every registered GovAPITool, validates
    # primitive != None, unique tool_id, and compute_permission_tier() totality.
    # Failure raises SystemExit(78) (EX_CONFIG) per contracts/routing-consistency.md § 5.
    try:
        routing_index = build_routing_index(list(registry._tools.values()))
    except RoutingValidationError as exc:
        logger.critical("Tool registry validation failed: %s", exc)
        raise SystemExit(78) from exc

    for warning in routing_index.warnings:
        logger.warning("Routing index warning: %s", warning)

    return routing_index
