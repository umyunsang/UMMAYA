# SPDX-License-Identifier: Apache-2.0
"""Mock verify adapter — simple_auth_module (간편인증 / Simple Auth AX-channel).

Epic ε #2296 — FR-001 (new verify mocks), FR-005 (transparency fields).

Source mode: HARNESS_ONLY — mirrors the AX-infrastructure-callable-channel reference
shape for simple (app-cert / pass / kakao) identity verification.
Issues a DelegationToken rather than a bare AuthContext (Epic ε pattern).

Contract: specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md § 1
Data model: specs/2296-ax-mock-adapters/data-model.md § 1-2
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from kosmos.memdir.consent_ledger import DelegationIssuedEvent, append_delegation_issued
from kosmos.primitives.delegation import DelegationContext, DelegationToken
from kosmos.primitives.verify import SimpleAuthModuleContext, register_verify_adapter
from kosmos.tools.transparency import stamp_mock_response

# ---------------------------------------------------------------------------
# Per-adapter transparency constants (mock-adapter-response-shape.md § 4)
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/simple_auth"
_SECURITY_WRAPPING: Final = "OAuth2.1 + PKCE + scope-bound bearer"
_POLICY_AUTHORITY: Final = (
    "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do"
    "?bbsId=BBSMSTR_000000000016&nttId=104636"
)
_INTERNATIONAL_REF: Final = "Japan マイナポータル API"
_MOCK_FIDELITY_GRADE: Final = "B-official-policy-private-hub-api-inferred"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://www.kisa.or.kr/1051203",
        "https://www.ez-iok.com/guide/eziok_intro/",
        "https://www.ez-iok.com/guide/eziok_std_guide/",
    ],
    "supports": [
        "official KISA electronic-signature provider recognition framework",
        "public integrated simple-auth hub JSON request and result pattern",
        "service ID, encrypted client transaction ID, service type, and provider-result "
        "verification pattern",
    ],
    "inference_boundary": (
        "Government simple-auth relay contracts are provider and institution gated; "
        "KOSMOS mirrors common hub transaction semantics and does not claim provider "
        "result validity."
    ),
    "live_swap_requirements": [
        "approved relying-party registration",
        "service ID and encryption key material",
        "provider result comparison and verification procedure",
        "agency-specific callback/result contract",
    ],
}

_TOOL_ID: Final = "mock_verify_module_simple_auth"
_ISSUER_DID: Final = "did:web:simpleauth.go.kr"

# ---------------------------------------------------------------------------
# Bilingual search hint
# ---------------------------------------------------------------------------

SEARCH_HINT: Final[dict[str, list[str]]] = {
    "ko": ["간편인증", "카카오인증", "PASS인증", "네이버인증", "간편인증서"],
    "en": ["simple auth", "easy cert", "kakao cert", "pass cert", "ganpyeon injeung"],
}


# ---------------------------------------------------------------------------
# JWS helper (Mock — no real cryptography)
# ---------------------------------------------------------------------------


def _mock_vp_jwt(scope: str, issued_at: datetime, expires_at: datetime) -> str:
    """Construct a deterministic Mock JWS triple (header.payload.signature).

    The signature segment is the literal 'mock-signature-not-cryptographic'
    per data-model.md § 1.
    """
    header_b64 = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "vp+jwt"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload_b64 = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "iss": _ISSUER_DID,
                    "scope": scope,
                    "iat": int(issued_at.timestamp()),
                    "exp": int(expires_at.timestamp()),
                }
            ).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{header_b64}.{payload_b64}.mock-signature-not-cryptographic"


# ---------------------------------------------------------------------------
# invoke — registered via register_verify_adapter
# ---------------------------------------------------------------------------


def invoke(session_context: dict[str, Any]) -> SimpleAuthModuleContext:
    """Issue a DelegationToken for the simple-auth AX channel.

    session_context keys consumed:
    - ``scope_list`` (list[str], required): scopes to embed in the token.
    - ``session_id`` (str, optional): calling session UUID for ledger.
    - ``purpose_ko`` (str, optional): Korean purpose statement.
    - ``purpose_en`` (str, optional): English purpose statement.
    - ``ledger_root`` (Path, optional): test override for ledger directory.
    """
    scope_list: list[str] = session_context.get("scope_list", ["verify:simple_auth.identity"])
    scope_str = ",".join(scope_list)
    session_id: str = session_context.get("session_id", "mock-session-unknown")
    purpose_ko: str = session_context.get("purpose_ko", "간편인증 신원확인")
    purpose_en: str = session_context.get("purpose_en", "Simple-auth identity verification")

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)
    raw_token = f"del_{secrets.token_urlsafe(24)}"

    token = DelegationToken(
        vp_jwt=_mock_vp_jwt(scope_str, now, expires_at),
        delegation_token=raw_token,
        scope=scope_str,
        issuer_did=_ISSUER_DID,
        issued_at=now,
        expires_at=expires_at,  # alias field
    )
    context = DelegationContext(
        token=token,
        citizen_did=None,
        purpose_ko=purpose_ko,
        purpose_en=purpose_en,
    )

    # Append delegation_issued ledger event.
    ledger_root = session_context.get("ledger_root")
    ledger_event = DelegationIssuedEvent(
        ts=now,
        session_id=session_id,
        delegation_token=raw_token,
        scope=scope_str,
        expires_at=expires_at,
        issuer_did=_ISSUER_DID,
        verify_tool_id=_TOOL_ID,
    )
    append_delegation_issued(ledger_event, ledger_root=ledger_root)

    # Build the transparency dict via stamp_mock_response on an empty payload —
    # we need the six stamped fields to populate the typed context (Spec 031
    # AuthContext envelope wraps the DelegationContext + carries transparency).
    transparency = stamp_mock_response(
        {},
        reference_implementation=_REFERENCE_IMPL,
        actual_endpoint_when_live=_ACTUAL_ENDPOINT,
        security_wrapping_pattern=_SECURITY_WRAPPING,
        policy_authority=_POLICY_AUTHORITY,
        international_reference=_INTERNATIONAL_REF,
        mock_fidelity_grade=_MOCK_FIDELITY_GRADE,
        mock_evidence=_MOCK_EVIDENCE,
    )

    # Return a typed AuthContext variant so verify(family_hint=...) accepts it
    # (Codex P1 #2446 fix). The wrapped DelegationContext carries the OID4VP
    # envelope; the six aliased transparency fields surface in model_dump(by_alias).
    return SimpleAuthModuleContext.model_validate(
        {
            "published_tier": "simple_auth_module_aal2",
            "nist_aal_hint": "AAL2",
            "verified_at": now,
            "delegation_context": context,
            **transparency,
        }
    )


register_verify_adapter("simple_auth_module", invoke)
