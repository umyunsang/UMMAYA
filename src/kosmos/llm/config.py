# SPDX-License-Identifier: Apache-2.0
"""Configuration model for the KOSMOS LLM client."""

from __future__ import annotations

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMClientConfig(BaseSettings):
    """Settings for the FriendliAI K-EXAONE LLM client.

    Environment variables (no global prefix — each field declares its own alias):
        KOSMOS_FRIENDLI_TOKEN       — required API token
        KOSMOS_FRIENDLI_BASE_URL    — API base URL
        KOSMOS_FRIENDLI_MODEL       — model identifier
        KOSMOS_LLM_SESSION_BUDGET   — per-session token budget
    """

    model_config = SettingsConfigDict(
        env_prefix="",  # each field uses an explicit validation_alias
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    token: SecretStr = Field(
        ...,
        validation_alias="KOSMOS_FRIENDLI_TOKEN",
        description="FriendliAI API token.",
    )
    base_url: AnyHttpUrl = Field(  # type: ignore[assignment]
        default="https://api.friendli.ai/serverless/v1",
        validation_alias="KOSMOS_FRIENDLI_BASE_URL",
        description="FriendliAI API base URL.",
    )
    model: str = Field(
        default="LGAI-EXAONE/K-EXAONE-236B-A23B",
        validation_alias="KOSMOS_FRIENDLI_MODEL",
        description="FriendliAI model identifier.",
    )
    session_budget: int = Field(
        # Default 1_000_000 — K-EXAONE 236B-A23B + FriendliAI Tier 1 supports
        # 1M context. KOSMOS agentic loop emits a system prompt + Available
        # tools catalog (12 tools — 5 primitives + MVP-7) + per-turn message
        # history; each turn consumes 5-15K tokens. The prior 100K budget was
        # exhausted within 2-3 turns of a real citizen scenario. Override via
        # KOSMOS_LLM_SESSION_BUDGET if a session needs further tuning.
        default=1_000_000,
        validation_alias="KOSMOS_LLM_SESSION_BUDGET",
        description="Maximum tokens allowed per session.",
    )
    timeout: float = Field(
        default=180.0,
        validation_alias="KOSMOS_LLM_TIMEOUT_SECONDS",
        description=(
            "HTTP request timeout in seconds. K-EXAONE reasoning streams can stay "
            "silent for over 60 seconds on high-effort turns."
        ),
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts on transient failures.",
    )

    @field_validator("token")
    @classmethod
    def token_must_not_be_empty(cls, value: SecretStr) -> SecretStr:
        """Reject tokens that are blank after stripping whitespace."""
        if not value.get_secret_value().strip():
            raise ValueError("KOSMOS_FRIENDLI_TOKEN must not be empty")
        return value

    @field_validator("session_budget")
    @classmethod
    def session_budget_must_be_positive(cls, value: int) -> int:
        """Enforce session_budget > 0."""
        if value <= 0:
            raise ValueError("session_budget must be > 0")
        return value

    @field_validator("timeout")
    @classmethod
    def timeout_must_be_positive(cls, value: float) -> float:
        """Enforce timeout > 0."""
        if value <= 0:
            raise ValueError("timeout must be > 0")
        return value

    @field_validator("max_retries")
    @classmethod
    def max_retries_must_be_non_negative(cls, value: int) -> int:
        """Enforce max_retries >= 0."""
        if value < 0:
            raise ValueError("max_retries must be >= 0")
        return value
