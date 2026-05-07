# SPDX-License-Identifier: Apache-2.0
"""T081 — Unit test: exactly 4 primitives are registered on the main surface.

SC-001 (spec.md): The public primitive surface MUST expose exactly these four
names: lookup, resolve_location, submit, verify.

No more, no fewer.
"""

from __future__ import annotations

import kosmos.primitives as primitives_module

_EXPECTED_PRIMITIVES: frozenset[str] = frozenset({"lookup", "resolve_location", "submit", "verify"})


def test_primitive_count_is_four() -> None:
    """Assert exactly 4 names are exported via __all__."""
    exported = frozenset(primitives_module.__all__)
    assert len(exported) == 4, (
        f"SC-001: expected exactly 4 primitives, got {len(exported)}: {sorted(exported)}"
    )


def test_primitive_names_match_canonical_set() -> None:
    """Assert the exported names exactly match the canonical active primitive set."""
    exported = frozenset(primitives_module.__all__)
    assert exported == _EXPECTED_PRIMITIVES, (
        f"SC-001: primitive surface mismatch.\n"
        f"  Expected : {sorted(_EXPECTED_PRIMITIVES)}\n"
        f"  Got      : {sorted(exported)}\n"
        f"  Missing  : {sorted(_EXPECTED_PRIMITIVES - exported)}\n"
        f"  Extra    : {sorted(exported - _EXPECTED_PRIMITIVES)}"
    )


def test_all_primitives_are_callable() -> None:
    """Assert each active primitive resolves to a callable on the module."""
    for name in _EXPECTED_PRIMITIVES:
        obj = getattr(primitives_module, name, None)
        assert callable(obj), f"SC-001: primitive {name!r} is not callable (got {type(obj)!r})"
