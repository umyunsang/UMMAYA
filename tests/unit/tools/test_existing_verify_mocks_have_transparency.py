# SPDX-License-Identifier: Apache-2.0
"""T022 — Existing 5 verify mocks carry six transparency fields after retrofit.

Parameterised over the 5 remaining verify mocks (after digital_onepass deletion).
Asserts that each mock's invoke() returns an object whose model_dump(by_alias=True)
carries all six transparency fields populated and non-empty.

Contract: specs/2296-ax-mock-adapters/contracts/mock-adapter-response-shape.md § 4
          "EXISTING (retrofitted)" rows.
"""

from __future__ import annotations

import pytest

# The 5 existing (retrofitted) verify mock modules.
_EXISTING_VERIFY_MOCKS = [
    "kosmos.tools.mock.verify_mobile_id",
    "kosmos.tools.mock.verify_gongdong_injeungseo",
    "kosmos.tools.mock.verify_geumyung_injeungseo",
    "kosmos.tools.mock.verify_ganpyeon_injeung",
    "kosmos.tools.mock.verify_mydata",
]

_SIX_TRANSPARENCY_FIELDS = [
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
]


@pytest.mark.parametrize("module_path", _EXISTING_VERIFY_MOCKS)
def test_existing_verify_mock_has_six_transparency_fields(module_path: str) -> None:
    """Each retrofitted existing verify mock carries all six transparency fields."""
    import importlib

    mod = importlib.import_module(module_path)
    assert hasattr(mod, "invoke"), f"{module_path} has no invoke() function"
    result = mod.invoke({})

    # Existing verify mocks return Pydantic context objects; use model_dump to get dict.
    d = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result

    for field in _SIX_TRANSPARENCY_FIELDS:
        value = d.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), (
            f"{module_path}: transparency field {field!r} is missing or empty. "
            f"Got value={value!r}. Retrofit must call stamp_mock_response or populate fields."
        )


@pytest.mark.parametrize("module_path", _EXISTING_VERIFY_MOCKS)
def test_existing_verify_mock_mode_is_mock(module_path: str) -> None:
    """The _mode field must be exactly 'mock' for all existing retrofitted mocks."""
    import importlib

    mod = importlib.import_module(module_path)
    result = mod.invoke({})
    d = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result

    assert d.get("_mode") == "mock", f"{module_path}: expected _mode='mock', got {d.get('_mode')!r}"


@pytest.mark.parametrize("module_path", _EXISTING_VERIFY_MOCKS)
def test_existing_verify_mock_reference_impl_is_public_mydata(module_path: str) -> None:
    """All 5 existing mocks use 'public-mydata-read-v240930' as reference_implementation."""
    import importlib

    mod = importlib.import_module(module_path)
    result = mod.invoke({})
    d = result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result

    assert d.get("_reference_implementation") == "public-mydata-read-v240930", (
        f"{module_path}: expected _reference_implementation='public-mydata-read-v240930', "
        f"got {d.get('_reference_implementation')!r}"
    )


def test_digital_onepass_is_not_in_existing_mocks() -> None:
    """Verify that digital_onepass is NOT in the existing mock list (FR-004 deletion guard)."""
    for module_path in _EXISTING_VERIFY_MOCKS:
        assert "digital_onepass" not in module_path, (
            f"verify_digital_onepass should have been deleted (FR-004) but found in mock list: "
            f"{module_path}"
        )


def test_verify_mydata_has_evidence_grade() -> None:
    """MyData verify mock exposes evidence metadata for private credential requirements."""
    from kosmos.tools.mock.verify_mydata import invoke

    result = invoke({})
    dumped = result.model_dump(by_alias=True)
    assert dumped["_mock_fidelity_grade"] == (
        "B-public-mydata-standard-private-credential-required"
    )
    assert dumped["_mock_evidence"]["credential_status"] == "student_no_live_authority"
    assert "live_swap_requirements" in dumped["_mock_evidence"]
