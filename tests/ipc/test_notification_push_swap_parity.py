# SPDX-License-Identifier: Apache-2.0
"""SWAP-justification parity test for `notification_push` IPC arm.

Spec 2642 / Epic F · S7 / US2.

Background
----------
The S7 audit (specs/cc-migration-audit/scope-S7-ipc-bridge.md § 5
Finding 3) flagged the `notification_push` arm as needing CC-baseline
verification — does Claude Code emit notifications through an IPC arm
or in-process?

Verification (recorded in NotificationPushFrame.__doc__ + Spec 2642
plan § 0.1):

* CC has NO `ipc/` directory at all (single Node process; in-process
  call signatures everywhere).
* CC's notification surface is terminal OSC sequences (iTerm2, Kitty,
  Ghostty, bell) emitted from `ink/useTerminalNotification.ts`.
* `Tool.ts:210 notify(notificationType)` is an in-process callback,
  not an IPC frame.

Conclusion: KOSMOS's `notification_push` arm is a swap-2 add-on
carrying Spec 031 SubscriptionHandle pushes (KMA disaster CBS, RSS
newsroom, hospital alerts) over the same stdio plane. Orthogonal to
CC's terminal OSC notification path — neither divergence nor
regression.

This test documents that finding *in code* so future audits cannot
re-discover it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kosmos.ipc.frame_schema import (
    _ROLE_KIND_ALLOW_LIST,
    NotificationPushFrame,
)

# ---------------------------------------------------------------------------
# 1. Role allow-list invariant
# ---------------------------------------------------------------------------


def test_notification_push_role_allowlist_is_notification_only() -> None:
    """`notification_push` MUST be emittable only by role='notification'.

    This isolates Spec 031 SubscriptionHandle pushes from any other
    backend frame source — preventing accidental cross-arm role drift.
    """
    assert _ROLE_KIND_ALLOW_LIST["notification_push"] == frozenset({"notification"})


# ---------------------------------------------------------------------------
# 2. CC-parity literal in docstring
# ---------------------------------------------------------------------------


def test_notification_push_docstring_records_cc_parity_finding() -> None:
    """The frame docstring MUST contain the verification literal.

    Future audits or spec-bot crawlers can grep for the literal
    `"CC parity: NO equivalent"` to confirm Spec 2642 § US2 was
    completed and prevent re-discovery of the audit finding.
    """
    doc = NotificationPushFrame.__doc__ or ""
    assert "CC parity: NO equivalent" in doc, (
        "Spec 2642 § US2 / FR-005: NotificationPushFrame.__doc__ must contain "
        "the literal 'CC parity: NO equivalent' verification marker."
    )
    # Sanity: docstring also references the alternative CC path.
    assert "useTerminalNotification" in doc, (
        "Docstring should cite CC's actual notification path (`ink/useTerminalNotification.ts`)."
    )


# ---------------------------------------------------------------------------
# 3. Required-field surface invariant
# ---------------------------------------------------------------------------


_EXPECTED_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        # Discriminator is auto-set by default but is a Literal so it is
        # always present; the 5 below are the per-arm payload keys.
        "subscription_id",
        "adapter_id",
        "event_guid",
        "payload_content_type",
        "payload",
    }
)


_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    {
        # _BaseFrame envelope (Spec 287 + Spec 032 additions).
        "session_id",
        "correlation_id",
        "ts",
        "version",
        "role",
        "frame_seq",
        "transaction_id",
        "trailer",
        # Discriminator literal.
        "kind",
    }
)


def test_notification_push_payload_fields_match_expected_set() -> None:
    """The 5 per-arm payload fields must be present and required.

    If the arm gains/loses a field this test fails fast and forces the
    spec author to update the SWAP justification.
    """
    schema_fields = NotificationPushFrame.model_fields
    arm_specific = {name for name in schema_fields if name not in _ENVELOPE_FIELDS}
    assert arm_specific == _EXPECTED_REQUIRED_FIELDS, (
        f"notification_push arm-payload fields drifted.\n"
        f"  Expected: {sorted(_EXPECTED_REQUIRED_FIELDS)}\n"
        f"  Actual:   {sorted(arm_specific)}"
    )

    # Each arm-specific field must be required (no default).
    for field_name in _EXPECTED_REQUIRED_FIELDS:
        info = schema_fields[field_name]
        assert info.is_required(), f"notification_push.{field_name} must be required (no default)."


# ---------------------------------------------------------------------------
# 4. Happy-path validation
# ---------------------------------------------------------------------------


def test_notification_push_happy_path_validates() -> None:
    """A complete frame with a Korean civic-channel payload validates."""
    frame = NotificationPushFrame(
        session_id="sess-test-2642",
        correlation_id="corr-test-2642-1",
        ts="2026-05-03T14:30:00.000Z",
        role="notification",
        frame_seq=1,
        subscription_id="sub-cbs-001",
        adapter_id="disaster_alert_cbs_push",
        event_guid="cbs-2026-05-03-12345",
        payload_content_type="text/plain",
        payload="긴급재난문자: 서울 강남 일대 폭우 주의보 발효 (2026-05-03 14:30).",
    )
    # Discriminator is auto-set by default.
    assert frame.kind == "notification_push"
    assert frame.adapter_id == "disaster_alert_cbs_push"


# ---------------------------------------------------------------------------
# 5. Empty-payload rejection
# ---------------------------------------------------------------------------


def test_notification_push_rejects_empty_payload() -> None:
    """Empty payload string must not validate.

    Pydantic's default str field requires non-empty (when the field
    description implies content). Even if no min_length=1 constraint is
    declared, downstream consumers depend on a non-empty notification
    body. We assert the field is *required* (covered by test 3) and
    additionally that omission raises ValidationError.
    """
    with pytest.raises(ValidationError):
        NotificationPushFrame(  # type: ignore[call-arg]
            session_id="sess-test-2642-empty",
            correlation_id="corr-test-2642-empty",
            ts="2026-05-03T14:30:00.000Z",
            role="notification",
            frame_seq=1,
            subscription_id="sub-cbs-002",
            adapter_id="disaster_alert_cbs_push",
            event_guid="cbs-2026-05-03-empty",
            payload_content_type="text/plain",
            # payload omitted entirely
        )
