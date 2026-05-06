#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run the national AX target-state citizen-demand matrix through the real TUI.

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
OUT_ROOT="${1:-$REPO_ROOT/specs/realuse-audit-2026-05-05/fixes/target-state-matrix-$(date +%Y%m%d-%H%M%S)}"
SCENARIO="$REPO_ROOT/specs/realuse-audit-2026-05-05/scenarios/target-state-generic.sh"
AUDIT="$REPO_ROOT/scripts/realuse-audit-report.py"
FILTER="${KOSMOS_REALUSE_FILTER:-}"
LIMIT="${KOSMOS_REALUSE_LIMIT:-0}"
SCENARIO_YAML="$REPO_ROOT/eval/scenarios/national_ax_citizen_requests_v1.yaml"
CASES_FILE="${TMPDIR:-/tmp}/kosmos-realuse-cases-$$.tsv"
trap 'rm -f "$CASES_FILE"' EXIT

uv run python - "$SCENARIO_YAML" > "$CASES_FILE" <<'PY'
import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
for scenario in data["scenarios"]:
    chain = scenario.get("expected_ax_chain") or []
    first = chain[0]["primitive"] if chain else ""
    sequence = ",".join(item["primitive"] for item in chain)
    print(f"{scenario['id']}|{first}|{sequence}|{scenario['request_ko']}")
PY

mkdir -p "$OUT_ROOT"
SUMMARY="$OUT_ROOT/summary.tsv"
printf 'id\tstatus\tharness_rc\taudit_rc\tout_dir\n' > "$SUMMARY"

ran=0
failed=0

while IFS='|' read -r id expected_first expected_chain prompt; do
  if [[ -n "$FILTER" && "$id" != *"$FILTER"* ]]; then
    continue
  fi
  if [[ "$LIMIT" != "0" && "$ran" -ge "$LIMIT" ]]; then
    break
  fi

  case_dir="$OUT_ROOT/$id"
  mkdir -p "$case_dir"
  printf '%s\n' "$prompt" > "$case_dir/prompt.txt"
  echo "=== target-state $id ==="

  location_context="${KOSMOS_REALUSE_LOCATION_CONTEXT:-}"
  if [[ -z "$location_context" && ",$expected_chain," == *",resolve_location,"* ]]; then
    location_context="부산 사하구 다대1동"
  fi

  KOSMOS_ONBOARDING_AUTO_COMPLETE=1 \
  KOSMOS_PIPA_CONSENT=opt-in-explicit \
  KOSMOS_TMUX_SAMPLE_FRAMES=1 \
  KOSMOS_REALUSE_LABEL="$id" \
  KOSMOS_REALUSE_PROMPT="$prompt" \
  KOSMOS_REALUSE_LOCATION_CONTEXT="$location_context" \
    "$REPO_ROOT/scripts/tui-tmux-capture.sh" "$case_dir" "$SCENARIO"
  harness_rc=$?

  "$AUDIT" "$case_dir" \
    --require-first-tool "$expected_first" \
    --require-tool-chain "$expected_chain" \
    --write >/dev/null
  audit_rc=$?

  status="pass"
  if [[ "$harness_rc" != "0" || "$audit_rc" != "0" ]]; then
    status="fail"
    failed=$((failed + 1))
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$status" "$harness_rc" "$audit_rc" "$case_dir" >> "$SUMMARY"
  ran=$((ran + 1))
done < "$CASES_FILE"

echo "=== target-state matrix complete: ran=$ran failed=$failed out=$OUT_ROOT ==="
exit "$failed"
