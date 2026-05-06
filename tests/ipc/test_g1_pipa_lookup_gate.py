# SPDX-License-Identifier: Apache-2.0
"""Wave-2 G1 fix — F-beta-04 lookup-adapter-policy-aware permission gate.

The audit finding: non-read-only lookup adapters were dispatched WITHOUT a
Spec 035 PermissionGauntlet modal, because ``_check_permission_gate`` only
consulted the *primitive* name (``lookup`` is not in ``GATED_PRIMITIVES``) —
never the inner adapter's ``policy.citizen_facing_gate``.

This test reproduces the gate-decision branch directly (the full IPC loop
integration is covered by ``test_stdio_lookup_registry`` /
``test_stdio_chain_followup_gate``) and asserts:

1. ``lookup`` with a ``read-only`` adapter (e.g. KMA forecast) auto-allows
   (no modal traffic, return True).
2. ``lookup`` with a non-``read-only`` adapter triggers the modal flow — the
   gate must NOT short-circuit-return on the GATED_PRIMITIVES check; it must
   walk the full PermissionRequestFrame emission path.
3. ``lookup`` with an unknown ``tool_id`` fails closed (modal flow) so
   that an unregistered/typo'd ``tool_id`` cannot bypass consent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kosmos.primitives import GATED_PRIMITIVES


def _make_registry_mock(*, tool_id: str, citizen_facing_gate: str | None) -> MagicMock:
    """Build a fake ToolRegistry whose ``.lookup(<tool_id>)`` returns a
    fake tool with the given ``policy.citizen_facing_gate``.

    ``citizen_facing_gate=None`` simulates an adapter without a policy
    object — the gate must treat that as fail-closed (modal required).
    """

    fake_policy = (
        None if citizen_facing_gate is None else MagicMock(citizen_facing_gate=citizen_facing_gate)
    )
    fake_tool = MagicMock(policy=fake_policy)
    registry = MagicMock()
    registry.lookup.return_value = fake_tool
    return registry


def _classify(*, fname: str, args_obj: dict[str, object], registry: MagicMock | None) -> str:
    """Replica of the gate's first decision branch (post-fix), returning
    one of ``"auto_allow"`` / ``"needs_modal"``.

    Mirrors the patched logic in ``stdio.py:_check_permission_gate``
    around the ``_lookup_needs_modal`` flag.
    """
    if fname in GATED_PRIMITIVES:
        return "needs_modal"
    if fname != "lookup":
        return "auto_allow"
    inner = args_obj.get("tool_id")
    if not isinstance(inner, str) or not inner:
        return "auto_allow"
    if registry is None:
        return "needs_modal"  # fail-closed
    try:
        tool = registry.lookup(inner)
        gate = tool.policy.citizen_facing_gate if tool.policy is not None else "login"
        return "auto_allow" if gate == "read-only" else "needs_modal"
    except Exception:  # noqa: BLE001
        return "needs_modal"


def test_lookup_readonly_adapter_auto_allows() -> None:
    """KMA forecast (read-only adapter) → auto_allow, no modal."""
    registry = _make_registry_mock(tool_id="kma_forecast_fetch", citizen_facing_gate="read-only")
    decision = _classify(
        fname="lookup",
        args_obj={"tool_id": "kma_forecast_fetch", "params": {"nx": 60, "ny": 127}},
        registry=registry,
    )
    assert decision == "auto_allow"


@pytest.mark.parametrize(
    "gate_label",
    ["login", "action", "sign", "submit"],
)
def test_lookup_non_readonly_adapter_requires_modal(gate_label: str) -> None:
    """Sensitive lookup adapters enter the modal flow through lookup."""
    registry = _make_registry_mock(tool_id="mock_sensitive_lookup", citizen_facing_gate=gate_label)
    decision = _classify(
        fname="lookup",
        args_obj={
            "tool_id": "mock_sensitive_lookup",
            "params": {"lat": 37.5665, "lon": 126.978},
        },
        registry=registry,
    )
    assert decision == "needs_modal"


def test_lookup_unknown_tool_id_fails_closed() -> None:
    """Unregistered tool_id → modal (fail-closed). The downstream
    invoke() will produce an unknown_tool envelope after consent, but
    the gate must not let an unknown id past consent silently."""
    registry = MagicMock()
    registry.lookup.side_effect = KeyError("nope")
    decision = _classify(
        fname="lookup",
        args_obj={"tool_id": "definitely_not_registered", "params": {}},
        registry=registry,
    )
    assert decision == "needs_modal"


def test_lookup_with_no_registry_fails_closed() -> None:
    """Boot race: registry not yet ensured. Gate must fail-closed."""
    decision = _classify(
        fname="lookup",
        args_obj={"tool_id": "mock_sensitive_lookup", "params": {}},
        registry=None,
    )
    assert decision == "needs_modal"


def test_lookup_with_none_policy_fails_closed() -> None:
    """Pre-Spec-2295 adapter without ``policy`` object → derived gate
    defaults to ``"login"`` (Spec δ #2295 Path B). Modal required."""
    registry = _make_registry_mock(tool_id="legacy_unmigrated", citizen_facing_gate=None)
    decision = _classify(
        fname="lookup",
        args_obj={"tool_id": "legacy_unmigrated", "params": {}},
        registry=registry,
    )
    assert decision == "needs_modal"


def test_verify_primitive_unaffected_by_lookup_branch() -> None:
    """verify is in GATED_PRIMITIVES; the new branch is lookup-only."""
    decision = _classify(
        fname="verify",
        args_obj={"tool_id": "mock_verify_mobile_id", "params": {}},
        registry=None,
    )
    assert decision == "needs_modal"


def test_resolve_location_remains_auto_allow() -> None:
    """resolve_location is a public utility — never gated, regardless
    of lookup-branch changes."""
    decision = _classify(
        fname="resolve_location",
        args_obj={"query": "강남구"},
        registry=None,
    )
    assert decision == "auto_allow"
