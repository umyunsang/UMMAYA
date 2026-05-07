# SPDX-License-Identifier: Apache-2.0
"""Delegation token envelope — Epic ε #2296.

Provides:
- ``DelegationToken``: scope-bound, time-bound, session-bound credential issued
  by a verify adapter and consumed by a submit or lookup adapter.
- ``DelegationContext``: wrapper carrying the token plus bilingual purpose strings.
- ``IdentityAssertion``: alternative result type for identity-SSO-only adapters
  (e.g. ``mock_verify_module_any_id_sso``) that do NOT produce a delegation grant.
- ``validate_delegation()``: async function that validates a delegation token
  against scope, expiry, session binding, and revocation.

Protocol reference:
  specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 3-4
Data model:
  specs/2296-ax-mock-adapters/data-model.md § 1-3
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scope-grammar regex (data-model.md § 1 + delegation-token-envelope.md § 3)
# Accepts single-scope strings AND comma-joined multi-scope strings for US1.
# ---------------------------------------------------------------------------

_SINGLE_SCOPE_PATTERN: re.Pattern[str] = re.compile(
    r"^(lookup|submit|verify):[a-z0-9_]+\.[a-z0-9_-]+$"
)

_MULTI_SCOPE_PATTERN: re.Pattern[str] = re.compile(
    r"^((lookup|submit|verify):[a-z0-9_]+\.[a-z0-9_-]+)"
    r"(,(lookup|submit|verify):[a-z0-9_]+\.[a-z0-9_-]+)*$"
)


# ---------------------------------------------------------------------------
# DelegationToken
# ---------------------------------------------------------------------------


class DelegationToken(BaseModel):
    """Opaque, scope-bound, time-bound credential issued by a verify adapter.

    In Mock mode the ``vp_jwt`` header is ``{"alg":"none","typ":"vp+jwt"}``;
    the signature segment is the literal string ``"mock-signature-not-cryptographic"``.

    Validators:
    - ``expires_at > issued_at``
    - ``scope`` matches the multi-scope grammar
    - ``delegation_token`` starts with ``del_`` and has >= 24 chars after the prefix
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vp_jwt: str = Field(
        min_length=1,
        description=(
            "Verifiable Presentation as JWS (header.payload.signature dot-separated). "
            "In Mock mode: header=base64({alg:none,typ:vp+jwt}), "
            "signature='mock-signature-not-cryptographic'."
        ),
    )
    delegation_token: str = Field(
        min_length=1,
        description=(
            "Opaque bearer token consumed by submit/lookup adapters. "
            "Must start with 'del_' and have >= 24 chars after the prefix."
        ),
    )
    scope: str = Field(
        min_length=1,
        description=(
            "Comma-joined list of scope entries, each matching "
            "'<verb>:<adapter_family>.<action>'. Single-scope is also valid."
        ),
    )
    issuer_did: str = Field(
        min_length=1,
        description="DID of the issuing verify adapter, e.g. 'did:web:mobileid.go.kr'.",
    )
    issued_at: datetime = Field(description="UTC tz-aware token mint time.")
    expires_at: datetime = Field(
        description="UTC tz-aware expiry. Must be > issued_at. 24h max in Mock mode."
    )
    mode: Literal["mock"] = Field(
        default="mock",
        alias="_mode",
        description="Always 'mock' for Epic ε. Reserved for future 'live' value.",
    )

    @field_validator("vp_jwt")
    @classmethod
    def _validate_jws_shape(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"vp_jwt must be a dot-separated JWS (header.payload.signature), "
                f"got {len(parts)} parts"
            )
        return v

    @field_validator("delegation_token")
    @classmethod
    def _validate_token_prefix(cls, v: str) -> str:
        prefix = "del_"
        if not v.startswith(prefix):
            raise ValueError(f"delegation_token must start with {prefix!r}, got {v[:8]!r}...")
        suffix_len = len(v) - len(prefix)
        if suffix_len < 24:
            raise ValueError(
                f"delegation_token must have >= 24 chars after 'del_' prefix, got {suffix_len}"
            )
        return v

    @field_validator("scope")
    @classmethod
    def _validate_scope_grammar(cls, v: str) -> str:
        if not _MULTI_SCOPE_PATTERN.match(v):
            raise ValueError(
                f"scope must match '<verb>:<adapter_family>.<action>' "
                f"(comma-joined for multi-scope); got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _validate_expiry_after_issued(self) -> DelegationToken:
        if self.expires_at <= self.issued_at:
            raise ValueError(
                f"expires_at ({self.expires_at.isoformat()}) must be strictly "
                f"greater than issued_at ({self.issued_at.isoformat()})"
            )
        return self

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------------------
# DelegationContext
# ---------------------------------------------------------------------------


class DelegationContext(BaseModel):
    """Carries a ``DelegationToken`` plus bilingual purpose strings for the permission UI.

    Returned by verify adapters (except ``mock_verify_module_any_id_sso``).
    Passed forward through the LLM's tool-call context to the next adapter.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    token: DelegationToken = Field(description="The opaque delegation credential.")
    citizen_did: str | None = Field(
        default=None,
        description=(
            "Citizen DID if the verify ceremony surfaced one "
            "(e.g. 'did:web:mobileid.go.kr' issuance). Optional."
        ),
    )
    purpose_ko: str = Field(
        min_length=1,
        max_length=200,
        description="Korean purpose statement shown in the permission UI.",
    )
    purpose_en: str = Field(
        min_length=1,
        max_length=200,
        description="English purpose statement shown in the permission UI.",
    )


# ---------------------------------------------------------------------------
# IdentityAssertion
# ---------------------------------------------------------------------------


class IdentityAssertion(BaseModel):
    """Returned by ``mock_verify_module_any_id_sso`` INSTEAD of ``DelegationContext``.

    Any-ID SSO is identity-only — it does NOT produce a delegation grant.
    A submit/lookup adapter receiving an ``IdentityAssertion`` MUST reject with
    ``DelegationGrantMissing`` (fail-closed, Constitution § II).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    assertion_jwt: str = Field(
        min_length=1,
        description="Identity assertion as JWS (header.payload.signature).",
    )
    citizen_did: str | None = Field(
        default=None,
        description="Citizen DID if Any-ID surfaced one.",
    )
    expires_at: datetime = Field(description="UTC tz-aware assertion validity window.")
    mode: Literal["mock"] = Field(
        default="mock",
        alias="_mode",
        description="Always 'mock' for Epic ε.",
    )

    @field_validator("assertion_jwt")
    @classmethod
    def _validate_jws_shape(cls, v: str) -> str:
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"assertion_jwt must be a dot-separated JWS (header.payload.signature), "
                f"got {len(parts)} parts"
            )
        return v

    @field_validator("expires_at")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("IdentityAssertion.expires_at must be timezone-aware UTC")
        return v


# ---------------------------------------------------------------------------
# DelegationValidationOutcome
# ---------------------------------------------------------------------------


class DelegationValidationOutcome(StrEnum):
    """Possible outcomes from ``validate_delegation``."""

    OK = "ok"
    EXPIRED = "expired"
    SCOPE_VIOLATION = "scope_violation"
    SESSION_VIOLATION = "session_violation"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# LedgerReader protocol — injected by callers (avoids circular imports)
# ---------------------------------------------------------------------------


class LedgerReader(Protocol):
    """Protocol for the ledger reader dependency injected into ``validate_delegation``."""

    async def find_issuance_session(self, delegation_token: str) -> str | None:
        """Return the session_id from the matching ``delegation_issued`` event,
        or ``None`` if no issuance record exists.
        """
        ...


# ---------------------------------------------------------------------------
# validate_delegation
# ---------------------------------------------------------------------------


def _scope_matches(token_scope: str, required: str) -> bool:
    """Return True if ``required`` is one of the comma-joined scope entries in ``token_scope``.

    Examples::
        _scope_matches("submit:hometax.tax-return", "submit:hometax.tax-return") → True
        _scope_matches("lookup:hometax.simplified,submit:hometax.tax-return",
                       "submit:hometax.tax-return") → True
        _scope_matches("lookup:hometax.simplified,submit:hometax.tax-return",
                       "submit:gov24.minwon") → False
    """
    return required in token_scope.split(",")


# Session-scoped revocation store — Codex P1 #2445 fix.
# Module-global dict keyed by ``session_id`` → set of revoked ``delegation_token``
# values. Submit / lookup adapters read from this store via ``revoked_for_session``;
# the ``/consent revoke`` slash command (or any future revocation surface) writes
# to it via ``revoke_token`` so the ``DelegationValidationOutcome.REVOKED`` branch
# can actually trigger across calls. Per data-model.md § 9.1, the store is
# session-lifetime in-memory only — survival across restarts is delegated to the
# Spec 035 audit ledger (replayed by ``FileLedgerReader`` if needed).
_REVOKED_TOKENS_BY_SESSION: dict[str, set[str]] = {}


def revoke_token(session_id: str, delegation_token: str) -> None:
    """Mark a delegation token as revoked within a session.

    Subsequent ``validate_delegation`` calls for the same ``session_id`` that
    reference this token will return ``DelegationValidationOutcome.REVOKED``.
    The ``/consent revoke <token>`` slash command (Spec 035 follow-up) is the
    user-facing entry point. For programmatic revocation in tests, call this
    function directly.
    """
    _REVOKED_TOKENS_BY_SESSION.setdefault(session_id, set()).add(delegation_token)


def revoked_for_session(session_id: str) -> set[str]:
    """Return the set of revoked tokens for ``session_id``.

    Returns the live module-level set so callers see writes made by
    ``revoke_token``. Returns an empty set (not ``None``) when no tokens have
    been revoked in this session — safe to pass directly into
    ``validate_delegation(revoked_set=...)``.
    """
    return _REVOKED_TOKENS_BY_SESSION.setdefault(session_id, set())


def clear_revoked_for_session(session_id: str) -> None:
    """Clear all revocation entries for ``session_id`` (test helper)."""
    _REVOKED_TOKENS_BY_SESSION.pop(session_id, None)


async def validate_delegation(
    context: DelegationContext,
    *,
    required_scope: str,
    current_session_id: str,
    revoked_set: set[str],
    ledger_reader: LedgerReader,
) -> DelegationValidationOutcome:
    """Validate a delegation token against scope, expiry, session binding, and revocation.

    Check order (most actionable error first):
      1. expired — ``token.expires_at <= now(UTC)``
      2. scope_violation — ``required_scope`` not in comma-joined ``token.scope``
      3. session_violation — issuance session differs from ``current_session_id``
      4. revoked — token in ``revoked_set``

    Args:
        context: The ``DelegationContext`` carrying the token to validate.
        required_scope: The exact scope string the consumer adapter requires,
            e.g. ``"submit:hometax.tax-return"``.
        current_session_id: Session ID of the consuming call.
        revoked_set: In-memory session-scoped set of revoked token values.
        ledger_reader: Async reader that resolves the issuance session for a token.

    Returns:
        ``DelegationValidationOutcome.OK`` when all checks pass.
        One of the four rejection outcomes otherwise.
    """
    token = context.token

    # Check 1 — expiry
    if token.expires_at <= datetime.now(UTC):
        logger.info("validate_delegation: token expired at %s", token.expires_at.isoformat())
        return DelegationValidationOutcome.EXPIRED

    # Check 2 — scope
    if not _scope_matches(token.scope, required_scope):
        logger.info(
            "validate_delegation: scope violation (token=%r required=%r)",
            token.scope,
            required_scope,
        )
        return DelegationValidationOutcome.SCOPE_VIOLATION

    # Check 3 — session binding
    issued_session_id = await ledger_reader.find_issuance_session(token.delegation_token)
    if issued_session_id != current_session_id:
        logger.info(
            "validate_delegation: session violation (issued=%r current=%r)",
            issued_session_id,
            current_session_id,
        )
        return DelegationValidationOutcome.SESSION_VIOLATION

    # Check 4 — revocation
    if token.delegation_token in revoked_set:
        logger.info(
            "validate_delegation: token %r is in the revoked_set",
            token.delegation_token[:12],
        )
        return DelegationValidationOutcome.REVOKED

    return DelegationValidationOutcome.OK


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DelegationContext",
    "DelegationToken",
    "DelegationValidationOutcome",
    "IdentityAssertion",
    "LedgerReader",
    "_scope_matches",
    "validate_delegation",
]
