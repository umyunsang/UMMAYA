# SPDX-License-Identifier: Apache-2.0
"""KOSMOS Five-Primitive Harness surface.

Exports the five primitive symbols that make up the main-tool surface:

- ``lookup``: read/search/fetch (re-exported from Spec 022, byte-identical).
- ``resolve_location``: geocoding (re-exported from Spec 022, byte-identical).
- ``submit``: write-transaction absorber (Spec 031 US1, T024).
- ``subscribe``: CBS / REST pull / RSS 2.0 iterator (Spec 031 US3, T057).
- ``verify``: delegation-only identity binding (Spec 031 US2, T042).

All five primitives are now real implementations — the Phase 1 scaffold
placeholders have been fully replaced by their user-story coroutines.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kosmos.primitives.submit import submit
from kosmos.primitives.subscribe import subscribe
from kosmos.primitives.verify import verify
from kosmos.tools.lookup import lookup
from kosmos.tools.resolve_location import resolve_location

# Single-source-of-truth registry mapping each LLM-visible primitive name
# to its async callable. Epic #2077 T010 (FR-003) — replaces the prior
# hardcoded enumerations scattered in ``kosmos.ipc.stdio``. The registry is
# the authoritative answer to "which tool names is the platform permitted
# to execute"; downstream code MUST read from this constant rather than
# duplicating the list.
#
# Return type is intentionally ``Any`` because the five primitives have
# heterogeneous return shapes (lookup/resolve_location/submit/verify return
# ``Awaitable[<Output>]``; subscribe returns ``AsyncIterator[<Event>]``).
# Call-shape adaptation lives in the IPC dispatcher, not here.
PRIMITIVE_REGISTRY: dict[str, Callable[..., Any]] = {
    "lookup": lookup,
    "resolve_location": resolve_location,
    "submit": submit,
    "subscribe": subscribe,
    "verify": verify,
}

# Subset of ``PRIMITIVE_REGISTRY`` whose invocation requires a Spec 033
# permission decision before dispatch.
#
# ``GATED_PRIMITIVES`` — full set of primitives that enter the permission
# bridge (all three: verify / submit / subscribe).
#
# ``LIGHT_GATE_PRIMITIVES`` — subset that gets *light* permission treatment
# (single-decision, risk_level="low"): verify, because it is a delegation-
# only identity binding (read-only from the citizen's data perspective, but
# still requires explicit consent per Spec 031 § US2).
#
# ``HEAVY_GATE_PRIMITIVES`` — side-effecting primitives (Layer 2/3):
# submit (irreversible write) and subscribe (persistent stream).
#
# The complement (``PRIMITIVE_REGISTRY.keys() - GATED_PRIMITIVES``) is the
# fully auto-allowed set: lookup / resolve_location.
GATED_PRIMITIVES: frozenset[str] = frozenset({"verify", "submit", "subscribe"})
LIGHT_GATE_PRIMITIVES: frozenset[str] = frozenset({"verify"})
HEAVY_GATE_PRIMITIVES: frozenset[str] = frozenset({"submit", "subscribe"})

# ``__all__`` enumerates the LLM-visible primitive *surface* — the five root
# verbs (Migration Tree § L1-C.C1). The metadata constants ``PRIMITIVE_REGISTRY``
# and ``GATED_PRIMITIVES`` live alongside but are explicitly imported by name
# from downstream callers (``from kosmos.primitives import PRIMITIVE_REGISTRY``);
# they intentionally stay out of ``__all__`` so ``test_primitive_count_is_five``
# (Spec 031 SC-001 invariant) keeps the surface canonical.
__all__ = [
    "lookup",
    "resolve_location",
    "submit",
    "subscribe",
    "verify",
]
# Metadata constants (GATED_PRIMITIVES / LIGHT_GATE_PRIMITIVES /
# HEAVY_GATE_PRIMITIVES / PRIMITIVE_REGISTRY) are intentionally NOT in __all__
# — they are imported by name from downstream callers
# (``from kosmos.primitives import PRIMITIVE_REGISTRY``) and the Spec 031
# SC-001 invariant requires the LLM-visible surface to expose exactly the
# 5 root verbs. ``test_primitive_count_is_five`` enforces this.
