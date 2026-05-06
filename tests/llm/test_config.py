# SPDX-License-Identifier: Apache-2.0
"""Unit tests for LLMClientConfig loading from environment variables."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from kosmos.llm.config import LLMClientConfig


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all KOSMOS_* env vars to ensure a clean state for every test."""
    for key in list(os.environ):
        if key.startswith("KOSMOS_"):
            monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Required field — missing token
# ---------------------------------------------------------------------------


def test_missing_token_raises_error() -> None:
    """No KOSMOS_FRIENDLI_TOKEN in environment raises ValidationError."""
    with pytest.raises(ValidationError):
        LLMClientConfig()


# ---------------------------------------------------------------------------
# Token loading
# ---------------------------------------------------------------------------


def test_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """KOSMOS_FRIENDLI_TOKEN is surfaced as the secret value."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert config.token.get_secret_value() == "test-token-123"


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


def test_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """base_url defaults to the FriendliAI v1 endpoint."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert str(config.base_url) == "https://api.friendli.ai/serverless/v1"


def test_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """model defaults to the canonical K-EXAONE deployment identifier."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert config.model == "LGAI-EXAONE/K-EXAONE-236B-A23B"


def test_default_session_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """session_budget defaults to 1 000 000 tokens (Epic #2077 — K-EXAONE 1M context)."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert config.session_budget == 1_000_000


def test_default_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """timeout defaults to 180.0 seconds for K-EXAONE high-effort streams."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert config.timeout == 180.0


def test_default_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """max_retries defaults to 3."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    config = LLMClientConfig()
    assert config.max_retries == 3


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


def test_override_base_url_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """KOSMOS_FRIENDLI_BASE_URL overrides the default base_url."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    monkeypatch.setenv("KOSMOS_FRIENDLI_BASE_URL", "https://custom.example.com/v2")
    config = LLMClientConfig()
    assert str(config.base_url) == "https://custom.example.com/v2"


def test_override_model_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """KOSMOS_FRIENDLI_MODEL overrides the default model identifier."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    monkeypatch.setenv("KOSMOS_FRIENDLI_MODEL", "dep-custom-model-abc")
    config = LLMClientConfig()
    assert config.model == "dep-custom-model-abc"


def test_override_session_budget_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """KOSMOS_LLM_SESSION_BUDGET overrides the default session_budget."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    monkeypatch.setenv("KOSMOS_LLM_SESSION_BUDGET", "50000")
    config = LLMClientConfig()
    assert config.session_budget == 50000


def test_override_timeout_via_kosmos_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """KOSMOS_LLM_TIMEOUT_SECONDS overrides the default HTTP timeout."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    monkeypatch.setenv("KOSMOS_LLM_TIMEOUT_SECONDS", "240")
    config = LLMClientConfig()
    assert config.timeout == 240.0


# ---------------------------------------------------------------------------
# Validation errors — invalid field values
# ---------------------------------------------------------------------------


def test_invalid_session_budget_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """session_budget of 0 is rejected with ValidationError."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    monkeypatch.setenv("KOSMOS_LLM_SESSION_BUDGET", "0")
    with pytest.raises(ValidationError):
        LLMClientConfig()


def test_invalid_timeout_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    """A negative timeout is rejected with ValidationError."""
    monkeypatch.setenv("KOSMOS_FRIENDLI_TOKEN", "test-token-123")
    with pytest.raises(ValidationError):
        LLMClientConfig(timeout=-1)
