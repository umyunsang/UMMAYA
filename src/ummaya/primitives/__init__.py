# SPDX-License-Identifier: Apache-2.0
"""UMMAYA active primitive harness surface.

Exports the active primitive symbols that make up the main-tool surface:

- ``find``: read/search/fetch (re-exported from Spec 022).
- ``locate``: geocoding (re-exported from Spec 022).
- ``send``: write-transaction absorber (Spec 031 US1, T024).
- ``check``: delegation-only identity binding (Spec 031 US2, T042).
- ``document``: local public-document authoring and review harness.

``subscribe`` is intentionally not part of the active surface. National alert
and notice subscriptions are app/phone push-notification concerns, not a CLI
tool-call primitive until UMMAYA has a real app runtime to own delivery.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ummaya.primitives.document import document
from ummaya.primitives.submit import send
from ummaya.primitives.verify import check
from ummaya.tools.lookup import find
from ummaya.tools.resolve_location import locate

# Backward-compatible Spec 022 symbol. The active LLM-visible root verb is
# `locate`; this alias is kept as the identical canonical coroutine for older
# contracts and imports.
lookup = find
resolve_location = locate
submit = send
verify = check

# Single-source-of-truth registry mapping each LLM-visible primitive name
# to its async callable. Epic #2077 T010 (FR-003) — replaces the prior
# hardcoded enumerations scattered in ``ummaya.ipc.stdio``. The registry is
# the authoritative answer to "which tool names is the platform permitted
# to execute"; downstream code MUST read from this constant rather than
# duplicating the list.
#
# Return type is intentionally ``Any`` because the active primitives have
# heterogeneous return shapes.
# Call-shape adaptation lives in the IPC dispatcher, not here.
PRIMITIVE_REGISTRY: dict[str, Callable[..., Any]] = {
    "find": find,
    "locate": locate,
    "send": send,
    "check": check,
    "document": document,
}

# Subset of ``PRIMITIVE_REGISTRY`` whose invocation requires a Spec 033
# permission decision before dispatch.
#
# ``GATED_PRIMITIVES`` — full set of primitives that enter the permission
# bridge (check / send).
#
# ``LIGHT_GATE_PRIMITIVES`` — subset that gets *light* permission treatment
# (single-decision, risk_level="low"): check, because it is a delegation-
# only identity binding (read-only from the citizen's data perspective, but
# still requires explicit consent per Spec 031 § US2).
#
# ``HEAVY_GATE_PRIMITIVES`` — side-effecting primitives (Layer 2/3):
# send (irreversible write).
#
# The complement (``PRIMITIVE_REGISTRY.keys() - GATED_PRIMITIVES``) is the
# fully auto-allowed set: find / locate.
GATED_PRIMITIVES: frozenset[str] = frozenset({"check", "send", "document"})
LIGHT_GATE_PRIMITIVES: frozenset[str] = frozenset({"check"})
HEAVY_GATE_PRIMITIVES: frozenset[str] = frozenset({"send", "document"})

# ``__all__`` enumerates the LLM-visible primitive *surface* — the active root
# verbs. The metadata constants ``PRIMITIVE_REGISTRY``
# and ``GATED_PRIMITIVES`` live alongside but are explicitly imported by name
# from downstream callers (``from ummaya.primitives import PRIMITIVE_REGISTRY``);
__all__ = [
    "find",
    "locate",
    "send",
    "check",
    "document",
]
# Metadata constants (GATED_PRIMITIVES / LIGHT_GATE_PRIMITIVES /
# HEAVY_GATE_PRIMITIVES / PRIMITIVE_REGISTRY) are intentionally NOT in __all__
# — they are imported by name from downstream callers
# (``from ummaya.primitives import PRIMITIVE_REGISTRY``) and the Spec 031
# active root verbs.
