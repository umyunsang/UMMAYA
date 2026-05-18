# SPDX-License-Identifier: Apache-2.0
"""Live MobileID check adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ummaya.primitives.verify import MobileIdContext, register_verify_adapter
from ummaya.tools.errors import _require_env
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.live.mobileid_client import (
    MobileIdClient,
    MobileIdVerificationError,
    ensure_verified_response,
)
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry

_TOOL_ID = "live_verify_mobile_id"
_DOC_URL = "https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide"
_PROCEDURE_URL = "https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do"
_ID_TYPE_EVIDENCE_KEYS = frozenset(
    {
        "cardtype",
        "credentialcategory",
        "credentialkind",
        "credentialtype",
        "doctype",
        "documenttype",
        "identitytype",
        "idtype",
        "type",
        "types",
        "vctype",
    }
)


class LiveMobileIdVpInput(BaseModel):
    """Encrypted VP presentation metadata accepted by the MobileID daemon."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    present_type: str = Field(alias="presentType", min_length=1)
    encrypt_type: str = Field(alias="encryptType", min_length=1)
    key_type: str = Field(alias="keyType", min_length=1)
    auth_type: str = Field(alias="authType", min_length=1)
    did: str = Field(min_length=1)
    nonce: str | None = Field(default=None, min_length=1)
    zkp_nonce: str | None = Field(default=None, alias="zkpNonce", min_length=1)
    type: Literal["verify"] = "verify"
    data: str = Field(min_length=1, repr=False)

    @model_validator(mode="after")
    def _require_nonce(self) -> LiveMobileIdVpInput:
        if not self.nonce and not self.zkp_nonce:
            raise ValueError("MobileID VP input requires nonce or zkpNonce.")
        return self


class LiveMobileIdCheckInput(BaseModel):
    """LLM-facing input model for `live_verify_mobile_id`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trxcode: str = Field(min_length=1, description="MobileID transaction code.")
    id_type: Literal["mdl", "resident"] = "mdl"
    vp: LiveMobileIdVpInput | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=60)

    @field_validator("trxcode")
    @classmethod
    def _strip_trxcode(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("trxcode is required.")
        return stripped


class _MobileIdCheckClient(Protocol):
    async def verify_vp(
        self,
        *,
        trxcode: str,
        vp: LiveMobileIdVpInput,
    ) -> dict[str, object]: ...

    async def transaction_status(self, trxcode: str) -> dict[str, object]: ...


LIVE_VERIFY_MOBILE_ID_TOOL = GovAPITool(
    id=_TOOL_ID,
    name_ko="모바일신분증 실시간 본인확인",
    ministry="MOIS",
    category=["check", "identity", "mobile_id"],
    endpoint=_DOC_URL,
    auth_type="api_key",
    input_schema=LiveMobileIdCheckInput,
    output_schema=MobileIdContext,
    search_hint=(
        "모바일신분증 모바일 운전면허증 모바일 주민등록증 모바일ID 본인확인 "
        "mobile id mobile driver license check"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url=_PROCEDURE_URL,
        real_classification_text=(
            "모바일신분증 개발지원센터 서비스 신청 및 승인 절차에 따른 본인확인 연계."
        ),
        citizen_facing_gate="login",
        last_verified=datetime(2026, 5, 18, tzinfo=UTC),
    ),
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=10,
    adapter_mode="live",
    primitive="check",
    published_tier_minimum="mobile_id_mdl_aal2",
    nist_aal_hint="AAL2",
    llm_description=(
        "check(tool_id='live_verify_mobile_id', params={trxcode, id_type, vp?}) "
        "confirms an existing MobileID verification-daemon transaction. "
        "Returns only a MobileIdContext-compatible result; never returns raw VP, CI, DI, "
        "resident identifiers, phone numbers, names, or birthdate fields."
    ),
)


async def handle_live_mobile_id_check(
    input_model: LiveMobileIdCheckInput,
    *,
    client: _MobileIdCheckClient | None = None,
) -> MobileIdContext:
    """Verify a MobileID transaction and return a safe auth context."""
    effective_client = client or _client_from_env(input_model)
    if input_model.vp is not None:
        vp_result = await effective_client.verify_vp(
            trxcode=input_model.trxcode,
            vp=input_model.vp,
        )
        ensure_verified_response(vp_result, source="/mip/vp")

    status_result = await effective_client.transaction_status(input_model.trxcode)
    ensure_verified_response(status_result, source="/mip/trxsts")

    id_type = _resolve_id_type(
        requested=input_model.id_type,
        vp_result=vp_result if input_model.vp is not None else None,
        status_result=status_result,
    )
    published_tier: Literal["mobile_id_mdl_aal2", "mobile_id_resident_aal2"] = (
        "mobile_id_resident_aal2" if id_type == "resident" else "mobile_id_mdl_aal2"
    )
    return MobileIdContext(
        published_tier=published_tier,
        nist_aal_hint="AAL2",
        verified_at=datetime.now(UTC),
        external_session_ref=f"mobileid:{input_model.trxcode}",
        id_type=id_type,
    )


def _resolve_id_type(
    *,
    requested: Literal["mdl", "resident"],
    vp_result: dict[str, object] | None,
    status_result: dict[str, object],
) -> Literal["mdl", "resident"]:
    evidence = set(_extract_id_type_evidence(status_result))
    if vp_result is not None:
        evidence.update(_extract_id_type_evidence(vp_result))

    if len(evidence) > 1:
        raise MobileIdVerificationError("MobileID upstream returned conflicting id type evidence.")
    if evidence:
        observed = evidence.pop()
        if observed != requested:
            raise MobileIdVerificationError(
                "MobileID upstream id type did not match requested id_type."
            )
        return observed
    if requested == "resident":
        raise MobileIdVerificationError(
            "MobileID resident id_type requires corroborating upstream credential evidence."
        )
    return "mdl"


def _extract_id_type_evidence(value: object) -> set[Literal["mdl", "resident"]]:
    evidence: set[Literal["mdl", "resident"]] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).replace("_", "").replace("-", "").lower()
            if normalized_key in _ID_TYPE_EVIDENCE_KEYS:
                normalized_id_type = _normalize_id_type_value(item)
                if normalized_id_type is not None:
                    evidence.add(normalized_id_type)
            evidence.update(_extract_id_type_evidence(item))
    elif isinstance(value, list):
        for item in value:
            evidence.update(_extract_id_type_evidence(item))
    return evidence


def _normalize_id_type_value(value: object) -> Literal["mdl", "resident"] | None:
    if isinstance(value, str):
        normalized = (
            value.replace("_", "").replace("-", "").replace(" ", "").replace("/", "").lower()
        )
        if (
            "resident" in normalized
            or "jumin" in normalized
            or normalized == "rrn"
            or "주민" in value
        ):
            return "resident"
        if (
            normalized == "mdl"
            or "mobiledriverlicense" in normalized
            or "driverlicense" in normalized
            or "drivinglicense" in normalized
            or "운전" in value
            or "면허" in value
        ):
            return "mdl"
        return None
    if isinstance(value, list):
        nested = {_normalize_id_type_value(item) for item in value}
        concrete = {item for item in nested if item is not None}
        return concrete.pop() if len(concrete) == 1 else None
    return None


def _client_from_env(input_model: LiveMobileIdCheckInput) -> MobileIdClient:
    return MobileIdClient(
        base_url=_require_env("UMMAYA_MOBILEID_BASE_URL"),
        client_id=_require_env("UMMAYA_MOBILEID_CLIENT_ID"),
        timeout_seconds=input_model.timeout_seconds or 10.0,
    )


async def _executor_adapter(input_model: BaseModel) -> dict[str, Any]:
    if not isinstance(input_model, LiveMobileIdCheckInput):
        input_model = LiveMobileIdCheckInput.model_validate(input_model)
    output = await handle_live_mobile_id_check(input_model)
    return output.model_dump(mode="json")


async def _verify_adapter(session_context: dict[str, object]) -> MobileIdContext:
    input_model = LiveMobileIdCheckInput.model_validate(_extract_check_input(session_context))
    return await handle_live_mobile_id_check(input_model)


def _extract_check_input(session_context: dict[str, object]) -> dict[str, object]:
    allowed = {"trxcode", "id_type", "vp", "timeout_seconds"}
    return {key: value for key, value in session_context.items() if key in allowed}


def register(registry: ToolRegistry, executor: ToolExecutor) -> None:
    """Register the live MobileID check adapter in registry and executor paths."""
    registry.register(LIVE_VERIFY_MOBILE_ID_TOOL)
    executor.register_adapter(_TOOL_ID, _executor_adapter)
    register_verify_adapter("mobile_id", _verify_adapter, tool_id=_TOOL_ID)


__all__ = [
    "LIVE_VERIFY_MOBILE_ID_TOOL",
    "LiveMobileIdCheckInput",
    "LiveMobileIdVpInput",
    "handle_live_mobile_id_check",
    "register",
]
