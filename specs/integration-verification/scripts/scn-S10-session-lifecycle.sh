#!/usr/bin/env bash
# S10: session lifecycle — lookup → exit → verify memdir JSONL → re-launch (resume covered separately)
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "내일 서울 종로구 날씨"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 01-kma-short-term

# /resume / /fork / /continue probes
send_text_pane "/resume"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 02-resume
send_keys_pane Escape; sleep 1

send_text_pane "/fork"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 03-fork
send_keys_pane Escape; sleep 1

# trigger memdir write — second turn
send_text_pane "방금 답변에서 강수확률만 다시 알려줘"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 04-multi-turn-citation

# Markdown table render check (large response)
send_text_pane "강남역 내과 5곳 표로 정리"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 05-markdown-table
