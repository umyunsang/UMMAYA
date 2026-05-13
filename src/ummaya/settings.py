# SPDX-License-Identifier: Apache-2.0
"""Centralised pydantic-settings configuration for UMMAYA.

All runtime configuration is read from ``UMMAYA_``-prefixed environment
variables (FR-032, FR-033, FR-034).  Defaults are fail-closed: empty strings
for secrets, conservative integers for rate/freshness windows.

Usage::

    from ummaya.settings import settings
    key = settings.ummaya_kakao_api_key
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ummaya.safety._settings import SafetySettings


class UmmayaSettings(BaseSettings):
    """UMMAYA runtime configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="UMMAYA_",
        env_file=".env",
        extra="ignore",
    )

    # --- Retrieval gate (FR-033) ---
    lookup_topk: int = Field(default=5, ge=1, le=20)
    """Default top-k for lookup(mode='search'). Clamped to [1, 20]."""

    # --- NMC freshness SLO (FR-034; enforcement deferred to follow-on epic) ---
    nmc_freshness_minutes: int = Field(default=30, ge=1, le=1440)
    """Max acceptable age of NMC hvidate field in minutes."""

    # --- External API keys (FR-032) ---
    kakao_api_key: str = Field(default="")
    """Kakao REST API key (UMMAYA_KAKAO_API_KEY)."""

    juso_confm_key: str = Field(default="")
    """행정안전부 도로명주소 확인키 (UMMAYA_JUSO_CONFM_KEY)."""

    sgis_key: str = Field(default="")
    """SGIS API consumer key (UMMAYA_SGIS_KEY)."""

    sgis_secret: str = Field(default="")
    """SGIS API consumer secret (UMMAYA_SGIS_SECRET)."""

    data_go_kr_api_key: str = Field(default="")
    """공공데이터포털 통합 API 키, shared by KOROAD / KMA / HIRA / NMC / NFA / MOHW."""

    # --- Live adapter gateway (release CLI path) ---
    live_adapter_mode: Literal["auto", "proxy", "direct"] = Field(default="auto")
    """Live adapter route (UMMAYA_LIVE_ADAPTER_MODE).

    ``auto`` routes packaged CLI executions through the operator-managed proxy
    and source-tree executions through direct local adapters. ``proxy`` forces
    the gateway route; ``direct`` forces the legacy local-env route.
    """

    live_adapter_proxy_url: str = Field(
        default="https://ummaya-live-gateway-ygjh3ipzqq-du.a.run.app/v1/adapters"
    )
    """Operator-managed live adapter gateway base URL.

    Public release users should not need Kakao/data.go.kr credentials locally;
    the gateway keeps those operator credentials server-side.
    """

    live_adapter_proxy_timeout_seconds: float = Field(default=30.0, gt=0)
    """HTTP timeout for operator-managed live adapter proxy calls."""

    live_adapter_proxy_token: str = Field(default="")
    """Optional bearer token for private/self-hosted live adapter gateways."""

    live_adapter_gateway_token: str = Field(default="")
    """Optional bearer token required by the hosted live adapter gateway server."""

    live_adapter_gateway_rate_limit_per_minute: int = Field(default=120, ge=1, le=10_000)
    """Per-client, per-tool request limit enforced by the hosted gateway."""

    live_adapter_gateway_max_body_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)
    """Maximum live adapter gateway request body size in bytes."""

    # --- Safety pipeline (Epic #466) ---
    safety: SafetySettings = Field(default_factory=SafetySettings)
    """Four-layer safety pipeline configuration (UMMAYA_SAFETY_* env vars)."""

    # --- Agent Swarm (Epic #13) ---
    agent_mailbox_root: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "mailbox",
    )
    """Root directory for FileMailbox (UMMAYA_AGENT_MAILBOX_ROOT).

    MUST be an absolute path. Relative paths are rejected at validation time.
    Default: ~/.ummaya/mailbox
    """

    agent_mailbox_max_messages: int = Field(default=1000, ge=100, le=10_000)
    """Per-session message cap (UMMAYA_AGENT_MAILBOX_MAX_MESSAGES).

    Clamped to [100, 10000]. Default: 1000.
    """

    agent_max_workers: int = Field(default=4, ge=1, le=16)
    """Max concurrent workers per coordinator session (UMMAYA_AGENT_MAX_WORKERS).

    Clamped to [1, 16]. Default: 4.
    """

    agent_worker_timeout_seconds: int = Field(default=120, ge=10, le=600)
    """Worker timeout before coordinator cancels (UMMAYA_AGENT_WORKER_TIMEOUT_SECONDS).

    A worker that does not post a result or error message within this timeout
    is cancelled by the coordinator and treated as an error.
    Clamped to [10, 600]. Default: 120.
    """

    @field_validator("agent_mailbox_root", mode="after")
    @classmethod
    def _agent_mailbox_root_must_be_absolute(cls, v: Path) -> Path:
        """Reject relative paths for agent_mailbox_root (FR-032)."""
        if not v.is_absolute():
            raise ValueError(f"agent_mailbox_root must be an absolute path, got: {v!r}")
        return v

    # --- Permission v2 (Spec 033, Epic #1297) ---
    permission_timeout_sec: int = Field(default=30, ge=1, le=300)
    """Consent prompt timeout in seconds (UMMAYA_PERMISSION_TIMEOUT_SEC).

    The citizen has this many seconds to respond to a PIPA consent prompt
    before the pipeline times out and falls back to ``deny``.
    Clamped to [1, 300]. Default: 30.
    """

    permission_ttl_session_sec: int = Field(default=3600, ge=60, le=86400)
    """Session-scoped permission rule TTL in seconds (UMMAYA_PERMISSION_TTL_SESSION_SEC).

    Session-scoped ``allow`` rules expire after this many seconds regardless
    of process lifetime.  Clamped to [60, 86400] (1 min to 24 hours).
    Default: 3600 (1 hour).
    """

    permission_key_path: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "keys" / "ledger.key",
    )
    """Path to the HMAC key file (UMMAYA_PERMISSION_KEY_PATH).

    Must be an absolute path.  File is created with mode ``0o400`` on first boot
    via ``hmac_key.load_or_generate_key()``.  If the file exists with wrong mode,
    ledger operations fail closed (Invariant C3).
    Default: ``~/.ummaya/keys/ledger.key``.
    """

    permission_key_registry_path: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "keys" / "registry.json",
    )
    """Path to the HMAC key rotation registry (UMMAYA_PERMISSION_KEY_REGISTRY_PATH).

    JSON array; one entry per key version with ``key_id`` + ``retired_at`` fields.
    Written by ``ummaya-permissions rotate-key``.  If absent, the ledger uses the
    default key_id ``"k0001"`` (Spec 033 FR-D04).
    Must be an absolute path.
    Default: ``~/.ummaya/keys/registry.json``.
    """

    permission_ledger_path: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "consent_ledger.jsonl",
    )
    """Path to the append-only PIPA consent ledger (UMMAYA_PERMISSION_LEDGER_PATH).

    JSONL file; one RFC 8785 JCS canonical record per line.  WORM semantics
    enforced in software — no update/delete API.
    Default: ``~/.ummaya/consent_ledger.jsonl``.
    """

    permission_rule_store_path: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "permissions.json",
    )
    """Path to the persistent tri-state rule store (UMMAYA_PERMISSION_RULE_STORE_PATH).

    JSON file; atomic writes via ``tmpfile + os.rename``.  Schema-validated at
    boot; falls back to ``default`` mode + prompt-always on violation.
    Default: ``~/.ummaya/permissions.json``.
    """

    @field_validator(
        "permission_key_path",
        "permission_key_registry_path",
        "permission_ledger_path",
        "permission_rule_store_path",
        mode="after",
    )
    @classmethod
    def _permission_paths_must_be_absolute(cls, v: Path) -> Path:
        """Reject relative paths to prevent writes into an unexpected CWD (Spec 033)."""
        if not v.is_absolute():
            raise ValueError(
                f"permission path must be absolute, got: {v!r}. "
                "Set the matching UMMAYA_PERMISSION_*_PATH env var to an absolute path."
            )
        return v

    # --- User-tier memdir root (Spec 027 / Spec 035 sibling) ---
    user_memdir_root: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "memdir" / "user",
    )
    """Root for user-tier memdir (UMMAYA_USER_MEMDIR_ROOT).

    Houses session-lifetime + cross-session user state: ``consent/``
    (Spec 035 ledger + Spec 1636 plugin install/uninstall receipts),
    ``plugins/`` (installed plugin bundles, see ``plugin_install_root``),
    ``onboarding/state.json`` (Spec 1635 resumable step state),
    ``preferences/a11y.json`` (accessibility toggles).

    Must be an absolute path. Default: ``~/.ummaya/memdir/user``.
    """

    # --- Plugin DX (Epic #1636 P5; data-model.md storage layout) ---
    plugin_install_root: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "memdir" / "user" / "plugins",
    )
    """Root directory holding installed plugin bundles (UMMAYA_PLUGIN_INSTALL_ROOT).

    One sub-directory per ``plugin_id`` containing the validated bundle (manifest.yaml,
    adapter.py, schema.py, tests/, .signature/).  ``index.json`` cached catalog
    snapshot lives here for offline ``ummaya plugin list``.  Must be an absolute path.
    Default: ``~/.ummaya/memdir/user/plugins`` (sibling of Spec 035 consent ledger).
    """

    plugin_bundle_cache: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "cache" / "plugin-bundles",
    )
    """Forensic cache for downloaded bundles (UMMAYA_PLUGIN_BUNDLE_CACHE).

    Bundles are retained on failed verification so an operator can inspect the
    artifact without re-downloading.  Must be an absolute path.
    Default: ``~/.ummaya/cache/plugin-bundles``.
    """

    plugin_vendor_root: Path = Field(
        default_factory=lambda: Path.home() / ".ummaya" / "vendor",
    )
    """Vendored helper binaries root (UMMAYA_PLUGIN_VENDOR_ROOT).

    Houses platform-specific ``slsa-verifier`` binaries written by
    ``scripts/bootstrap_slsa_verifier.sh`` on first install (R-3).  Must be an
    absolute path.  Default: ``~/.ummaya/vendor``.
    """

    plugin_slsa_skip: bool = Field(default=False)
    """Opt-in dev flag to skip SLSA provenance verification (UMMAYA_PLUGIN_SLSA_SKIP).

    Off by default (fail-closed per Constitution §II).  Setting to True writes
    ``slsa_verification="skipped"`` to the consent receipt and surfaces a banner
    in the install UI.  Forbidden in production environments — CI gate enforces
    via release-manifest workflow.
    """

    plugin_catalog_url: str = Field(
        default=("https://raw.githubusercontent.com/ummaya-plugin-store/index/main/index.json"),
    )
    """Plugin catalog URL (UMMAYA_PLUGIN_CATALOG_URL).

    Resolves ``ummaya plugin install <name>`` against the curated index. Override
    to a ``file://`` URL in tests so the install integration test can use a fake
    catalog without network access.
    Default: the ummaya-plugin-store/index repo's main branch.
    """

    @field_validator(
        "user_memdir_root",
        "plugin_install_root",
        "plugin_bundle_cache",
        "plugin_vendor_root",
        mode="after",
    )
    @classmethod
    def _plugin_paths_must_be_absolute(cls, v: Path) -> Path:
        """Reject relative paths for UMMAYA_PLUGIN_* path env vars (Epic #1636)."""
        if not v.is_absolute():
            raise ValueError(
                f"plugin path must be absolute, got: {v!r}. "
                "Set the matching UMMAYA_PLUGIN_*_ROOT/CACHE env var to an absolute path."
            )
        return v


settings: UmmayaSettings = UmmayaSettings()
"""Module-level singleton.  Import this directly in production code."""
