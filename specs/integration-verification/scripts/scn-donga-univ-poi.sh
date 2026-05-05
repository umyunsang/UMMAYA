#!/usr/bin/env bash
# Source-only — uses tui-tmux-capture.sh helpers (TMUX_SESSION/OUTDIR exported)
set -euo pipefail

# Wait for KOSMOS REPL boot (5–8s typical).
wait_for_pane "KOSMOS|❯" 25
snapshot_pane 01-boot

# Citizen query that previously routed "동아대학교" through Kakao address
# endpoint → empty → LLM hallucinated "부산 동래구" hospitals. After the
# keyword-fanout fix, resolve_location returns the real Sahagu coordinates
# and HIRA hospital_search must surface 사하구 hospitals (대학병원 / 동아대
# 의료원 / etc.), not 동래구 ones.
send_text_pane "동아대학교 근처 병원 알려줘"
sleep 1
snapshot_pane 02-typed
send_enter_pane

sleep 5
snapshot_pane 03-after-5s
sleep 10
snapshot_pane 04-after-15s
sleep 15
snapshot_pane 05-after-30s
sleep 20
snapshot_pane 06-after-50s

# Final answer must reach the pane within 90 s. Either the ⏺ tool_call line
# referencing hira_hospital_search, the synthesis prose, or a structured
# error envelope counts as a settle marker.
wait_for_pane "사하구|동아대|병원|hira_hospital_search|오류" 90 || true
snapshot_pane 07-final-answer

send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 1
snapshot_pane 08-exit
