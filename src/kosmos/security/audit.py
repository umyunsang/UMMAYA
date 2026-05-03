# SPDX-License-Identifier: Apache-2.0
"""Authoritative Authenticator Assurance Level (AAL) lookup for KOSMOS tools.

Implements the single-source-of-truth ``TOOL_MIN_AAL`` table and the
``PublicPathMeta`` dataclass that captures the ``check_eligibility`` rules-only
fallback path.

References
----------
- NIST SP 800-63-4 "Digital Identity Guidelines" (2024): defines
  AAL1/AAL2/AAL3 and the "no authentication" baseline used here as
  ``"public"``. SP 800-63-4 is the sole authoritative source for this table;
  earlier revisions are not cited.
- ``specs/024-tool-security-v1/data-model.md`` §2 — authoritative table.
- ``specs/024-tool-security-v1/spec.md`` — FR-002, FR-003, FR-004.

The table covers the ``GovAPITool`` tools bound to V3 (``auth_level`` ==
``TOOL_MIN_AAL[tool_id]``):

- ``lookup`` — AAL1
- ``resolve_location`` — AAL1
- ``nfa_emergency_info_service`` — AAL1 (Spec 029)
- ``mohw_welfare_eligibility_search`` — AAL1 (Spec 2522 US4: read-only public catalog)

Spec 031 v1.2 GA (T080) supersedes the legacy 8-verb row set with the
dual-axis ``(published_tier_minimum, nist_aal_hint)`` contract carried on
``AdapterRegistration``; see ``docs/security/tool-template-security-spec-v1.md``
§2. The six legacy verbs (``check_eligibility`` / ``subscribe_alert`` /
``reserve_slot`` / ``issue_certificate`` / ``submit_application`` / ``pay``)
no longer appear as ``GovAPITool`` IDs.

Every ``GovAPITool.auth_level`` MUST equal its row here; drift is a load-time
failure enforced by validator ``V3`` in ``kosmos.tools.models``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, model_validator

_TOOL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")
# DPA reference identifiers: letter-led, 6..64 chars, alphanumeric + dash/underscore.
# Rejects empty/whitespace-only and placeholder strings like "TBD" or "N/A".
_DPA_REFERENCE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{5,63}$")
# DoS cap on unbounded audit string fields (M5). 64 chars is generous for
# UUIDs (36), SHA-256 prefix slugs, rate-limit bucket names, and conventional
# DPA identifiers while preventing payload inflation.
_MAX_AUDIT_STRING_LEN: Final[int] = 64
# NIST SP 800-92 §2.3.2 recommends bounding audit timestamps against a trusted
# clock; we allow ±300 s (5 min) skew between the producing host and UTC now.
MAX_CLOCK_SKEW_SECONDS: Final[int] = 300

AALLevel = Literal["public", "AAL1", "AAL2", "AAL3"]
PIPAClass = Literal["non_personal", "personal", "sensitive", "identifier"]
AdapterMode = Literal["mock", "live"]
PermissionDecision = Literal[
    "allow",
    "deny_aal",
    "deny_scope",
    "deny_irreversible_introspect_failed",
    "deny_deny_by_default",
]
MerkleCoveredHash = Literal["sanitized_output_hash", "output_hash"]

TOOL_MIN_AAL: Final[dict[str, AALLevel]] = {
    # Spec 031 T080 — legacy 8-verb table replaced by dual-axis contract.
    # Only primitives/Phase-2 adapters whose tool_id still flows through V3
    # (GovAPITool.auth_level == TOOL_MIN_AAL[tool_id]) remain. Six legacy
    # verbs (check_eligibility / subscribe_alert / reserve_slot /
    # issue_certificate / submit_application / pay) are superseded by the
    # v1.2 dual-axis table; see docs/security/tool-template-security-spec-v1.md §2.
    "lookup": "AAL1",
    "resolve_location": "AAL1",
    # Phase 2 API adapters (spec 029):
    # NFA EMS stats — api_key serviceKey auth; citizen_facing_gate=login derives AAL2.
    "nfa_emergency_info_service": "AAL2",
    # Spec 2522 US4: citizen_facing_gate changed from "login" to "read-only"
    # (live evidence: NationalWelfarelistV001 is a public API-key-only catalog;
    # no citizen authentication required). derive_min_auth_level("read-only") = AAL1.
    "mohw_welfare_eligibility_search": "AAL1",
}


@dataclass(frozen=True)
class PublicPathMeta:
    """Metadata describing a tool's rules-only public-path fallback.

    Only ``check_eligibility`` carries a public-path today: it may be invoked
    at AAL1 when the evaluation is purely rules-based over public inputs with
    no PII in either the request or the response. Every other tool MUST run at
    its declared ``TOOL_MIN_AAL`` row.

    Attributes
    ----------
    tool_id:
        Canonical tool identifier the public-path applies to.
    fallback_aal:
        AAL level permitted when the public-path preconditions hold.
    condition:
        Human-readable precondition narrative reproduced verbatim from the
        spec so audit reviewers can trace the carve-out.
    """

    tool_id: str
    fallback_aal: AALLevel
    condition: str


PUBLIC_PATH_META: Final[dict[str, PublicPathMeta]] = {
    "check_eligibility": PublicPathMeta(
        tool_id="check_eligibility",
        fallback_aal="AAL1",
        condition=(
            "AAL1 permitted for rules-only evaluation over public inputs "
            "with no PII in request or response"
        ),
    ),
}


_HEX_SHA256_LEN: Final[int] = 64


def _is_hex_sha256(value: str) -> bool:
    """Return True when *value* is a lowercase hex SHA-256 digest."""
    if len(value) != _HEX_SHA256_LEN:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


class ToolCallAuditRecord(BaseModel):
    """Immutable per-call evidence artifact for KOSMOS tool invocations.

    Schema version ``v1``. Authoritative field spec and invariants live in
    ``specs/024-tool-security-v1/data-model.md`` §3 and the JSON Schema at
    ``docs/security/tool-call-audit-record.schema.json``.

    Invariants enforced via ``model_validator(mode="after")``:

    - ``I1``: ``sanitized_output_hash is not None`` ↔
      ``merkle_covered_hash == "sanitized_output_hash"``.
    - ``I2``: ``public_path_marker = True`` →
      ``tool_id == "check_eligibility"`` AND
      ``auth_level_presented == "AAL1"`` AND
      ``pipa_class == "non_personal"``.
    - ``I3``: ``pipa_class != "non_personal"`` → ``dpa_reference is not None``
      AND matches ``^[A-Za-z][A-Za-z0-9_-]{5,63}$`` (no whitespace, no
      ``TBD``/``N/A`` placeholders).
    - ``I4``: ``timestamp.tzinfo is not None`` (RFC 3339 naive timestamps
      rejected) AND ``|now - timestamp| <= MAX_CLOCK_SKEW_SECONDS`` (NIST SP
      800-92 §2.3.2 trusted-clock guidance).
    - ``I5``: ``permission_decision == "allow"`` AND
      ``pipa_class != "non_personal"`` → ``sanitized_output_hash is not None``.
      Ensures Merkle coverage binds the redacted view, never raw PII.

    DoS hardening: all unbounded string fields (``tool_id``, ``session_id``,
    ``caller_identity``, ``rate_limit_bucket``, ``dpa_reference``,
    ``merkle_leaf_id``) are capped at ``_MAX_AUDIT_STRING_LEN`` (64 chars).

    Mock/live parity: the only permitted shape-differing field between a mock
    record and a live record for the same tool is ``adapter_mode``.

    Performance target: ``model_validate`` runs in < 5 ms per record, averaged
    over 1000 iterations (validated in ``tests/unit/test_tool_call_audit_record.py``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_version: Literal["v1"]
    tool_id: str
    adapter_mode: AdapterMode
    session_id: str
    caller_identity: str
    permission_decision: PermissionDecision
    auth_level_presented: AALLevel
    pipa_class: PIPAClass
    dpa_reference: str | None = None
    input_hash: str
    output_hash: str
    sanitized_output_hash: str | None = None
    merkle_covered_hash: MerkleCoveredHash
    merkle_leaf_id: str | None = None
    timestamp: datetime
    cost_tokens: int
    rate_limit_bucket: str
    public_path_marker: bool

    @model_validator(mode="after")
    def _validate_invariants(self) -> ToolCallAuditRecord:  # noqa: C901 — I1..I5 invariants + field-shape checks form an intentionally flat single-pass validator (spec 024 §3.2)
        # Field-shape checks that JSON Schema enforces via pattern/minLength/maxLength.
        # ASCII-only regex rejects non-ASCII letters that str.islower() would accept.
        if not _TOOL_ID_PATTERN.fullmatch(self.tool_id):
            raise ValueError(f"tool_id must match ^[a-z][a-z0-9_]*$; got {self.tool_id!r}")
        if len(self.tool_id) > _MAX_AUDIT_STRING_LEN:
            raise ValueError(
                f"tool_id must be <= {_MAX_AUDIT_STRING_LEN} chars; got {len(self.tool_id)}"
            )
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if len(self.session_id) > _MAX_AUDIT_STRING_LEN:
            raise ValueError(
                f"session_id must be <= {_MAX_AUDIT_STRING_LEN} chars; got {len(self.session_id)}"
            )
        if not self.caller_identity:
            raise ValueError("caller_identity must be non-empty")
        if len(self.caller_identity) > _MAX_AUDIT_STRING_LEN:
            raise ValueError(
                f"caller_identity must be <= {_MAX_AUDIT_STRING_LEN} chars; "
                f"got {len(self.caller_identity)}"
            )
        if not self.rate_limit_bucket:
            raise ValueError("rate_limit_bucket must be non-empty")
        if len(self.rate_limit_bucket) > _MAX_AUDIT_STRING_LEN:
            raise ValueError(
                f"rate_limit_bucket must be <= {_MAX_AUDIT_STRING_LEN} chars; "
                f"got {len(self.rate_limit_bucket)}"
            )
        if self.merkle_leaf_id is not None and len(self.merkle_leaf_id) > _MAX_AUDIT_STRING_LEN:
            raise ValueError(
                f"merkle_leaf_id must be <= {_MAX_AUDIT_STRING_LEN} chars; "
                f"got {len(self.merkle_leaf_id)}"
            )
        if self.cost_tokens < 0:
            raise ValueError(f"cost_tokens must be >= 0; got {self.cost_tokens}")
        if not _is_hex_sha256(self.input_hash):
            raise ValueError("input_hash must be a lowercase hex SHA-256 digest (64 chars)")
        if not _is_hex_sha256(self.output_hash):
            raise ValueError("output_hash must be a lowercase hex SHA-256 digest (64 chars)")
        if self.sanitized_output_hash is not None and not _is_hex_sha256(
            self.sanitized_output_hash
        ):
            raise ValueError(
                "sanitized_output_hash must be a lowercase hex SHA-256 digest "
                "(64 chars) when provided"
            )
        # M4: dpa_reference pattern + length. Trimming is enforced upstream in
        # kosmos.tools.models V2 so reaching the audit layer with whitespace is
        # itself a bug; we still reject here as a defense-in-depth backstop.
        if self.dpa_reference is not None:
            stripped = self.dpa_reference.strip()
            if stripped != self.dpa_reference:
                raise ValueError("dpa_reference must not contain leading or trailing whitespace.")
            if not _DPA_REFERENCE_PATTERN.fullmatch(self.dpa_reference):
                raise ValueError(
                    "dpa_reference must match ^[A-Za-z][A-Za-z0-9_-]{5,63}$ "
                    f"(got {self.dpa_reference!r}); placeholders like 'TBD' "
                    "or 'N/A' are rejected."
                )

        # I1: sanitized_output_hash non-null iff merkle_covered_hash binds it.
        if self.sanitized_output_hash is not None:
            if self.merkle_covered_hash != "sanitized_output_hash":
                raise ValueError(
                    "I1 violation: sanitized_output_hash is set but "
                    "merkle_covered_hash != 'sanitized_output_hash'."
                )
        else:
            if self.merkle_covered_hash != "output_hash":
                raise ValueError(
                    "I1 violation: sanitized_output_hash is None but "
                    "merkle_covered_hash != 'output_hash'."
                )

        # I2: public_path_marker implies check_eligibility + AAL1 + non_personal.
        if self.public_path_marker:
            if self.tool_id != "check_eligibility":
                raise ValueError(
                    "I2 violation: public_path_marker=True requires "
                    f"tool_id='check_eligibility'; got {self.tool_id!r}."
                )
            if self.auth_level_presented != "AAL1":
                raise ValueError(
                    "I2 violation: public_path_marker=True requires "
                    "auth_level_presented='AAL1'; got "
                    f"{self.auth_level_presented!r}."
                )
            if self.pipa_class != "non_personal":
                raise ValueError(
                    "I2 violation: public_path_marker=True requires "
                    f"pipa_class='non_personal'; got {self.pipa_class!r}."
                )

        # I3: pipa_class != non_personal implies dpa_reference is non-null.
        if self.pipa_class != "non_personal" and not self.dpa_reference:
            raise ValueError(
                f"I3 violation: pipa_class={self.pipa_class!r} requires a non-empty dpa_reference."
            )

        # I4: timestamps must be timezone-aware (RFC 3339 with tz).
        if self.timestamp.tzinfo is None:
            raise ValueError("I4 violation: timestamp must be timezone-aware (RFC 3339).")

        # I4 (extended): bound timestamp skew against UTC now. NIST SP 800-92 §2.3.2
        # calls for trustworthy audit clocks; a record produced more than
        # MAX_CLOCK_SKEW_SECONDS from the server clock is rejected as either
        # replayed or from a misconfigured host.
        skew = abs((datetime.now(UTC) - self.timestamp).total_seconds())
        if skew > MAX_CLOCK_SKEW_SECONDS:
            raise ValueError(
                f"I4 violation: timestamp skew {skew:.1f}s exceeds "
                f"MAX_CLOCK_SKEW_SECONDS={MAX_CLOCK_SKEW_SECONDS} (NIST SP 800-92 §2.3.2)."
            )

        # I5: when a tool produces PII-class output and the call was allowed,
        # sanitized_output_hash MUST be non-null so that Merkle coverage binds
        # the redacted view rather than the raw PII. Denied calls never produce
        # output, so the invariant only applies on allow.
        if (
            self.permission_decision == "allow"
            and self.pipa_class != "non_personal"
            and self.sanitized_output_hash is None
        ):
            raise ValueError(
                "I5 violation: pipa_class="
                f"{self.pipa_class!r} with permission_decision='allow' "
                "requires a non-null sanitized_output_hash (spec 024 §3.2 I5)."
            )

        return self


__all__ = [
    "AALLevel",
    "AdapterMode",
    "MerkleCoveredHash",
    "PermissionDecision",
    "PIPAClass",
    "PUBLIC_PATH_META",
    "PublicPathMeta",
    "TOOL_MIN_AAL",
    "ToolCallAuditRecord",
]
