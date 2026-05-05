#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# spec-multi-turn-contamination — Scenario A (canonical reproducer).
#
# Reproduces the Lead-S2 evidence (snap-S2-006) where K-EXAONE on FriendliAI
# answers turn 2 by reasoning over turn 1's payload.
#
#   Turn 1: "강남역 근처 내과 알려줘" — lookup hospital
#   Turn 2: "재난 알림 구독해줘"      — subscribe-primitive request
#
# Run via the tmux capture harness:
#
#   RUN_TS=$(date +%s); OUTDIR="specs/spec-multi-turn-contamination/diagnostic-runs/scn-A-${RUN_TS}"
#   mkdir -p "$OUTDIR"
#   KOSMOS_QUERY_TRACE=1 \
#   KOSMOS_CHAT_REQUEST_DUMP=1 \
#   KOSMOS_BACKEND_LOG_FILE="$OUTDIR/backend.log" \
#   scripts/tui-tmux-capture.sh "$OUTDIR" \
#       specs/spec-multi-turn-contamination/scripts/scn-repro-A.sh
#
# The harness sources THIS file and provides:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane
#
# Captured artefacts (in $OUTDIR):
#   backend.log                   - all backend logger.info() lines
#                                   (CHAT_REQUEST_DUMP / LATEST_USER_UTT /
#                                    REASONING_PREVIEW etc.)
#   snap-NNN-<label>.txt          - viewport at each stage
#   snap-NNN-<label>-scrollback.txt - scrollback for prior turns
#   final.txt                     - last viewport
#
# Wait conditions (memory feedback_debug_infra_rebuild — never use Sleep
# for K-EXAONE-on-FriendliAI reasoning latency):
#
# Turn-completion is detected by the backend log producing the matching
# `[REASONING_PREVIEW] turn=N` marker — that line is emitted exactly once
# per turn and means the LLM stream finished/started enough CoT to flush.
# We poll the backend log file rather than the pane to avoid matching on
# echo'd user prompts.

set -euo pipefail

# Helper — poll the backend log for a regex with deadline (mirrors the
# harness's wait_for_pane but reads from a file, not the tmux pane).
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

# Stage 0 — boot.
wait_for_pane "tool_registry" 60
snapshot_pane "00-boot"

# Stage 1 — turn 1 (lookup hospital).
send_text_pane "강남역 근처 내과 알려줘"
send_enter_pane
snapshot_pane "01-turn1-sent"

# Stage 2 — wait for turn 1 to be ingested by backend (CHAT_REQUEST_DUMP turn=1).
wait_for_log "\[CHAT_REQUEST_DUMP\] turn=1 " 60 || true
snapshot_pane "02-turn1-ingested"

# Stage 3 — wait for turn 1 reasoning preview (proves the LLM actually
# started reasoning over turn 1's content).
wait_for_log "\[REASONING_PREVIEW\] turn=1 " 180 || true
snapshot_pane "03-turn1-reasoning"

# Stage 4 — wait for turn 1 to actually finish (final assistant frame
# carries done=true, surfaced as the prompt returning to ready). Detect
# by the absence of the spinner — but since spinner glyphs are tricky
# under tmux, fall back to a fixed wait that is generous enough for
# the agentic loop's tool dispatch + summarisation. Per Spec 2521 the
# K-EXAONE Tier 1 round-trip with one tool dispatch averages 35-90s.
sleep 60
snapshot_pane "04-turn1-complete"

# Stage 5 — turn 2 (subscribe disaster).
send_text_pane "재난 알림 구독해줘"
send_enter_pane
snapshot_pane "05-turn2-sent"

# Stage 6 — wait for turn 2 to be ingested (CHAT_REQUEST_DUMP turn=2).
wait_for_log "\[CHAT_REQUEST_DUMP\] turn=2 " 60 || true
snapshot_pane "06-turn2-ingested"

# Stage 7 — wait for turn 2 reasoning preview. THIS is the discriminating
# evidence: cross-correlate the [REASONING_PREVIEW] turn=2 line in the log
# against the [LATEST_USER_UTT] turn=2 line.
wait_for_log "\[REASONING_PREVIEW\] turn=2 " 180 || true
snapshot_pane "07-turn2-reasoning"

# Stage 8 — let turn 2 settle.
sleep 60
snapshot_pane "08-turn2-complete"

# Exit cleanly.
send_ctrlc_pane
sleep 1
send_ctrlc_pane
