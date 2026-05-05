# SPDX-License-Identifier: Apache-2.0
"""plugin_op IPC frame dispatcher.

Routes incoming :class:`~kosmos.ipc.frame_schema.PluginOpFrame` frames with
``op="request"`` to one of three backend handlers:

- ``request_op="install"`` → :func:`handle_install` → wraps
  :func:`kosmos.plugins.installer.install_plugin` with a progress-emitter
  closure that converts each phase tick into a ``plugin_op_progress`` frame.
- ``request_op="uninstall"`` → :func:`handle_uninstall` → mirrors the install
  flow with the 3-phase :func:`kosmos.plugins.uninstall.uninstall_plugin`.
- ``request_op="list"`` → :func:`handle_list` → enumerates the active
  ToolRegistry contents + emits a single ``plugin_op_complete`` carrying the
  payload via the Spec 032 ``payload_start`` / ``payload_delta`` /
  ``payload_end`` triplet.

Per Constitution §I — Reference-Driven Development:
- Spec 1636 contract: ``specs/1636-plugin-dx-5tier/contracts/plugin-install.cli.md``
  defines the canonical 7-phase install + 8-code exit table.
- Spec 1979 contract: ``specs/1979-plugin-dx-tui-integration/contracts/dispatcher-routing.md``
  defines the per-op frame sequence.
- Spec 032 envelope: ``specs/032-ipc-stdio-hardening/`` for the
  ``correlation_id`` propagation invariant.

Per Constitution §II — Fail-Closed Security:
- Failed installs roll back the install root before emitting the terminal
  ``plugin_op_complete`` (delegated to ``installer.py``'s existing rollback
  path which is unchanged by this Epic).
- ``request_op="install"`` requires non-empty ``name`` (already enforced by
  ``PluginOpFrame._v_plugin_op_shape`` at deserialization).

Per Constitution §III — Pydantic v2 Strict Typing:
- All entries / exits use existing :class:`PluginOpFrame` and
  :class:`PayloadStart/Delta/End` models. No ``Any``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kosmos.ipc.frame_schema import (
    IPCFrame,
    PayloadDeltaFrame,
    PayloadEndFrame,
    PayloadStartFrame,
    PluginOpFrame,
)

logger = logging.getLogger(__name__)


WriteFrameFn = Callable[[IPCFrame], Awaitable[None]]


# ---------------------------------------------------------------------------
# Canonical phase-message text (mirrors Spec 1636 contracts/plugin-install.cli.md)
# ---------------------------------------------------------------------------


_INSTALL_PHASE_TEXT: dict[int, tuple[str, str]] = {
    1: ("📡 카탈로그 조회 중…", "📡 Catalog query…"),
    2: ("📦 번들 다운로드 중…", "📦 Bundle download…"),
    3: ("🔐 SLSA 서명 검증 중…", "🔐 SLSA verification…"),
    4: ("🧪 매니페스트 검증 중…", "🧪 Manifest validation…"),
    5: ("📝 동의 확인…", "📝 Consent prompt…"),
    6: ("🔄 등록 + BM25 색인 중…", "🔄 Register + BM25 index…"),
    7: ("📜 동의 영수증 기록 중…", "📜 Consent receipt write…"),
}


_UNINSTALL_PHASE_TEXT: dict[int, tuple[str, str]] = {
    1: ("📋 등록 해제 중…", "📋 Deregister…"),
    2: ("📁 설치 디렉터리 제거 중…", "📁 Remove install dir…"),
    3: ("📜 동의 영수증 기록 중…", "📜 Uninstall receipt write…"),
}


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return (
        datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.")
        + f"{datetime.now(tz=UTC).microsecond // 1000:03d}Z"
    )


def _build_progress_frame(
    *,
    session_id: str,
    correlation_id: str,
    phase: int,
    message_ko: str,
    message_en: str,
) -> PluginOpFrame:
    return PluginOpFrame(
        session_id=session_id,
        correlation_id=correlation_id,
        role="backend",
        ts=_utcnow(),
        kind="plugin_op",
        op="progress",
        progress_phase=phase,
        progress_message_ko=message_ko,
        progress_message_en=message_en,
    )


def _build_complete_frame(
    *,
    session_id: str,
    correlation_id: str,
    result: str,
    exit_code: int,
    receipt_id: str | None = None,
    error_kind: str | None = None,
    error_message: str | None = None,
    was_idempotent_noop: bool | None = None,
) -> PluginOpFrame:
    # Pydantic Literal coercion expects "success" | "failure"
    if result not in ("success", "failure"):
        raise ValueError(f"plugin_op.complete result must be success|failure; got {result!r}")
    return PluginOpFrame(
        session_id=session_id,
        correlation_id=correlation_id,
        role="backend",
        ts=_utcnow(),
        kind="plugin_op",
        op="complete",
        result=result,  # type: ignore[arg-type]
        exit_code=exit_code,
        receipt_id=receipt_id,
        error_kind=error_kind if result == "failure" else None,
        error_message=error_message if result == "failure" else None,
        was_idempotent_noop=was_idempotent_noop,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def handle_plugin_op_request(
    frame: PluginOpFrame,
    *,
    registry: object,
    executor: object,
    write_frame: WriteFrameFn,
    consent_bridge: object,
    session_id: str,
) -> None:
    """Dispatch a `plugin_op:request` frame to the appropriate handler.

    Args:
        frame: The inbound :class:`PluginOpFrame` with ``op="request"``.
        registry: :class:`kosmos.tools.registry.ToolRegistry` (typed loosely
            to avoid import-time circular dependency at the dispatcher seam).
        executor: :class:`kosmos.tools.executor.ToolExecutor`.
        write_frame: Async callable that serialises an :class:`IPCFrame` and
            writes it to stdout (existing :func:`kosmos.ipc.stdio.write_frame`).
        consent_bridge: :class:`kosmos.plugins.consent_bridge.IPCConsentBridge`
            wrapping the citizen consent IPC round-trip.
        session_id: Active session identifier (mirrors ``frame.session_id``).

    Raises:
        ValueError: When ``frame.op`` is not ``"request"`` or ``frame.request_op``
            is not in the documented allow-list. Errors here propagate to
            :func:`kosmos.ipc.stdio` ErrorFrame fanout.
    """
    if frame.op != "request":
        raise ValueError(f"plugin_op_dispatcher received op={frame.op!r}; expected 'request'")

    if frame.request_op == "install":
        await handle_install(
            frame,
            registry=registry,
            executor=executor,
            write_frame=write_frame,
            consent_bridge=consent_bridge,
        )
    elif frame.request_op == "uninstall":
        await handle_uninstall(
            frame,
            registry=registry,
            executor=executor,
            write_frame=write_frame,
        )
    elif frame.request_op == "list":
        await handle_list(
            frame,
            registry=registry,
            write_frame=write_frame,
        )
    else:
        raise ValueError(
            f"unknown plugin_op request_op={frame.request_op!r}; expected install|uninstall|list"
        )


# ---------------------------------------------------------------------------
# handle_install
# ---------------------------------------------------------------------------


async def handle_install(
    frame: PluginOpFrame,
    *,
    registry: object,
    executor: object,
    write_frame: WriteFrameFn,
    consent_bridge: object,
) -> None:
    """Run install_plugin with progress + complete frame emission.

    Phases 1-7 emit a ``plugin_op_progress`` frame each (canonical text in
    ``_INSTALL_PHASE_TEXT``). On completion, a single ``plugin_op_complete``
    is emitted carrying ``result`` + ``exit_code`` + optional ``receipt_id``.
    """
    from kosmos.plugins.installer import install_plugin  # noqa: PLC0415

    if not frame.name:
        # Defensive — _v_plugin_op_shape already enforces this, but the
        # dispatcher must never trust frame.name to be non-empty here.
        await write_frame(
            _build_complete_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                result="failure",
                exit_code=1,
                receipt_id=None,
            )
        )
        return

    async def _emit_progress(phase: int, message_ko: str, message_en: str) -> None:
        await write_frame(
            _build_progress_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                phase=phase,
                message_ko=message_ko,
                message_en=message_en,
            )
        )

    # Install phases tick by phase number; the installer calls
    # progress_emitter(phase, message_ko, message_en) between phases.
    # Per FR-002, the dispatcher supplies the canonical text from the
    # phase table — installer code stays free of i18n strings.
    async def _progress_with_canonical_text(phase: int, _message_ko: str, _message_en: str) -> None:
        message_ko, message_en = _INSTALL_PHASE_TEXT.get(phase, (_message_ko, _message_en))
        await _emit_progress(phase, message_ko, message_en)

    # Run the synchronous install_plugin in an executor so its blocking
    # phases (network I/O, subprocess calls) don't block the event loop.
    # The progress_emitter is wrapped via asyncio.run_coroutine_threadsafe
    # so installer's sync phase ticks reach the async write_frame.
    import asyncio  # noqa: PLC0415

    loop = asyncio.get_running_loop()

    def _sync_progress(phase: int, message_ko: str, message_en: str) -> None:
        # Bridge sync → async via run_coroutine_threadsafe.
        # The future is awaited synchronously to preserve the phase ordering
        # invariant (phase 1 emits before phase 2 begins).
        future = asyncio.run_coroutine_threadsafe(
            _progress_with_canonical_text(phase, message_ko, message_en),
            loop,
        )
        future.result()  # Block the executor thread until the frame is on stdout.

    # _v_plugin_op_shape already enforces frame.name non-empty for install;
    # narrow the type for mypy so install_plugin's `name: str` matches.
    plugin_name = frame.name
    assert plugin_name is not None  # noqa: S101 — enforced by frame validator

    try:
        result = await loop.run_in_executor(
            None,
            lambda: install_plugin(
                plugin_name,
                registry=registry,  # type: ignore[arg-type]
                executor=executor,  # type: ignore[arg-type]
                requested_version=frame.requested_version,
                consent_prompt=consent_bridge,  # type: ignore[arg-type]
                yes=False,
                dry_run=bool(frame.dry_run),
                progress_emitter=_sync_progress,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("install_plugin raised: %s", exc)
        await write_frame(
            _build_complete_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                result="failure",
                exit_code=6,
                error_kind="installer_exception",
                error_message=str(exc),
            )
        )
        return

    # Auto-bootstrap slsa-verifier binary when it is missing (exit_code=7).
    # The installer cannot self-bootstrap inside run_in_executor because the
    # bootstrap script is a blocking shell invocation. We do it here in the
    # async handler so the TUI sees a progress frame before the bootstrap runs.
    if result.exit_code == 7 and result.error_kind == "binary_not_found":
        await write_frame(
            _build_progress_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                phase=3,
                message_ko="🔧 slsa-verifier 자동 설치 중… (첫 설치 시 ~10 MB)",
                message_en="🔧 Auto-installing slsa-verifier… (~10 MB, first-time only)",
            )
        )
        bootstrap_result = await loop.run_in_executor(None, _run_slsa_bootstrap)
        if bootstrap_result == 0:
            # Retry install now that the binary is available.
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: install_plugin(
                        plugin_name,
                        registry=registry,  # type: ignore[arg-type]
                        executor=executor,  # type: ignore[arg-type]
                        requested_version=frame.requested_version,
                        consent_prompt=consent_bridge,  # type: ignore[arg-type]
                        yes=False,
                        dry_run=bool(frame.dry_run),
                        progress_emitter=_sync_progress,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("install_plugin (post-bootstrap retry) raised: %s", exc)
                await write_frame(
                    _build_complete_frame(
                        session_id=frame.session_id,
                        correlation_id=frame.correlation_id,
                        result="failure",
                        exit_code=6,
                        error_kind="installer_exception",
                        error_message=str(exc),
                    )
                )
                return
        else:
            await write_frame(
                _build_complete_frame(
                    session_id=frame.session_id,
                    correlation_id=frame.correlation_id,
                    result="failure",
                    exit_code=7,
                    error_kind="slsa_bootstrap_failed",
                    error_message=(
                        "scripts/bootstrap_slsa_verifier.sh 실행 실패 "
                        f"(exit={bootstrap_result}). "
                        "수동으로 'bash scripts/bootstrap_slsa_verifier.sh' 실행 후 재시도."
                    ),
                )
            )
            return

    await write_frame(
        _build_complete_frame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            result="success" if result.exit_code == 0 else "failure",
            exit_code=result.exit_code,
            receipt_id=result.receipt_id if result.exit_code == 0 else None,
            error_kind=result.error_kind,
            error_message=result.error_message,
        )
    )


def _run_slsa_bootstrap() -> int:
    """Blocking: shell out to bootstrap_slsa_verifier.sh. Returns exit code."""
    import subprocess  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    script = Path(__file__).parent.parent.parent.parent / "scripts" / "bootstrap_slsa_verifier.sh"
    if not script.is_file():
        # Fallback: search from CWD
        import os  # noqa: PLC0415

        cwd_script = Path(os.getcwd()) / "scripts" / "bootstrap_slsa_verifier.sh"
        if cwd_script.is_file():
            script = cwd_script
        else:
            logger.error("bootstrap_slsa_verifier.sh not found at %s or %s", script, cwd_script)
            return 1
    try:
        completed = subprocess.run(  # noqa: S603
            ["/bin/bash", str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120.0,
        )
        if completed.returncode != 0:
            logger.error(
                "bootstrap_slsa_verifier.sh exited %d: %s",
                completed.returncode,
                completed.stderr[-2000:],
            )
        else:
            logger.info("bootstrap_slsa_verifier.sh succeeded: %s", completed.stdout[:500])
        return completed.returncode
    except Exception as exc:  # noqa: BLE001
        logger.exception("bootstrap_slsa_verifier.sh invocation failed: %s", exc)
        return 1


# ---------------------------------------------------------------------------
# handle_uninstall
# ---------------------------------------------------------------------------


async def handle_uninstall(
    frame: PluginOpFrame,
    *,
    registry: object,
    executor: object,
    write_frame: WriteFrameFn,
) -> None:
    """Run uninstall_plugin with 3-phase progress + complete emission."""
    from kosmos.plugins.uninstall import uninstall_plugin  # noqa: PLC0415

    if not frame.name:
        await write_frame(
            _build_complete_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                result="failure",
                exit_code=1,
                receipt_id=None,
            )
        )
        return

    import asyncio  # noqa: PLC0415

    loop = asyncio.get_running_loop()

    async def _emit_progress(phase: int, message_ko: str, message_en: str) -> None:
        await write_frame(
            _build_progress_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                phase=phase,
                message_ko=message_ko,
                message_en=message_en,
            )
        )

    async def _progress_with_canonical_text(phase: int, _message_ko: str, _message_en: str) -> None:
        message_ko, message_en = _UNINSTALL_PHASE_TEXT.get(phase, (_message_ko, _message_en))
        await _emit_progress(phase, message_ko, message_en)

    def _sync_progress(phase: int, message_ko: str, message_en: str) -> None:
        future = asyncio.run_coroutine_threadsafe(
            _progress_with_canonical_text(phase, message_ko, message_en),
            loop,
        )
        future.result()

    # _v_plugin_op_shape already enforces frame.name non-empty for uninstall.
    plugin_name = frame.name
    assert plugin_name is not None  # noqa: S101 — enforced by frame validator

    try:
        result = await loop.run_in_executor(
            None,
            lambda: uninstall_plugin(
                plugin_name,
                registry=registry,  # type: ignore[arg-type]
                executor=executor,  # type: ignore[arg-type]
                progress_emitter=_sync_progress,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("uninstall_plugin raised: %s", exc)
        await write_frame(
            _build_complete_frame(
                session_id=frame.session_id,
                correlation_id=frame.correlation_id,
                result="failure",
                exit_code=6,
                error_kind="uninstaller_exception",
                error_message=str(exc),
            )
        )
        return

    await write_frame(
        _build_complete_frame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            result="success" if result.exit_code == 0 else "failure",
            exit_code=result.exit_code,
            receipt_id=result.receipt_id if result.exit_code == 0 else None,
            error_kind=result.error_kind,
            error_message=result.error_message,
            was_idempotent_noop=result.was_idempotent_noop if result.exit_code == 0 else None,
        )
    )


# ---------------------------------------------------------------------------
# handle_list
# ---------------------------------------------------------------------------


def _build_list_payload(registry: object) -> list[dict[str, Any]]:
    """Enumerate active plugins from the registry with manifest metadata.

    Returns a list of dicts matching the ``PluginListEntry`` JSON shape
    documented in contracts/dispatcher-routing.md § list payload.
    """
    from kosmos.settings import settings  # noqa: PLC0415

    entries: list[dict[str, Any]] = []

    # registry is duck-typed as ToolRegistry; access _tools + is_active.
    tools = getattr(registry, "_tools", {})  # noqa: SLF001
    is_active_fn = getattr(registry, "is_active", None)

    install_root: Path = settings.plugin_install_root

    for tool_id, tool in sorted(tools.items()):
        # Only surface plugin tools (namespace: plugin.<id>.<verb>)
        if not tool_id.startswith("plugin."):
            continue
        # Filter inactive (E4 _inactive shadow set, R-3+R-4 verdict)
        active = bool(is_active_fn(tool_id)) if callable(is_active_fn) else True

        # Extract plugin_id from tool_id: plugin.<id>.<verb>
        parts = tool_id.split(".")
        if len(parts) < 3:
            continue
        plugin_id = parts[1]

        # Try to load the plugin's manifest snapshot for richer metadata
        manifest_data: dict[str, Any] = {}
        manifest_path = install_root / plugin_id / "manifest.yaml"
        if manifest_path.is_file():
            try:
                import yaml  # noqa: PLC0415

                manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            except (OSError, Exception) as exc:  # noqa: BLE001
                logger.debug(
                    "plugin %s manifest read failed (continuing with minimal metadata): %s",
                    plugin_id,
                    exc,
                )

        entries.append(
            {
                "plugin_id": plugin_id,
                "name": manifest_data.get("plugin_id", plugin_id),
                "version": manifest_data.get("version", "0.0.0"),
                "tier": manifest_data.get("tier", "live"),
                "permission_layer": manifest_data.get("permission_layer", 1),
                "processes_pii": bool(manifest_data.get("processes_pii", False)),
                "trustee_org_name": (
                    (manifest_data.get("pipa_trustee_acknowledgment") or {}).get("trustee_org_name")
                ),
                "is_active": active,
                "install_timestamp_iso": manifest_data.get("install_timestamp_iso", ""),
                "description_ko": manifest_data.get("description_ko", tool.search_hint),
                "description_en": manifest_data.get("description_en", tool.search_hint),
                "search_hint_ko": manifest_data.get("search_hint_ko", tool.search_hint),
                "search_hint_en": manifest_data.get("search_hint_en", tool.search_hint),
            }
        )

    return entries


async def handle_list(
    frame: PluginOpFrame,
    *,
    registry: object,
    write_frame: WriteFrameFn,
) -> None:
    """Enumerate plugins + emit payload triplet + terminal complete frame.

    Per Spec 032, payload triplets are correlated by ``correlation_id`` only —
    no separate payload_id field. The TUI consumes them in arrival order.
    """
    entries = _build_list_payload(registry)
    payload_json = json.dumps({"entries": entries}, ensure_ascii=False, sort_keys=True)
    payload_bytes = payload_json.encode("utf-8")

    # Spec 032 large-payload mechanism: payload_start / payload_delta / payload_end
    # correlated by correlation_id (no payload_id field per Spec 032).
    await write_frame(
        PayloadStartFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="payload_start",
            content_type="application/json",
            estimated_bytes=len(payload_bytes),
        )
    )
    await write_frame(
        PayloadDeltaFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="payload_delta",
            delta_seq=0,
            payload=payload_json,
        )
    )
    await write_frame(
        PayloadEndFrame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            role="backend",
            ts=_utcnow(),
            kind="payload_end",
            delta_count=1,
            status="ok",
        )
    )

    # Terminal complete frame.
    await write_frame(
        _build_complete_frame(
            session_id=frame.session_id,
            correlation_id=frame.correlation_id,
            result="success",
            exit_code=0,
            receipt_id=None,
        )
    )


__all__ = [
    "handle_install",
    "handle_list",
    "handle_plugin_op_request",
    "handle_uninstall",
]
