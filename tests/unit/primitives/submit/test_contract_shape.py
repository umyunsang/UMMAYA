# SPDX-License-Identifier: Apache-2.0
"""T016 — Contract shape tests for the submit primitive.

Loads ``specs/031-five-primitive-harness/contracts/submit.input.schema.json``
and ``submit.output.schema.json``, validates them against fixture payloads,
and asserts that no domain-specific (SC-002) banned fields appear in either
schema.

References:
- specs/031-five-primitive-harness/contracts/submit.input.schema.json
- specs/031-five-primitive-harness/contracts/submit.output.schema.json
- specs/031-five-primitive-harness/data-model.md § 1
- FR-001, FR-002, FR-003, SC-002
"""

from __future__ import annotations

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Schema paths
# ---------------------------------------------------------------------------

_CONTRACTS_DIR = (
    pathlib.Path(__file__).parents[4]  # repo root
    / "specs"
    / "031-five-primitive-harness"
    / "contracts"
)

_INPUT_SCHEMA_PATH = _CONTRACTS_DIR / "submit.input.schema.json"
_OUTPUT_SCHEMA_PATH = _CONTRACTS_DIR / "submit.output.schema.json"

# SC-002 banned strings — must NEVER appear as property names in either schema.
_BANNED_FIELD_NAMES = frozenset(
    [
        "check_eligibility",
        "reserve_slot",
        "subscribe_alert",
        "pay",
        "issue_certificate",
        "submit_application",
        "declared_income_krw",
        "certificate_type",
        "family_register",
        "resident_register",
    ]
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_schema(path: pathlib.Path) -> dict[str, object]:
    """Load and parse a JSON Schema file."""
    assert path.exists(), f"Contract schema not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_property_names(schema: dict[str, object]) -> set[str]:
    """Recursively collect all property names from a JSON Schema object."""
    names: set[str] = set()
    props = schema.get("properties")
    if isinstance(props, dict):
        for key, val in props.items():
            names.add(key)
            if isinstance(val, dict):
                names |= _collect_property_names(val)
    for sub_key in ("items", "additionalProperties"):
        sub = schema.get(sub_key)
        if isinstance(sub, dict):
            names |= _collect_property_names(sub)
    for array_key in ("allOf", "anyOf", "oneOf"):
        sub_list = schema.get(array_key)
        if isinstance(sub_list, list):
            for entry in sub_list:
                if isinstance(entry, dict):
                    names |= _collect_property_names(entry)
    return names


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def input_schema() -> dict[str, object]:
    return _load_schema(_INPUT_SCHEMA_PATH)


@pytest.fixture(scope="module")
def output_schema() -> dict[str, object]:
    return _load_schema(_OUTPUT_SCHEMA_PATH)


# ---------------------------------------------------------------------------
# T016-A: Schema structural contracts
# ---------------------------------------------------------------------------


def test_input_schema_required_fields(input_schema: dict[str, object]) -> None:
    """submit.input MUST require tool_id and params (FR-001)."""
    required = set(input_schema.get("required", []))
    assert "tool_id" in required, "tool_id must be in required"
    assert "params" in required, "params must be in required"


def test_input_schema_no_extra_required_fields(input_schema: dict[str, object]) -> None:
    """submit.input MUST NOT require any domain-specific fields beyond tool_id/params."""
    required = set(input_schema.get("required", []))
    domain_required = required - {"tool_id", "params"}
    assert not domain_required, (
        f"submit.input schema has unexpected required fields: {domain_required} "
        "(SC-002: main envelope must be domain-agnostic)"
    )


def test_output_schema_required_fields(output_schema: dict[str, object]) -> None:
    """submit.output MUST require transaction_id, status, and adapter_receipt (FR-004/FR-005)."""
    required = set(output_schema.get("required", []))
    assert "transaction_id" in required
    assert "status" in required
    assert "adapter_receipt" in required


def test_output_schema_status_enum(output_schema: dict[str, object]) -> None:
    """status field must be closed enum: pending/succeeded/failed/rejected."""
    props = output_schema.get("properties", {})
    status_schema = props.get("status", {})
    status_values = set(status_schema.get("enum", []))
    assert status_values == {"pending", "succeeded", "failed", "rejected"}, (
        f"status enum mismatch: got {status_values}"
    )


def test_input_schema_additional_properties_true(input_schema: dict[str, object]) -> None:
    """params sub-schema must allow additionalProperties (adapter owns shape)."""
    props = input_schema.get("properties", {})
    params_schema = props.get("params", {})
    # The main envelope sets additionalProperties=false (envelope-level),
    # but params itself must not restrict further — its value is opaque.
    assert params_schema.get("additionalProperties") is True, (
        "params must allow additionalProperties=true so adapter-specific params are not rejected"
    )


def test_output_schema_additional_properties_true(output_schema: dict[str, object]) -> None:
    """adapter_receipt must allow additionalProperties (adapter owns shape)."""
    props = output_schema.get("properties", {})
    receipt_schema = props.get("adapter_receipt", {})
    assert receipt_schema.get("additionalProperties") is True, (
        "adapter_receipt must allow additionalProperties=true (adapter-opaque receipt)"
    )


# ---------------------------------------------------------------------------
# T016-B: SC-002 banned field names check
# ---------------------------------------------------------------------------


def test_input_schema_no_banned_field_names(input_schema: dict[str, object]) -> None:
    """No banned domain-specific field names may appear in submit.input schema."""
    all_property_names = _collect_property_names(input_schema)
    violations = all_property_names & _BANNED_FIELD_NAMES
    assert not violations, (
        f"submit.input.schema.json contains banned field names: {sorted(violations)} "
        "(SC-002 violation)"
    )


def test_output_schema_no_banned_field_names(output_schema: dict[str, object]) -> None:
    """No banned domain-specific field names may appear in submit.output schema."""
    all_property_names = _collect_property_names(output_schema)
    violations = all_property_names & _BANNED_FIELD_NAMES
    assert not violations, (
        f"submit.output.schema.json contains banned field names: {sorted(violations)} "
        "(SC-002 violation)"
    )


# ---------------------------------------------------------------------------
# T016-C: Fixture payload validation (lightweight inline fixtures)
# ---------------------------------------------------------------------------


def test_valid_input_fixture_shape(input_schema: dict[str, object]) -> None:
    """A canonical valid SubmitInput payload must satisfy the schema structure."""
    fixture = {
        "tool_id": "mock_traffic_fine_pay_v1",
        "params": {"fine_reference": "2026-04-19-0001", "payment_method": "virtual_account"},
    }
    # Manual structural check (no jsonschema dep — SC-008 prohibits new deps)
    required = set(input_schema.get("required", []))
    for field in required:
        assert field in fixture, f"Fixture missing required field: {field}"

    # tool_id pattern check
    import re

    pattern = input_schema["properties"]["tool_id"]["pattern"]
    assert re.fullmatch(pattern, fixture["tool_id"]), (
        f"tool_id {fixture['tool_id']!r} must match pattern {pattern!r}"
    )


def test_valid_output_fixture_shape(output_schema: dict[str, object]) -> None:
    """A canonical valid SubmitOutput payload must satisfy the schema structure."""
    fixture = {
        "transaction_id": "urn:ummaya:send:abc123",
        "status": "succeeded",
        "adapter_receipt": {"receipt_number": "2026-04-19-0001"},
    }
    required = set(output_schema.get("required", []))
    for field in required:
        assert field in fixture, f"Fixture missing required field: {field}"

    # status must be in enum
    status_enum = set(output_schema["properties"]["status"]["enum"])
    assert fixture["status"] in status_enum, (
        f"status {fixture['status']!r} not in valid enum {status_enum}"
    )


def test_rejected_output_fixture_shape(output_schema: dict[str, object]) -> None:
    """A 'rejected' status payload (e.g. tier gate) must be schema-valid."""
    fixture = {
        "transaction_id": "urn:ummaya:send:rejected001",
        "status": "rejected",
        "adapter_receipt": {"reason": "published_tier_minimum not met"},
    }
    status_enum = set(output_schema["properties"]["status"]["enum"])
    assert fixture["status"] in status_enum
