# SPDX-License-Identifier: Apache-2.0
"""Verify primitive — delegation-only identity binding for Spec 031 US2.

FR-009 (harness-not-reimplementation): KOSMOS holds NO private keys, performs
NO certificate signing, and runs NO HSM or VC-issuer logic. All authentication
evidence is supplied externally; this module wraps it into a typed AuthContext.

FR-010 (no coercion): a family_hint that disagrees with the observed session
evidence produces a VerifyMismatchError. The dispatcher NEVER silently coerces
one family to another.

Data model: specs/031-five-primitive-harness/data-model.md § 2
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field, model_validator

from kosmos.primitives.delegation import DelegationContext, IdentityAssertion
from kosmos.tools.registry import NistAalHint, PublishedTier

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("kosmos.primitives.verify")

# ---------------------------------------------------------------------------
# VerifyInput
# ---------------------------------------------------------------------------

FamilyHint = Literal[
    "gongdong_injeungseo",
    "geumyung_injeungseo",
    "ganpyeon_injeung",
    "digital_onepass",
    "mobile_id",
    "mydata",
]


class VerifyInput(BaseModel):
    """Main-surface input for the verify primitive (FR-006)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family_hint: FamilyHint
    session_context: dict[str, object] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# _AuthContextBase
# ---------------------------------------------------------------------------

_GONGDONG_TIERS: frozenset[str] = frozenset(
    {
        "gongdong_injeungseo_personal_aal3",
        "gongdong_injeungseo_corporate_aal3",
        "gongdong_injeungseo_bank_only_aal2",
    }
)

_GEUMYUNG_TIERS: frozenset[str] = frozenset(
    {
        "geumyung_injeungseo_personal_aal2",
        "geumyung_injeungseo_business_aal3",
    }
)

_GANPYEON_TIERS: frozenset[str] = frozenset(
    {
        "ganpyeon_injeung_pass_aal2",
        "ganpyeon_injeung_kakao_aal2",
        "ganpyeon_injeung_naver_aal2",
        "ganpyeon_injeung_toss_aal2",
        "ganpyeon_injeung_bank_aal2",
        "ganpyeon_injeung_samsung_aal2",
        "ganpyeon_injeung_payco_aal2",
    }
)

_DIGITAL_ONEPASS_TIERS: frozenset[str] = frozenset(
    {
        "digital_onepass_level1_aal1",
        "digital_onepass_level2_aal2",
        "digital_onepass_level3_aal3",
    }
)

_MOBILE_ID_TIERS: frozenset[str] = frozenset(
    {
        "mobile_id_mdl_aal2",
        "mobile_id_resident_aal2",
    }
)

_MYDATA_TIERS: frozenset[str] = frozenset({"mydata_individual_aal2"})

# Spec 2296 Epic ε — AX-infrastructure callable-channel verify modules.
# One frozenset per family; values mirror the new PublishedTier values added
# in src/kosmos/tools/registry.py.
_SIMPLE_AUTH_MODULE_TIERS: frozenset[str] = frozenset({"simple_auth_module_aal2"})
_MODID_TIERS: frozenset[str] = frozenset({"modid_aal3"})
_KEC_TIERS: frozenset[str] = frozenset({"kec_aal3"})
_GEUMYUNG_MODULE_TIERS: frozenset[str] = frozenset({"geumyung_module_aal3"})
_ANY_ID_SSO_TIERS: frozenset[str] = frozenset({"any_id_sso_aal2"})


class _AuthContextBase(BaseModel):
    """Common fields shared by all six auth-family context variants.

    Epic ε #2296 (T007): adds six optional transparency fields per
    data-model.md § 8. Mock adapters populate these via ``stamp_mock_response``.
    Live adapters leave them ``None`` (the regression test only asserts non-None
    for ``source_mode == 'mock'`` adapters).

    Lead-S3 #2659 (2026-05-04): adds a ``status`` discriminator stamped at the
    envelope top-level so the TUI's ``VerifyPrimitive.renderToolResultMessage``
    can render the green ``인증 완료`` label instead of falling back to the
    ambiguous ``결과 수신됨`` else-branch. Reaching an ``AuthContext`` instance
    means delegation succeeded — ``verify()`` rejects all failure paths through
    ``VerifyMismatchError`` (which carries ``status="failed"``). This is the
    last layer of the citizen-facing success/failure cascade.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    # Status discriminator — every AuthContext implies delegation success.
    # Failure is signalled by ``VerifyMismatchError`` (sister model below).
    status: Literal["verified"] = "verified"

    published_tier: PublishedTier
    nist_aal_hint: NistAalHint
    verified_at: datetime
    external_session_ref: str | None = None

    # --- Six optional transparency fields (data-model.md § 8) ---
    # Populated by mock adapters via stamp_mock_response().
    # Live adapters leave all six as None (forward-compatible contract).
    transparency_mode: str | None = Field(default=None, alias="_mode")
    transparency_reference_implementation: str | None = Field(
        default=None, alias="_reference_implementation"
    )
    transparency_actual_endpoint_when_live: str | None = Field(
        default=None, alias="_actual_endpoint_when_live"
    )
    transparency_security_wrapping_pattern: str | None = Field(
        default=None, alias="_security_wrapping_pattern"
    )
    transparency_policy_authority: str | None = Field(default=None, alias="_policy_authority")
    transparency_international_reference: str | None = Field(
        default=None, alias="_international_reference"
    )
    mock_fidelity_grade: str | None = Field(default=None, alias="_mock_fidelity_grade")
    mock_evidence: dict[str, object] | None = Field(default=None, alias="_mock_evidence")


# ---------------------------------------------------------------------------
# Six family context classes  (T039 + T040 — per-family published_tier
# narrowing via @model_validator)
# ---------------------------------------------------------------------------


class GongdongInjeungseoContext(_AuthContextBase):
    """공동인증서 (KOSCOM Joint Certificate) authentication context."""

    family: Literal["gongdong_injeungseo"] = "gongdong_injeungseo"
    certificate_issuer: str = Field(
        min_length=1,
        description="Issuing CA name, e.g. 'KICA', 'KFTC', 'TradeSign'.",
    )

    @model_validator(mode="after")
    def _check_published_tier(self) -> GongdongInjeungseoContext:
        if self.published_tier not in _GONGDONG_TIERS:
            raise ValueError(
                f"GongdongInjeungseoContext.published_tier must be one of "
                f"{sorted(_GONGDONG_TIERS)}, got {self.published_tier!r}"
            )
        return self


class GeumyungInjeungseoContext(_AuthContextBase):
    """금융인증서 (Financial Certificate, KFTC) authentication context."""

    family: Literal["geumyung_injeungseo"] = "geumyung_injeungseo"
    bank_cluster: Literal["kftc"] = Field(description="금융결제원 클라우드 cluster identifier.")

    @model_validator(mode="after")
    def _check_published_tier(self) -> GeumyungInjeungseoContext:
        if self.published_tier not in _GEUMYUNG_TIERS:
            raise ValueError(
                f"GeumyungInjeungseoContext.published_tier must be one of "
                f"{sorted(_GEUMYUNG_TIERS)}, got {self.published_tier!r}"
            )
        return self


class GanpyeonInjeungContext(_AuthContextBase):
    """간편인증 (Simple/App-cert) — Kakao / Naver / Toss / PASS / etc."""

    family: Literal["ganpyeon_injeung"] = "ganpyeon_injeung"
    provider: Literal["pass", "kakao", "naver", "toss", "bank", "samsung", "payco"]
    delegation_context: DelegationContext | None = Field(
        default=None,
        description=(
            "Optional scope-bound delegation grant emitted when the verify request "
            "included downstream lookup/submit scopes."
        ),
    )

    @model_validator(mode="after")
    def _check_published_tier(self) -> GanpyeonInjeungContext:
        if self.published_tier not in _GANPYEON_TIERS:
            raise ValueError(
                f"GanpyeonInjeungContext.published_tier must be one of "
                f"{sorted(_GANPYEON_TIERS)}, got {self.published_tier!r}"
            )
        return self


class DigitalOnepassContext(_AuthContextBase):
    """Digital Onepass Level 1–3 authentication context."""

    family: Literal["digital_onepass"] = "digital_onepass"
    level: Literal[1, 2, 3]

    @model_validator(mode="after")
    def _check_published_tier(self) -> DigitalOnepassContext:
        if self.published_tier not in _DIGITAL_ONEPASS_TIERS:
            raise ValueError(
                f"DigitalOnepassContext.published_tier must be one of "
                f"{sorted(_DIGITAL_ONEPASS_TIERS)}, got {self.published_tier!r}"
            )
        return self


class MobileIdContext(_AuthContextBase):
    """모바일 신분증 (Mobile ID) authentication context."""

    family: Literal["mobile_id"] = "mobile_id"
    id_type: Literal["mdl", "resident"] = Field(description="모바일운전면허 | 모바일주민등록증")

    @model_validator(mode="after")
    def _check_published_tier(self) -> MobileIdContext:
        if self.published_tier not in _MOBILE_ID_TIERS:
            raise ValueError(
                f"MobileIdContext.published_tier must be one of "
                f"{sorted(_MOBILE_ID_TIERS)}, got {self.published_tier!r}"
            )
        return self


class MyDataContext(_AuthContextBase):
    """마이데이터 OAuth 2.0 + mTLS authentication context."""

    family: Literal["mydata"] = "mydata"
    provider_id: str = Field(min_length=1, description="마이데이터 사업자 코드.")

    @model_validator(mode="after")
    def _check_published_tier(self) -> MyDataContext:
        if self.published_tier not in _MYDATA_TIERS:
            raise ValueError(
                f"MyDataContext.published_tier must be one of "
                f"{sorted(_MYDATA_TIERS)}, got {self.published_tier!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Spec 2296 Epic ε — AX-infrastructure callable-channel verify families.
# These five contexts wrap a DelegationContext (or IdentityAssertion for
# any_id_sso) issued by mock_verify_module_* adapters. The wrapped envelope
# is the OID4VP-style delegation grant the AX gateway is expected to mint
# once the policy mandate ships. Per data-model.md § 1-3 + Codex P1 #2446.
# ---------------------------------------------------------------------------


class SimpleAuthModuleContext(_AuthContextBase):
    """간편인증 (Simple Auth) AX-channel verify context wrapping a DelegationContext."""

    family: Literal["simple_auth_module"] = "simple_auth_module"
    delegation_context: DelegationContext

    @model_validator(mode="after")
    def _check_published_tier(self) -> SimpleAuthModuleContext:
        if self.published_tier not in _SIMPLE_AUTH_MODULE_TIERS:
            raise ValueError(
                f"SimpleAuthModuleContext.published_tier must be one of "
                f"{sorted(_SIMPLE_AUTH_MODULE_TIERS)}, got {self.published_tier!r}"
            )
        return self


class ModidContext(_AuthContextBase):
    """모바일ID (KOMSCO OID4VP + DID) AX-channel verify context."""

    family: Literal["modid"] = "modid"
    delegation_context: DelegationContext

    @model_validator(mode="after")
    def _check_published_tier(self) -> ModidContext:
        if self.published_tier not in _MODID_TIERS:
            raise ValueError(
                f"ModidContext.published_tier must be one of "
                f"{sorted(_MODID_TIERS)}, got {self.published_tier!r}"
            )
        return self


class KECContext(_AuthContextBase):
    """공동인증서 (KEC joint cert) AX-channel verify context."""

    family: Literal["kec"] = "kec"
    delegation_context: DelegationContext

    @model_validator(mode="after")
    def _check_published_tier(self) -> KECContext:
        if self.published_tier not in _KEC_TIERS:
            raise ValueError(
                f"KECContext.published_tier must be one of "
                f"{sorted(_KEC_TIERS)}, got {self.published_tier!r}"
            )
        return self


class GeumyungModuleContext(_AuthContextBase):
    """금융인증서 (FNS Financial Cert) AX-channel verify context."""

    family: Literal["geumyung_module"] = "geumyung_module"
    delegation_context: DelegationContext

    @model_validator(mode="after")
    def _check_published_tier(self) -> GeumyungModuleContext:
        if self.published_tier not in _GEUMYUNG_MODULE_TIERS:
            raise ValueError(
                f"GeumyungModuleContext.published_tier must be one of "
                f"{sorted(_GEUMYUNG_MODULE_TIERS)}, got {self.published_tier!r}"
            )
        return self


class AnyIdSsoContext(_AuthContextBase):
    """Any-ID SSO (digital_onepass successor) verify context wrapping an IdentityAssertion.

    Per delegation-flow-design.md § 2.2: Any-ID is identity-SSO only — it does NOT
    issue a delegation grant. Downstream submit/lookup adapters that receive an
    AnyIdSsoContext (rather than one of the four DelegationContext-wrapping variants
    above) MUST reject the call with DelegationGrantMissing per spec FR-001.
    """

    family: Literal["any_id_sso"] = "any_id_sso"
    identity_assertion: IdentityAssertion

    @model_validator(mode="after")
    def _check_published_tier(self) -> AnyIdSsoContext:
        if self.published_tier not in _ANY_ID_SSO_TIERS:
            raise ValueError(
                f"AnyIdSsoContext.published_tier must be one of "
                f"{sorted(_ANY_ID_SSO_TIERS)}, got {self.published_tier!r}"
            )
        return self


# ---------------------------------------------------------------------------
# AuthContext discriminated union + VerifyMismatchError + VerifyOutput
# ---------------------------------------------------------------------------

AuthContext = Annotated[
    GongdongInjeungseoContext
    | GeumyungInjeungseoContext
    | GanpyeonInjeungContext
    | DigitalOnepassContext
    | MobileIdContext
    | MyDataContext
    # Spec 2296 Epic ε — 5 new AX-channel families.
    | SimpleAuthModuleContext
    | ModidContext
    | KECContext
    | GeumyungModuleContext
    | AnyIdSsoContext,
    Field(discriminator="family"),
]


class VerifyMismatchError(BaseModel):
    """Structured result when family_hint disagrees with session evidence (FR-010).

    ``family`` is fixed to ``"mismatch_error"`` so that a discriminated union
    over ``AuthContext | VerifyMismatchError`` can dispatch on the ``family``
    field without ambiguity.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Status discriminator — sister field to ``_AuthContextBase.status``. The
    # dispatchPrimitive ([H1] branch, 2026-05-04) classifies ``family ==
    # "mismatch_error"`` as ``ok: false``, so the TUI's renderer normally enters
    # the failure branch directly. ``status="failed"`` is defense-in-depth so
    # any caller that bypasses the dispatcher classification (older fixtures,
    # raw envelope inspection) still reads explicit failure.
    status: Literal["failed"] = "failed"

    family: Literal["mismatch_error"] = "mismatch_error"
    reason: Literal["family_mismatch"] = "family_mismatch"
    expected_family: str
    observed_family: str
    message: str


class VerifyOutput(BaseModel):
    """Top-level output envelope for the verify primitive."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: Annotated[
        GongdongInjeungseoContext
        | GeumyungInjeungseoContext
        | GanpyeonInjeungContext
        | DigitalOnepassContext
        | MobileIdContext
        | MyDataContext
        | VerifyMismatchError,
        Field(discriminator="family"),
    ]


# ---------------------------------------------------------------------------
# Dispatcher (T041) — delegation only, no CA/signing logic here
# ---------------------------------------------------------------------------

# Registry for mock/live verify adapters.  Keys are FamilyHint strings.
_VERIFY_ADAPTERS: dict[str, object] = {}


def register_verify_adapter(family: str, adapter: object) -> None:
    """Register a callable adapter for a given family.

    Adapters must accept ``(session_context: dict[str, object]) -> AuthContext``
    or raise / return ``VerifyMismatchError``.  Called at module import time by
    each ``src/kosmos/tools/mock/verify_<family>.py``.
    """
    _VERIFY_ADAPTERS[family] = adapter


async def verify(
    family_hint: str,
    session_context: dict[str, object] | None = None,
) -> AuthContext | VerifyMismatchError:
    """Verify primitive dispatcher (T041).

    Delegates entirely to the registered adapter for ``family_hint``.  Returns
    ``VerifyMismatchError`` if:

    1. No adapter is registered for ``family_hint`` (adapter missing).
    2. The adapter itself signals a family mismatch via ``VerifyMismatchError``.
    3. The adapter returns an ``AuthContext`` whose ``family`` field disagrees
       with ``family_hint`` (coercion guard — FR-010).

    KOSMOS is a harness.  All cryptographic validation, cert chain evaluation,
    and credential issuance happen inside the external provider; this function
    only wraps the result.
    """
    if session_context is None:
        session_context = {}

    with _tracer.start_as_current_span("gen_ai.tool_loop.iteration") as span:
        span.set_attribute("gen_ai.tool.name", f"verify:{family_hint}")
        span.set_attribute("kosmos.verify.family_hint", family_hint)

        adapter = _VERIFY_ADAPTERS.get(family_hint)
        if adapter is None:
            logger.warning("verify: no adapter registered for family=%s", family_hint)
            span.set_attribute("error.type", "adapter_not_found")
            return VerifyMismatchError(
                family="mismatch_error",
                reason="family_mismatch",
                expected_family=family_hint,
                observed_family="<no_adapter>",
                message=(
                    f"No verify adapter registered for family {family_hint!r}. "
                    "Register a mock or live adapter via register_verify_adapter()."
                ),
            )

        import asyncio
        import inspect

        if inspect.iscoroutinefunction(adapter):
            result = await adapter(session_context)
        else:
            result = adapter(session_context)  # type: ignore[operator]
            if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                result = await result

        # FR-010: guard against coercion — reject a returned context whose family
        # does not match family_hint.
        if isinstance(result, VerifyMismatchError):
            span.set_attribute("error.type", "verify_mismatch")
            return result

        # Validate it is a known AuthContext variant
        if not isinstance(
            result,
            (
                GongdongInjeungseoContext,
                GeumyungInjeungseoContext,
                GanpyeonInjeungContext,
                DigitalOnepassContext,
                MobileIdContext,
                MyDataContext,
                # Spec 2296 Epic ε — 5 new AX-channel families (Codex P1 #2446 fix).
                SimpleAuthModuleContext,
                ModidContext,
                KECContext,
                GeumyungModuleContext,
                AnyIdSsoContext,
            ),
        ):
            span.set_attribute("error.type", "unexpected_adapter_return_type")
            return VerifyMismatchError(
                family="mismatch_error",
                reason="family_mismatch",
                expected_family=family_hint,
                observed_family=str(type(result)),
                message=(
                    f"Adapter for {family_hint!r} returned unexpected type "
                    f"{type(result).__name__!r}. Expected an AuthContext variant."
                ),
            )

        observed = getattr(result, "family", None)
        if observed != family_hint:
            logger.error(
                "verify FR-010: family_hint=%s but adapter returned family=%s — coercion blocked",
                family_hint,
                observed,
            )
            span.set_attribute("error.type", "family_mismatch")
            return VerifyMismatchError(
                family="mismatch_error",
                reason="family_mismatch",
                expected_family=family_hint,
                observed_family=str(observed),
                message=(
                    f"Adapter returned family={observed!r} but caller specified "
                    f"family_hint={family_hint!r}. Coercion is prohibited (FR-010)."
                ),
            )

        span.set_attribute("kosmos.verify.observed_family", str(observed))
        return result


__all__ = [
    "AuthContext",
    "DigitalOnepassContext",
    "FamilyHint",
    "GanpyeonInjeungContext",
    "GeumyungInjeungseoContext",
    "GongdongInjeungseoContext",
    "MobileIdContext",
    "MyDataContext",
    "VerifyInput",
    "VerifyMismatchError",
    "VerifyOutput",
    "_AuthContextBase",
    "register_verify_adapter",
    "verify",
]
