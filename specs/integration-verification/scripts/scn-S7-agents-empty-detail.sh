#!/usr/bin/env bash
# Lead-FU-5 (S7 /agents data wire) — empty-state visual verification.
#
# Proves the --detail empty-state fix: header columns + "subscribe 도구
# 호출 시 표시" placeholder render correctly even with 0 subscriptions.

set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

# Default /agents — compact empty state
send_text_pane "/agents"
sleep 1
send_enter_pane
sleep 3
snapshot_pane 01-agents-default
send_keys_pane Escape
sleep 1
snapshot_pane 02-after-default-dismiss

# /agents --detail — header + placeholder
send_text_pane "/agents --detail"
sleep 1
send_enter_pane
sleep 3
snapshot_pane 03-agents-detail
send_keys_pane Escape
sleep 1
snapshot_pane 04-after-detail-dismiss
