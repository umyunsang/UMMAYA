#!/usr/bin/env bash
set -euo pipefail
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
snapshot_pane "boot"
send_text_pane "/onboarding"
sleep 1
snapshot_pane "onboarding-typed"
send_enter_pane
wait_for_pane "preflight|theme|pipa|ministry|terminal|온보딩|Onboarding" 10 || true
snapshot_pane "onboarding-step1"
sleep 2
snapshot_pane "onboarding-stable"
send_keys_pane "Escape"
sleep 1
snapshot_pane "after-escape"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
