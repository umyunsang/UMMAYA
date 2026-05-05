# SPDX-License-Identifier: Apache-2.0
"""Spec 035 receipt set + harness session schema.

KOSMOS-invented permission orchestration classes removed in Epic δ #2295.

Retained classes:
- SessionContext        — session state for query engine
- ConsentDecision       — PIPA §15(2) 4-tuple + citizen grant/deny
- ConsentLedgerRecord   — append-only WORM ledger record (Spec 033 FR-D02)
- LedgerVerifyReport    — output of ``kosmos permissions verify``
- ToolPermissionContext — per-invocation context for v2 permission pipeline
- AdapterPermissionMetadata — read-only projection from GovAPITool
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, constr, field_validator

# PermissionMode inlined here because modes.py was deleted in Epic δ #2295.
PermissionMode = Literal["default", "plan", "acceptEdits", "bypassPermissions", "dontAsk"]


class SessionContext(BaseModel):
    """Session state passed in from the query engine.

    The pipeline does not create or mutate sessions.
    """

    model_config = ConfigDict(frozen=True)

    session_id: str
    """Unique session identifier for audit trail."""

    citizen_id: str | None = None
    """Citizen identity; ``None`` in v1 (no auth yet)."""

    auth_level: int = 0
    """Authentication level: 0=anonymous, 1=basic, 2=verified."""

    consented_providers: tuple[str, ...] = Field(default=())
    """Providers for which the citizen has accepted ToS."""

    @field_validator("consented_providers", mode="before")
    @classmethod
    def _coerce_to_tuple(cls, v: object) -> tuple[str, ...]:
        """Coerce list inputs to tuple to keep the frozen model immutable."""
        if isinstance(v, list):
            return tuple(v)
        return v  # type: ignore[return-value]


class AdapterPermissionMetadata(BaseModel):
    """Read-only projection from ``GovAPITool`` for permission pipeline use.

    Reference: specs/033-permission-v2-spectrum/data-model.md § 1.4
    Invariant A1: Pipeline FAILS CLOSED if any field is missing/None.
    Source: ``src/kosmos/tools/models.py :: GovAPITool``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    tool_id: StrictStr
    """Canonical adapter identifier."""

    is_irreversible: bool
    """True when invocation produces an irreversible side effect."""

    auth_level: Literal["public", "AAL1", "AAL2", "AAL3"]
    """Minimum NIST SP 800-63-4 AAL required to invoke the adapter."""

    pipa_class: Literal["일반", "민감", "고유식별", "특수"]
    """PIPA personal-data classification of adapter input/output."""

    requires_auth: bool
    """True if citizen authentication is required."""

    auth_type: Literal["public", "api_key", "oauth"]
    """Authentication mechanism required by the upstream API."""


class ToolPermissionContext(BaseModel):
    """Per-invocation context passed through the v2 permission pipeline.

    Reference: specs/033-permission-v2-spectrum/data-model.md § 1.3
    Invariant T1: Every adapter call constructs exactly one context.
    Invariant T2: ``is_irreversible``, ``auth_level``, ``pipa_class`` come
                  from ``AdapterPermissionMetadata`` — the citizen cannot
                  spoof these.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    tool_id: StrictStr
    """Canonical adapter identifier."""

    mode: PermissionMode
    """Current session permission mode."""

    is_irreversible: bool
    """From AdapterPermissionMetadata — citizen cannot override."""

    auth_level: Literal["public", "AAL1", "AAL2", "AAL3"]
    """From AdapterPermissionMetadata."""

    pipa_class: Literal["일반", "민감", "고유식별", "특수"]
    """From AdapterPermissionMetadata."""

    session_id: StrictStr
    """Unique session identifier (from Spec 032 session context)."""

    correlation_id: StrictStr
    """Correlation id from Spec 032 IPC envelope for trace linkage."""

    arguments: dict[str, str | int | float | bool | None]
    """Adapter call arguments.  Strict types; no Any."""

    adapter_metadata: AdapterPermissionMetadata
    """Full metadata projection for downstream pipeline steps."""


class ConsentDecision(BaseModel):
    """PIPA §15(2) 4-tuple + user grant/deny decision (Spec 033 FR-D01).

    Reference: specs/033-permission-v2-spectrum/data-model.md § 1.5
    Invariant C1: All 4 PIPA tuple fields must be non-empty StrictStr.
    Invariant C2: ``data_items`` is a frozen tuple (ordering preserved).
    Invariant C3: 민감/고유식별/특수 with ``granted=False`` → immediate deny.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    # PIPA §15(2) 4-tuple — all required, no empty strings
    purpose: Annotated[str, Field(min_length=1)]
    """목적 — purpose of personal data processing."""

    data_items: tuple[Annotated[str, Field(min_length=1)], ...]
    """항목 — data items collected (frozen tuple, ordered)."""

    retention_period: Annotated[str, Field(min_length=1)]
    """보유기간 — ISO 8601 duration or ``일회성`` for one-shot use."""

    refusal_right: Annotated[str, Field(min_length=1)]
    """거부권 + 불이익 고지문 — right to refuse + consequences disclosure."""

    # User choice
    granted: bool
    """True if the citizen granted consent; False if refused."""

    # Context binding
    tool_id: StrictStr
    """Adapter that requested consent."""

    pipa_class: Literal["일반", "민감", "고유식별", "특수"]
    """PIPA classification driving consent requirements."""

    auth_level: Literal["public", "AAL1", "AAL2", "AAL3"]
    """Authentication level at time of consent."""

    decided_at: datetime
    """UTC tz-aware timestamp when the citizen made the decision."""

    action_digest: Annotated[str, constr(pattern=r"^[0-9a-f]{64}$")]
    """SHA-256 hex of canonical(tool_id, args, timestamp-bucket).  64 chars."""

    scope: Literal["one-shot", "session", "user"]
    """How long this consent decision is valid."""


_HEX64_PATTERN = r"^[0-9a-f]{64}$"
_KEY_ID_PATTERN = r"^k\d{4}$"


class ConsentLedgerRecord(BaseModel):
    """Single append-only record in the PIPA consent ledger (Spec 033 FR-D02).

    Reference: specs/033-permission-v2-spectrum/data-model.md § 1.6
    Invariants L1–L5 (see data-model.md § 2.1 for full table):
    - L1: Append-only WORM; no update/delete API.
    - L2: Hash chain: ``record_hash[N]`` == SHA-256(canonical(record[N]
          with ``record_hash`` and ``hmac_seal`` excluded)).
          ``prev_hash[N+1] == record_hash[N]``.
    - L3: HMAC seal is independent of hash chain (two-layer defense).
    - L4: ``key_id`` allows rotation; old records stay verifiable.
    - L5: All hashing targets RFC 8785 JCS canonical form.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    # Schema identity
    version: Literal["1.0.0"]
    """Schema version (Kantara CR-inspired versioning)."""

    # Sequence
    sequence: Annotated[int, Field(ge=0)]
    """Monotonically increasing record index (0-based).  Genesis record = 0."""

    # Time
    recorded_at: datetime
    """UTC tz-aware timestamp of ledger append."""

    # Adapter + consent context
    tool_id: StrictStr
    """Adapter that triggered this ledger record."""

    mode: PermissionMode
    """Permission mode active at time of record."""

    granted: bool
    """Whether the citizen granted consent for this call."""

    action_digest: Annotated[str, constr(pattern=_HEX64_PATTERN)]
    """SHA-256 hex of canonical(tool_id, args, timestamp-bucket).  64 chars."""

    # Hash chain (FR-D02)
    prev_hash: Annotated[str, constr(pattern=_HEX64_PATTERN)]
    """SHA-256 of previous record's canonical form.
    Genesis sentinel: 64 × ``0``."""

    record_hash: Annotated[str, constr(pattern=_HEX64_PATTERN)]
    """SHA-256 over ``canonical(record)`` with ``record_hash`` + ``hmac_seal``
    zeroed-out before hashing."""

    # HMAC seal (FR-D04)
    hmac_seal: Annotated[str, constr(pattern=_HEX64_PATTERN)]
    """HMAC-SHA-256(canonical(record)) with ``hmac_seal`` field excluded."""

    key_id: Annotated[str, constr(pattern=_KEY_ID_PATTERN)]
    """HMAC key identifier (e.g. ``k0001``). Allows rotation-aware verify."""

    # Optional Kantara v1.1.0 coupling
    consent_receipt_id: StrictStr | None = None
    """Kantara CR v1.1.0 receipt id.  Set when PIPA consent was captured."""

    # PIPA §15(2) disclosure snapshot (FR-D02 consent-receipt semantics).
    # All optional so existing ledgers remain valid; populated for any record
    # that rode through a prompt or auto-decision path that had the fields.
    purpose: StrictStr | None = None
    """PIPA §15(2)(1) 목적 captured at consent time."""

    data_items: tuple[StrictStr, ...] | None = None
    """PIPA §15(2)(2) 항목 — items the citizen consented to process."""

    retention_period: StrictStr | None = None
    """PIPA §15(2)(4) 보유기간 captured at consent time."""

    refusal_right: StrictStr | None = None
    """PIPA §15(2)(3) 거부권 and consequence text shown to the citizen."""

    pipa_class: Literal["일반", "민감", "고유식별", "특수"] | None = None
    """Adapter's PIPA classification at decision time."""

    auth_level: Literal["public", "AAL1", "AAL2", "AAL3"] | None = None
    """Authentication level enforced at decision time."""

    session_id: StrictStr | None = None
    """Session that produced this decision — audit binding."""

    correlation_id: StrictStr | None = None
    """Correlation id joining this record to the tool-call audit trail."""

    # Withdrawal / action metadata (Spec 033 WS3 closure)
    action: Literal["allow", "deny", "withdraw"] = "allow"
    """Ledger action type.

    - ``"allow"``    — citizen granted consent (default; backward-compat sentinel).
    - ``"deny"``     — citizen denied consent.
    - ``"withdraw"`` — citizen revoked a prior consent receipt.

    Defaults to ``"allow"`` so pre-WS3 ledger lines that lack this field
    parse correctly (``extra="forbid"`` is preserved; ``action`` is not
    missing — the model default fills it in when deserialising from JSON that
    omits the key).
    """

    scope_receipt_id: StrictStr | None = None
    """Receipt ID that this record revokes (non-null iff ``action=="withdraw"``).

    Set to the ``consent_receipt_id`` of the target allow/deny record.
    ``None`` for ``allow`` and ``deny`` records.
    """

    withdrawn_at: datetime | None = None
    """UTC tz-aware timestamp when the withdrawal was processed.

    Non-null iff ``action=="withdraw"``.  Distinct from ``recorded_at`` so
    the audit trail can distinguish "when was the withdraw decision made"
    from "when was it durably committed to the ledger".
    """


class LedgerVerifyReport(BaseModel):
    """Output of ``kosmos permissions verify`` (Spec 033 FR-D05).

    Reference: specs/033-permission-v2-spectrum/contracts/ledger-verify.cli.md
    Exit codes:
        0  — all checks passed
        1  — chain integrity failure (CHAIN_*)
        2  — HMAC seal failure
        3  — key missing / unreadable
        4  — file corrupt / unreadable
        5  — schema violation in at least one record
        6  — key file mode wrong (0400 expected)
        64 — usage error
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    passed: bool
    """True only when both hash chain and all HMAC seals verified."""

    total_records: Annotated[int, Field(ge=0)]
    """Total number of records in the ledger file."""

    first_broken_index: int | None
    """0-based index of first broken record; ``None`` when passed=True."""

    broken_reason: (
        Literal[
            "CHAIN_RECORD_HASH_MISMATCH",
            "CHAIN_PREV_HASH_MISMATCH",
            "HMAC_SEAL_MISMATCH",
            "KEY_MISSING",
            "FILE_CORRUPT",
            "SCHEMA_VIOLATION",
            "KEY_FILE_MODE",
        ]
        | None
    )
    """Machine-readable failure reason; ``None`` when passed=True."""

    exit_code: Literal[0, 1, 2, 3, 4, 5, 6, 64]
    """Process exit code for CLI use."""
