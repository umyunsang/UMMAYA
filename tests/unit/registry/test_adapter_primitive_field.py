# SPDX-License-Identifier: Apache-2.0
"""T014 — AdapterRegistration primitive-field contract tests.

Proves the Spec 031 Phase 2 registry metadata model:
1. Accepts the active primitive names (lookup, resolve_location, submit, verify).
2. Rejects unknown primitives with a pydantic ValidationError.
3. Enforces ``extra='forbid'`` / ``frozen=True`` invariants on the model_config.
4. Accepts None on ``published_tier_minimum`` / ``nist_aal_hint`` during the
   pre-v1.2 compatibility window (FR-028).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kosmos.tools.registry import (
    AdapterPrimitive,
    AdapterRegistration,
    AdapterSourceMode,
)


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Minimum valid AdapterRegistration kwargs; tests layer overrides on top.

    Dual-axis fields default to non-None so constructions succeed under
    V12_GA_ACTIVE=True (Spec 031 T079 GA cut). Tests that need to exercise
    the pre-v1.2 compatibility window (None allowed) must ``monkeypatch`` the
    toggle off explicitly.

    Note: KOSMOS-invented Spec 033/024/025 fields (auth_level, pipa_class,
    dpa_reference) removed from AdapterRegistration in Epic δ #2295.
    """
    base: dict[str, object] = {
        "tool_id": "fake_adapter",
        "primitive": AdapterPrimitive.lookup,
        "module_path": "kosmos.tools.mock.data_go_kr.fake_adapter",
        "input_model_ref": "kosmos.tools.mock.data_go_kr.fake_adapter:FakeInput",
        "source_mode": AdapterSourceMode.OPENAPI,
        "published_tier_minimum": "digital_onepass_level2_aal2",
        "nist_aal_hint": "AAL2",
        "auth_type": "api_key",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "primitive_value",
    ["lookup", "resolve_location", "submit", "verify"],
)
def test_accepts_active_primitive_names(primitive_value: str) -> None:
    reg = AdapterRegistration(**_base_kwargs(primitive=primitive_value))
    assert reg.primitive == AdapterPrimitive(primitive_value)


def test_rejects_inactive_subscribe_primitive() -> None:
    with pytest.raises(ValidationError):
        AdapterRegistration(**_base_kwargs(primitive="subscribe"))


def test_rejects_unknown_primitive() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AdapterRegistration(**_base_kwargs(primitive="delete"))
    assert "primitive" in str(exc_info.value).lower()


def test_extra_fields_forbidden() -> None:
    """extra='forbid' must reject unknown keys on the registration envelope."""
    with pytest.raises(ValidationError):
        AdapterRegistration(**_base_kwargs(surprise_field="oops"))


def test_model_is_frozen() -> None:
    reg = AdapterRegistration(**_base_kwargs())
    with pytest.raises(ValidationError):
        reg.tool_id = "mutated"  # type: ignore[misc]


def test_pre_v12_allows_none_dual_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-v1.2 compatibility window (FR-028): both dual-axis fields may be None.

    Requires the v1.2 backstop toggled off — T079 flipped the runtime default
    to ``True``, so this test explicitly forces the legacy compatibility mode
    to prove the FR-028 contract still holds in that window.
    """
    import kosmos.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", False)

    reg = AdapterRegistration(**_base_kwargs(published_tier_minimum=None, nist_aal_hint=None))
    assert reg.published_tier_minimum is None
    assert reg.nist_aal_hint is None


def test_accepts_v12_dual_axis_values() -> None:
    reg = AdapterRegistration(
        **_base_kwargs(
            published_tier_minimum="digital_onepass_level2_aal2",
            nist_aal_hint="AAL2",
        )
    )
    assert reg.published_tier_minimum == "digital_onepass_level2_aal2"
    assert reg.nist_aal_hint == "AAL2"


def test_harness_only_source_mode() -> None:
    reg = AdapterRegistration(**_base_kwargs(source_mode=AdapterSourceMode.HARNESS_ONLY))
    assert reg.source_mode == AdapterSourceMode.HARNESS_ONLY


def test_tool_id_pattern_rejects_uppercase() -> None:
    with pytest.raises(ValidationError):
        AdapterRegistration(**_base_kwargs(tool_id="BadAdapter"))
