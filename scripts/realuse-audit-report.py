#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Summarize real-use TUI capture artifacts into a local audit report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_FORBIDDEN = [
    r"Cannot find module",
    r"Traceback \(most recent call last\)",
    r"Unhandled(?:Promise)?Rejection",
    r"\bTypeError:",
    r"\bReferenceError:",
    r"permission_timeout",
    r"auth_required",
    r"인증 거부",
    r"요청 시간 초과",
    r"인증 시스템.{0,20}오류",
    r"네트워크 오류",
    r"활성 부처 에이전트",
    r"\b0 agents\b",
]

TEXT_SUFFIXES = {".txt", ".tsv", ".md", ".jsonl", ".log"}
MAX_FILE_BYTES = 1_000_000
DISPLAY_TOOL_ALIASES = {
    "find": "lookup",
    "locate": "resolve_location",
    "send": "submit",
    "auth": "verify",
    "watch": "subscribe",
}
_TOOL_NAME_PATTERN = "|".join(
    [
        "resolve_location",
        "lookup",
        "submit",
        "verify",
        "subscribe",
        *DISPLAY_TOOL_ALIASES,
    ]
)
TOOL_CALL_RE = re.compile(rf"(?:⏺|●)\s*({_TOOL_NAME_PATTERN})\(([^)]*)\)")
SPECULATIVE_AVAILABILITY_RE = re.compile(
    r"(운영\s*가능성|야간\s*진료\s*가능|진료\s*가능|현재\s*진료\s*중|"
    r"가능성.{0,20}(병원|응급실|진료)|"
    r"(병원|응급실|진료|운영).{0,20}가능성|24\s*시간\s*운영)"
)
UNSUPPORTED_INSURANCE_RE = re.compile(
    r"건강보험\s*적용|"
    r"(본인\s*부담|실비|진료비).{0,40}"
    r"(약\s*)?\d+(?:\.\d+)?\s*(?:[-~]\s*\d+(?:\.\d+)?)?\s*(?:%|퍼센트)"
)
UNSUPPORTED_MEDICAL_ADVICE_RE = re.compile(
    r"((?<![A-Za-z0-9])39\s*(?:°\s*)?C(?![A-Za-z0-9])|"
    r"39\s*도|해열제|수분\s*공급|의식이\s*흐려)"
)
OPEN_PERMISSION_MODAL_RE = re.compile(
    r"Do you want to proceed\?|Esc to cancel · Tab to amend|권한 요청|허용하시겠습니까"
)
ACTIVE_SPINNER_RE = re.compile(
    r"^\s*[^\w\s]\s+[A-Za-z][A-Za-z'’\-/]*…\s+\(\d+(?:ms|s|m|h)"
)
VISIBLE_TOOL_EVIDENCE_RE = re.compile(
    r"(?:⎿|검증 결과:|record\s+—|collection\s+—|처리:|접수 번호:|상태:|"
    r"반려 사유:|납부 단계:)"
)
REJECTED_SUBMIT_EVIDENCE_RE = re.compile(
    r"(?:상태:\s*(?:반려됨|실패|rejected|failed)|"
    r"모의 제출 반려|제출이 반려되었습니다|반려 사유:)"
)


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    argument: str
    path: str
    line: int
    evidence: str = ""

    @property
    def normalized(self) -> str:
        return f"{self.name}({self.argument.strip()})"

    @property
    def retry_signature(self) -> str:
        if not self.evidence:
            return self.normalized
        return f"{self.normalized} => {self.evidence}"


def canonical_tool_name(name: str) -> str:
    return DISPLAY_TOOL_ALIASES.get(name, name)


@dataclass(frozen=True)
class AuditReport:
    root: str
    status: str
    files_scanned: int
    frame_count: int
    findings: list[Finding]
    tool_calls: list[ToolCall]


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
    return files


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def count_frames(root: Path) -> int:
    timeline = root / "frames" / "timeline.tsv"
    if not timeline.exists():
        return 0
    lines = read_lines(timeline)
    return max(0, len(lines) - 1)


def scan_patterns(
    root: Path,
    files: list[Path],
    expected: list[str],
    forbidden: list[str],
) -> list[Finding]:
    findings: list[Finding] = []
    forbidden_res = [(pattern, re.compile(pattern)) for pattern in forbidden]
    expected_res = [(pattern, re.compile(pattern)) for pattern in expected]
    expected_hits: dict[str, bool] = dict.fromkeys(expected, False)

    for path in files:
        rel = str(path.relative_to(root))
        for line_no, line in enumerate(read_lines(path), start=1):
            for pattern, regex in forbidden_res:
                if regex.search(line):
                    findings.append(
                        Finding(
                            severity="error",
                            category="forbidden_pattern",
                            path=rel,
                            line=line_no,
                            message=pattern,
                        )
                    )
            for pattern, regex in expected_res:
                if regex.search(line):
                    expected_hits[pattern] = True

    for pattern, seen in expected_hits.items():
        if not seen:
            findings.append(
                Finding(
                    severity="error",
                    category="missing_expected_pattern",
                    path=".",
                    line=0,
                    message=pattern,
                )
            )

    return findings


def scan_final_ui_state(root: Path, files: list[Path]) -> list[Finding]:
    """Fail captures that end while a modal or spinner is still active.

    Historical scrollback can legitimately contain old permission prompts, so
    this check only reads current-viewport artifacts (`final.txt` and stable
    snapshots). This catches the false-pass class where the first tool call was
    rendered but the user-facing turn never actually completed.
    """
    findings: list[Finding] = []
    final_state_files = [
        path
        for path in files
        if path.name == "final.txt"
        or path.name.endswith("-stable.txt")
        or path.name.endswith("-forbidden-pattern.txt")
    ]
    for path in final_state_files:
        rel = str(path.relative_to(root))
        for line_no, line in enumerate(read_lines(path), start=1):
            if OPEN_PERMISSION_MODAL_RE.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        category="ui_flow",
                        path=rel,
                        line=line_no,
                        message="capture ended with an active permission prompt",
                    )
                )
            if ACTIVE_SPINNER_RE.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        category="paint_flow",
                        path=rel,
                        line=line_no,
                        message="capture ended with an active reasoning/tool spinner",
                    )
                )
    return findings


def collect_tool_calls(root: Path, files: list[Path]) -> list[ToolCall]:
    canonical_files = [
        path
        for path in files
        if path.name == "final-scrollback.txt"
        or path.name.endswith("-post-settle-scrollback.txt")
        or path.name.endswith("-final-scrollback.txt")
    ]
    if not canonical_files:
        canonical_files = [path for path in files if path.name == "final.txt"]

    calls = collect_tool_calls_from_files(root, canonical_files)
    if calls:
        return calls

    # Final viewport snapshots can lose transient tool progress when a later
    # backend error clears or replaces the scrollback. Fall back to sampled
    # scrollback snapshots and merge only the newly-visible suffix from each
    # snapshot so a persistent line is not counted once per frame.
    sampled_scrollback = [
        path
        for path in files
        if "frames" not in path.parts and path.name.endswith("-scrollback.txt")
    ]
    calls = collect_tool_call_sequence_delta(root, sampled_scrollback)
    if calls:
        return calls

    frame_files = frame_files_in_timeline_order(root, files)
    return collect_tool_call_sequence_delta(root, frame_files)


def collect_tool_calls_from_files(root: Path, scan_files: list[Path]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for path in scan_files:
        rel = str(path.relative_to(root))
        lines = read_lines(path)
        for line_no, line in enumerate(lines, start=1):
            for match in TOOL_CALL_RE.finditer(line):
                calls.append(
                    ToolCall(
                        name=canonical_tool_name(match.group(1)),
                        argument=match.group(2),
                        path=rel,
                        line=line_no,
                        evidence=visible_evidence_after_call(lines, line_no - 1),
                    )
                )
    return calls


def collect_tool_call_sequence_delta(root: Path, scan_files: list[Path]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    previous_snapshot: list[str] = []

    for path in scan_files:
        snapshot_calls = collect_tool_calls_from_files(root, [path])
        snapshot_keys = [call.normalized for call in snapshot_calls]
        prefix_len = 0
        max_prefix = min(len(previous_snapshot), len(snapshot_keys))
        while (
            prefix_len < max_prefix
            and previous_snapshot[prefix_len] == snapshot_keys[prefix_len]
        ):
            prefix_len += 1
        calls.extend(snapshot_calls[prefix_len:])
        previous_snapshot = snapshot_keys

    return calls


def frame_files_in_timeline_order(root: Path, files: list[Path]) -> list[Path]:
    timeline = root / "frames" / "timeline.tsv"
    if not timeline.exists():
        return sorted(path for path in files if "frames" in path.parts and path.suffix == ".txt")

    ordered: list[Path] = []
    for line in read_lines(timeline)[1:]:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        frame_path = timeline.parent / parts[3]
        if frame_path.exists():
            ordered.append(frame_path)
    return ordered


def visible_evidence_after_call(lines: list[str], start_index: int) -> str:
    """Return the user-visible result facts immediately following a tool call."""
    evidence: list[str] = []
    for line in lines[start_index + 1 : start_index + 10]:
        if TOOL_CALL_RE.search(line):
            break
        stripped = " ".join(line.strip().split())
        if not stripped:
            continue
        if stripped.startswith("✻ Baked") or stripped.startswith("─"):
            break
        if VISIBLE_TOOL_EVIDENCE_RE.search(stripped):
            evidence.append(stripped)
        if len(evidence) >= 4:
            break
    return " | ".join(evidence)


def _extract_jsonish_query(argument: str) -> str:
    try:
        decoded = json.loads(argument)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, dict):
        value = decoded.get("query")
        return value.strip() if isinstance(value, str) else ""
    match = re.search(r'"query"\s*:\s*"([^"]+)"', argument)
    if match:
        return match.group(1).strip()
    return argument.strip()


@lru_cache(maxsize=1)
def _audit_registry() -> object | None:
    try:
        from kosmos.tools.executor import ToolExecutor
        from kosmos.tools.register_all import register_all_tools
        from kosmos.tools.registry import ToolRegistry

        registry = ToolRegistry()
        executor = ToolExecutor(registry=registry)
        register_all_tools(registry, executor)
        return registry
    except Exception:
        return None


def _resolve_query_prefers_non_location_adapter(query: str) -> bool:
    if not query:
        return False
    registry = _audit_registry()
    if registry is None:
        return False
    try:
        from kosmos.tools.search import search

        candidates = search(
            query=query,
            bm25_index=registry.bm25_index,
            registry=registry,
            top_k=5,
        )
    except Exception:
        return False
    positive = [candidate for candidate in candidates if candidate.score > 0]
    if not positive:
        return False
    top_score = positive[0].score
    for candidate in positive:
        if candidate.tool_id == "resolve_location" and candidate.score >= top_score - 1e-9:
            return False
    return positive[0].tool_id != "resolve_location"


def scan_tool_semantics(calls: list[ToolCall]) -> list[Finding]:
    findings: list[Finding] = []
    for call in calls:
        query = _extract_jsonish_query(call.argument)
        if call.name == "resolve_location" and _resolve_query_prefers_non_location_adapter(query):
            findings.append(
                Finding(
                    severity="error",
                    category="tool_arbitration",
                    path=call.path,
                    line=call.line,
                    message=(
                        "resolve_location was used for a non-geographic service "
                        f"or agency name according to registry retrieval: {query}"
                    ),
                )
            )
    return findings


def scan_tool_flow(calls: list[ToolCall]) -> list[Finding]:
    findings: list[Finding] = []
    previous = ""
    repeat_count = 1

    for call in calls:
        current = call.retry_signature
        if current == previous:
            repeat_count += 1
            if repeat_count == 2:
                findings.append(
                    Finding(
                        severity="warn",
                        category="tool_retry_drift",
                        path=call.path,
                        line=call.line,
                        message=f"same tool call repeated without visible new evidence: {current}",
                    )
                )
        else:
            previous = current
            repeat_count = 1

    return findings


def scan_rejected_submit_results(calls: list[ToolCall]) -> list[Finding]:
    findings: list[Finding] = []
    for call in calls:
        if call.name != "submit":
            continue
        if not REJECTED_SUBMIT_EVIDENCE_RE.search(call.evidence):
            continue
        findings.append(
            Finding(
                severity="error",
                category="tool_result",
                path=call.path,
                line=call.line,
                message=(
                    "submit rendered a rejected or failed result; it must not "
                    "satisfy the expected real-use chain"
                ),
            )
        )
    return findings


def scan_zero_result_retries(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    canonical_files = [
        path
        for path in files
        if path.name == "final-scrollback.txt"
        or path.name.endswith("-post-settle-scrollback.txt")
        or path.name.endswith("-final-scrollback.txt")
        or path.name == "final.txt"
    ]
    for path in canonical_files:
        rel = str(path.relative_to(root))
        previous_zero_tool: str | None = None
        pending_tool: tuple[str, int] | None = None
        for line_no, line in enumerate(read_lines(path), start=1):
            call_match = TOOL_CALL_RE.search(line)
            if call_match:
                tool_key = f"{call_match.group(1)}({call_match.group(2).strip()})"
                if previous_zero_tool == tool_key:
                    findings.append(
                        Finding(
                            severity="error",
                            category="tool_retry_drift",
                            path=rel,
                            line=line_no,
                            message=(
                                "tool was called again immediately after a zero-result "
                                f"response: {tool_key}"
                            ),
                        )
                    )
                pending_tool = (tool_key, line_no)
                continue
            if pending_tool and re.search(r"collection\s+—\s+0건", line):
                previous_zero_tool = pending_tool[0]
                pending_tool = None
            elif pending_tool and "⎿" in line:
                previous_zero_tool = None
                pending_tool = None
    return findings


def scan_grounding(root: Path, files: list[Path], calls: list[ToolCall]) -> list[Finding]:
    findings: list[Finding] = []
    called_args = " ".join(call.argument.lower() for call in calls)
    has_insurance_source = "nhis" in called_args or "health_insurance" in called_args
    canonical_files = [
        path
        for path in files
        if path.name == "final-scrollback.txt"
        or path.name.endswith("-post-settle-scrollback.txt")
        or path.name.endswith("-final-scrollback.txt")
        or path.name == "final.txt"
    ]
    for path in canonical_files:
        rel = str(path.relative_to(root))
        for line_no, line in enumerate(read_lines(path), start=1):
            if SPECULATIVE_AVAILABILITY_RE.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        category="unsupported_grounding",
                        path=rel,
                        line=line_no,
                        message=(
                            "answer upgrades a registry record into availability/status "
                            "without a tool-provided field"
                        ),
                    )
                )
            if not has_insurance_source and UNSUPPORTED_INSURANCE_RE.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        category="unsupported_grounding",
                        path=rel,
                        line=line_no,
                        message=(
                            "answer gives insurance/payment percentages without an "
                            "insurance-domain tool result"
                        ),
                    )
                )
            if UNSUPPORTED_MEDICAL_ADVICE_RE.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        category="unsupported_grounding",
                        path=rel,
                        line=line_no,
                        message=(
                            "answer gives medical triage or treatment advice "
                            "without a guideline-domain tool result"
                        ),
                    )
                )
    return findings


def scan_required_first_tool(
    calls: list[ToolCall],
    required_first_tool: str | None,
) -> list[Finding]:
    if not required_first_tool:
        return []
    if not calls:
        return [
            Finding(
                severity="error",
                category="tool_flow",
                path=".",
                line=0,
                message=f"expected first tool {required_first_tool!r}, but no tool call rendered",
            )
        ]
    first = calls[0]
    if first.name == required_first_tool:
        return []
    return [
        Finding(
            severity="error",
            category="tool_flow",
            path=first.path,
            line=first.line,
            message=f"expected first tool {required_first_tool!r}, got {first.name!r}",
        )
    ]


def scan_required_tool_chain(
    calls: list[ToolCall],
    required_tool_chain: list[str],
) -> list[Finding]:
    """Require a scenario's expected primitive sequence as an ordered subsequence."""
    if not required_tool_chain:
        return []

    call_index = 0
    for required in required_tool_chain:
        while call_index < len(calls) and calls[call_index].name != required:
            call_index += 1
        if call_index >= len(calls):
            observed = " -> ".join(call.name for call in calls) or "<none>"
            return [
                Finding(
                    severity="error",
                    category="tool_flow",
                    path=".",
                    line=0,
                    message=(
                        "expected ordered tool chain "
                        f"{' -> '.join(required_tool_chain)!r}, observed {observed!r}"
                    ),
                )
            ]
        call_index += 1

    return []


def render_markdown(report: AuditReport) -> str:
    lines = [
        "# Real-Use Audit Report",
        "",
        f"- Root: `{report.root}`",
        f"- Status: `{report.status}`",
        f"- Files scanned: `{report.files_scanned}`",
        f"- Distinct sampled frames: `{report.frame_count}`",
        f"- Tool calls observed: `{len(report.tool_calls)}`",
        "",
    ]
    if report.findings:
        lines.append("## Findings")
        lines.append("")
        for finding in report.findings:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            lines.append(
                f"- `{finding.severity}` `{finding.category}` {location} — {finding.message}"
            )
        lines.append("")
    if report.tool_calls:
        lines.append("## Tool Calls")
        lines.append("")
        for call in report.tool_calls:
            suffix = f" — {call.evidence}" if call.evidence else ""
            lines.append(
                f"- `{call.name}` {call.path}:{call.line} "
                f"`{call.argument.strip()}`{suffix}"
            )
        lines.append("")
    return "\n".join(lines)


def build_report(
    root: Path,
    expected: list[str],
    forbidden: list[str],
    required_first_tool: str | None,
    required_tool_chain: list[str],
) -> AuditReport:
    files = iter_text_files(root)
    findings = scan_patterns(root, files, expected, forbidden)
    findings.extend(scan_final_ui_state(root, files))
    calls = collect_tool_calls(root, files)
    findings.extend(scan_tool_semantics(calls))
    findings.extend(scan_required_first_tool(calls, required_first_tool))
    findings.extend(scan_required_tool_chain(calls, required_tool_chain))
    findings.extend(scan_tool_flow(calls))
    findings.extend(scan_rejected_submit_results(calls))
    findings.extend(scan_zero_result_retries(root, files))
    findings.extend(scan_grounding(root, files, calls))
    status = "fail" if any(item.severity == "error" for item in findings) else "pass"
    return AuditReport(
        root=str(root),
        status=status,
        files_scanned=len(files),
        frame_count=count_frames(root),
        findings=findings,
        tool_calls=calls,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expect", action="append", default=[])
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument(
        "--require-first-tool",
        choices=["lookup", "resolve_location", "submit", "verify", "subscribe"],
        default=None,
    )
    parser.add_argument(
        "--require-tool-chain",
        default="",
        help="Comma-separated ordered primitive sequence expected for the scenario.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        sys.stderr.write(f"realuse-audit-report: not a directory: {root}\n")
        return 2

    forbidden = [*DEFAULT_FORBIDDEN, *args.forbid]
    required_tool_chain = [
        canonical_tool_name(item.strip())
        for item in args.require_tool_chain.split(",")
        if item.strip()
    ]
    report = build_report(
        root,
        args.expect,
        forbidden,
        args.require_first_tool,
        required_tool_chain,
    )
    markdown = render_markdown(report)

    if args.write:
        (root / "audit.md").write_text(markdown, encoding="utf-8")
        (root / "audit.json").write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.json:
        sys.stdout.write(json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(markdown + "\n")

    return 1 if report.status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
