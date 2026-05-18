# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the live MobileID check adapter."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ummaya.primitives.verify import MobileIdContext
from ummaya.tools.live.mobileid_client import MobileIdUpstreamError, MobileIdVerificationError
from ummaya.tools.live.verify_mobile_id import (
    LiveMobileIdCheckInput,
    LiveMobileIdVpInput,
    handle_live_mobile_id_check,
)


class _FakeMobileIdClient:
    def __init__(
        self,
        *,
        vp_result: dict[str, object] | None = None,
        status_result: dict[str, object] | None = None,
    ) -> None:
        self.vp_result = vp_result or {"result": True, "status": "VERIFIED"}
        self.status_result = status_result or {"result": True, "status": "COMPLETED"}
        self.vp_calls: list[dict[str, object]] = []
        self.status_calls: list[str] = []

    async def verify_vp(
        self,
        *,
        trxcode: str,
        vp: LiveMobileIdVpInput,
    ) -> dict[str, object]:
        self.vp_calls.append({"trxcode": trxcode, "vp": vp.model_dump()})
        return self.vp_result

    async def transaction_status(self, trxcode: str) -> dict[str, object]:
        self.status_calls.append(trxcode)
        return self.status_result


def _vp() -> LiveMobileIdVpInput:
    return LiveMobileIdVpInput(
        presentType="VP",
        encryptType="AES",
        keyType="RSA",
        authType="PIN",
        did="did:example:safe",
        nonce="NONCE-SAFE",
        type="verify",
        data="RAW-VP-SHOULD-NOT-LEAK",
    )


@pytest.mark.asyncio
async def test_live_mobileid_check_returns_mobileid_context() -> None:
    client = _FakeMobileIdClient()
    output = await handle_live_mobile_id_check(
        LiveMobileIdCheckInput(trxcode="TRX-SAFE-001", id_type="mdl", vp=_vp()),
        client=client,
    )

    assert isinstance(output, MobileIdContext)
    assert output.family == "mobile_id"
    assert output.published_tier == "mobile_id_mdl_aal2"
    assert output.nist_aal_hint == "AAL2"
    assert output.id_type == "mdl"
    assert output.external_session_ref == "mobileid:TRX-SAFE-001"
    assert client.status_calls == ["TRX-SAFE-001"]
    assert len(client.vp_calls) == 1


@pytest.mark.asyncio
async def test_live_mobileid_check_resident_id_type_uses_resident_tier() -> None:
    output = await handle_live_mobile_id_check(
        LiveMobileIdCheckInput(trxcode="TRX-SAFE-002", id_type="resident"),
        client=_FakeMobileIdClient(status_result={"result": True, "credentialType": "resident"}),
    )

    assert output.id_type == "resident"
    assert output.published_tier == "mobile_id_resident_aal2"


@pytest.mark.asyncio
async def test_live_mobileid_check_resident_requires_upstream_evidence() -> None:
    with pytest.raises(MobileIdVerificationError):
        await handle_live_mobile_id_check(
            LiveMobileIdCheckInput(trxcode="TRX-SAFE-002", id_type="resident"),
            client=_FakeMobileIdClient(),
        )


@pytest.mark.asyncio
async def test_live_mobileid_check_fails_closed_on_id_type_mismatch() -> None:
    with pytest.raises(MobileIdVerificationError):
        await handle_live_mobile_id_check(
            LiveMobileIdCheckInput(trxcode="TRX-SAFE-002", id_type="resident"),
            client=_FakeMobileIdClient(
                status_result={"result": True, "credentialType": "mobile_driver_license"}
            ),
        )


@pytest.mark.asyncio
async def test_live_mobileid_check_accepts_nested_mdl_evidence() -> None:
    output = await handle_live_mobile_id_check(
        LiveMobileIdCheckInput(trxcode="TRX-SAFE-002", id_type="mdl"),
        client=_FakeMobileIdClient(
            status_result={
                "result": True,
                "credential": {"type": ["VerifiableCredential", "MobileDriverLicenseCredential"]},
            }
        ),
    )

    assert output.id_type == "mdl"
    assert output.published_tier == "mobile_id_mdl_aal2"


@pytest.mark.asyncio
async def test_live_mobileid_check_output_never_contains_raw_identity_fields() -> None:
    client = _FakeMobileIdClient(
        vp_result={
            "result": True,
            "status": "VERIFIED",
            "ci": "CI-SHOULD-NOT-LEAK",
            "data": "RAW-VP-SHOULD-NOT-LEAK",
        },
        status_result={
            "result": True,
            "status": "COMPLETED",
            "di": "DI-SHOULD-NOT-LEAK",
            "phoneNumber": "PHONE-SHOULD-NOT-LEAK",
            "name": "NAME-SHOULD-NOT-LEAK",
            "birthDate": "BIRTHDATE-SHOULD-NOT-LEAK",
        },
    )

    output = await handle_live_mobile_id_check(
        LiveMobileIdCheckInput(trxcode="TRX-SAFE-003", vp=_vp()),
        client=client,
    )

    serialized = json.dumps(output.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    assert "mobileid:TRX-SAFE-003" in serialized
    assert "CI-SHOULD-NOT-LEAK" not in serialized
    assert "DI-SHOULD-NOT-LEAK" not in serialized
    assert "RAW-VP-SHOULD-NOT-LEAK" not in serialized
    assert "PHONE-SHOULD-NOT-LEAK" not in serialized
    assert "NAME-SHOULD-NOT-LEAK" not in serialized
    assert "BIRTHDATE-SHOULD-NOT-LEAK" not in serialized


def test_live_mobileid_check_requires_non_blank_trxcode() -> None:
    with pytest.raises(ValidationError):
        LiveMobileIdCheckInput(trxcode="   ")


def test_live_mobileid_vp_requires_nonce_or_zkp_nonce() -> None:
    with pytest.raises(ValidationError):
        LiveMobileIdVpInput(
            presentType="VP",
            encryptType="AES",
            keyType="RSA",
            authType="PIN",
            did="did:example:safe",
            type="verify",
            data="RAW-VP-SHOULD-NOT-LEAK",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_result",
    [
        {"result": False, "status": "COMPLETED"},
        {"result": True, "status": "EXPIRED"},
        {"result": True, "status": "CANCELLED"},
        {"result": True, "status": "WAITING"},
    ],
)
async def test_live_mobileid_check_fails_closed_on_bad_status(
    status_result: dict[str, object],
) -> None:
    with pytest.raises(MobileIdVerificationError):
        await handle_live_mobile_id_check(
            LiveMobileIdCheckInput(trxcode="TRX-SAFE-004"),
            client=_FakeMobileIdClient(status_result=status_result),
        )


@pytest.mark.asyncio
async def test_live_mobileid_check_does_not_swallow_upstream_error() -> None:
    class _FailingClient(_FakeMobileIdClient):
        async def transaction_status(self, trxcode: str) -> dict[str, object]:
            raise MobileIdUpstreamError("upstream unavailable")

    with pytest.raises(MobileIdUpstreamError):
        await handle_live_mobile_id_check(
            LiveMobileIdCheckInput(trxcode="TRX-SAFE-005"),
            client=_FailingClient(),
        )
