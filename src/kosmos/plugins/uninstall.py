# SPDX-License-Identifier: Apache-2.0
"""End-to-end plugin uninstall flow (Spec 1979 — mirror of installer.py).

Implements the 3-phase uninstall per
``specs/1979-plugin-dx-tui-integration/contracts/dispatcher-routing.md``:

1. 📋 등록 해제 — :meth:`ToolRegistry.deregister` + BM25 corpus rebuild.
2. 📁 설치 디렉터리 제거 — ``shutil.rmtree(install_root / plugin_id)``.
3. 📜 동의 영수증 기록 — append :class:`PluginConsentReceipt` with
   ``action_type="plugin_uninstall"`` to the existing consent ledger.

The function is **idempotent** on already-removed plugins — calling
``uninstall_plugin("seoul-subway", ...)`` twice does not raise; the
second call returns ``exit_code=0`` with a debug log.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Success (or idempotent no-op). |
| 6 | I/O error during rmtree or registry deregister. |

Per Constitution §II — Fail-Closed Security: if rmtree partially
succeeds and then fails, the partial state is logged but no rollback
attempt is made (the registry has already deregistered the tool, so
the citizen sees the plugin as uninstalled even if the on-disk dir is
half-removed; a re-run will clean it up).
"""

from __future__ import annotations

import logging
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from kosmos.plugins.installer import (
    PluginConsentReceipt,
    _allocate_consent_position,
    _write_consent_receipt,
)
from kosmos.settings import settings
from kosmos.tools.errors import ToolNotFoundError
from kosmos.tools.executor import ToolExecutor
from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


_EXIT_OK = 0
_EXIT_IO = 6


@dataclass(frozen=True, slots=True)
class UninstallResult:
    """Outcome record returned from :func:`uninstall_plugin`."""

    exit_code: int
    plugin_id: str
    receipt_id: str | None
    error_kind: str | None
    error_message: str | None
    was_idempotent_noop: bool = False


def _enumerate_plugin_tool_ids(registry: ToolRegistry, plugin_id: str) -> list[str]:
    """Return all registered tool_ids matching ``plugin.<plugin_id>.<verb>``."""
    prefix = f"plugin.{plugin_id}."
    return [tid for tid in list(registry._tools) if tid.startswith(prefix)]  # noqa: SLF001


def uninstall_plugin(
    plugin_id: str,
    *,
    registry: ToolRegistry,
    executor: ToolExecutor,
    progress_emitter: Callable[[int, str, str], None] | None = None,
) -> UninstallResult:
    """Reverse of :func:`install_plugin` — 3-phase remove flow.

    Args:
        plugin_id: The plugin's ``plugin_id`` (matches install root subdir name).
        registry: Central :class:`ToolRegistry` to deregister tools from.
        executor: :class:`ToolExecutor` (currently unused — reserved for future
            adapter-shutdown hooks).
        progress_emitter: Optional ``(phase, message_ko, message_en)`` callback
            mirroring :func:`install_plugin`'s seam.

    Returns:
        :class:`UninstallResult` with ``exit_code=0`` on success or idempotent
        no-op, ``exit_code=6`` on I/O failure.
    """
    del executor  # Reserved for future adapter-shutdown hooks; unused today.

    def _emit(phase: int) -> None:
        if progress_emitter is not None:
            try:
                progress_emitter(phase, "", "")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "progress_emitter raised at uninstall phase %d (continuing): %s",
                    phase,
                    exc,
                )

    install_root = settings.plugin_install_root
    plugin_dir = install_root / plugin_id

    # --- Phase 1: deregister + BM25 rebuild -------------------------------
    _emit(1)
    deregistered = _enumerate_plugin_tool_ids(registry, plugin_id)
    if not deregistered and not plugin_dir.exists():
        # Idempotent no-op — plugin was never installed (or already uninstalled).
        logger.info(
            "uninstall_plugin: plugin %s not installed; idempotent no-op",
            plugin_id,
        )
        return UninstallResult(
            exit_code=_EXIT_OK,
            plugin_id=plugin_id,
            receipt_id=None,
            error_kind=None,
            error_message=None,
            was_idempotent_noop=True,
        )

    for tool_id in deregistered:
        try:
            registry.deregister(tool_id)
        except ToolNotFoundError:
            # Race — already deregistered by a concurrent uninstall. Ignore.
            logger.debug("uninstall_plugin: tool %s already deregistered", tool_id)

    # --- Phase 2: rmtree install dir --------------------------------------
    _emit(2)
    if plugin_dir.exists():
        try:
            shutil.rmtree(plugin_dir)
        except OSError as exc:
            logger.exception(
                "uninstall_plugin: rmtree failed for %s (continuing to receipt): %s",
                plugin_dir,
                exc,
            )
            return UninstallResult(
                exit_code=_EXIT_IO,
                plugin_id=plugin_id,
                receipt_id=None,
                error_kind="rmtree_failed",
                error_message=str(exc),
            )

    # --- Phase 3: append uninstall receipt --------------------------------
    _emit(3)
    receipt_id = f"rcpt-{uuid.uuid4().hex}"
    consent_root = settings.user_memdir_root / "consent"
    receipt = PluginConsentReceipt(
        receipt_id=receipt_id,
        timestamp_iso=datetime.now(UTC).isoformat(),
        action_type="plugin_uninstall",
        plugin_id=plugin_id,
        plugin_version="0.0.0",  # Manifest may already be gone post-rmtree
        slsa_verification=Literal["passed"].__args__[0],  # type: ignore[attr-defined]
        trustee_org_name=None,
        consent_ledger_position=_allocate_consent_position(consent_root),
    )
    try:
        _write_consent_receipt(receipt, consent_root=consent_root)
    except OSError as exc:
        logger.exception("uninstall_plugin: receipt write failed for %s: %s", plugin_id, exc)
        return UninstallResult(
            exit_code=_EXIT_IO,
            plugin_id=plugin_id,
            receipt_id=None,
            error_kind="receipt_write_failed",
            error_message=str(exc),
        )

    logger.info(
        "Uninstalled plugin %s (%d tools deregistered, receipt=%s)",
        plugin_id,
        len(deregistered),
        receipt_id,
    )
    return UninstallResult(
        exit_code=_EXIT_OK,
        plugin_id=plugin_id,
        receipt_id=receipt_id,
        error_kind=None,
        error_message=None,
    )


__all__ = ["UninstallResult", "uninstall_plugin"]
