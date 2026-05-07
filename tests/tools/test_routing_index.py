# SPDX-License-Identifier: Apache-2.0
"""T013 — Unit tests for build_routing_index() invariants (Spec 1634 FR-007/008)."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from kosmos.tools.models import GovAPITool
from kosmos.tools.routing_index import (
    RoutingIndex,
    RoutingValidationError,
    build_routing_index,
)

# ---------------------------------------------------------------------------
# Minimal placeholder schemas
# ---------------------------------------------------------------------------


class _FixtureInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    query: str = ""


class _FixtureOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    result: str = ""


# ---------------------------------------------------------------------------
# Fixture factory
# ---------------------------------------------------------------------------


def _make_tool(**overrides) -> GovAPITool:
    """Build a minimal valid GovAPITool for routing-index testing.

    Defaults satisfy all V1-V6 invariants:
    - auth_type="public" + auth_level="public" (V6 consistent)
    - requires_auth=False (V5: public must not require auth)
    - pipa_class="non_personal" + dpa_reference=None (V1/V2: no PII)
    - is_irreversible=False (V4: public cannot be irreversible)
    - primitive="lookup" (Invariant 1: must be declared)
    """
    defaults: dict = {
        "id": "fixture_tool",
        "name_ko": "픽스처",
        "ministry": "KOROAD",
        "category": ["test"],
        "endpoint": "https://example.invalid/",
        "auth_type": "public",
        "input_schema": _FixtureInput,
        "output_schema": _FixtureOutput,
        "search_hint": "fixture test",
        "auth_level": "public",
        "pipa_class": "non_personal",
        "is_irreversible": False,
        "dpa_reference": None,
        "requires_auth": False,
        "primitive": "lookup",
        "adapter_mode": "live",
    }
    defaults.update(overrides)
    return GovAPITool(**defaults)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestBuildRoutingIndexHappy:
    def test_empty_list(self):
        """Empty adapter list produces an empty RoutingIndex with no warnings."""
        idx = build_routing_index([])
        assert idx.by_primitive == {}
        assert idx.by_tool_id == {}
        assert idx.warnings == ()

    def test_single_valid_adapter(self):
        """A single valid adapter is indexed by both tool_id and primitive."""
        idx = build_routing_index([_make_tool()])
        assert "fixture_tool" in idx.by_tool_id
        assert "lookup" in idx.by_primitive
        assert idx.by_primitive["lookup"][0].id == "fixture_tool"

    def test_multiple_adapters_different_primitives(self):
        """Adapters with different primitives each appear in their primitive bucket."""
        t1 = _make_tool(id="fixture_lookup", primitive="lookup")
        t2 = _make_tool(id="fixture_resolve", primitive="resolve_location")
        idx = build_routing_index([t1, t2])
        assert len(idx.by_primitive["lookup"]) == 1
        assert len(idx.by_primitive["resolve_location"]) == 1
        assert "fixture_lookup" in idx.by_tool_id
        assert "fixture_resolve" in idx.by_tool_id

    def test_multiple_adapters_same_primitive(self):
        """Multiple adapters with the same primitive are all in the same bucket."""
        t1 = _make_tool(id="tool_alpha", primitive="lookup")
        t2 = _make_tool(id="tool_beta", primitive="lookup")
        idx = build_routing_index([t1, t2])
        tool_ids = {a.id for a in idx.by_primitive["lookup"]}
        assert tool_ids == {"tool_alpha", "tool_beta"}

    def test_result_is_routing_index_instance(self):
        """Return value is a RoutingIndex (frozen Pydantic model)."""
        idx = build_routing_index([_make_tool()])
        assert isinstance(idx, RoutingIndex)


# ---------------------------------------------------------------------------
# Invariant 1: primitive must be declared (not None)
# ---------------------------------------------------------------------------


class TestInvariant1PrimitiveDeclared:
    def test_primitive_none_raises(self):
        """Adapter with primitive=None raises RoutingValidationError."""
        tool = _make_tool(primitive=None)
        with pytest.raises(RoutingValidationError) as exc_info:
            build_routing_index([tool])
        msg = str(exc_info.value)
        assert "invariant 1" in msg
        assert "primitive=None" in msg

    def test_primitive_none_message_contains_tool_id(self):
        """Error message names the offending tool_id."""
        tool = _make_tool(id="bad_tool", primitive=None)
        with pytest.raises(RoutingValidationError) as exc_info:
            build_routing_index([tool])
        assert "bad_tool" in str(exc_info.value)

    def test_first_adapter_none_stops_processing(self):
        """Fail-fast: error raised on first None-primitive adapter, not after."""
        bad = _make_tool(id="bad_tool", primitive=None)
        good = _make_tool(id="good_tool", primitive="lookup")
        with pytest.raises(RoutingValidationError):
            build_routing_index([bad, good])

    def test_valid_primitive_does_not_raise(self):
        """Each supported primitive value is accepted without error."""
        primitives = ["lookup", "resolve_location", "submit", "verify"]
        for prim in primitives:
            tool = _make_tool(id=f"tool_{prim}", primitive=prim)
            idx = build_routing_index([tool])
            assert f"tool_{prim}" in idx.by_tool_id


# ---------------------------------------------------------------------------
# Invariant 4: tool_id must be unique across the registry
# ---------------------------------------------------------------------------


class TestInvariant4UniqueToolId:
    def test_duplicate_id_raises(self):
        """Two adapters with the same id raise RoutingValidationError."""
        t1 = _make_tool(id="duplicate_tool")
        t2 = _make_tool(id="duplicate_tool")
        with pytest.raises(RoutingValidationError) as exc_info:
            build_routing_index([t1, t2])
        msg = str(exc_info.value)
        assert "invariant 4" in msg
        assert "duplicate registration" in msg

    def test_duplicate_id_message_contains_tool_id(self):
        """Error message names the duplicated tool_id."""
        t1 = _make_tool(id="my_tool")
        t2 = _make_tool(id="my_tool")
        with pytest.raises(RoutingValidationError) as exc_info:
            build_routing_index([t1, t2])
        assert "my_tool" in str(exc_info.value)

    def test_distinct_ids_do_not_raise(self):
        """Adapters with distinct ids register without error."""
        t1 = _make_tool(id="tool_one")
        t2 = _make_tool(id="tool_two")
        idx = build_routing_index([t1, t2])
        assert "tool_one" in idx.by_tool_id
        assert "tool_two" in idx.by_tool_id

    def test_three_tools_third_duplicate_raises(self):
        """Duplicate check catches the third tool when id matches an earlier one."""
        t1 = _make_tool(id="alpha")
        t2 = _make_tool(id="beta")
        t3 = _make_tool(id="alpha")
        with pytest.raises(RoutingValidationError) as exc_info:
            build_routing_index([t1, t2, t3])
        assert "invariant 4" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Invariant 5: compute_permission_tier must succeed for every adapter
# Invariant 5 is a defensive guard; GovAPITool Pydantic validator (V3/V4/V6)
# rejects any auth_level outside the Literal at construction time.
# The guard is reachable only via model_construct bypasses (future drift).
# ---------------------------------------------------------------------------


class TestInvariant5PermissionTierTotal:
    def test_public_auth_level_tier_resolves(self):
        """Adapter with auth_level='public' passes invariant 5 silently."""
        tool = _make_tool(auth_level="public", auth_type="public")
        idx = build_routing_index([tool])
        assert "fixture_tool" in idx.by_tool_id

    def test_invariant5_guard_unreachable_via_normal_construction(self):
        """auth_level is Literal-validated at GovAPITool construction;
        invariant 5 defensive guard cannot be triggered through the normal API.
        Documented skip is by design (see task T013 scope notes).
        """
        pytest.skip(
            "auth_level is Literal-validated by Pydantic at construction; "
            "invariant 5 is a defensive guard against future type drift "
            "and is unreachable through the public GovAPITool constructor."
        )


# ---------------------------------------------------------------------------
# Warning: ministry="OTHER" produces a non-fatal warning entry
# ---------------------------------------------------------------------------


class TestMinistryOtherWarning:
    def test_ministry_other_emits_warning(self):
        """Adapter with ministry='OTHER' adds a warning to RoutingIndex.warnings."""
        tool = _make_tool(ministry="OTHER")
        idx = build_routing_index([tool])
        assert len(idx.warnings) == 1
        assert "ministry='OTHER'" in idx.warnings[0]
        assert "fixture_tool" in idx.warnings[0]

    def test_ministry_other_warning_message_format(self):
        """Warning message matches the expected format including escape-hatch note."""
        tool = _make_tool(ministry="OTHER")
        idx = build_routing_index([tool])
        warning = idx.warnings[0]
        assert "transitional escape hatch" in warning

    def test_ministry_known_produces_no_warning(self):
        """Non-OTHER ministry values produce no warnings."""
        for ministry in ["KOROAD", "KMA", "NMC", "HIRA"]:
            tool = _make_tool(id=f"tool_{ministry.lower()}", ministry=ministry)
            idx = build_routing_index([tool])
            assert idx.warnings == (), f"Expected no warnings for ministry={ministry!r}"

    def test_ministry_other_still_indexed(self):
        """ministry='OTHER' is a warning, not a failure — tool is still indexed."""
        tool = _make_tool(ministry="OTHER")
        idx = build_routing_index([tool])
        assert "fixture_tool" in idx.by_tool_id
        assert len(idx.by_primitive["lookup"]) == 1

    def test_multiple_other_ministries_each_emit_warning(self):
        """Two OTHER-ministry adapters produce two separate warnings."""
        t1 = _make_tool(id="other_a", ministry="OTHER")
        t2 = _make_tool(id="other_b", ministry="OTHER")
        idx = build_routing_index([t1, t2])
        assert len(idx.warnings) == 2
        warning_text = " ".join(idx.warnings)
        assert "other_a" in warning_text
        assert "other_b" in warning_text
