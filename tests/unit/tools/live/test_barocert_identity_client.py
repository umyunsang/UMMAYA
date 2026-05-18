# SPDX-License-Identifier: Apache-2.0
"""Tests for the live BaroCert identity client boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ummaya.tools.live.barocert_identity_client import (
    BarocertIdentityRequest,
    BarocertProvider,
    BarocertProviderError,
    parse_identity_receipt,
    parse_identity_status,
    parse_identity_verification,
    provider_metadata,
    redact_barocert_payload,
)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "barocert"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_provider_metadata_covers_toss_kakao_naver() -> None:
    assert {provider.value for provider in BarocertProvider} == {"toss", "kakao", "naver"}

    assert provider_metadata(BarocertProvider.toss).request_method == "requestUserIdentity"
    assert provider_metadata("toss").status_method == "getUserIdentityStatus"
    assert provider_metadata("toss").verify_method == "verifyUserIdentity"

    assert provider_metadata("kakao").request_method == "requestIdentity"
    assert provider_metadata("naver").verify_method == "verifyIdentity"


def test_identity_request_requires_encrypted_placeholders() -> None:
    request = BarocertIdentityRequest(
        provider="toss",
        client_code="TESTCLIENT01",
        receiver_hp_encrypted="ENCRYPTED_HP_PLACEHOLDER",
        receiver_name_encrypted="ENCRYPTED_NAME_PLACEHOLDER",
        receiver_birthday_encrypted="ENCRYPTED_BIRTHDAY_PLACEHOLDER",
        token="ENCRYPTED_TOKEN_PLACEHOLDER",
        expire_in=300,
        app_use_yn=True,
        device_os_type="IOS",
        return_url="ummaya://barocert/callback",
    )

    assert request.to_user_identity_payload() == {
        "receiverHP": "ENCRYPTED_HP_PLACEHOLDER",
        "receiverName": "ENCRYPTED_NAME_PLACEHOLDER",
        "receiverBirthday": "ENCRYPTED_BIRTHDAY_PLACEHOLDER",
        "token": "ENCRYPTED_TOKEN_PLACEHOLDER",
        "expireIn": 300,
        "appUseYN": True,
        "deviceOSType": "IOS",
        "returnURL": "ummaya://barocert/callback",
    }

    with pytest.raises(ValidationError):
        BarocertIdentityRequest(
            provider="toss",
            client_code="TESTCLIENT01",
            receiver_hp_encrypted="ENCRYPTED_HP_PLACEHOLDER",
            receiver_name_encrypted="ENCRYPTED_NAME_PLACEHOLDER",
            receiver_birthday_encrypted="ENCRYPTED_BIRTHDAY_PLACEHOLDER",
            token="",
        )


def test_redaction_removes_identity_fields_recursively() -> None:
    redacted = redact_barocert_payload(
        {
            "receiptID": "TOSS_RECEIPT_SANITIZED_001",
            "ci": "SYNTHETIC_CI_PLACEHOLDER",
            "di": "SYNTHETIC_DI_PLACEHOLDER",
            "signedData": "SYNTHETIC_SIGNED_DATA_PLACEHOLDER",
            "receiverHP": "ENCRYPTED_HP_PLACEHOLDER",
            "nested": [{"receiverName": "ENCRYPTED_NAME_PLACEHOLDER", "safe": "keep"}],
        }
    )

    assert redacted["receiptID"] == "TOSS_RECEIPT_SANITIZED_001"
    assert redacted["ci"] == "<redacted>"
    assert redacted["di"] == "<redacted>"
    assert redacted["signedData"] == "<redacted>"
    assert redacted["receiverHP"] == "<redacted>"
    assert redacted["nested"] == [{"receiverName": "<redacted>", "safe": "keep"}]


def test_toss_receipt_status_and_verify_fixture_parsing() -> None:
    receipt = parse_identity_receipt("toss", _fixture("toss_request_receipt.json"))
    assert receipt.provider == BarocertProvider.toss
    assert receipt.receipt_id == "TOSS_RECEIPT_SANITIZED_001"

    status = parse_identity_status(
        "toss",
        receipt.receipt_id,
        _fixture("toss_status_complete.json"),
    )
    assert status.state == "complete"
    assert status.is_complete is True

    verification = parse_identity_verification(
        "toss",
        receipt.receipt_id,
        _fixture("toss_verify_complete.json"),
    )
    assert verification.identity_evidence_present is True
    assert verification.signed_data_present is True
    dumped = verification.model_dump()
    assert "SYNTHETIC_CI_PLACEHOLDER" not in str(dumped)
    assert "SYNTHETIC_DI_PLACEHOLDER" not in str(dumped)
    assert "SYNTHETIC_SIGNED_DATA_PLACEHOLDER" not in str(dumped)


@pytest.mark.parametrize("provider", ["toss", "kakao", "naver"])
def test_provider_status_fixture_variants_parse(provider: str) -> None:
    fixture_name = f"{provider}_status_complete.json"
    receipt_id = f"{provider.upper()}_RECEIPT_SANITIZED_001"

    status = parse_identity_status(provider, receipt_id, _fixture(fixture_name))

    assert status.provider.value == provider
    assert status.receipt_id == receipt_id
    assert status.is_complete is True


def test_negative_provider_states_fail_closed() -> None:
    with pytest.raises(BarocertProviderError, match="missing_receipt_id"):
        parse_identity_receipt("toss", {"scheme": "barocert-toss://identity/SANITIZED"})

    with pytest.raises(BarocertProviderError, match="expired"):
        parse_identity_status(
            "toss",
            "TOSS_RECEIPT_SANITIZED_001",
            _fixture("toss_status_expired.json"),
        )

    with pytest.raises(BarocertProviderError, match="provider_mismatch"):
        parse_identity_verification(
            "toss",
            "TOSS_RECEIPT_SANITIZED_001",
            {"provider": "kakao", "receiptID": "TOSS_RECEIPT_SANITIZED_001", "state": 1},
        )

    with pytest.raises(BarocertProviderError, match="upstream_error"):
        parse_identity_verification(
            "toss",
            "TOSS_RECEIPT_SANITIZED_001",
            _fixture("toss_verify_repeated.json"),
        )
