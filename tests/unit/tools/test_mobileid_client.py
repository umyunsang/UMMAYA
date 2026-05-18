# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the MobileID verification-daemon client boundary."""

from __future__ import annotations

import json

import httpx
import pytest

from ummaya.tools.live.mobileid_client import (
    MobileIdClient,
    MobileIdEnvelopeError,
    MobileIdUpstreamError,
    decode_mip_envelope,
    encode_mip_envelope,
    redact_mobileid_identity_fields,
)


def test_mip_envelope_round_trips_inner_json() -> None:
    inner = {
        "type": "mip",
        "version": "1.0.0",
        "cmd": 400,
        "request": "presentation",
        "trxcode": "TRX-SAFE-001",
    }

    envelope = encode_mip_envelope(inner)

    assert sorted(envelope) == ["data"]
    assert decode_mip_envelope(envelope) == inner


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": ""},
        {"data": "not-base64"},
        {"data": "W10="},  # [] is valid JSON but not the daemon object contract.
    ],
)
def test_mip_envelope_decode_rejects_malformed_payload(payload: object) -> None:
    with pytest.raises(MobileIdEnvelopeError):
        decode_mip_envelope(payload)


def test_redact_mobileid_identity_fields_recursively() -> None:
    redacted = redact_mobileid_identity_fields(
        {
            "trxcode": "TRX-SAFE-001",
            "ci": "CI-SHOULD-NOT-LEAK",
            "nested": {
                "data": "RAW-VP-SHOULD-NOT-LEAK",
                "phoneNumber": "PHONE-SHOULD-NOT-LEAK",
                "name": "NAME-SHOULD-NOT-LEAK",
            },
            "items": [{"di": "DI-SHOULD-NOT-LEAK"}, {"status": "COMPLETED"}],
        }
    )

    serialized = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
    assert "TRX-SAFE-001" in serialized
    assert "COMPLETED" in serialized
    assert "CI-SHOULD-NOT-LEAK" not in serialized
    assert "DI-SHOULD-NOT-LEAK" not in serialized
    assert "RAW-VP-SHOULD-NOT-LEAK" not in serialized
    assert "PHONE-SHOULD-NOT-LEAK" not in serialized
    assert "NAME-SHOULD-NOT-LEAK" not in serialized
    assert "REDACTED" in serialized


@pytest.mark.asyncio
async def test_post_envelope_uses_mobileid_content_type_and_decodes_response() -> None:
    seen: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/mip/trxsts"
        assert request.headers["content-type"] == "application/json; charset=utf-8"
        assert request.headers["x-mobileid-client-id"] == "client-safe"
        outer = json.loads(request.content.decode("utf-8"))
        seen.append(decode_mip_envelope(outer))
        return httpx.Response(
            200,
            json=encode_mip_envelope(
                {
                    "result": True,
                    "trxcode": "TRX-SAFE-001",
                    "status": "COMPLETED",
                }
            ),
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mobileid.example.test",
    ) as http_client:
        client = MobileIdClient(
            base_url="https://mobileid.example.test",
            client_id="client-safe",
            http_client=http_client,
        )
        decoded = await client.post_envelope("/mip/trxsts", {"trxcode": "TRX-SAFE-001"})

    assert seen == [{"trxcode": "TRX-SAFE-001"}]
    assert decoded["result"] is True
    assert decoded["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_post_envelope_redacts_upstream_non_2xx_message() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502,
            text='{"ci":"CI-SHOULD-NOT-LEAK","data":"RAW-VP-SHOULD-NOT-LEAK"}',
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mobileid.example.test",
    ) as http_client:
        client = MobileIdClient(
            base_url="https://mobileid.example.test",
            client_id="client-safe",
            http_client=http_client,
        )

        with pytest.raises(MobileIdUpstreamError) as exc_info:
            await client.post_envelope("/mip/trxsts", {"trxcode": "TRX-SAFE-001"})

    message = str(exc_info.value)
    assert "502" in message
    assert "CI-SHOULD-NOT-LEAK" not in message
    assert "RAW-VP-SHOULD-NOT-LEAK" not in message
