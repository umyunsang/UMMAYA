# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ``ummaya.tools.verify_canonical_map``.

Asserts FR-008b regression criteria:
- The canonical map has ≥10 entries.
- All 10 canonical tool_id keys are present.
- Each family_hint value matches the expected canonical value.
- ``resolve_family`` returns the correct family_hint for every key.
- ``resolve_family`` returns ``None`` for an unknown tool_id.
- ``get_canonical_map`` is read-only (MappingProxyType).
- Repeated calls hit ``lru_cache`` (idempotent, same object).

References
----------
- ``specs/2297-zeta-e2e-smoke/data-model.md § 2`` — validation rules
- ``specs/2297-zeta-e2e-smoke/contracts/verify-input-shape.md`` — I-V4
- ``prompts/system_v1.md <check_families>`` — canonical source-of-truth
"""

from __future__ import annotations

import pytest

from ummaya.tools.verify_canonical_map import (
    get_canonical_map,
    resolve_family,
    resolve_tool_id,
)

# ---------------------------------------------------------------------------
# Canonical expected mapping (per data-model.md § 2)
# ---------------------------------------------------------------------------

EXPECTED_MAPPING: dict[str, str] = {
    "mock_verify_gongdong_injeungseo": "gongdong_injeungseo",
    "mock_verify_geumyung_injeungseo": "geumyung_injeungseo",
    "mock_verify_ganpyeon_injeung": "ganpyeon_injeung",
    "mock_verify_mobile_id": "mobile_id",
    "mock_verify_mydata": "mydata",
    "mock_verify_module_simple_auth": "simple_auth_module",
    "mock_verify_module_modid": "modid",
    "mock_verify_module_kec": "kec",
    "mock_verify_module_geumyung": "geumyung_module",
    "mock_verify_module_any_id_sso": "any_id_sso",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_canonical_map_has_at_least_ten_entries() -> None:
    """The canonical map MUST have ≥10 entries (FR-008b assertion)."""
    mapping = get_canonical_map()
    assert len(mapping) >= 10, f"Expected ≥10 entries in canonical map, got {len(mapping)}"


def test_all_ten_canonical_tool_ids_present() -> None:
    """All 10 canonical tool_id keys from data-model.md § 2 MUST be present."""
    mapping = get_canonical_map()
    missing = [tid for tid in EXPECTED_MAPPING if tid not in mapping]
    assert not missing, f"Missing tool_ids in canonical map: {missing}"


@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(EXPECTED_MAPPING.items()),
    ids=list(EXPECTED_MAPPING.keys()),
)
def test_family_hint_values_match_canonical(tool_id: str, expected_family: str) -> None:
    """Each family_hint value MUST match the canonical expected value."""
    mapping = get_canonical_map()
    actual = mapping[tool_id]
    assert actual == expected_family, (
        f"tool_id={tool_id!r}: expected family_hint {expected_family!r}, got {actual!r}"
    )


@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    list(EXPECTED_MAPPING.items()),
    ids=list(EXPECTED_MAPPING.keys()),
)
def test_resolve_family_returns_correct_family(tool_id: str, expected_family: str) -> None:
    """``resolve_family`` MUST return the correct family_hint for each key."""
    result = resolve_family(tool_id)
    assert result == expected_family, (
        f"resolve_family({tool_id!r}) returned {result!r}, expected {expected_family!r}"
    )


def test_resolve_family_returns_none_for_unknown() -> None:
    """``resolve_family`` MUST return ``None`` for an unknown tool_id."""
    result = resolve_family("mock_verify_module_NONEXISTENT")
    assert result is None


def test_resolve_family_returns_none_for_empty_string() -> None:
    """``resolve_family`` MUST return ``None`` for an empty string."""
    result = resolve_family("")
    assert result is None


def test_resolve_tool_id_accepts_family_aliases_for_runtime_recovery() -> None:
    """Internal family aliases are normalized to canonical mock_verify tool ids."""
    assert resolve_tool_id("mobile_id") == "mock_verify_mobile_id"
    assert resolve_tool_id("simple_auth_module") == "mock_verify_module_simple_auth"
    assert resolve_tool_id("mock_verify_mobile_id") == "mock_verify_mobile_id"


def test_get_canonical_map_is_read_only() -> None:
    """``get_canonical_map`` returns a read-only mapping (MappingProxyType)."""
    mapping = get_canonical_map()
    with pytest.raises((TypeError, AttributeError)):
        mapping["new_key"] = "new_value"  # type: ignore[index]


def test_get_canonical_map_is_idempotent() -> None:
    """Repeated calls MUST return the same object (lru_cache hit)."""
    m1 = get_canonical_map()
    m2 = get_canonical_map()
    assert m1 is m2, "get_canonical_map() MUST return the same cached object"


def test_canonical_family_hint_values_are_all_present() -> None:
    """All 10 expected family_hint values from data-model.md § 2 MUST appear."""
    expected_families = set(EXPECTED_MAPPING.values())
    actual_families = set(get_canonical_map().values())
    missing_families = expected_families - actual_families
    assert not missing_families, f"Missing family_hint values in canonical map: {missing_families}"


def test_canonical_map_tool_ids_start_with_mock_verify() -> None:
    """All canonical tool_id keys MUST start with 'mock_verify_'."""
    mapping = get_canonical_map()
    invalid = [tid for tid in mapping if not tid.startswith("mock_verify_")]
    assert not invalid, f"tool_ids NOT starting with 'mock_verify_': {invalid}"
