# SPDX-License-Identifier: Apache-2.0
"""Mock verify adapter — ganpyeon_injeung (간편인증 — Kakao/Naver/Toss/PASS/etc.).

Source mode: OOS — shape-mirrored from Barocert developers.barocert.com SDK docs.
FR-009 (delegation-only): no signing keys, no CA logic. Fixture-backed.
Default fixture uses 'kakao' provider. Test code may pass _fixture_override.

Epic ε #2296 T022: retrofitted with six transparency fields per
contracts/mock-adapter-response-shape.md § 4 "EXISTING (retrofitted)" rows.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from kosmos.memdir.consent_ledger import DelegationIssuedEvent, append_delegation_issued
from kosmos.primitives.delegation import DelegationContext, DelegationToken
from kosmos.primitives.verify import (
    GanpyeonInjeungContext,
    register_verify_adapter,
)
from kosmos.tools.registry import (
    AdapterPrimitive,
    AdapterRegistration,
    AdapterSourceMode,
)

# ---------------------------------------------------------------------------
# Per-adapter transparency constants (mock-adapter-response-shape.md § 4)
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "public-mydata-read-v240930"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/ganpyeon_injeung"
_SECURITY_WRAPPING: Final = "OAuth2.1 + PKCE + app-to-app redirect"
_POLICY_AUTHORITY: Final = (
    "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do"
    "?bbsId=BBSMSTR_000000000016&nttId=104636"
)
_INTERNATIONAL_REF: Final = "Japan JPKI"
_ISSUER_DID: Final = "did:web:ganpyeon.go.kr"

ADAPTER_REGISTRATION = AdapterRegistration(
    tool_id="mock_verify_ganpyeon_injeung",
    primitive=AdapterPrimitive.verify,
    module_path="kosmos.tools.mock.verify_ganpyeon_injeung",
    input_model_ref="kosmos.primitives.verify:VerifyInput",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="ganpyeon_injeung_kakao_aal2",
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    search_hint={
        "ko": ["간편인증", "카카오인증", "네이버인증", "토스인증", "PASS", "삼성패스"],
        "en": ["simple auth", "kakao cert", "naver cert", "toss cert", "PASS", "ganpyeon injeung"],
    },
    auth_type="oauth",
)

# Recorded fixture — default provider is 'kakao'.
_FIXTURE = GanpyeonInjeungContext.model_validate(
    {
        "family": "ganpyeon_injeung",
        "published_tier": "ganpyeon_injeung_kakao_aal2",
        "nist_aal_hint": "AAL2",
        "verified_at": datetime(2026, 4, 19, 9, 0, 0, tzinfo=UTC),
        "external_session_ref": "mock-ganpyeon-ref-001",
        "provider": "kakao",
        # Six transparency fields (T022 retrofit)
        "_mode": "mock",
        "_reference_implementation": _REFERENCE_IMPL,
        "_actual_endpoint_when_live": _ACTUAL_ENDPOINT,
        "_security_wrapping_pattern": _SECURITY_WRAPPING,
        "_policy_authority": _POLICY_AUTHORITY,
        "_international_reference": _INTERNATIONAL_REF,
    },
    by_alias=True,
)


def _mock_vp_jwt(scope: str, issued_at: datetime, expires_at: datetime) -> str:
    """Construct a Mock VP-JWT for the scope-bound delegation grant."""
    header = {"alg": "none", "typ": "vp+jwt"}
    payload = {
        "iss": _ISSUER_DID,
        "scope": scope,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.mock-signature-not-cryptographic"


def _scope_list_from_session(session_context: dict[str, object]) -> list[str]:
    raw = session_context.get("scope_list")
    if isinstance(raw, list):
        scopes = [scope for scope in raw if isinstance(scope, str) and scope.strip()]
        if scopes:
            return scopes
    return ["verify:ganpyeon.identity"]


def _build_delegation_context(session_context: dict[str, object]) -> DelegationContext:
    scope_str = ",".join(_scope_list_from_session(session_context))
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)
    raw_token = f"del_{secrets.token_urlsafe(24)}"
    token = DelegationToken(
        vp_jwt=_mock_vp_jwt(scope_str, now, expires_at),
        delegation_token=raw_token,
        scope=scope_str,
        issuer_did=_ISSUER_DID,
        issued_at=now,
        expires_at=expires_at,
    )
    purpose_ko = session_context.get("purpose_ko")
    purpose_en = session_context.get("purpose_en")
    session_id = session_context.get("session_id")
    issuing_session_id = (
        session_id if isinstance(session_id, str) and session_id else "mock-session-unknown"
    )
    ledger_root = session_context.get("ledger_root")
    append_delegation_issued(
        DelegationIssuedEvent(
            ts=now,
            session_id=issuing_session_id,
            delegation_token=raw_token,
            scope=scope_str,
            expires_at=expires_at,
            issuer_did=_ISSUER_DID,
            verify_tool_id="mock_verify_ganpyeon_injeung",
        ),
        ledger_root=ledger_root if isinstance(ledger_root, Path) else None,
    )

    return DelegationContext(
        token=token,
        citizen_did=None,
        purpose_ko=purpose_ko if isinstance(purpose_ko, str) and purpose_ko else "간편인증 위임",
        purpose_en=(
            purpose_en
            if isinstance(purpose_en, str) and purpose_en
            else "Simple-auth delegated workflow"
        ),
    )


def invoke(session_context: dict[str, object]) -> GanpyeonInjeungContext:
    """Return the recorded fixture plus a scope-bound DelegationContext."""
    base = _FIXTURE.model_dump(by_alias=True)
    base["delegation_context"] = _build_delegation_context(session_context)
    if session_context.get("_fixture_override"):
        overrides: dict[str, object] = dict(session_context["_fixture_override"])  # type: ignore[call-overload]
        base.update(overrides)
    return GanpyeonInjeungContext.model_validate(base, by_alias=True)


register_verify_adapter("ganpyeon_injeung", invoke)
