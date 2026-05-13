#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""UMMAYA PTY scenario harness — Spec 1978 T001 skeleton.

Drives `bun run tui` inside a real PTY (so Ink's raw-mode `useInput` works) and
captures the framed stdout (NDJSON IPC) and DEBUG stderr separately. Used by
reviewers to verify Epic #1978 acceptance scenarios per
`specs/1978-tui-kexaone-wiring/quickstart.md`.

UMMAYA-original — Claude Code's restored source has no equivalent harness.
The closest CC pattern is the inline reproduction recipes scattered through
`.references/claude-code-sourcemap/restored-src/src/utils/expect/` for
prompt fixtures, but those run against an in-process LLM mock, not a live
TTY-driven binary. UMMAYA needs a dedicated harness because memory
`feedback_runtime_verification` requires PTY-driven scenario capture rather
than code-grep claims of closure.

Subcommand bodies are intentionally minimal in T001 — Phase 2 only ships the
skeleton + the boot drain. Each subcommand's full keystroke / assertion
sequence lands in Phase 7 tasks T073-T077.

Usage::

    python scripts/pty-scenario.py greeting
    python scripts/pty-scenario.py lookup-emergency-room --capture-out /tmp/s2.log
    python scripts/pty-scenario.py submit-fine-pay --auto-allow-once
    python scripts/pty-scenario.py verify-gongdong
    python scripts/pty-scenario.py subscribe-cbs

Exit codes: 0 = scenario passed, 1 = scenario failed, 2 = harness error.

This file is dependency-free Python stdlib only. ``UMMAYA_FRIENDLI_TOKEN`` is
required for greeting / lookup; ``UMMAYA_DATA_GO_KR_API_KEY`` may be required
for live find runs. Mock-based scenarios (send / check / subscribe) need
no external secrets once Phase F adapter registration lands.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pty
import re
import select
import signal
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("pty-scenario")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
TUI_DIR = WORKTREE_ROOT / "tui"
DEFAULT_BOOT_MS = 8_000
DEFAULT_TURN_TIMEOUT_MS = 25_000
DEFAULT_PERMISSION_TIMEOUT_MS = 60_000
DEFAULT_SUBSCRIBE_TIMEOUT_MS = 30_000

ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]|\x1b\([AB012]")

# Seconds between small poll intervals when scanning for frame markers.
_POLL_INTERVAL = 0.25


def strip_ansi(buf: bytes) -> str:
    """Drop terminal escape sequences so reviewers can scan content easily."""
    return ANSI_RE.sub(b"", buf).decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Harness primitives
# ---------------------------------------------------------------------------


@dataclass
class HarnessResult:
    """Result envelope returned by every scenario subcommand."""

    scenario: str
    pid: int
    exit_code: int | None
    boot_ms: int
    total_ms: int
    captured_stdout: bytearray = field(default_factory=bytearray)
    captured_stderr: bytearray = field(default_factory=bytearray)
    markers_seen: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def stdout_text(self) -> str:
        return strip_ansi(bytes(self.captured_stdout))

    @property
    def stderr_text(self) -> str:
        return self.captured_stderr.decode("utf-8", errors="replace")


def _spawn_tui(env_overrides: dict[str, str]) -> tuple[int, int]:
    """Fork the TUI under a PTY; returns (pid, master_fd).

    UMMAYA-1978 T003b: invoke bun directly (bypassing `bun run` wrapper) AND
    explicitly preload the MACRO shim. `bun run` (a) loses TTY-ness on its
    child (process.stdout.isTTY=undefined → main.tsx isNonInteractive=true →
    --print branch crash) and (b) skips bunfig.toml's preload entry, which
    leaves CC's `MACRO.VERSION` build-time constant undefined and crashes
    commander. Direct invocation + explicit --preload closes both gaps.
    """
    cmd = ["bun", "--preload", "./src/stubs/macro-preload.ts", "src/main.tsx"]
    env = os.environ.copy()
    env.setdefault("DISABLE_INSTALLATION_CHECKS", "1")
    env.setdefault("UMMAYA_TUI_LOG_LEVEL", "DEBUG")
    env.setdefault("OTEL_SDK_DISABLED", "true")
    env.setdefault("TERM", "xterm-256color")
    env.setdefault("COLUMNS", "120")
    env.setdefault("LINES", "40")
    env.setdefault("FORCE_COLOR", "0")
    # UMMAYA-1978 T003b: tell main.tsx that fd1 is a real TTY slave even
    # though Bun's `process.stdout.isTTY` reports undefined under wrapper
    # invocations. See `tui/src/main.tsx` `ummayaForceInteractive` for the
    # consuming side. NEVER set this in citizen runtimes.
    env.setdefault("UMMAYA_FORCE_INTERACTIVE", "1")
    env.update(env_overrides)

    pid, fd = pty.fork()
    if pid == 0:
        # Child — exec the TUI in the worktree's tui/ directory.
        os.chdir(str(TUI_DIR))
        os.execvpe(cmd[0], cmd, env)  # noqa: S606
    return pid, fd


def _drain(fd: int, deadline: float, dest: bytearray, label: str) -> None:
    """Read from ``fd`` until ``deadline``, appending bytes to ``dest``."""
    while time.time() < deadline:
        timeout = max(0.05, deadline - time.time())
        readable, _, _ = select.select([fd], [], [], timeout)
        if not readable:
            continue
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            return
        if not chunk:
            return
        dest.extend(chunk)
        sys.stdout.write(f"[{label}+{len(chunk)}B] ")
        sys.stdout.flush()


def _send(fd: int, payload: bytes, label: str) -> None:
    """Write bytes to PTY master."""
    os.write(fd, payload)
    sys.stdout.write(f"[{label}->{len(payload)}B] ")
    sys.stdout.flush()


def _shutdown(pid: int, fd: int, grace_ms: int = 1500) -> int | None:  # noqa: C901
    """Send Ctrl-C twice + SIGTERM, then reap. Returns exit code if available."""
    try:
        os.write(fd, b"\x03")  # Ctrl-C #1
        time.sleep(0.4)
        os.write(fd, b"\x03")  # Ctrl-C #2 — TUI's "press again to exit"
    except OSError:
        pass
    deadline = time.time() + grace_ms / 1000
    while time.time() < deadline:
        try:
            done_pid, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return None
        if done_pid != 0:
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
            if os.WIFSIGNALED(status):
                return 128 + os.WTERMSIG(status)
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.4)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        _, status = os.waitpid(pid, 0)
    except ChildProcessError:
        return None
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return None


def _scan_markers(text: str, needles: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for needle in needles:
        n = text.count(needle)
        if n:
            counts[needle] = n
    return counts


def _parse_ipc_frames(raw: bytes) -> list[dict]:
    """Extract NDJSON IPC frames from raw PTY output (which may include ANSI noise)."""
    frames: list[dict] = []
    for line in strip_ansi(raw).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            if "kind" in obj:
                frames.append(obj)
        except json.JSONDecodeError:
            pass
    return frames


def _drain_until(
    fd: int,
    dest: bytearray,
    deadline: float,
    predicate,  # (frames: list[dict]) -> bool
    label: str,
) -> bool:
    """Drain PTY output into *dest* until *predicate(frames)* returns True or deadline expires.

    Returns True if predicate was satisfied, False on timeout.
    """
    while time.time() < deadline:
        timeout = max(_POLL_INTERVAL, deadline - time.time())
        readable, _, _ = select.select([fd], [], [], min(_POLL_INTERVAL, timeout))
        if readable:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            dest.extend(chunk)
            log.debug("[%s +%dB]", label, len(chunk))
        frames = _parse_ipc_frames(bytes(dest))
        if predicate(frames):
            return True
    return False


# ---------------------------------------------------------------------------
# Common scenario runner skeleton
# ---------------------------------------------------------------------------


def _run_skeleton(
    scenario: str,
    boot_ms: int,
    env_overrides: dict[str, str] | None = None,
) -> HarnessResult:
    env_overrides = env_overrides or {}
    started = time.time()
    pid, fd = _spawn_tui(env_overrides)
    result = HarnessResult(
        scenario=scenario,
        pid=pid,
        exit_code=None,
        boot_ms=0,
        total_ms=0,
    )
    try:
        # Phase 1: drain boot output.
        boot_deadline = started + boot_ms / 1000
        _drain(fd, boot_deadline, result.captured_stdout, f"{scenario}-boot")
        result.boot_ms = int((time.time() - started) * 1000)
        # Phase 2-N: subcommand-specific keystrokes go here in Phase 7 tasks.
        # For T001 skeleton we just clean up.
    finally:
        result.exit_code = _shutdown(pid, fd)
        result.total_ms = int((time.time() - started) * 1000)
    return result


# ---------------------------------------------------------------------------
# Subcommand handlers (skeletons — bodies land in Phase 7)
# ---------------------------------------------------------------------------


def cmd_greeting(_args: argparse.Namespace) -> HarnessResult:
    """T073: send '안녕하세요', wait for assistant_chunk frames, capture latency."""
    scenario = "greeting"
    turn_timeout_ms = DEFAULT_TURN_TIMEOUT_MS
    started = time.time()
    pid, fd = _spawn_tui({})
    result = HarnessResult(scenario=scenario, pid=pid, exit_code=None, boot_ms=0, total_ms=0)

    first_chunk_ms: int | None = None
    done_chunk_ms: int | None = None

    try:
        # Phase 1: drain boot output.
        boot_deadline = started + DEFAULT_BOOT_MS / 1000
        _drain(fd, boot_deadline, result.captured_stdout, f"{scenario}-boot")
        result.boot_ms = int((time.time() - started) * 1000)
        log.debug("boot done in %dms", result.boot_ms)

        # Phase 2: send Korean greeting.
        _send(fd, "안녕하세요\r".encode(), f"{scenario}-input")
        send_ts = time.time()

        # Phase 3: wait for first assistant_chunk frame.
        turn_deadline = send_ts + turn_timeout_ms / 1000

        def _has_first_chunk(frames: list[dict]) -> bool:
            return any(f.get("kind") == "assistant_chunk" for f in frames)

        found_first = _drain_until(
            fd,
            result.captured_stdout,
            turn_deadline,
            _has_first_chunk,
            f"{scenario}-first-chunk",
        )
        if found_first:
            first_chunk_ms = int((time.time() - send_ts) * 1000)
            log.debug("first assistant_chunk in %dms", first_chunk_ms)

        # Phase 4: wait for done=true assistant_chunk.
        def _has_done_chunk(frames: list[dict]) -> bool:
            return any(f.get("kind") == "assistant_chunk" and f.get("done") for f in frames)

        found_done = _drain_until(
            fd,
            result.captured_stdout,
            turn_deadline,
            _has_done_chunk,
            f"{scenario}-done-chunk",
        )
        if found_done:
            done_chunk_ms = int((time.time() - send_ts) * 1000)
            log.debug("done assistant_chunk in %dms", done_chunk_ms)

    finally:
        result.exit_code = _shutdown(pid, fd)
        result.total_ms = int((time.time() - started) * 1000)

    # Evaluate success: at minimum a first assistant_chunk must have arrived.
    success = first_chunk_ms is not None
    if not success:
        result.errors.append("timeout: no assistant_chunk frames received within turn timeout")

    # Print structured JSON summary to stdout as required by spec.
    result.markers_seen = _scan_markers(result.stdout_text, ["assistant_chunk"])
    return result


def cmd_lookup_emergency_room(_args: argparse.Namespace) -> HarnessResult:
    """T074: assert lookup and resolve_location frames for an emergency-room query."""
    scenario = "lookup-emergency-room"
    started = time.time()
    pid, fd = _spawn_tui({})
    result = HarnessResult(scenario=scenario, pid=pid, exit_code=None, boot_ms=0, total_ms=0)

    seen_call_ids: list[dict] = []  # {name, call_id, arguments}

    try:
        # Phase 1: boot.
        boot_deadline = started + DEFAULT_BOOT_MS / 1000
        _drain(fd, boot_deadline, result.captured_stdout, f"{scenario}-boot")
        result.boot_ms = int((time.time() - started) * 1000)
        log.debug("boot done in %dms", result.boot_ms)

        # Phase 2: first message.
        _send(fd, "응급실 알려줘\r".encode(), f"{scenario}-turn1")
        turn1_deadline = time.time() + DEFAULT_TURN_TIMEOUT_MS / 1000

        def _has_any_tool_call(frames: list[dict]) -> bool:
            return any(f.get("kind") == "tool_call" for f in frames)

        _drain_until(
            fd,
            result.captured_stdout,
            turn1_deadline,
            _has_any_tool_call,
            f"{scenario}-tc1",
        )

        # Phase 3: second message with location qualifier.
        _send(fd, "강남구 응급실\r".encode(), f"{scenario}-turn2")
        turn2_deadline = time.time() + DEFAULT_TURN_TIMEOUT_MS / 1000
        _drain_until(
            fd,
            result.captured_stdout,
            turn2_deadline,
            _has_any_tool_call,
            f"{scenario}-tc2",
        )

    finally:
        result.exit_code = _shutdown(pid, fd)
        result.total_ms = int((time.time() - started) * 1000)

    # Collect all tool_call frames observed.
    frames = _parse_ipc_frames(bytes(result.captured_stdout))
    tool_calls = [f for f in frames if f.get("kind") == "tool_call"]
    for tc in tool_calls:
        seen_call_ids.append({
            "name": tc.get("name"),
            "call_id": tc.get("call_id"),
            "arguments": tc.get("arguments", {}),
        })

    primitive_names_seen = {tc["name"] for tc in seen_call_ids}
    has_lookup = "find" in primitive_names_seen
    has_resolve = "locate" in primitive_names_seen
    # Accept either primitive alone or the chain; the spec expects both
    # primitives to appear in the call sequence.
    success = has_lookup or has_resolve

    if not has_lookup:
        result.errors.append("no tool_call with name='find' observed")
    if not has_resolve:
        result.errors.append("no tool_call with name='locate' observed")
    # Both required per SC-001; mark success only when chain is complete.
    success = has_lookup and has_resolve

    {
        "scenario": scenario,
        "success": success,
        "tool_calls": seen_call_ids,
        "primitives_seen": sorted(primitive_names_seen),
        "has_lookup": has_lookup,
        "has_resolve_location": has_resolve,
        "total_ms": result.total_ms,
    }
    result.markers_seen = _scan_markers(
        result.stdout_text,
        ["tool_call", "find", "locate"],
    )
    return result


def _check_friendli_token(scenario: str) -> None:
    """Emit structured error JSON and raise SystemExit(1) if FRIENDLI_API_KEY is absent."""
    if not os.environ.get("FRIENDLI_API_KEY") and not os.environ.get("UMMAYA_FRIENDLI_TOKEN"):
        raise SystemExit(1)


def cmd_submit_fine_pay(args: argparse.Namespace) -> HarnessResult:  # noqa: C901
    """T075: handle permission_request and assert submit tool_call/tool_result."""
    _check_friendli_token("submit-fine-pay")
    scenario = "submit-fine-pay"
    started = time.time()

    # Determine permission decision from mutually-exclusive flags.
    if args.auto_allow_once:
        decision = "allow_once"
    elif args.auto_allow_session:
        decision = "allow_session"
    elif args.auto_deny:
        decision = "deny"
    else:
        decision = "allow_once"  # default when caller omits flag (non-crash path)

    pid, fd = _spawn_tui({})
    result = HarnessResult(scenario=scenario, pid=pid, exit_code=None, boot_ms=0, total_ms=0)


    try:
        # Phase 1: boot.
        boot_deadline = started + DEFAULT_BOOT_MS / 1000
        _drain(fd, boot_deadline, result.captured_stdout, f"{scenario}-boot")
        result.boot_ms = int((time.time() - started) * 1000)
        log.debug("boot done in %dms", result.boot_ms)

        # Phase 2: send citizen prompt that triggers send primitive.
        _send(fd, "교통 범칙금 납부할게\r".encode(), f"{scenario}-input")
        send_ts = time.time()

        # Phase 3: wait for permission_request frame.
        perm_deadline = send_ts + DEFAULT_PERMISSION_TIMEOUT_MS / 1000

        def _has_permission_request(frames: list[dict]) -> bool:
            return any(f.get("kind") == "permission_request" for f in frames)

        found_perm = _drain_until(
            fd,
            result.captured_stdout,
            perm_deadline,
            _has_permission_request,
            f"{scenario}-perm-req",
        )
        if found_perm:
            log.debug("permission_request received; sending decision=%s", decision)

            # Phase 4: respond with the chosen permission decision.
            perm_response = (
                json.dumps(
                    {"kind": "permission_response", "decision": decision},
                    ensure_ascii=False,
                )
                + "\r\n"
            )
            _send(fd, perm_response.encode("utf-8"), f"{scenario}-perm-resp")
        else:
            log.debug("no permission_request within timeout; proceeding to tool_call watch")

        # Phase 5: wait for tool_call{name:"send"} frame.
        tc_deadline = time.time() + DEFAULT_TURN_TIMEOUT_MS / 1000

        def _has_submit_tool_call(frames: list[dict]) -> bool:
            return any(f.get("kind") == "tool_call" and f.get("name") == "send" for f in frames)

        _drain_until(
            fd, result.captured_stdout, tc_deadline, _has_submit_tool_call, f"{scenario}-tool-call"
        )

        # Phase 6: wait for matching tool_result (or error frame when denied).
        tr_deadline = time.time() + DEFAULT_TURN_TIMEOUT_MS / 1000

        def _has_tool_result_or_error(frames: list[dict]) -> bool:
            return any(f.get("kind") in ("tool_result", "error") for f in frames)

        _drain_until(
            fd,
            result.captured_stdout,
            tr_deadline,
            _has_tool_result_or_error,
            f"{scenario}-tool-result",
        )

    finally:
        result.exit_code = _shutdown(pid, fd)
        result.total_ms = int((time.time() - started) * 1000)

    # Evaluate success per decision path.
    frames = _parse_ipc_frames(bytes(result.captured_stdout))
    tool_calls = [f for f in frames if f.get("kind") == "tool_call" and f.get("name") == "send"]
    tool_results = [f for f in frames if f.get("kind") in ("tool_result", "error")]

    if decision == "deny":
        # Deny path: no submit tool_call should have been dispatched.
        if tool_calls:
            result.errors.append("deny path: submit tool_call was dispatched despite deny decision")
    else:
        # Allow path: both tool_call and a tool_result must be present.
        bool(tool_calls) and bool(tool_results)
        if not tool_calls:
            result.errors.append("allow path: no tool_call{name:'send'} observed")
        if not tool_results:
            result.errors.append("allow path: no tool_result observed after submit dispatch")

    result.markers_seen = _scan_markers(
        result.stdout_text,
        ["permission_request", "tool_call", "tool_result"],
    )
    return result


def cmd_verify_gongdong(_args: argparse.Namespace) -> HarnessResult:
    """T076: assert verify tool_call and AuthContext tool_result."""
    _check_friendli_token("verify-gongdong")
    scenario = "verify-gongdong"
    started = time.time()
    pid, fd = _spawn_tui({})
    result = HarnessResult(scenario=scenario, pid=pid, exit_code=None, boot_ms=0, total_ms=0)

    tool_call_ms: int | None = None
    auth_context_ms: int | None = None

    try:
        # Phase 1: boot.
        boot_deadline = started + DEFAULT_BOOT_MS / 1000
        _drain(fd, boot_deadline, result.captured_stdout, f"{scenario}-boot")
        result.boot_ms = int((time.time() - started) * 1000)
        log.debug("boot done in %dms", result.boot_ms)

        # Phase 2: send citizen verify prompt.
        _send(fd, "공동인증서로 본인인증 부탁해\r".encode(), f"{scenario}-input")
        send_ts = time.time()

        # Phase 3: wait for tool_call{name:"check"}.
        tc_deadline = send_ts + DEFAULT_TURN_TIMEOUT_MS / 1000

        def _has_verify_tool_call(frames: list[dict]) -> bool:
            return any(f.get("kind") == "tool_call" and f.get("name") == "check" for f in frames)

        found_tc = _drain_until(
            fd, result.captured_stdout, tc_deadline, _has_verify_tool_call, f"{scenario}-tool-call"
        )
        if found_tc:
            tool_call_ms = int((time.time() - send_ts) * 1000)
            log.debug("verify tool_call in %dms", tool_call_ms)

        # Phase 4: wait for tool_result with kind="check" + family="gongdong_injeungseo".
        tr_deadline = time.time() + DEFAULT_TURN_TIMEOUT_MS / 1000

        def _has_auth_context(frames: list[dict]) -> bool:
            return any(
                f.get("kind") == "tool_result"
                and f.get("output", {}).get("kind") == "check"
                and f.get("output", {}).get("family") == "gongdong_injeungseo"
                for f in frames
            )

        found_tr = _drain_until(
            fd, result.captured_stdout, tr_deadline, _has_auth_context, f"{scenario}-auth-ctx"
        )
        if found_tr:
            auth_context_ms = int((time.time() - send_ts) * 1000)
            log.debug("AuthContext envelope in %dms", auth_context_ms)

    finally:
        result.exit_code = _shutdown(pid, fd)
        result.total_ms = int((time.time() - started) * 1000)

    # Collect verify tool_result details.
    frames = _parse_ipc_frames(bytes(result.captured_stdout))
    verify_results = [
        f for f in frames
        if f.get("kind") == "tool_result" and f.get("output", {}).get("kind") == "check"
    ]

    if verify_results:
        output = verify_results[0].get("output", {})
        {
            "family": output.get("family"),
            "published_tier": output.get("published_tier"),
            "nist_aal_hint": output.get("nist_aal_hint"),
        }

    if tool_call_ms is None:
        result.errors.append("timeout: no tool_call{name:'check'} observed")
    if auth_context_ms is None:
        result.errors.append(
            "timeout: no tool_result{kind:'check', family:'gongdong_injeungseo'} observed"
        )

    result.markers_seen = _scan_markers(
        result.stdout_text,
        ["tool_call", "tool_result", "gongdong_injeungseo"],
    )
    return result


def cmd_subscribe_cbs(_args: argparse.Namespace) -> HarnessResult:
    """T077 will send '재난문자 구독해줘' and capture ≥ 1 simulated alert."""
    return _run_skeleton("subscribe-cbs", DEFAULT_BOOT_MS)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pty-scenario.py",
        description="UMMAYA PTY scenario harness (Spec 1978).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging to stderr.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name, helptext, handler in [
        ("greeting", "User Story 1 — '안녕하세요' (FR-001 / SC-001)", cmd_greeting),
        (
            "lookup-emergency-room",
            "US1 — 응급실 lookup chain (SC-001)",
            cmd_lookup_emergency_room,
        ),
        (
            "submit-fine-pay",
            "US2 — Mock submit + permission gauntlet (SC-002)",
            cmd_submit_fine_pay,
        ),
        ("verify-gongdong", "US3 — Mock verify gongdong_injeungseo (SC-003)", cmd_verify_gongdong),
        ("subscribe-cbs", "US4 — Mock CBS subscribe (FR-012)", cmd_subscribe_cbs),
    ]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument(
            "--capture-out",
            type=Path,
            default=None,
            help="Persist stdout (frame stream) here.",
        )
        p.add_argument(
            "--capture-err",
            type=Path,
            default=None,
            help="Persist stderr (DEBUG log) here.",
        )
        if name == "submit-fine-pay":
            perm_group = p.add_mutually_exclusive_group(required=False)
            perm_group.add_argument(
                "--auto-allow-once",
                action="store_true",
                help="Auto-respond to permission_request with decision='allow_once'.",
            )
            perm_group.add_argument(
                "--auto-allow-session",
                action="store_true",
                help="Auto-respond to permission_request with decision='allow_session'.",
            )
            perm_group.add_argument(
                "--auto-deny",
                action="store_true",
                help=(
                    "Auto-respond to permission_request with decision='deny' "
                    "and assert no submit dispatch."
                ),
            )
        p.set_defaults(handler=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "debug", False) else logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    handler = args.handler

    try:
        result = handler(args)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"\n[harness-error] {type(exc).__name__}: {exc}\n")
        return 2

    if result.markers_seen:
        pass
    if result.errors:
        for _err in result.errors:
            pass

    if args.capture_out is not None:
        args.capture_out.parent.mkdir(parents=True, exist_ok=True)
        args.capture_out.write_bytes(bytes(result.captured_stdout))
    if args.capture_err is not None:
        args.capture_err.parent.mkdir(parents=True, exist_ok=True)
        args.capture_err.write_bytes(bytes(result.captured_stderr))

    # Codex P1 (PR #2074): a crashed/terminated TUI process must fail the
    # scenario even if the marker checks did not append an error. Treat
    # exit_code != 0 (and None/SIGKILL) as a hard failure so silently
    # broken backends never report a false-positive pass.
    if result.exit_code is None or result.exit_code != 0:
        result.errors.append(
            f"TUI process exited with non-zero status: exit_code={result.exit_code!r}"
        )

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
