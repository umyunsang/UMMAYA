#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# spec-multi-turn-contamination — Scenario B (negative-control baseline).
#
# Same intent twice in a row. If the contamination is purely "multi-turn
# always wrong", this should also exhibit the bug. If it's content-shape-
# dependent (e.g. tool-result residue from turn 1 carries forward), this
# scenario should be cleaner because turn 2's intent IS turn 1's intent.
#
#   Turn 1: "강남역 근처 내과 알려줘"
#   Turn 2: "강남역 근처 내과 알려줘"  (identical)

set -euo pipefail

wait_for_log() {
  local pattern="${1:?wait_for_log <regex>}"
  local deadline="${2:-180}"
  local logfile="${KOSMOS_BACKEND_LOG_FILE:-$OUTDIR/backend.log}"
  local start=$(date +%s)
  while true; do
    if [[ -f "$logfile" ]] && grep -qE -- "$pattern" "$logfile" 2>/dev/null; then
      local elapsed=$(( $(date +%s) - start ))
      echo "[wait_for_log MATCH \"$pattern\" after ${elapsed}s]"
      return 0
    fi
    local now=$(date +%s)
    if (( now - start >= deadline )); then
      echo "[wait_for_log TIMEOUT \"$pattern\" after ${deadline}s]" >&2
      return 1
    fi
    sleep 0.5
  done
}

wait_for_pane "tool_registry" 60
snapshot_pane "00-boot"

# Turn 1.
send_text_pane "강남역 근처 내과 알려줘"
send_enter_pane
snapshot_pane "01-turn1-sent"
wait_for_log "\[CHAT_REQUEST_DUMP\] turn=1 " 60 || true
snapshot_pane "02-turn1-ingested"
wait_for_log "\[REASONING_PREVIEW\] turn=1 " 180 || true
snapshot_pane "03-turn1-reasoning"
sleep 60
snapshot_pane "04-turn1-complete"

# Turn 2 — identical to turn 1.
send_text_pane "강남역 근처 내과 알려줘"
send_enter_pane
snapshot_pane "05-turn2-sent"
wait_for_log "\[CHAT_REQUEST_DUMP\] turn=2 " 60 || true
snapshot_pane "06-turn2-ingested"
wait_for_log "\[REASONING_PREVIEW\] turn=2 " 180 || true
snapshot_pane "07-turn2-reasoning"
sleep 60
snapshot_pane "08-turn2-complete"

send_ctrlc_pane
sleep 1
send_ctrlc_pane
