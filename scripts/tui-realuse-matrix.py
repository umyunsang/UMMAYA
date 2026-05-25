#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the UMMAYA real-use TUI scenario matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MATRIX = Path("specs/2773-rollback-debug-infra/scenario-matrix.json")
GENERIC_SCENARIO = Path("specs/2773-rollback-debug-infra/scripts/generic-realuse.bun-pty.ts")
PYTHON_PTY_CAPTURE = Path("scripts/tui-realuse-pty-capture.py")


@dataclass(frozen=True)
class Scenario:
    id: str
    priority: str
    domain: str
    prompt_ko: str
    expected_chain: list[str]
    observe_regex: str
    result_regex: str
    require_expanded_trace: bool
    require_error_rendering: bool
    allow_rejected: bool
    require_regex: list[str]
    forbid_regex: list[str]
    expand: bool
    decision_path: str
    decision_feedback: str
    decision_ready_regex: str
    after_decision_timeout_sec: str
    after_decision_regex: str
    final_regex: str


def load_matrix(path: Path) -> list[Scenario]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[Scenario] = []
    for raw in payload["scenarios"]:
        if not isinstance(raw, dict):
            raise ValueError("scenario entry must be an object")
        scenarios.append(
            Scenario(
                id=str(raw["id"]),
                priority=str(raw.get("priority", "P2")),
                domain=str(raw.get("domain", "unknown")),
                prompt_ko=str(raw["prompt_ko"]),
                expected_chain=[str(item) for item in raw.get("expected_chain", [])],
                observe_regex=str(raw.get("observe_regex", "")),
                result_regex=str(raw.get("result_regex", "")),
                require_expanded_trace=bool(raw.get("require_expanded_trace", False)),
                require_error_rendering=bool(raw.get("require_error_rendering", False)),
                allow_rejected=bool(
                    raw.get("allow_rejected", raw.get("expect_rejected", False))
                ),
                require_regex=[str(item) for item in raw.get("require_regex", [])],
                forbid_regex=[str(item) for item in raw.get("forbid_regex", [])],
                expand=bool(raw.get("expand", True)),
                decision_path=str(raw.get("decision_path", "")),
                decision_feedback=str(raw.get("decision_feedback", "")),
                decision_ready_regex=str(raw.get("decision_ready_regex", "")),
                after_decision_timeout_sec=str(raw.get("after_decision_timeout_sec", "")),
                after_decision_regex=str(raw.get("after_decision_regex", "")),
                final_regex=str(raw.get("final_regex", "")),
            )
        )
    return scenarios


def select_scenarios(
    scenarios: list[Scenario],
    ids: list[str],
    priorities: list[str],
    domains: list[str],
) -> list[Scenario]:
    selected = scenarios
    if ids:
        wanted = set(ids)
        selected = [scenario for scenario in selected if scenario.id in wanted]
    if priorities:
        wanted = set(priorities)
        selected = [scenario for scenario in selected if scenario.priority in wanted]
    if domains:
        wanted = set(domains)
        selected = [scenario for scenario in selected if scenario.domain in wanted]
    return selected


def run_command(command: list[str], env: dict[str, str]) -> int:
    completed = subprocess.run(command, env=env, check=False)  # noqa: S603
    return int(completed.returncode)


def build_scenario_env(scenario: Scenario, out_dir: Path) -> dict[str, str]:
    resolved_out_dir = out_dir.resolve()
    env = os.environ.copy()
    env.update(
        {
            "UMMAYA_REALUSE_PROMPT": scenario.prompt_ko,
            "UMMAYA_REALUSE_OBSERVE_REGEX": scenario.observe_regex,
            "UMMAYA_REALUSE_EXPAND": "1" if scenario.expand else "0",
            "UMMAYA_PTY_SAMPLE_FRAMES": env.get("UMMAYA_PTY_SAMPLE_FRAMES", "1"),
            "UMMAYA_BACKEND_LOG_FILE": str(resolved_out_dir / "backend.log"),
            "UMMAYA_CHAT_REQUEST_DUMP": env.get("UMMAYA_CHAT_REQUEST_DUMP", "1"),
        }
    )
    optional_values = {
        "UMMAYA_REALUSE_DECISION_PATH": scenario.decision_path,
        "UMMAYA_REALUSE_DECISION_FEEDBACK": scenario.decision_feedback,
        "UMMAYA_REALUSE_DECISION_READY_REGEX": scenario.decision_ready_regex,
        "UMMAYA_REALUSE_AFTER_DECISION_TIMEOUT_SEC": scenario.after_decision_timeout_sec,
        "UMMAYA_REALUSE_AFTER_DECISION_REGEX": scenario.after_decision_regex,
        "UMMAYA_REALUSE_RESULT_REGEX": scenario.result_regex,
        "UMMAYA_REALUSE_FINAL_REGEX": scenario.final_regex,
    }
    env.update({key: value for key, value in optional_values.items() if value})
    return env


def run_scenario(
    scenario: Scenario,
    capture_root: Path,
    strict_frames: bool,
    dry_run: bool,
    audit_only: bool = False,
    driver: str = "bun-pty",
) -> dict[str, Any]:
    out_dir = capture_root / scenario.id
    env = build_scenario_env(scenario, out_dir)

    if driver == "python-pty":
        capture_cmd = [
            sys.executable,
            str(PYTHON_PTY_CAPTURE),
            str(out_dir),
        ]
    else:
        capture_cmd = [
            "bun",
            "scripts/bun-pty-capture.ts",
            str(out_dir),
            str(GENERIC_SCENARIO),
        ]
    audit_cmd = [
        sys.executable,
        "scripts/tui-realuse-audit.py",
        str(out_dir),
    ]
    if scenario.expected_chain:
        audit_cmd.extend(["--expect-chain", ",".join(scenario.expected_chain)])
    if scenario.require_expanded_trace:
        audit_cmd.append("--require-expanded-trace")
    if scenario.require_error_rendering:
        audit_cmd.append("--require-error-rendering")
    if scenario.allow_rejected:
        audit_cmd.append("--allow-rejected")
    if strict_frames:
        audit_cmd.append("--strict-frames")
    for pattern in scenario.require_regex:
        audit_cmd.extend(["--require-regex", pattern])
    for pattern in scenario.forbid_regex:
        audit_cmd.extend(["--forbid-regex", pattern])

    if dry_run:
        return {
            "id": scenario.id,
            "status": "dry_run",
            "driver": driver,
            "capture_cmd": capture_cmd,
            "audit_cmd": audit_cmd,
        }

    if audit_only:
        capture_status = 0 if out_dir.exists() else 99
        audit_status = run_command(audit_cmd, env) if capture_status == 0 else 99
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        capture_status = run_command(capture_cmd, env)
        audit_status = run_command(audit_cmd, env) if capture_status == 0 else 99
    status = "pass" if capture_status == 0 and audit_status == 0 else "fail"
    return {
        "id": scenario.id,
        "status": status,
        "driver": driver,
        "capture_status": capture_status,
        "audit_status": audit_status,
        "capture_dir": str(out_dir),
    }


def write_summary(capture_root: Path, results: list[dict[str, Any]]) -> None:
    capture_root.mkdir(parents=True, exist_ok=True)
    overall = "fail" if any(item["status"] == "fail" for item in results) else "pass"
    payload = {"overall": overall, "results": results}
    (capture_root / "matrix-summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = ["# Real-Use Scenario Matrix", "", f"Overall: **{overall}**", ""]
    for item in results:
        lines.append(f"- `{item['id']}`: {item['status']}")
    (capture_root / "matrix-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument(
        "--capture-root",
        type=Path,
        default=Path("specs/2773-rollback-debug-infra/captures"),
    )
    parser.add_argument("--id", action="append", default=[])
    parser.add_argument("--priority", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--driver",
        choices=["bun-pty", "python-pty"],
        default=os.environ.get("UMMAYA_REALUSE_DRIVER", "bun-pty"),
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="rerun audits against existing capture directories without recapturing",
    )
    parser.add_argument("--strict-frames", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = load_matrix(args.matrix)
    selected = select_scenarios(scenarios, args.id, args.priority, args.domain)
    if args.list:
        for scenario in selected:
            sys.stdout.write(f"{scenario.id}\t{scenario.priority}\t{scenario.domain}\n")
        return 0

    if not selected:
        sys.stderr.write("no scenarios selected\n")
        return 2

    results = [
        run_scenario(
            scenario,
            capture_root=args.capture_root,
            strict_frames=args.strict_frames,
            dry_run=args.dry_run,
            audit_only=args.audit_only,
            driver=args.driver,
        )
        for scenario in selected
    ]
    write_summary(args.capture_root, results)
    sys.stdout.write(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n")
    return 1 if any(item["status"] == "fail" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
