# SPDX-License-Identifier: Apache-2.0
"""Tests for the KB identity live client.

Fixtures are synthetic and sanitized; no test in this module calls KB.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ummaya.tools.live.kb_identity_client import (
    KbIdentityClient,
    KbIdentityClientError,
    KbIdentityConfig,
    sanitize_identity_payload,
)

FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "kbcert"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _config() -> KbIdentityConfig:
    return KbIdentityConfig(
        base_url="https://stg-openapi.kbstar.com:8443/",
        api_key="synthetic-api-key",
        hs_key="synthetic-hs-key",
        company_cd="TEST0000",
    )


def test_request_body_and_headers_are_constructed_without_identity_fields() -> None:
    client = KbIdentityClient(_config())

    headers = client.build_headers()
    body = client.build_request_body(req_tx_id="synthetic-req-tx-id")

    assert headers["apiKey"] == "synthetic-api-key"
    assert headers["hsKey"] == "synthetic-hs-key"
    assert headers["Content-Type"] == "application/json; charset=UTF-8"
    assert body == {
        "dataHeader": {},
        "dataBody": {
            "companyCd": "TEST0000",
            "reqTxId": "synthetic-req-tx-id",
            "requestType": "NONE",
        },
    }
    assert "CI" not in json.dumps(body)
    assert "DI" not in json.dumps(body)


def test_result_body_requires_cert_tx_id() -> None:
    client = KbIdentityClient(_config())

    with pytest.raises(KbIdentityClientError, match="certTxId is required"):
        client.build_result_body(req_tx_id="synthetic-req-tx-id", cert_tx_id="")


def test_parse_request_response_returns_sanitized_receipt() -> None:
    client = KbIdentityClient(_config())

    receipt = client.parse_request_response(
        _fixture("request_success.json"),
        expected_req_tx_id="synthetic-req-tx-id",
    )

    assert receipt.req_tx_id == "synthetic-req-tx-id"
    assert receipt.cert_tx_id == "synthetic-cert-tx-id"
    assert receipt.call_url == "https://cert.kbstar.com/quics?page=C111978"
    assert receipt.result_code == "ok"
    assert receipt.identity_evidence_present is False


def test_parse_result_response_redacts_identity_values() -> None:
    client = KbIdentityClient(_config())

    receipt = client.parse_result_response(
        _fixture("result_success.json"),
        expected_req_tx_id="synthetic-req-tx-id",
        expected_cert_tx_id="synthetic-cert-tx-id",
    )
    dumped = receipt.model_dump_json()

    assert receipt.identity_evidence_present is True
    assert receipt.req_tx_id == "synthetic-req-tx-id"
    assert receipt.cert_tx_id == "synthetic-cert-tx-id"
    for sentinel in (
        "SENTINEL_CI_SHOULD_NOT_LEAK",
        "SENTINEL_DI_SHOULD_NOT_LEAK",
        "SENTINEL_USER_NAME_SHOULD_NOT_LEAK",
        "SENTINEL_BIRTHDAY_SHOULD_NOT_LEAK",
        "SENTINEL_GENDER_SHOULD_NOT_LEAK",
        "SENTINEL_NATIONALITY_SHOULD_NOT_LEAK",
    ):
        assert sentinel not in dumped


def test_failed_status_raises_sanitized_error() -> None:
    client = KbIdentityClient(_config())

    with pytest.raises(KbIdentityClientError) as exc_info:
        client.parse_result_response(
            _fixture("result_failed.json"),
            expected_req_tx_id="synthetic-req-tx-id",
            expected_cert_tx_id="synthetic-cert-tx-id",
        )

    message = str(exc_info.value)
    assert "KB identity response failed" in message
    assert "SENTINEL_CI_SHOULD_NOT_LEAK" not in message


def test_mismatched_req_tx_id_raises_fail_closed() -> None:
    client = KbIdentityClient(_config())

    with pytest.raises(KbIdentityClientError, match="reqTxId mismatch"):
        client.parse_result_response(
            _fixture("result_mismatch.json"),
            expected_req_tx_id="synthetic-req-tx-id",
            expected_cert_tx_id="synthetic-cert-tx-id",
        )


def test_sanitize_identity_payload_recursively_drops_forbidden_keys() -> None:
    payload = {
        "outer": {
            "CI": "SENTINEL_CI_SHOULD_NOT_LEAK",
            "safe": "kept",
            "nested": [{"DI": "SENTINEL_DI_SHOULD_NOT_LEAK", "status": "ok"}],
        }
    }

    sanitized = sanitize_identity_payload(payload)
    dumped = json.dumps(sanitized)

    assert "SENTINEL_CI_SHOULD_NOT_LEAK" not in dumped
    assert "SENTINEL_DI_SHOULD_NOT_LEAK" not in dumped
    assert sanitized == {"outer": {"safe": "kept", "nested": [{"status": "ok"}]}}


@pytest.mark.asyncio
async def test_upstream_non_2xx_raises_sanitized_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"CI": "SENTINEL_CI_SHOULD_NOT_LEAK"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = KbIdentityClient(_config(), http_client=http_client)
        with pytest.raises(KbIdentityClientError) as exc_info:
            await client.request_identity(req_tx_id="synthetic-req-tx-id")

    assert "upstream HTTP 503" in str(exc_info.value)
    assert "SENTINEL_CI_SHOULD_NOT_LEAK" not in str(exc_info.value)
