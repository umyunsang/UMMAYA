# SPDX-License-Identifier: Apache-2.0
"""K-EXAONE/FriendliAI reasoning payload policy."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ReasoningMode = Literal["fast", "balanced", "deep", "diagnostic", "auto"]
ReasoningModeSource = Literal["env", "session", "legacy-env", "default"]

_MODES: set[str] = {"fast", "balanced", "deep", "diagnostic", "auto"}


@dataclass(frozen=True)
class ResolvedReasoningPolicy:
    """Provider-facing reasoning policy for one request."""

    mode: ReasoningMode
    source: ReasoningModeSource
    enable_thinking: bool
    parse_reasoning: bool
    include_reasoning: bool
    persist_thinking: bool = False


def parse_reasoning_mode(value: object) -> ReasoningMode | None:
    """Return a valid reasoning mode from an untrusted value."""
    if value is None:
        return None
    normalized = str(value).lower()
    if normalized in _MODES:
        return normalized  # type: ignore[return-value]
    return None


def resolve_reasoning_policy(
    reasoning_mode: ReasoningMode | str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> ResolvedReasoningPolicy:
    """Resolve request, settings, and env state into FriendliAI payload fields."""
    effective_env = os.environ if env is None else env
    env_mode = parse_reasoning_mode(effective_env.get("UMMAYA_K_EXAONE_REASONING_MODE"))
    if env_mode is not None:
        return _policy_for(env_mode, "env")

    explicit_mode = parse_reasoning_mode(reasoning_mode)
    if explicit_mode is not None:
        return _policy_for(explicit_mode, "session")

    legacy_mode = _legacy_thinking_mode(effective_env)
    if legacy_mode is not None:
        return _policy_for(legacy_mode, "legacy-env")

    return _policy_for("balanced", "default")


def _legacy_thinking_mode(env: Mapping[str, str]) -> ReasoningMode | None:
    raw = env.get("UMMAYA_K_EXAONE_THINKING")
    if raw is None:
        return None
    normalized = raw.lower()
    if normalized in {"1", "true", "yes"}:
        return "deep"
    if normalized in {"0", "false", "no"}:
        return "fast"
    return None


def _policy_for(
    mode: ReasoningMode,
    source: ReasoningModeSource,
) -> ResolvedReasoningPolicy:
    enable_thinking = mode in {"deep", "diagnostic"}
    return ResolvedReasoningPolicy(
        mode=mode,
        source=source,
        enable_thinking=enable_thinking,
        parse_reasoning=True,
        include_reasoning=enable_thinking,
    )
