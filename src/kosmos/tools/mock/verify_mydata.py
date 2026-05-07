# SPDX-License-Identifier: Apache-2.0
"""Mock verify adapter — mydata (마이데이터 OAuth 2.0 + mTLS).

Source mode: OOS — shape-mirrored from KFTC MyData v240930 specification
(마이데이터 표준 API 규격서, open-source schema).
FR-009 (delegation-only): no TLS private keys, no OAuth server logic. Fixture-backed.

Epic ε #2296 T022: retrofitted with six transparency fields per
contracts/mock-adapter-response-shape.md § 4 "EXISTING (retrofitted)" rows.
"""

from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from kosmos.memdir.consent_ledger import DelegationIssuedEvent, append_delegation_issued
from kosmos.primitives.delegation import DelegationContext, DelegationToken
from kosmos.primitives.verify import (
    MyDataContext,
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
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/mydata"
_SECURITY_WRAPPING: Final = "마이데이터 표준동의서 OAuth2 + mTLS + finAuth"
_POLICY_AUTHORITY: Final = "https://www.kftc.or.kr/kftc/main/EgovMenuContent.do?menuId=CNT020400"
_INTERNATIONAL_REF: Final = "Singapore Myinfo"
_TOOL_ID: Final = "mock_verify_mydata"
_ISSUER_DID: Final = "did:web:mydata.kftc.or.kr"

ADAPTER_REGISTRATION = AdapterRegistration(
    tool_id=_TOOL_ID,
    primitive=AdapterPrimitive.verify,
    module_path="kosmos.tools.mock.verify_mydata",
    input_model_ref="kosmos.primitives.verify:VerifyInput",
    source_mode=AdapterSourceMode.OOS,
    published_tier_minimum="mydata_individual_aal2",
    nist_aal_hint="AAL2",
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    search_hint={
        "ko": [
            "마이데이터",
            "금융데이터",
            "금결원",
            "KFTC",
            "개인신용정보",
            "복지",
            "복지신청",
            "복지급여신청",
            "사회보장",
            "한부모가족",
            "한부모",
            "아동양육비",
        ],
        "en": [
            "mydata",
            "open banking",
            "KFTC mydata",
            "personal credit data",
            "welfare",
            "welfare application",
            "benefit application",
            "social assistance",
        ],
    },
    auth_type="oauth",
)

# Recorded fixture — provider_id is an anonymised test code.
_FIXTURE = MyDataContext.model_validate(
    {
        "family": "mydata",
        "published_tier": "mydata_individual_aal2",
        "nist_aal_hint": "AAL2",
        "verified_at": datetime(2026, 4, 19, 9, 0, 0, tzinfo=UTC),
        "external_session_ref": "mock-mydata-ref-001",
        "provider_id": "TEST_PROVIDER_001",
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
    """Construct a mock VP JWS that mirrors the other delegation verify adapters."""
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


def _scope_list(session_context: dict[str, object]) -> list[str]:
    raw = session_context.get("scope_list")
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, str) and entry]
    if isinstance(raw, str) and raw:
        return [entry.strip() for entry in raw.split(",") if entry.strip()]
    return []


def _issue_delegation_context(session_context: dict[str, object]) -> DelegationContext | None:
    """Issue a scope-bound delegation grant when MyData is used for downstream action."""
    scopes = _scope_list(session_context)
    if not scopes:
        return None

    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)
    scope_str = ",".join(scopes)
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
        citizen_did=None,
        purpose_ko=str(session_context.get("purpose_ko") or "마이데이터 위임"),
        purpose_en=str(session_context.get("purpose_en") or "MyData delegation"),
    )

    raw_ledger_root = session_context.get("ledger_root")
    ledger_root = raw_ledger_root if isinstance(raw_ledger_root, Path) else None
    append_delegation_issued(
        DelegationIssuedEvent(
            ts=now,
            session_id=str(session_context.get("session_id") or "mock-session-unknown"),
            delegation_token=raw_token,
            scope=scope_str,
            expires_at=expires_at,
            issuer_did=_ISSUER_DID,
            verify_tool_id=_TOOL_ID,
        ),
        ledger_root=ledger_root,
    )
    return context


def invoke(session_context: dict[str, Any]) -> MyDataContext:
    """Return the recorded fixture; override via session_context for test variants."""
    delegation_context = _issue_delegation_context(session_context)
    raw_override = session_context.get("_fixture_override")
    if isinstance(raw_override, dict):
        overrides: dict[str, object] = {str(key): value for key, value in raw_override.items()}
        base = _FIXTURE.model_dump(by_alias=True)
        if delegation_context is not None:
            base["delegation_context"] = delegation_context
        base.update(overrides)
        return MyDataContext.model_validate(base, by_alias=True)
    if delegation_context is None:
        return _FIXTURE
    base = _FIXTURE.model_dump(by_alias=True)
    base["delegation_context"] = delegation_context
    return MyDataContext.model_validate(base, by_alias=True)


register_verify_adapter("mydata", invoke)
