#!/usr/bin/env bash
set -euo pipefail
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
snapshot_pane "boot"
send_text_pane "/consent list"
send_enter_pane
sleep 1.5
snapshot_pane "consent-list"
send_keys_pane "Escape"
sleep 0.5
send_text_pane "/agents"
send_enter_pane
sleep 1.5
snapshot_pane "agents"
send_keys_pane "Escape"
sleep 0.5
send_text_pane "/agents --detail"
send_enter_pane
sleep 1.5
snapshot_pane "agents-detail"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
