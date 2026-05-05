#!/usr/bin/env bash
# Live K-EXAONE + HIRA hospital search
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-ready"
send_text_pane "강남역 근처 내과 병원 알려줘"
sleep 1
snapshot_pane "user-typed"
send_enter_pane
wait_for_pane "Thinking|∴|⏺" 60 || snapshot_pane "no-thinking"
snapshot_pane "thinking"
sleep 8
snapshot_pane "post-thinking"
wait_for_pane "lookup|hira|hospital|병원|medical|허용|allow" 90 || snapshot_pane "no-tool"
snapshot_pane "tool-or-perm"
sleep 12
snapshot_pane "stage-2"
sleep 15
snapshot_pane "response-mid"
sleep 15
snapshot_pane "response-final"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
