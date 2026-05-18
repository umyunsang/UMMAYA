# SPDX-License-Identifier: Apache-2.0
"""Live check adapter for KB국민인증서 identity verification."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ummaya.primitives.verify import (
    KbIdentityContext,
    VerifyMismatchError,
    register_verify_adapter,
)
from ummaya.tools.live.kb_identity_client import (
    KbIdentityClient,
    KbIdentityClientError,
    KbIdentityConfig,
    KbIdentityReceipt,
)

_TOOL_ID = "live_verify_kb_identity"
_FAMILY = "kb_identity"
_REQUIRED_ENV = (
    "UMMAYA_KBCERT_BASE_URL",
    "UMMAYA_KBCERT_API_KEY",
    "UMMAYA_KBCERT_HS_KEY",
    "UMMAYA_KBCERT_COMPANY_CD",
)


class KbIdentityParams(BaseModel):
    """Session context accepted by the live KB check adapter."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    mode: Literal["auto", "request", "result"] = "auto"
    req_tx_id: str | None = Field(default=None, alias="reqTxId")
    cert_tx_id: str | None = Field(default=None, alias="certTxId")
    request_type: str | None = Field(default=None, alias="requestType")
    fixture_response: dict[str, object] | None = Field(default=None, alias="_fixture_response")


async def invoke(session_context: dict[str, object]) -> KbIdentityContext | VerifyMismatchError:
    """Run the KB identity check flow and return a sanitized AuthContext."""
    try:
        params = KbIdentityParams.model_validate(session_context)
        config = _config_from_env()
        client = KbIdentityClient(config)
        mode = _resolve_mode(params)
        if mode == "request":
            req_tx_id = params.req_tx_id or _generate_req_tx_id()
            receipt = (
                client.parse_request_response(
                    params.fixture_response,
                    expected_req_tx_id=req_tx_id,
                )
                if params.fixture_response is not None
                else await client.request_identity(
                    req_tx_id=req_tx_id,
                    request_type=params.request_type,
                )
            )
        else:
            req_tx_id = _require_param(params.req_tx_id, "reqTxId")
            cert_tx_id = _require_param(params.cert_tx_id, "certTxId")
            receipt = (
                client.parse_result_response(
                    params.fixture_response,
                    expected_req_tx_id=req_tx_id,
                    expected_cert_tx_id=cert_tx_id,
                )
                if params.fixture_response is not None
                else await client.lookup_result(
                    req_tx_id=req_tx_id,
                    cert_tx_id=cert_tx_id,
                    request_type=params.request_type,
                )
            )
        return _context_from_receipt(receipt)
    except ValidationError:
        return _mismatch("Invalid KB identity parameters.")
    except (KbIdentityClientError, ValueError) as exc:
        return _mismatch(str(exc))


def _config_from_env() -> KbIdentityConfig:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        raise KbIdentityClientError(
            "Missing KB identity configuration: " + ", ".join(missing),
            reason="missing_configuration",
        )
    return KbIdentityConfig(
        base_url=os.environ["UMMAYA_KBCERT_BASE_URL"],
        api_key=os.environ["UMMAYA_KBCERT_API_KEY"],
        hs_key=os.environ["UMMAYA_KBCERT_HS_KEY"],
        company_cd=os.environ["UMMAYA_KBCERT_COMPANY_CD"],
        request_type=os.environ.get("UMMAYA_KBCERT_REQUEST_TYPE", "NONE"),
    )


def _resolve_mode(params: KbIdentityParams) -> Literal["request", "result"]:
    if params.mode == "request":
        return "request"
    if params.mode == "result":
        return "result"
    return "result" if params.cert_tx_id else "request"


def _require_param(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise KbIdentityClientError(f"{field_name} is required.", reason="missing_field")
    return value.strip()


def _generate_req_tx_id() -> str:
    return "ummaya-" + secrets.token_urlsafe(24)


def _context_from_receipt(receipt: KbIdentityReceipt) -> KbIdentityContext:
    return KbIdentityContext(
        published_tier="kb_identity_aal2",
        nist_aal_hint="AAL2",
        verified_at=datetime.now(UTC),
        external_session_ref=(f"kbcert:reqTxId={receipt.req_tx_id};certTxId={receipt.cert_tx_id}"),
        provider="kb",
    )


def _mismatch(message: str) -> VerifyMismatchError:
    return VerifyMismatchError(
        family="mismatch_error",
        reason="family_mismatch",
        expected_family=_FAMILY,
        observed_family="kb_identity_error",
        message=message,
    )


register_verify_adapter(_FAMILY, invoke)

__all__ = ["KbIdentityParams", "invoke"]
