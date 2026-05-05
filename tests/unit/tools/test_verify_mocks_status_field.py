# SPDX-License-Identifier: Apache-2.0
"""Lead-S3 #2659 (2026-05-04) — verify mock envelope ``status`` field regression.

Every ``verify_*`` mock adapter MUST stamp ``status="verified"`` on its returned
``AuthContext`` envelope so the TUI's ``VerifyPrimitive.renderToolResultMessage``
renders the green ``인증 완료`` label instead of the ambiguous ``결과 수신됨``
fallback (``tui/src/tools/VerifyPrimitive/VerifyPrimitive.ts`` line 297).

Sister contract: ``VerifyMismatchError`` carries ``status="failed"`` so
defense-in-depth callers that bypass ``dispatchPrimitive``'s [H1] inner-payload
classification still surface explicit failure.

Spec context:
- Lead-S3 root cause: envelope.status missing → TUI hallucination cascade.
- Citizen UX impact: "결과 수신됨" reads as uncertain → mis-info safety risk.
- LLM cascade impact: K-EXAONE reads "uncertain" → wrong chain branch.
"""

from __future__ import annotations

import importlib

import pytest

from kosmos.primitives.verify import VerifyMismatchError

# All 10 verify mock adapter modules.
_ALL_VERIFY_MOCKS = [
    # 5 retrofitted existing (Spec 2296 T022).
    "kosmos.tools.mock.verify_mobile_id",
    "kosmos.tools.mock.verify_mydata",
    "kosmos.tools.mock.verify_gongdong_injeungseo",
    "kosmos.tools.mock.verify_geumyung_injeungseo",
    "kosmos.tools.mock.verify_ganpyeon_injeung",
    # 5 new AX-channel mocks (Spec 2296 FR-001).
    "kosmos.tools.mock.verify_module_simple_auth",
    "kosmos.tools.mock.verify_module_modid",
    "kosmos.tools.mock.verify_module_kec",
    "kosmos.tools.mock.verify_module_geumyung",
    "kosmos.tools.mock.verify_module_any_id_sso",
]


@pytest.mark.parametrize("module_path", _ALL_VERIFY_MOCKS)
def test_verify_mock_envelope_has_status_verified(module_path: str) -> None:
    """Each mock_verify_* adapter stamps ``status="verified"`` on success.

    The TUI's ``VerifyPrimitive.renderToolResultMessage`` reads
    ``result['status']`` and maps ``"verified"`` → ``인증 완료`` (green).
    Any other value (including missing) falls through to ``결과 수신됨``.
    """
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "invoke"), f"{module_path}: no invoke() function"

    result = mod.invoke({})
    assert hasattr(result, "model_dump"), f"{module_path}: invoke() did not return a Pydantic model"

    dumped = result.model_dump(by_alias=True)
    status = dumped.get("status")
    assert status == "verified", (
        f"{module_path}: envelope ``status`` field must be 'verified' "
        f"(success path), got {status!r}. Lead-S3 fix: _AuthContextBase "
        f"now stamps status='verified' as a class default. If this fails, "
        f"check that the adapter returns a typed AuthContext variant "
        f"(not a raw dict)."
    )


@pytest.mark.parametrize("module_path", _ALL_VERIFY_MOCKS)
def test_verify_mock_status_is_in_one_of_two_values(module_path: str) -> None:
    """The ``status`` field is exactly ``verified`` or ``failed`` — no other values."""
    mod = importlib.import_module(module_path)
    result = mod.invoke({})
    dumped = result.model_dump(by_alias=True)
    status = dumped.get("status")
    assert status in {"verified", "failed"}, (
        f"{module_path}: status must be one of {{'verified', 'failed'}}, "
        f"got {status!r}. Anything else triggers the TUI fallback render."
    )


def test_verify_mismatch_error_carries_status_failed() -> None:
    """The failure-path companion model carries ``status="failed"``.

    ``VerifyMismatchError`` is the canonical failure envelope returned by
    ``verify()`` when:
      - no adapter is registered for the requested family,
      - the adapter raises a coercion mismatch (FR-010),
      - the dispatcher detects a family mismatch on the returned context.

    The ``dispatchPrimitive`` [H1] branch on the TUI side already classifies
    ``family == "mismatch_error"`` as ``ok: false``, but ``status="failed"``
    is the second line of defense for any caller that inspects the raw
    envelope (smoke fixtures, replay tools, audit log readers).
    """
    mismatch = VerifyMismatchError(
        family="mismatch_error",
        reason="family_mismatch",
        expected_family="mobile_id",
        observed_family="mydata",
        message="Test mismatch — adapter returned wrong family.",
    )
    dumped = mismatch.model_dump()
    assert dumped["status"] == "failed", (
        "VerifyMismatchError must stamp status='failed' as defense-in-depth "
        "(the dispatcher already flips ok=false but raw consumers benefit)."
    )


def test_verify_mock_count_is_exactly_ten() -> None:
    """Regression guard: this test exercises 10 mock_verify_* adapters."""
    assert len(_ALL_VERIFY_MOCKS) == 10, (
        f"Expected 10 verify mocks (5 existing + 5 AX-channel), "
        f"got {len(_ALL_VERIFY_MOCKS)}. If the inventory shifts, update the "
        f"Lead-S3 audit spec along with this test."
    )
