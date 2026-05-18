# SPDX-License-Identifier: Apache-2.0
"""Tests for the live KB identity check adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ummaya.tools.live.verify_kb_identity as kb_adapter
import ummaya.tools.mock  # noqa: F401
from ummaya.primitives.verify import (
    GanpyeonInjeungContext,
    KbIdentityContext,
    VerifyMismatchError,
    verify,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.verify_canonical_map import resolve_family

FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "kbcert"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _env() -> dict[str, str]:
    return {
        "UMMAYA_KBCERT_BASE_URL": "https://stg-openapi.kbstar.com:8443/",
        "UMMAYA_KBCERT_API_KEY": "synthetic-api-key",
        "UMMAYA_KBCERT_HS_KEY": "synthetic-hs-key",
        "UMMAYA_KBCERT_COMPANY_CD": "TEST0000",
    }


@pytest.mark.asyncio
async def test_request_mode_returns_kb_identity_context(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _env().items():
        monkeypatch.setenv(key, value)

    result = await kb_adapter.invoke(
        {
            "mode": "request",
            "reqTxId": "synthetic-req-tx-id",
            "_fixture_response": _fixture("request_success.json"),
        }
    )

    assert isinstance(result, KbIdentityContext)
    assert result.family == "kb_identity"
    assert result.provider == "kb"
    assert result.external_session_ref == (
        "kbcert:reqTxId=synthetic-req-tx-id;certTxId=synthetic-cert-tx-id"
    )


@pytest.mark.asyncio
async def test_result_mode_redacts_identity_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _env().items():
        monkeypatch.setenv(key, value)

    result = await kb_adapter.invoke(
        {
            "mode": "result",
            "reqTxId": "synthetic-req-tx-id",
            "certTxId": "synthetic-cert-tx-id",
            "_fixture_response": _fixture("result_success.json"),
        }
    )
    dumped = result.model_dump_json() if hasattr(result, "model_dump_json") else str(result)

    assert isinstance(result, KbIdentityContext)
    assert "SENTINEL_CI_SHOULD_NOT_LEAK" not in dumped
    assert "SENTINEL_DI_SHOULD_NOT_LEAK" not in dumped
    assert "SENTINEL_USER_NAME_SHOULD_NOT_LEAK" not in dumped


@pytest.mark.asyncio
async def test_missing_credentials_returns_sanitized_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in _env():
        monkeypatch.delenv(key, raising=False)

    result = await kb_adapter.invoke({"mode": "request", "reqTxId": "synthetic-req-tx-id"})

    assert isinstance(result, VerifyMismatchError)
    assert result.expected_family == "kb_identity"
    assert "UMMAYA_KBCERT_API_KEY" in result.message


@pytest.mark.asyncio
async def test_validation_errors_do_not_echo_identity_payload() -> None:
    result = await kb_adapter.invoke(
        {
            "mode": "request",
            "_fixture_response": [{"CI": "SENTINEL_CI_SHOULD_NOT_LEAK"}],
        }
    )

    assert isinstance(result, VerifyMismatchError)
    assert result.message == "Invalid KB identity parameters."
    assert "SENTINEL_CI_SHOULD_NOT_LEAK" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_verify_dispatch_supports_kb_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _env().items():
        monkeypatch.setenv(key, value)

    result = await verify(
        "kb_identity",
        {
            "mode": "request",
            "reqTxId": "synthetic-req-tx-id",
            "_fixture_response": _fixture("request_success.json"),
        },
    )

    assert isinstance(result, KbIdentityContext)


def test_live_kb_tool_is_discoverable_under_check() -> None:
    registry = ToolRegistry()
    executor = ToolExecutor(registry=registry)
    register_all_tools(registry, executor)

    tool = registry.find("live_verify_kb_identity")

    assert tool.primitive == "check"
    assert tool.adapter_mode == "live"
    assert tool.is_core is False
    assert resolve_family("live_verify_kb_identity") == "kb_identity"


@pytest.mark.asyncio
async def test_existing_ganpyeon_mock_remains_unchanged() -> None:
    result = await verify("ganpyeon_injeung", {})

    assert isinstance(result, GanpyeonInjeungContext)
    assert result.provider == "kakao"
    assert result.external_session_ref == "mock-ganpyeon-ref-001"
