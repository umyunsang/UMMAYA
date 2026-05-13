# SPDX-License-Identifier: Apache-2.0
"""T074 — Unit tests for v1.2 GA dual-axis enforcement backstop.

Toggles ``ummaya.security.v12_dual_axis.V12_GA_ACTIVE = True`` and asserts
that ``AdapterRegistration`` construction raises ``DualAxisMissingError`` when
either of the dual-axis fields (``published_tier_minimum`` / ``nist_aal_hint``)
is ``None`` (FR-030, SC-007).

Also asserts the pre-v1.2 compatibility window: with the toggle monkeypatched
to ``False``, both fields may be ``None`` without error (FR-028). Note: after
Phase 9 T073-T080 cutover, :data:`V12_GA_ACTIVE` now defaults to ``True``; the
compatibility-window tests explicitly toggle it off via ``monkeypatch``.

Expected red state:
  - ``DualAxisMissingError`` does not yet exist in ``ummaya.tools.errors``
    (Lead will add it as a subclass of ``RegistrationError``).
  - ``enforce()`` is not yet wired into ``AdapterRegistration.__init__``
    (Lead will wire it).
  Both of these cause ImportError / test failure in the red phase — that is
  the correct TDD signal.

References:
- specs/031-five-primitive-harness/spec.md FR-028, FR-030, SC-007
- specs/031-five-primitive-harness/tasks.md T074
- src/ummaya/security/v12_dual_axis.py (enforce + V12_GA_ACTIVE)
- src/ummaya/tools/errors.py (RegistrationError — parent class)
"""

from __future__ import annotations

import pytest

# Top-level imports so that ImportError surfaces immediately as a red test
# (explicit red state per T074 TDD contract).
from ummaya.tools.errors import (  # type: ignore[attr-defined]
    DualAxisMissingError,
    RegistrationError,
)
from ummaya.tools.registry import AdapterPrimitive, AdapterRegistration, AdapterSourceMode

# ---------------------------------------------------------------------------
# Helpers — kwargs factory
# ---------------------------------------------------------------------------


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Minimum valid AdapterRegistration kwargs with both dual-axis fields set.

    Mirrors the pattern from tests/unit/registry/test_adapter_primitive_field.py.

    Note: UMMAYA-invented Spec 033/024/025 fields (auth_level, pipa_class,
    dpa_reference, requires_auth, is_personal_data, is_concurrency_safe,
    cache_ttl_seconds, rate_limit_per_minute) removed from AdapterRegistration
    in Epic δ #2295 (Constitution § II cleanup).
    """
    base: dict[str, object] = {
        "tool_id": "fake_v12_adapter",
        "primitive": AdapterPrimitive.send,
        "module_path": "ummaya.tools.mock.data_go_kr.fake_v12_adapter",
        "input_model_ref": "ummaya.tools.mock.data_go_kr.fake_v12_adapter:FakeInput",
        "source_mode": AdapterSourceMode.HARNESS_ONLY,
        # Dual-axis fields — both set for the positive-control baseline.
        "published_tier_minimum": "digital_onepass_level2_aal2",
        "nist_aal_hint": "AAL2",
        "auth_type": "api_key",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test A — published_tier_minimum=None raises DualAxisMissingError
# ---------------------------------------------------------------------------


def test_v12_active_missing_published_tier_minimum_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """published_tier_minimum=None under V12_GA_ACTIVE=True raises DualAxisMissingError.

    The error message must mention the missing field name (FR-030).
    RED until Lead wires enforce() into AdapterRegistration and adds DualAxisMissingError.
    """
    import ummaya.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", True)

    with pytest.raises(DualAxisMissingError) as exc_info:
        AdapterRegistration(**_base_kwargs(published_tier_minimum=None))

    assert "published_tier_minimum" in str(exc_info.value), (
        "DualAxisMissingError message must name the missing field 'published_tier_minimum'."
    )


# ---------------------------------------------------------------------------
# Test B — nist_aal_hint=None raises DualAxisMissingError
# ---------------------------------------------------------------------------


def test_v12_active_missing_nist_aal_hint_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """nist_aal_hint=None under V12_GA_ACTIVE=True raises DualAxisMissingError.

    The error message must mention the missing field name (FR-030).
    RED until Lead wires enforce() and adds DualAxisMissingError.
    """
    import ummaya.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", True)

    with pytest.raises(DualAxisMissingError) as exc_info:
        AdapterRegistration(**_base_kwargs(nist_aal_hint=None))

    assert "nist_aal_hint" in str(exc_info.value), (
        "DualAxisMissingError message must name the missing field 'nist_aal_hint'."
    )


# ---------------------------------------------------------------------------
# Test C — both None raises DualAxisMissingError mentioning both fields
# ---------------------------------------------------------------------------


def test_v12_active_both_fields_missing_raises_mentioning_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both fields None raises DualAxisMissingError mentioning both names (FR-030).

    RED until Lead wires enforce() and adds DualAxisMissingError.
    """
    import ummaya.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", True)

    with pytest.raises(DualAxisMissingError) as exc_info:
        AdapterRegistration(**_base_kwargs(published_tier_minimum=None, nist_aal_hint=None))

    err_str = str(exc_info.value)
    assert "published_tier_minimum" in err_str, (
        "Error must mention 'published_tier_minimum' when it is the missing field."
    )
    assert "nist_aal_hint" in err_str, (
        "Error must mention 'nist_aal_hint' when it is the missing field."
    )


# ---------------------------------------------------------------------------
# Test D — both fields set → construction succeeds
# ---------------------------------------------------------------------------


def test_v12_active_both_fields_set_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both dual-axis fields set → AdapterRegistration constructs without error (FR-030).

    This is the positive control. RED only if enforce() is wired incorrectly.
    Expected green once Lead completes T079.
    """
    import ummaya.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", True)

    reg = AdapterRegistration(**_base_kwargs())
    assert reg.published_tier_minimum == "digital_onepass_level2_aal2"
    assert reg.nist_aal_hint == "AAL2"


# ---------------------------------------------------------------------------
# Test E — V12_GA_ACTIVE=False (default) allows both None (compat window)
# ---------------------------------------------------------------------------


def test_v12_inactive_both_none_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """V12_GA_ACTIVE=False → both None fields accepted (pre-v1.2 compat window FR-028).

    This must pass NOW (without any Lead changes) because the current default
    is V12_GA_ACTIVE=False and the current AdapterRegistration allows None.
    """
    import ummaya.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", False)

    reg = AdapterRegistration(**_base_kwargs(published_tier_minimum=None, nist_aal_hint=None))
    assert reg.published_tier_minimum is None
    assert reg.nist_aal_hint is None


# ---------------------------------------------------------------------------
# Test F — DualAxisMissingError is a subclass of RegistrationError
# ---------------------------------------------------------------------------


def test_dual_axis_missing_error_is_subclass_of_registration_error() -> None:
    """DualAxisMissingError MUST be a subclass of RegistrationError (FR-028 compat).

    Ensures existing ``except RegistrationError`` call sites keep working when
    DualAxisMissingError is raised by the v1.2 backstop.

    RED until Lead adds DualAxisMissingError(RegistrationError) to errors.py.
    """
    assert issubclass(DualAxisMissingError, RegistrationError), (
        "DualAxisMissingError must inherit from RegistrationError so that "
        "existing 'except RegistrationError' handlers catch it without change."
    )
