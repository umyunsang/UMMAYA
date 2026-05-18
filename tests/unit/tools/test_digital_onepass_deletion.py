# SPDX-License-Identifier: Apache-2.0
"""T036 — digital_onepass deletion regression guard (FR-004 / SC-004).

Asserts that ``verify_digital_onepass`` has been fully purged:

(a) BM25 search for "디지털원패스" and "digital_onepass" returns zero adapter matches
    from the main ToolRegistry (the only surface visible to the BM25 layer; verify
    sub-registry adapters are not indexed by BM25 but are checked separately in (c)).
(b) ``import ummaya.tools.mock.verify_digital_onepass`` raises ``ModuleNotFoundError``
    (the file is deleted on disk).
(c) ``ummaya.primitives.verify._VERIFY_ADAPTERS`` contains no key containing
    "digital_onepass" or "onepass".

FR-004: 서비스 종료 2025-12-30 — Digital Onepass service terminated 2025-12-30.
SC-004: BM25 deletion regression guard.

Reference: tasks.md T021 (deletion task), T036 (this test).
"""

from __future__ import annotations

import importlib

import pytest

# ---------------------------------------------------------------------------
# (a) BM25 search returns zero matches
# ---------------------------------------------------------------------------


def test_bm25_search_for_digital_onepass_korean_returns_zero() -> None:
    """BM25 search for '디지털원패스' returns zero results from the main ToolRegistry.

    The digital_onepass adapter was deleted (FR-004). Its search_hint keywords
    must not appear in the BM25 index.
    """
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    results = registry.search("디지털원패스")
    matching_ids = [
        r.tool.id for r in results if "digital_onepass" in r.tool.id or "onepass" in r.tool.id
    ]

    assert len(matching_ids) == 0, (
        f"SC-004 violation: BM25 search for '디지털원패스' returned adapter(s) "
        f"with digital_onepass/onepass in their ID: {matching_ids}. "
        f"The verify_digital_onepass adapter must be fully deleted (FR-004)."
    )


def test_bm25_search_for_digital_onepass_english_returns_zero() -> None:
    """BM25 search for 'digital_onepass' returns zero results from the main ToolRegistry."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    results = registry.search("digital_onepass")
    matching_ids = [
        r.tool.id for r in results if "digital_onepass" in r.tool.id or "onepass" in r.tool.id
    ]

    assert len(matching_ids) == 0, (
        f"SC-004 violation: BM25 search for 'digital_onepass' returned adapter(s) "
        f"with digital_onepass/onepass in their ID: {matching_ids}. "
        f"The verify_digital_onepass adapter must be fully deleted (FR-004)."
    )


def test_bm25_search_no_digital_onepass_in_all_results() -> None:
    """No BM25 result from any search keyword includes a digital_onepass adapter."""
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.tools.executor import ToolExecutor
    from ummaya.tools.register_all import register_all_tools
    from ummaya.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_all_tools(registry, executor)

    # Check with multiple related keyword variations
    for query in ("디지털원패스", "digital_onepass", "원패스", "onepass", "Digital Onepass"):
        results = registry.search(query)
        for r in results:
            assert "digital_onepass" not in r.tool.id, (
                f"SC-004 violation: BM25 search for {query!r} returned "
                f"tool {r.tool.id!r} containing 'digital_onepass'. "
                f"This adapter must be fully deleted (FR-004)."
            )
            assert "onepass" not in r.tool.id.lower(), (
                f"SC-004 violation: BM25 search for {query!r} returned "
                f"tool {r.tool.id!r} containing 'onepass'. "
                f"This adapter must be fully deleted (FR-004)."
            )


# ---------------------------------------------------------------------------
# (b) Module file is deleted — import raises ModuleNotFoundError
# ---------------------------------------------------------------------------


def test_verify_digital_onepass_module_raises_module_not_found_error() -> None:
    """Importing ummaya.tools.mock.verify_digital_onepass raises ModuleNotFoundError.

    FR-004: The file src/ummaya/tools/mock/verify_digital_onepass.py is deleted.
    If this test fails, the file was accidentally re-created or the import
    was re-added to __init__.py.
    """
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("ummaya.tools.mock.verify_digital_onepass")

    # Ensure the error is specifically about the missing module (not a transitive dep)
    error_msg = str(exc_info.value)
    assert "verify_digital_onepass" in error_msg or "No module named" in error_msg, (
        f"Expected ModuleNotFoundError mentioning verify_digital_onepass, got: {error_msg!r}"
    )


def test_verify_digital_onepass_not_in_mock_package_namespace() -> None:
    """ummaya.tools.mock does not expose verify_digital_onepass as an attribute."""
    import ummaya.tools.mock as mock_pkg  # noqa: F401 — trigger side-effect registration

    assert not hasattr(mock_pkg, "verify_digital_onepass"), (
        "FR-004 violation: ummaya.tools.mock still exposes verify_digital_onepass "
        "as an attribute. Remove it from __init__.py."
    )


# ---------------------------------------------------------------------------
# (c) Verify sub-registry contains no digital_onepass or onepass entry
# ---------------------------------------------------------------------------


def test_verify_adapter_registry_has_no_digital_onepass_key() -> None:
    """ummaya.primitives.verify._VERIFY_ADAPTERS contains no digital_onepass key.

    The family key used by register_verify_adapter() was "digital_onepass".
    After FR-004 deletion, no key containing "digital_onepass" should exist.
    """
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    for family_key in list(_VERIFY_ADAPTERS.keys()):
        assert "digital_onepass" not in family_key, (
            f"FR-004 violation: verify._VERIFY_ADAPTERS still has a key "
            f"{family_key!r} containing 'digital_onepass'. "
            f"The adapter must be removed from the registry."
        )
        assert "onepass" not in family_key, (
            f"FR-004 violation: verify._VERIFY_ADAPTERS has key {family_key!r} "
            f"containing 'onepass'. "
            f"Verify the digital_onepass adapter was fully removed."
        )


def test_verify_adapter_registry_exact_family_count_after_deletion() -> None:
    """After digital_onepass deletion, _VERIFY_ADAPTERS has exactly 10 families.

    This is the SC-003/SC-004 compound check: both the absence of digital_onepass
    AND the presence of the 10 replacement families.
    """
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import (
        _VERIFY_ADAPTER_FAMILIES,
        _VERIFY_ADAPTERS,
    )

    families = {
        _VERIFY_ADAPTER_FAMILIES.get(adapter_key, adapter_key) for adapter_key in _VERIFY_ADAPTERS
    }
    assert len(families) == 10, (
        f"Expected exactly 10 verify families after digital_onepass deletion "
        f"(FR-004 + 5 existing + 5 new Epic ε). "
        f"Got {len(families)}: {sorted(families)}"
    )


def test_digital_onepass_not_in_any_verify_adapter_id() -> None:
    """No tool_id value in _VERIFY_ADAPTERS contains 'digital_onepass' or 'onepass'.

    Checks the registered callable entries themselves (not just the family key)
    to guard against a rename-but-not-delete mistake.
    """
    import ummaya.tools.mock  # noqa: F401 — trigger side-effect registration
    from ummaya.primitives.verify import _VERIFY_ADAPTERS

    for family_key, adapter in _VERIFY_ADAPTERS.items():
        # Check the adapter's module name if accessible
        adapter_module = getattr(adapter, "__module__", "") or ""
        assert "digital_onepass" not in adapter_module, (
            f"FR-004 violation: verify adapter for family {family_key!r} "
            f"originates from module {adapter_module!r} containing 'digital_onepass'. "
            f"The adapter module must be deleted."
        )
        assert "onepass" not in adapter_module, (
            f"FR-004 violation: verify adapter for family {family_key!r} "
            f"originates from module {adapter_module!r} containing 'onepass'. "
            f"Check that the digital_onepass adapter was fully purged."
        )
