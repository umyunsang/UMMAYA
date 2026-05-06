# SPDX-License-Identifier: Apache-2.0
"""T020 — Integration test for published_tier_minimum gate (SC-005).

Registers a mock submit adapter with ``published_tier_minimum="ganpyeon_injeung_kakao_aal2"``,
then invokes it with a mismatched AuthContext (or no AuthContext) and asserts a structured
rejection is returned.

SC-005: A ``submit`` adapter declaring ``published_tier_minimum`` must gate access based on
the caller's ``published_tier``. A mismatched tier returns status=rejected in SubmitOutput,
not an unhandled exception.

Note on US2 AuthContext:
  The full AuthContext discriminated union (GanpyeonInjeungContext etc.) lands in US2 (T034+).
  For T020, we use a minimal stand-in Pydantic model that carries only the
  ``published_tier`` field needed to exercise the gate.
  The AuthContext-specific branch with full family validation is marked
  ``@pytest.mark.xfail`` so it becomes a passing assertion once US2 lands.

References:
- specs/031-five-primitive-harness/data-model.md § 2 (AuthContext)
- specs/031-five-primitive-harness/spec.md SC-005
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict

from kosmos.tools.models import AdapterRealDomainPolicy
from kosmos.tools.registry import AdapterPrimitive, AdapterRegistration, AdapterSourceMode

# ---------------------------------------------------------------------------
# Minimal AuthContext stand-in (pre-US2)
# ---------------------------------------------------------------------------


class _MinimalAuthContext(BaseModel):
    """Minimal stand-in for US2 AuthContext.

    Carries only ``published_tier`` so the SC-005 gate logic can be exercised
    before the full discriminated-union AuthContext lands in US2.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    published_tier: str


# ---------------------------------------------------------------------------
# Fixtures — adapter registration scoped to this test module
# ---------------------------------------------------------------------------


@pytest.fixture
def tier_gated_registration() -> AdapterRegistration:
    """An AdapterRegistration that requires ganpyeon_injeung_kakao_aal2."""
    return AdapterRegistration(
        tool_id="mock_tier_gated_submit_v1",
        primitive=AdapterPrimitive.submit,
        module_path="tests.integration.test_submit_published_tier_gate",
        input_model_ref="tests.integration.test_submit_published_tier_gate:_MinimalAuthContext",
        source_mode=AdapterSourceMode.HARNESS_ONLY,
        published_tier_minimum="ganpyeon_injeung_kakao_aal2",
        nist_aal_hint="AAL2",
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=10,
        search_hint={
            "ko": ["등록테스트", "계층게이트"],
            "en": ["tier gate test"],
        },
        auth_type="oauth",
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://example.gov.kr/policy/submit",
            real_classification_text="테스트 등록 submit 정책",
            citizen_facing_gate="submit",
            last_verified=datetime(2026, 4, 29, tzinfo=UTC),
        ),
    )


# ---------------------------------------------------------------------------
# T020-A: No auth_context → rejected (fail-closed, SC-005)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_without_auth_context_returns_rejected(
    tier_gated_registration: AdapterRegistration,
) -> None:
    """Invoking a tier-gated adapter without auth_context returns status=rejected.

    This test exercises the fail-closed default: when the caller provides no
    AuthContext and the adapter has published_tier_minimum set, the submit
    dispatcher MUST return a rejected SubmitOutput.

    The test uses the real ``submit()`` function with the adapter registration
    injected via the module-level registry fixture. Since we cannot mutate the
    global registry singleton in isolation without a reset mechanism, we test
    the gate logic by directly invoking the tier check helper.
    """
    # Import the tier-gate checker from submit (exposed for testability)
    from kosmos.primitives.submit import check_tier_gate

    auth_ctx = None  # no auth context supplied
    result = check_tier_gate(
        registration=tier_gated_registration,
        auth_context=auth_ctx,
    )
    assert result is not None, "check_tier_gate must return a rejection dict when auth_context=None"
    assert result["rejected"] is True
    assert "published_tier_minimum" in result.get("reason", "")


# ---------------------------------------------------------------------------
# T020-B: Auth context with insufficient tier → rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_with_insufficient_tier_returns_rejected(
    tier_gated_registration: AdapterRegistration,
) -> None:
    """Auth context with a lower tier than required → structured rejection."""
    from kosmos.primitives.submit import check_tier_gate

    # digital_onepass_level1_aal1 is AAL1 — below the required AAL2 tier
    auth_ctx = _MinimalAuthContext(published_tier="digital_onepass_level1_aal1")
    result = check_tier_gate(
        registration=tier_gated_registration,
        auth_context=auth_ctx,
    )
    assert result is not None, "Insufficient tier must produce a rejection"
    assert result["rejected"] is True


# ---------------------------------------------------------------------------
# T020-C: Auth context with matching tier → passes gate (not rejected)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_with_matching_tier_passes_gate(
    tier_gated_registration: AdapterRegistration,
) -> None:
    """Auth context exactly matching published_tier_minimum → gate passes."""
    from kosmos.primitives.submit import check_tier_gate

    # ganpyeon_injeung_kakao_aal2 matches the required minimum exactly
    auth_ctx = _MinimalAuthContext(published_tier="ganpyeon_injeung_kakao_aal2")
    result = check_tier_gate(
        registration=tier_gated_registration,
        auth_context=auth_ctx,
    )
    assert result is None, "Matching tier must return None (gate passes — no rejection)"


@pytest.mark.asyncio
async def test_submit_with_ax_module_aal3_tier_satisfies_aal2_gate(
    tier_gated_registration: AdapterRegistration,
) -> None:
    """AX-channel AAL3 verify tiers are recognised and satisfy lower AAL2 gates."""
    from kosmos.primitives.submit import check_tier_gate

    auth_ctx = _MinimalAuthContext(published_tier="modid_aal3")
    result = check_tier_gate(
        registration=tier_gated_registration,
        auth_context=auth_ctx,
    )
    assert result is None, "A recognised AAL3 module tier must satisfy an AAL2 gate"


# ---------------------------------------------------------------------------
# T020-D: Adapter with no tier minimum → always passes gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_no_tier_minimum_always_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adapter with published_tier_minimum=None never rejects on tier (pre-v1.2).

    Forces ``V12_GA_ACTIVE=False`` so the pre-v1.2 compatibility window
    (FR-028) is in effect; T079 flipped the runtime default to ``True``.
    """
    import kosmos.security.v12_dual_axis as _mod

    monkeypatch.setattr(_mod, "V12_GA_ACTIVE", False)

    from kosmos.primitives.submit import check_tier_gate

    reg_no_tier = AdapterRegistration(
        tool_id="mock_no_tier_v1",
        primitive=AdapterPrimitive.submit,
        module_path="tests.integration.test_submit_published_tier_gate",
        input_model_ref="tests.integration.test_submit_published_tier_gate:_MinimalAuthContext",
        source_mode=AdapterSourceMode.HARNESS_ONLY,
        published_tier_minimum=None,
        nist_aal_hint=None,
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=10,
        search_hint={},
        auth_type="oauth",
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://example.gov.kr/policy/submit",
            real_classification_text="테스트 no-tier submit 정책",
            citizen_facing_gate="submit",
            last_verified=datetime(2026, 4, 29, tzinfo=UTC),
        ),
    )
    result = check_tier_gate(registration=reg_no_tier, auth_context=None)
    assert result is None, "No tier minimum → gate always passes"


# ---------------------------------------------------------------------------
# T020-E: Full AuthContext family validation (xfail until US2 lands)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "US2 AuthContext full discriminated-union (GanpyeonInjeungContext) lands separately. "
        "This branch validates that family='ganpyeon_injeung' + published_tier match. "
        "Remove xfail when US2 (T034+) is merged."
    )
)
@pytest.mark.asyncio
async def test_submit_full_auth_context_family_validation(
    tier_gated_registration: AdapterRegistration,
) -> None:
    """Full US2 AuthContext family validation: ganpyeon_injeung family + matching tier → pass.

    This test will become a real assertion once the full AuthContext discriminated
    union from US2 is available. Until then it is an expected failure.
    """
    # This import will fail until US2 ships AuthContext
    from kosmos.primitives.verify import AuthContext  # type: ignore[import]  # noqa: F401

    raise AssertionError("US2 AuthContext not yet implemented — should xfail")
