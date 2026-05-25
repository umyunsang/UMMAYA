#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Capture one UMMAYA real-use TUI scenario through a POSIX PTY.

This is a Python-driver companion to ``scripts/bun-pty-capture.ts``.  It keeps
the same ``UMMAYA_REALUSE_*`` environment contract used by the matrix runner,
but uses ``pty.fork()`` so the child process sees a real TTY.  That matches the
older ``scripts/pty-scenario.py`` harness and avoids relying on Bun's terminal
API for child-process TTY detection.
"""

from __future__ import annotations

import argparse
import codecs
import fcntl
import hashlib
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import time
from dataclasses import dataclass
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
TUI_DIR = WORKTREE_ROOT / "tui"

ANSI_RE = re.compile(
    rb"\x1b\[\d+[ABCD]"
    rb"|\x1b\[[\d;?]*[A-Za-z]"
    rb"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    rb"|\x1bP[^\x07\x1b]*\x1b\\"
    rb"|\x1b[=>()#0-9?\\]"
)

KEYS: dict[str, bytes] = {
    "Enter": b"\r",
    "Tab": b"\t",
    "BackTab": b"\x1b[Z",
    "Backspace": b"\x7f",
    "Escape": b"\x1b",
    "Up": b"\x1b[A",
    "Down": b"\x1b[B",
    "Right": b"\x1b[C",
    "Left": b"\x1b[D",
    "Home": b"\x1b[H",
    "End": b"\x1b[F",
    "PageUp": b"\x1b[5~",
    "PageDown": b"\x1b[6~",
    "C-c": b"\x03",
    "C-d": b"\x04",
    "C-o": b"\x0f",
    "C-q": b"\x11",
    "C-z": b"\x1a",
}


def strip_ansi(raw: bytes) -> str:
    stripped = ANSI_RE.sub(b"", raw)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    return decoder.decode(stripped, final=False)


def env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def compile_env_regex(name: str, fallback: str) -> re.Pattern[str]:
    return re.compile(env(name, fallback), re.IGNORECASE | re.MULTILINE)


def sleep(ms: int) -> None:
    time.sleep(ms / 1000)


def set_winsize(fd: int, rows: int, cols: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


@dataclass
class Harness:
    pid: int
    fd: int
    out_dir: Path
    cols: int
    rows: int
    sample_frames: bool
    max_frames: int
    mirror: bool

    def __post_init__(self) -> None:
        self.buffer = bytearray()
        self.snap_seq = 0
        self.frame_seq = 0
        self.last_frame_hash = ""
        self.start_ms = time.time()
        self.frame_dir = self.out_dir / "frames"
        self.timeline = self.frame_dir / "timeline.tsv"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if self.sample_frames:
            self.frame_dir.mkdir(parents=True, exist_ok=True)
            self.timeline.write_text("seq\tts_ms\thash\tlabel\tfile\n", encoding="utf-8")

    def plain(self) -> str:
        return strip_ansi(bytes(self.buffer))

    def mark(self) -> int:
        return len(self.buffer)

    def plain_since(self, mark: int) -> str:
        return strip_ansi(bytes(self.buffer[mark:]))

    def drain_once(self, timeout: float = 0.12) -> bool:
        readable, _, _ = select.select([self.fd], [], [], timeout)
        if not readable:
            return False
        try:
            chunk = os.read(self.fd, 65536)
        except BlockingIOError:
            return False
        except OSError:
            return False
        if not chunk:
            return False
        self.buffer.extend(chunk)
        if self.mirror:
            sys.stderr.buffer.write(chunk)
            sys.stderr.buffer.flush()
        self.record_frame("pty-data")
        return True

    def write(self, data: bytes) -> None:
        os.write(self.fd, data)

    def send_text(self, text: str) -> None:
        self.write(text.encode("utf-8"))

    def send_key(self, key: str) -> None:
        try:
            self.write(KEYS[key])
        except KeyError as exc:
            raise ValueError(f"Unknown key: {key}") from exc

    def wait_for(
        self,
        pattern: re.Pattern[str],
        deadline_sec: float,
        *,
        since: int = 0,
        label: str = "waitForPane",
    ) -> None:
        start = time.time()
        deadline = start + deadline_sec
        while time.time() < deadline:
            text = self.plain_since(since)
            if pattern.search(text):
                elapsed = time.time() - start
                sys.stderr.write(f"\n[{label} MATCH {pattern.pattern!r} after {elapsed:.1f}s]\n")
                return
            self.drain_once()
        elapsed = time.time() - start
        sys.stderr.write(f"\n[{label} TIMEOUT {pattern.pattern!r} after {elapsed:.1f}s]\n")
        timeout_file = self.out_dir / f"timeout-{int(time.time() * 1000)}.txt"
        timeout_file.write_text(self.plain_since(since), encoding="utf-8")
        raise TimeoutError(f"{label} timeout: {pattern.pattern}")

    def snapshot(self, label: str) -> Path:
        path = self.out_dir / f"snap-{self.snap_seq:03d}-{label}.txt"
        self.snap_seq += 1
        path.write_text(self.plain(), encoding="utf-8")
        self.record_frame(f"snapshot:{label}")
        sys.stderr.write(f"[snapshot {path}]\n")
        return path

    def record_frame(self, label: str) -> None:
        if not self.sample_frames or self.frame_seq >= self.max_frames:
            return
        plain = self.plain()
        digest = hashlib.sha256(plain.encode("utf-8")).hexdigest()[:12]
        if digest == self.last_frame_hash:
            return
        file_name = f"frame_{self.frame_seq:04d}_{digest}.txt"
        (self.frame_dir / file_name).write_text(plain, encoding="utf-8")
        ts_ms = int((time.time() - self.start_ms) * 1000)
        with self.timeline.open("a", encoding="utf-8") as handle:
            handle.write(f"{self.frame_seq:04d}\t{ts_ms}\t{digest}\t{label}\t{file_name}\n")
        self.frame_seq += 1
        self.last_frame_hash = digest

    def finalise(self) -> None:
        for _ in range(5):
            if not self.drain_once(0.05):
                break
        (self.out_dir / "final.txt").write_text(self.plain(), encoding="utf-8")
        (self.out_dir / "final.raw.txt").write_bytes(bytes(self.buffer))
        self.record_frame("final")

    def shutdown(self) -> int | None:
        try:
            self.send_key("C-c")
            sleep(400)
            self.send_key("C-c")
        except OSError:
            pass
        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                done_pid, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return None
            if done_pid:
                return wait_status_to_exit_code(status)
            self.drain_once(0.1)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.pid, sig)
            except ProcessLookupError:
                pass
            except OSError:
                try:
                    os.kill(self.pid, sig)
                except ProcessLookupError:
                    pass
            deadline = time.time() + 1.0
            while time.time() < deadline:
                try:
                    done_pid, status = os.waitpid(self.pid, os.WNOHANG)
                except ChildProcessError:
                    return None
                if done_pid:
                    return wait_status_to_exit_code(status)
                sleep(100)
        return None


def wait_status_to_exit_code(status: int) -> int | None:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return None


def spawn_tui(cols: int, rows: int) -> tuple[int, int]:
    env_vars = os.environ.copy()
    env_vars.setdefault("DISABLE_INSTALLATION_CHECKS", "1")
    env_vars.setdefault("UMMAYA_TUI_LOG_LEVEL", "DEBUG")
    env_vars.setdefault("OTEL_SDK_DISABLED", "true")
    env_vars.setdefault("TERM", "xterm-256color")
    env_vars.setdefault("COLUMNS", str(cols))
    env_vars.setdefault("LINES", str(rows))
    env_vars.setdefault("FORCE_COLOR", "0")
    env_vars.setdefault("UMMAYA_FORCE_INTERACTIVE", "1")
    cmd = [
        "bun",
        "--preload",
        "./src/stubs/macro-preload.ts",
        "src/entrypoints/cli.tsx",
    ]

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(TUI_DIR)
        os.execvpe(cmd[0], cmd, env_vars)  # noqa: S606
    set_winsize(fd, rows, cols)
    os.set_blocking(fd, False)
    return pid, fd


def send_decision_path(harness: Harness, path: str, feedback: str) -> None:
    if path in {
        "Down+Enter",
        "Down+Down+Enter",
        "Down+Down+Tab+Text+Enter",
        "Down+Down+Tab+Text+Tab+Enter",
    }:
        harness.send_key("Down")
        sleep(150)
    if path in {
        "Down+Down+Enter",
        "Down+Down+Tab+Text+Enter",
        "Down+Down+Tab+Text+Tab+Enter",
    }:
        harness.send_key("Down")
        sleep(150)
    if path in {
        "Tab+Text+Enter",
        "Tab+Text+Tab+Enter",
        "Down+Down+Tab+Text+Enter",
        "Down+Down+Tab+Text+Tab+Enter",
    }:
        harness.send_key("Tab")
        sleep(300)
        if feedback:
            harness.send_text(feedback)
            sleep(300)
            if path in {"Tab+Text+Tab+Enter", "Down+Down+Tab+Text+Tab+Enter"}:
                harness.send_key("Tab")
                sleep(200)
    harness.send_key("Enter")


def run_capture(out_dir: Path) -> int:
    prompt = env("UMMAYA_REALUSE_PROMPT")
    if not prompt:
        raise ValueError("UMMAYA_REALUSE_PROMPT is required")

    cols = int(env("UMMAYA_DEBUG_COLS", "180"))
    rows = int(env("UMMAYA_DEBUG_ROWS", "60"))
    pid, fd = spawn_tui(cols, rows)
    harness = Harness(
        pid=pid,
        fd=fd,
        out_dir=out_dir.resolve(),
        cols=cols,
        rows=rows,
        sample_frames=env("UMMAYA_PTY_SAMPLE_FRAMES", "1") != "0",
        max_frames=int(env("UMMAYA_PTY_MAX_FRAMES", "500")),
        mirror=env("UMMAYA_PY_PTY_MIRROR", "0") == "1",
    )

    scenario_error: BaseException | None = None
    try:
        ready = compile_env_regex("UMMAYA_REALUSE_READY_REGEX", "UMMAYA|❯")
        observe = compile_env_regex(
            "UMMAYA_REALUSE_OBSERVE_REGEX",
            "resolve_location|lookup|verify|submit|subscribe|도구 결과|검색 오류|Error",
        )
        result = compile_env_regex(
            "UMMAYA_REALUSE_RESULT_REGEX",
            "⎿|도구 결과|검색 오류|Error|receipt|영수증|결과|완료",
        )
        expand = compile_env_regex(
            "UMMAYA_REALUSE_EXPAND_REGEX",
            "Showing detailed transcript|outbound_traces|request_url|response_status|status_code|응답 envelope|response envelope|adapter_receipt|receipt_id|transaction_id|delegation_context|Error|검색 오류",
        )
        after_decision = compile_env_regex(
            "UMMAYA_REALUSE_AFTER_DECISION_REGEX",
            "receipt|영수증|denied|거부|완료|제출|결과|Error|검색 오류",
        )
        decision_ready_raw = env("UMMAYA_REALUSE_DECISION_READY_REGEX")
        decision_ready = (
            re.compile(decision_ready_raw, re.IGNORECASE | re.MULTILINE)
            if decision_ready_raw
            else re.compile("허용하시겠습니까|권한 요청|Tab to amend|Esc to cancel", re.IGNORECASE | re.MULTILINE)
        )
        final_raw = env("UMMAYA_REALUSE_FINAL_REGEX")
        final_regex = (
            re.compile(final_raw, re.IGNORECASE | re.MULTILINE)
            if final_raw
            else None
        )

        harness.wait_for(ready, 60)
        harness.snapshot("boot")

        harness.send_text(prompt)
        after_input = harness.mark()
        harness.send_key("Enter")
        harness.snapshot("input-submitted")

        observe_mark = harness.mark()
        harness.wait_for(
            observe,
            float(env("UMMAYA_REALUSE_OBSERVE_TIMEOUT_SEC", "180")),
            since=after_input,
            label="waitForPaneSince",
        )
        final_search_start = after_input
        should_expand = env("UMMAYA_REALUSE_EXPAND", "1") != "0"
        should_wait_for_result = env(
            "UMMAYA_REALUSE_WAIT_FOR_RESULT",
            "1" if should_expand else "0",
        ) != "0"
        decision_path = env("UMMAYA_REALUSE_DECISION_PATH")
        if (
            not decision_path
            and should_wait_for_result
            and not result.search(harness.plain_since(observe_mark))
        ):
            result_mark = harness.mark()
            harness.wait_for(
                result,
                float(env("UMMAYA_REALUSE_RESULT_TIMEOUT_SEC", "180")),
                since=result_mark,
                label="waitForPaneSince",
            )
            final_search_start = harness.mark()
        harness.snapshot("post-tool-flow")

        if decision_path:
            allowed = {
                "Enter",
                "Down+Enter",
                "Down+Down+Enter",
                "Tab+Text+Enter",
                "Tab+Text+Tab+Enter",
                "Down+Down+Tab+Text+Enter",
                "Down+Down+Tab+Text+Tab+Enter",
            }
            if decision_path not in allowed:
                raise ValueError(f"Unsupported UMMAYA_REALUSE_DECISION_PATH: {decision_path}")
            if decision_ready_raw and not decision_ready.search(harness.plain_since(after_input)):
                harness.wait_for(
                    decision_ready,
                    float(env("UMMAYA_REALUSE_DECISION_READY_TIMEOUT_SEC", "180")),
                    since=harness.mark(),
                    label="waitForPaneSince",
                )
            harness.snapshot("decision-ready")
            after_decision_mark = harness.mark()
            send_decision_path(harness, decision_path, env("UMMAYA_REALUSE_DECISION_FEEDBACK"))
            harness.snapshot(f"decision-{decision_path}")
            harness.wait_for(
                after_decision,
                float(env("UMMAYA_REALUSE_AFTER_DECISION_TIMEOUT_SEC", "120")),
                since=after_decision_mark,
                label="waitForPaneSince",
            )
            final_search_start = after_decision_mark
            harness.snapshot("after-decision")

        if final_regex is not None and not final_regex.search(harness.plain_since(final_search_start)):
            harness.wait_for(
                final_regex,
                float(env("UMMAYA_REALUSE_FINAL_TIMEOUT_SEC", "180")),
                since=final_search_start,
                label="waitForPaneSince",
            )
            harness.snapshot("final-answer-ready")

        if should_expand:
            expand_mark = harness.mark()
            harness.send_key("C-o")
            harness.wait_for(
                expand,
                float(env("UMMAYA_REALUSE_EXPAND_TIMEOUT_SEC", "30")),
                since=expand_mark,
                label="waitForPaneSince",
            )
            harness.snapshot("expanded-tool-detail")
    except BaseException as exc:  # noqa: BLE001
        scenario_error = exc
        sys.stderr.write(f"\n[scenario ERROR] {exc}\n")
    finally:
        harness.finalise()
        exit_code = harness.shutdown()
        try:
            os.close(harness.fd)
        except OSError:
            pass
        sys.stderr.write(f"\n=== captures saved to {harness.out_dir} ===\n")
        if exit_code is not None:
            sys.stderr.write(f"[child exit {exit_code}]\n")
    return 1 if scenario_error else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_capture(args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
