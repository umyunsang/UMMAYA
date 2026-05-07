# SPDX-License-Identifier: Apache-2.0
"""TUI operational configuration loaded from KOSMOS_TUI_* environment variables.

All four variables are non-secret operational knobs with safe defaults.  They
are registered here — not in guard.py — because the startup guard only enforces
*required* secrets.  The presence of this module ensures the #468 audit-env-registry
script (`scripts/audit-env-registry.py`) treats every ``KOSMOS_TUI_*`` reference
found in ``src/`` as registered and does not flag them as unregistered leaked values.

Usage::

    from kosmos.config.env_registry import tui_settings
    theme = tui_settings.theme
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TUISettings(BaseSettings):
    """Runtime configuration for the KOSMOS TUI (Ink + React + Bun) layer.

    All fields are configurable via environment variables prefixed with
    ``KOSMOS_TUI_``.  For example, ``KOSMOS_TUI_THEME=dark`` activates the dark
    colour palette.  None of these fields are secrets; the startup guard does not
    enforce them.
    """

    model_config = SettingsConfigDict(
        env_prefix="KOSMOS_TUI_",
        env_file=".env",
        extra="ignore",
    )

    theme: Literal["default", "dark", "light"] = Field(
        default="default",
        description=(
            "Colour-palette selector consumed by tui/src/theme/provider.tsx (T022). "
            "Valid values: default | dark | light."
        ),
    )
    """Active theme for the Ink terminal UI (KOSMOS_TUI_THEME)."""

    log_level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = Field(
        default="WARN",
        description=(
            "IPC frame logging threshold consumed by tui/src/ipc/bridge.ts (T040). "
            "Valid values: DEBUG | INFO | WARN | ERROR."
        ),
    )
    """Log verbosity for IPC bridge frames (KOSMOS_TUI_LOG_LEVEL)."""

    ime_strategy: Literal["fork", "readline"] = Field(
        default="fork",
        description=(
            "Korean IME handling strategy consumed by tui/src/hooks/useKoreanIME.ts "
            "(T104).  Chosen by ADR-005.  Valid values: fork | readline."
        ),
    )
    """Korean IME input strategy (KOSMOS_TUI_IME_STRATEGY)."""

    soak_events_per_sec: int = Field(
        default=100,
        ge=1,
        description=(
            "Event rate for the 10-minute soak test (tui/tests/ipc/soak.test.ts, T028). "
            "Must be >= 1.  Production code MUST NOT read this variable."
        ),
    )
    """Soak-test IPC event rate in events/second (KOSMOS_TUI_SOAK_EVENTS_PER_SEC)."""


tui_settings: TUISettings = TUISettings()
"""Module-level singleton.  Import this directly in production TUI bootstrap code."""
