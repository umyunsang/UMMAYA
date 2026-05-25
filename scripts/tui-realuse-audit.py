#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit real-use TUI captures for agentic-flow regressions.

This script grades the artifacts produced by ``scripts/bun-pty-capture.ts`` or
``scripts/tui-tmux-capture.sh``. It intentionally evaluates the whole captured
trajectory, not only ``final.txt``: the failure class that triggered this gate
was a recoverable tool-parameter error that rendered like a normal result and
then terminated the agent loop.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

ERROR_PATTERNS = (
    r"Invalid parameters",
    r"InputValidationError",
    r"검색 오류",
    r"Tool execution failed",
    r"chain_prerequisite_missing",
    r"chain_followup_missing",
    r"Error:",
)
RAW_PROTOCOL_PATTERNS = (
    r'\{"version":"1\.0"',
    r'"correlation_id"\s*:',
    r'"frame_seq"\s*:',
)
TRACE_PATTERNS = (
    r"outbound_traces",
    r"request_url",
    r"response_status",
    r"status_code",
    r"응답 envelope",
    r"response envelope",
    r"adapter_receipt",
    r"receipt_id",
    r"transaction_id",
    r"delegation_context",
    r"\bmethod\b",
    r"\burl\b",
    r"trace_id",
    r"correlation_id",
)
EXPANDED_PERMISSION_DENIAL_PATTERNS = (
    r"permission_denied|permission_timeout",
    r"Showing detailed transcript",
    r"응답 envelope|response envelope|\"ok\"\s*:\s*false",
)
BACKEND_LOG_ABNORMAL_PATTERNS = (
    ("opentelemetry_context_detach", r"Failed to detach context"),
    ("python_traceback", r"Traceback \(most recent call last\):"),
    ("otel_context_token_mismatch", r"ValueError: <Token var=<ContextVar name='current_context'"),
    ("adapter_validation_error", r"adapter invocation failed .*ValidationError|Field required"),
)
VISIBLE_ABNORMAL_FLOW_PATTERNS = (
    ("verify_tool_choice_mismatch", r"verify_tool_choice_mismatch"),
    ("sensitive_lookup_auth_required", r"auth_required|Sensitive lookup auth prerequisite"),
    ("unknown_tool", r"Unknown tool|unknown_tool"),
    ("adapter_validation_error", r"ValidationError|Field required"),
)
SUBMIT_LEDGER_TOOL_ID_RE = re.compile(
    r"\b(?:mock_submit_[a-z0-9_]+|mock_[a-z0-9_]*_submit_v1|mock_traffic_fine_pay_v1)\b"
)
RED_ANSI_RE = re.compile(
    r"\x1b\[(?:[0-9;]*;)?(?:31|91|38;5;196|38;5;160|38;2;[0-9;]+)m"
)
PROVIDER_ABORT_RE = re.compile(
    r"API\s*Error\s*:\s*The\s*operation\s*was\s*aborted\.?|APIError:Theoperationwasaborted\.?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    details: str
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaptureFile:
    path: str
    text: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def collect_capture_files(capture_dir: Path) -> list[CaptureFile]:
    names: set[Path] = set()
    for pattern in (
        "snap-*.txt",
        "snap-*-scrollback.txt",
        "final.txt",
        "final.raw.txt",
        "*.ascii",
        "*.txt",
        "frames/*.txt",
    ):
        names.update(capture_dir.glob(pattern))

    skipped = {"audit.md", "audit.json"}
    files: list[CaptureFile] = []
    for path in sorted(names):
        if path.name in skipped or path.is_dir():
            continue
        files.append(CaptureFile(path=str(path.relative_to(capture_dir)), text=read_text(path)))
    return files


def compile_patterns(patterns: Sequence[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in patterns]


def find_first(files: Sequence[CaptureFile], pattern: re.Pattern[str]) -> tuple[int, str] | None:
    for index, file in enumerate(files):
        if pattern.search(file.text):
            return index, file.path
    return None


def find_chain_in_text(text: str, expected_chain: Sequence[str]) -> bool:
    """Return True when all chain tokens appear in order inside one snapshot."""
    offset = 0
    for token in expected_chain:
        pattern = re.compile(token, re.IGNORECASE | re.MULTILINE)
        match = pattern.search(text, offset)
        if match is None:
            return False
        offset = match.end()
    return True


def has_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def check_capture_completeness(files: Sequence[CaptureFile], strict_frames: bool) -> CheckResult:
    frame_count = sum(1 for file in files if file.path.startswith("frames/frame_"))
    snap_count = sum(1 for file in files if file.path.startswith("snap-"))
    has_final = any(file.path == "final.txt" for file in files)

    if not has_final:
        return CheckResult(
            name="capture_completeness",
            status="fail",
            details="final.txt is missing; the run cannot be audited.",
        )

    if strict_frames and frame_count < 2:
        return CheckResult(
            name="capture_completeness",
            status="fail",
            details="Strict mode requires at least two distinct frame snapshots.",
            evidence=[f"frames={frame_count}", f"snapshots={snap_count}"],
        )

    if frame_count == 0 and snap_count == 0:
        return CheckResult(
            name="capture_completeness",
            status="warn",
            details=(
                "No intermediate frames or snapshots were found; this is "
                "vulnerable to final-state fallacy."
            ),
        )

    return CheckResult(
        name="capture_completeness",
        status="pass",
        details="Capture contains final state and intermediate artifacts.",
        evidence=[f"frames={frame_count}", f"snapshots={snap_count}"],
    )


def check_replacement_character(files: Sequence[CaptureFile]) -> CheckResult:
    cooked_text = "\n".join(file.text for file in files if not file.path.endswith(".raw.txt"))
    if "\ufffd" in cooked_text:
        return CheckResult(
            name="utf8_replacement_character",
            status="fail",
            details=(
                "Captured text contains U+FFFD replacement characters, which "
                "means the TUI render or capture path corrupted terminal text."
            ),
        )

    return CheckResult(
        name="utf8_replacement_character",
        status="pass",
        details="No UTF-8 replacement characters were found in captured text.",
    )


def check_backend_log_health(capture_dir: Path) -> CheckResult:
    backend_log = capture_dir / "backend.log"
    if not backend_log.exists():
        return CheckResult(
            name="backend_log_health",
            status="warn",
            details="backend.log is missing; backend exception health could not be audited.",
        )

    text = read_text(backend_log)
    matches = [
        label
        for label, pattern in BACKEND_LOG_ABNORMAL_PATTERNS
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    ]
    if matches:
        return CheckResult(
            name="backend_log_health",
            status="fail",
            details=(
                "backend.log contains traceback or OpenTelemetry context errors. "
                "The capture is not packaging-ready even if the citizen-visible flow passed."
            ),
            evidence=matches,
        )

    return CheckResult(
        name="backend_log_health",
        status="pass",
        details="backend.log contains no audited traceback or OpenTelemetry context errors.",
    )


def check_expected_chain(
    files: Sequence[CaptureFile],
    expected_chain: Sequence[str],
) -> CheckResult:
    if not expected_chain:
        return CheckResult(
            name="agentic_chain_order",
            status="pass",
            details="No explicit chain expectation configured.",
        )

    frame_files = [file for file in files if file.path.startswith("frames/frame_")]
    snap_files = [file for file in files if file.path.startswith("snap-")]
    ordered_files = frame_files or snap_files or files

    for index, file in enumerate(ordered_files):
        if find_chain_in_text(file.text, expected_chain):
            return CheckResult(
                name="agentic_chain_order",
                status="pass",
                details="Expected tool chain was visible in order inside one chronological capture.",
                evidence=[f"chain@{index}:{file.path}"],
            )

    positions: list[tuple[str, int, str]] = []
    last_index = -1
    for token in expected_chain:
        pattern = re.compile(token, re.IGNORECASE | re.MULTILINE)
        found = find_first(ordered_files, pattern)
        if found is None:
            return CheckResult(
                name="agentic_chain_order",
                status="fail",
                details=f"Expected chain token was never observed: {token}",
                evidence=[item for item, _, _ in positions],
            )
        index, path = found
        positions.append((token, index, path))
        if index < last_index:
            return CheckResult(
                name="agentic_chain_order",
                status="fail",
                details=f"Expected chain order regressed at token: {token}",
                evidence=[f"{tok}@{idx}:{path}" for tok, idx, path in positions],
            )
        last_index = index

    return CheckResult(
        name="agentic_chain_order",
        status="pass",
        details="Expected tool chain was visible in chronological captures.",
        evidence=[f"{tok}@{idx}:{path}" for tok, idx, path in positions],
    )


def _expected_submit_tool_ids(expected_chain: Sequence[str]) -> list[str]:
    tool_ids: list[str] = []
    for token in expected_chain:
        for match in SUBMIT_LEDGER_TOOL_ID_RE.finditer(token):
            tool_id = match.group(0)
            if tool_id not in tool_ids:
                tool_ids.append(tool_id)
    return tool_ids


def check_expected_submit_ledgers(
    capture_dir: Path,
    expected_chain: Sequence[str],
) -> CheckResult:
    tool_ids = _expected_submit_tool_ids(expected_chain)
    if not tool_ids:
        return CheckResult(
            name="submit_ledger_evidence",
            status="pass",
            details="No submit adapter ledger evidence is required for this scenario.",
        )

    backend_log = capture_dir / "backend.log"
    if not backend_log.exists():
        return CheckResult(
            name="submit_ledger_evidence",
            status="fail",
            details="backend.log is missing; submit adapter execution cannot be proven.",
            evidence=tool_ids,
        )

    text = read_text(backend_log)
    missing = [
        tool_id
        for tool_id in tool_ids
        if not re.search(
            rf"Ledger record appended:.*tool_id={re.escape(tool_id)}\b",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
    ]
    if missing:
        return CheckResult(
            name="submit_ledger_evidence",
            status="fail",
            details=(
                "Expected submit adapter text was visible, but backend.log did "
                "not prove the irreversible mock submit ran. Search-result "
                "candidate text is not sufficient evidence."
            ),
            evidence=missing,
        )

    return CheckResult(
        name="submit_ledger_evidence",
        status="pass",
        details="Every expected submit adapter has a backend ledger append event.",
        evidence=tool_ids,
    )


def check_premature_terminal_error(files: Sequence[CaptureFile], text: str) -> CheckResult:
    has_invalid_params = bool(
        re.search(r"Invalid parameters|Missing .*lat|Missing .*lon|검색 오류", text, re.I)
    )
    if not has_invalid_params:
        return CheckResult(
            name="recoverable_error_loop",
            status="pass",
            details="No recoverable invalid-parameter error was visible.",
        )

    saw_resolve = has_any((r"locate",), text)
    saw_lookup_after_resolve = False
    resolve_index = next(
        (
            index
            for index, file in enumerate(files)
            if re.search(r"locate", file.text, re.I)
        ),
        None,
    )
    if resolve_index is not None:
        saw_lookup_after_resolve = any(
            re.search(r"lookup|find\(|kma_forecast_fetch|nmc_emergency_search", file.text, re.I)
            for file in files[resolve_index + 1 :]
        )

    if not saw_resolve or not saw_lookup_after_resolve:
        return CheckResult(
            name="recoverable_error_loop",
            status="fail",
            details=(
                "A recoverable missing-parameter error reached the user without a visible "
                "resolve_location -> lookup retry path."
            ),
            evidence=[
                f"saw_resolve={saw_resolve}",
                f"saw_lookup_after_resolve={saw_lookup_after_resolve}",
            ],
        )

    return CheckResult(
        name="recoverable_error_loop",
        status="pass",
        details="Recoverable location-parameter error was followed by a visible retry path.",
    )


def check_visible_abnormal_flow(text: str) -> CheckResult:
    """Fail avoidable recovery artifacts that stayed visible in a happy path."""
    matches = [
        label
        for label, pattern in VISIBLE_ABNORMAL_FLOW_PATTERNS
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    ]
    if matches:
        return CheckResult(
            name="visible_abnormal_flow",
            status="fail",
            details=(
                "The capture contains avoidable tool-selection recovery artifacts. "
                "A correct final answer after retry does not make this packaging-ready."
            ),
            evidence=matches,
        )

    return CheckResult(
        name="visible_abnormal_flow",
        status="pass",
        details="No audited avoidable tool-selection recovery artifact was visible.",
    )


def check_error_rendering(
    files: Sequence[CaptureFile],
    text: str,
    require_error_rendering: bool,
) -> CheckResult:
    tool_error_text = PROVIDER_ABORT_RE.sub("", text)
    has_error = has_any(ERROR_PATTERNS, tool_error_text)
    if not has_error and not require_error_rendering:
        return CheckResult(
            name="cc_error_rendering",
            status="pass",
            details="No tool error was visible in this capture.",
        )

    raw_text = "\n".join(file.text for file in files if file.path.endswith(".raw.txt"))
    has_red = bool(raw_text and RED_ANSI_RE.search(raw_text))
    has_ctrl_o_hint = bool(re.search(r"ctrl\+o|Ctrl\+O|to see all|expand", text, re.I))

    if has_error and raw_text and not has_red:
        return CheckResult(
            name="cc_error_rendering",
            status="fail",
            details=(
                "Tool error text was visible, but raw PTY output did not "
                "contain an ANSI red/error style."
            ),
            evidence=[f"ctrl_o_hint={has_ctrl_o_hint}"],
        )

    if require_error_rendering and not has_error:
        return CheckResult(
            name="cc_error_rendering",
            status="fail",
            details=(
                "The scenario expected an error-rendering assertion, but no "
                "error text was found."
            ),
        )

    if has_error:
        status = "pass" if has_red or not raw_text else "warn"
        details = (
            "Tool error was visible and raw ANSI color evidence was present."
            if has_red
            else "Tool error was visible; no raw PTY file was available to prove red/error color."
        )
        return CheckResult(
            name="cc_error_rendering",
            status=status,
            details=details,
            evidence=[f"raw_available={bool(raw_text)}", f"ctrl_o_hint={has_ctrl_o_hint}"],
        )

    return CheckResult(
        name="cc_error_rendering",
        status="pass",
        details="No tool error was visible in this capture.",
    )


def check_expanded_trace(text: str, require_expanded_trace: bool) -> CheckResult:
    has_trace = has_any(TRACE_PATTERNS, text)
    has_permission_denial_detail = all(
        re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        for pattern in EXPANDED_PERMISSION_DENIAL_PATTERNS
    )
    if require_expanded_trace and not has_trace and has_permission_denial_detail:
        return CheckResult(
            name="expanded_tool_trace",
            status="pass",
            details=(
                "Expanded permission-denial details were visible; no outbound "
                "request trace is expected after a terminal deny/timeout."
            ),
        )
    if require_expanded_trace and not has_trace:
        return CheckResult(
            name="expanded_tool_trace",
            status="fail",
            details=(
                "Expanded tool details were required, but no live trace, "
                "mock response envelope, receipt, or delegation evidence was visible."
            ),
        )

    return CheckResult(
        name="expanded_tool_trace",
        status="pass" if has_trace or not require_expanded_trace else "fail",
        details=(
            "Tool trace details were visible."
            if has_trace
            else "Expanded tool trace was not required for this run."
        ),
    )


def check_rejected_submit(text: str, allow_rejected: bool) -> CheckResult:
    """Fail happy-path captures where a submit result ended as rejected."""
    match = re.search(
        r'"status"\s*:\s*"rejected".{0,800}?(?:"reason"\s*:\s*"(?P<reason>[^"]+)")?',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return CheckResult(
            name="submit_rejected_status",
            status="pass",
            details="No rejected submit status was visible.",
        )
    if allow_rejected:
        return CheckResult(
            name="submit_rejected_status",
            status="pass",
            details="Rejected submit status was allowed for this scenario.",
        )
    reason = match.groupdict().get("reason") or "reason not captured"
    return CheckResult(
        name="submit_rejected_status",
        status="fail",
        details=(
            "A send primitive returned status='rejected'. This is an "
            "abnormal terminal flow for a happy-path scenario."
        ),
        evidence=[reason[:240]],
    )


def check_raw_protocol_leak(text: str) -> CheckResult:
    if has_any(RAW_PROTOCOL_PATTERNS, text):
        return CheckResult(
            name="raw_protocol_leak",
            status="fail",
            details="Raw IPC JSON appears in the citizen-visible terminal capture.",
        )

    return CheckResult(
        name="raw_protocol_leak",
        status="pass",
        details="No raw IPC frame leak was detected in captured text.",
    )


def check_require_forbid(
    text: str,
    required: Sequence[str],
    forbidden: Sequence[str],
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for pattern in required:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            checks.append(
                CheckResult(
                    "require_regex",
                    "pass",
                    f"Required regex matched: {pattern}",
                )
            )
        else:
            checks.append(
                CheckResult(
                    "require_regex",
                    "fail",
                    f"Required regex missing: {pattern}",
                )
            )

    for pattern in forbidden:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            checks.append(
                CheckResult(
                    "forbid_regex",
                    "fail",
                    f"Forbidden regex matched: {pattern}",
                )
            )
        else:
            checks.append(CheckResult("forbid_regex", "pass", f"Forbidden regex absent: {pattern}"))
    return checks


def write_reports(capture_dir: Path, checks: Sequence[CheckResult]) -> dict[str, object]:
    overall = "fail" if any(check.status == "fail" for check in checks) else "pass"
    payload: dict[str, object] = {
        "overall": overall,
        "checks": [asdict(check) for check in checks],
    }
    (capture_dir / "audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = ["# TUI Real-Use Audit", "", f"Overall: **{overall}**", ""]
    for check in checks:
        lines.append(f"## {check.name}: {check.status}")
        lines.append(check.details)
        if check.evidence:
            lines.append("")
            for item in check.evidence:
                lines.append(f"- `{item}`")
        lines.append("")
    (capture_dir / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


def run_audit(
    capture_dir: Path,
    expected_chain: Sequence[str],
    required: Sequence[str],
    forbidden: Sequence[str],
    require_expanded_trace: bool,
    require_error_rendering: bool,
    allow_rejected: bool,
    strict_frames: bool,
) -> dict[str, object]:
    files = collect_capture_files(capture_dir)
    text = "\n".join(file.text for file in files)
    checks: list[CheckResult] = [
        check_capture_completeness(files, strict_frames),
        check_replacement_character(files),
        check_backend_log_health(capture_dir),
        check_expected_chain(files, expected_chain),
        check_expected_submit_ledgers(capture_dir, expected_chain),
        check_premature_terminal_error(files, text),
        check_visible_abnormal_flow(text),
        check_error_rendering(files, text, require_error_rendering),
        check_expanded_trace(text, require_expanded_trace),
        check_rejected_submit(text, allow_rejected),
        check_raw_protocol_leak(text),
    ]
    checks.extend(check_require_forbid(text, required, forbidden))
    return write_reports(capture_dir, checks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument(
        "--expect-chain",
        default="",
        help="Comma-separated regex tokens that must appear in chronological order.",
    )
    parser.add_argument("--require-regex", action="append", default=[])
    parser.add_argument("--forbid-regex", action="append", default=[])
    parser.add_argument("--require-expanded-trace", action="store_true")
    parser.add_argument("--require-error-rendering", action="store_true")
    parser.add_argument("--allow-rejected", action="store_true")
    parser.add_argument("--strict-frames", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    capture_dir = args.capture_dir
    if not capture_dir.is_dir():
        raise SystemExit(f"capture dir not found: {capture_dir}")

    expected_chain = [item.strip() for item in args.expect_chain.split(",") if item.strip()]
    payload = run_audit(
        capture_dir=capture_dir,
        expected_chain=expected_chain,
        required=args.require_regex,
        forbidden=args.forbid_regex,
        require_expanded_trace=args.require_expanded_trace,
        require_error_rendering=args.require_error_rendering,
        allow_rejected=args.allow_rejected,
        strict_frames=args.strict_frames,
    )
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0 if payload["overall"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
