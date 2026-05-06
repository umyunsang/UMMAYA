# SPDX-License-Identifier: Apache-2.0
"""Mock verify adapter — modid (모바일ID / Mobile ID AX-channel).

Epic ε #2296 — FR-001 (new verify mocks), FR-005 (transparency fields).

Source mode: HARNESS_ONLY — mirrors the AX-infrastructure-callable-channel reference
shape for the Ministry of Interior and Safety 모바일 신분증 digital identity channel.
Issues a DelegationToken with OID4VP + DID-resolved RP envelope.

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
from kosmos.primitives.verify import ModidContext, register_verify_adapter
from kosmos.tools.transparency import stamp_mock_response

# ---------------------------------------------------------------------------
# Per-adapter transparency constants (mock-adapter-response-shape.md § 4)
# ---------------------------------------------------------------------------

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/modid"
_SECURITY_WRAPPING: Final = "OID4VP + DID-resolved RP + DPoP"
_POLICY_AUTHORITY: Final = (
    "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do"
    "?bbsId=BBSMSTR_000000000016&nttId=104637"
)
_INTERNATIONAL_REF: Final = "EU EUDI Wallet"
_MOCK_FIDELITY_GRADE: Final = "A-official-mobile-id-verifier-api-published"
_MOCK_EVIDENCE: Final[dict[str, Any]] = {
    "credential_status": "student_no_live_authority",
    "basis_urls": [
        "https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do",
        "https://dev.mobileid.go.kr/mip/dfs/useguide/apiusemethod.do",
        "https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide",
        "https://digital-strategy.ec.europa.eu/en/library/european-digital-identity-wallet-architecture-and-reference-framework",
    ],
    "supports": [
        "official Mobile ID onboarding, DID registration, test credential, and operation approval",
        "official verifier daemon HTTP APIs for transaction start, profile, VP "
        "verification, status, and re-verification",
        "EUDI Wallet interoperable wallet specification analog",
    ],
    "inference_boundary": (
        "KOSMOS does not perform cryptographic VP verification; it mirrors the ceremony "
        "envelope and delegation token expected after verifier success."
    ),
    "live_swap_requirements": [
        "KOMSCO/MOIS service-provider approval",
        "development and operation DID registration",
        "service code and blockchain account",
        "verifier daemon or library integration",
    ],
}

_TOOL_ID: Final = "mock_verify_module_modid"
_ISSUER_DID: Final = "did:web:mobileid.go.kr"

# ---------------------------------------------------------------------------
# Bilingual search hint
# ---------------------------------------------------------------------------

SEARCH_HINT: Final[dict[str, list[str]]] = {
    "ko": ["모바일ID", "모바일신분증", "행정안전부", "DID", "디지털신원"],
    "en": ["mobile ID", "mobile identity", "mobile resident card", "MOIS digital ID"],
}


# ---------------------------------------------------------------------------
# JWS helper (Mock — no real cryptography)
# ---------------------------------------------------------------------------


def _mock_vp_jwt(scope: str, issued_at: datetime, expires_at: datetime) -> str:
    """Construct a deterministic Mock JWS triple (header.payload.signature)."""
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


def invoke(session_context: dict[str, Any]) -> ModidContext:
    """Issue a DelegationToken for the Mobile-ID AX channel.

    session_context keys consumed:
    - ``scope_list`` (list[str], required): scopes to embed in the token.
    - ``session_id`` (str, optional): calling session UUID for ledger.
    - ``purpose_ko`` (str, optional): Korean purpose statement.
    - ``purpose_en`` (str, optional): English purpose statement.
    - ``ledger_root`` (Path, optional): test override for ledger directory.
    """
    scope_list: list[str] = session_context.get("scope_list", ["verify:modid.identity"])
    scope_str = ",".join(scope_list)
    session_id: str = session_context.get("session_id", "mock-session-unknown")
    purpose_ko: str = session_context.get("purpose_ko", "모바일 신분증 신원확인")
    purpose_en: str = session_context.get(
        "purpose_en", "Mobile-ID identity verification via OID4VP"
    )

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
    context = DelegationContext(
        token=token,
        citizen_did=f"did:web:mobileid.go.kr:{secrets.token_hex(8)}",
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
    return ModidContext.model_validate(
        {
            "published_tier": "modid_aal3",
            "nist_aal_hint": "AAL3",
            "verified_at": now,
            "delegation_context": context,
            **transparency,
        }
    )


register_verify_adapter("modid", invoke)
