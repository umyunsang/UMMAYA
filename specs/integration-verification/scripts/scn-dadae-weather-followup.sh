#!/usr/bin/env bash
# Source-only — uses tui-tmux-capture.sh helpers (TMUX_SESSION/OUTDIR exported)
set -euo pipefail

# G-class chain enforcement scenario (2026-05-04).
# snap-001-01-kma-now (scn-final-integ) showed K-EXAONE calling
# resolve_location twice and then producing a fabricated weather answer
# (16°C / 84% humidity / 05:00 KST) without ever invoking
# lookup(kma_current_observation). Raw KMA at 14:00 KST returned 20.7°C
# / 23% — a 4.7°C / 61%p drift. After this Epic G fix, the backend
# follow-up-lookup gate must reject the LLM's terminal-answer turn,
# inject a synthetic chain-recovery hint, and force a second pass that
# emits lookup(mode='fetch', tool_id='kma_current_observation', ...)
# before any answer reaches the citizen.

wait_for_pane "KOSMOS|❯" 25
snapshot_pane 01-boot

send_text_pane "지금 부산 사하구 다대1동 날씨 어때"
sleep 1
snapshot_pane 02-typed
send_enter_pane

# K-EXAONE reasoning latency is 30-90s on FriendliAI. The scenario must
# poll for any of: (a) the lookup tool_call line, (b) the answer
# containing real KMA observation values, or (c) an error envelope.
# Hardcoded sleeps were the false-positive source in donga-univ-poi-bug
# captures (project_partial_fix_revealed_by_better_infra memory).

wait_for_pane "resolve_location" 30 || true
snapshot_pane 03-after-resolve

# The follow-up gate's recovery loop should produce a kma_current_observation
# tool call within ~90s of the resolve_location result.  Without the gate,
# the answer turn fires immediately after resolve and we capture fabrication.
wait_for_pane "kma_current_observation|kma_short_term_forecast|기상청" 90 || true
snapshot_pane 04-after-followup-lookup

# The post-tool-call answer turn requires another K-EXAONE round-trip with
# tool_result in scope (~30-90 s on FriendliAI). Wait for a numeric value
# that only the real KMA observation can provide — temperature with a unit.
# Use degree-symbol or "°C" or a number followed by 도 — fabricated answers
# from the prior bug also produced these, but the gate catches them.
wait_for_pane "°C|기온은|습도는|풍속은|관측" 120 || true
snapshot_pane 05-final-answer
sleep 5
snapshot_pane 05b-final-answer-stable

send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 1
snapshot_pane 06-exit
