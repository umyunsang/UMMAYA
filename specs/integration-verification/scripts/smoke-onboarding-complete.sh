#!/usr/bin/env bash
# Onboarding 5-step 빠른 통과 → REPL 도달
set -euo pipefail
wait_for_pane "환경 점검|preflight|Bun" 30
snapshot_pane "step1-preflight"
send_enter_pane
sleep 1.5
snapshot_pane "step2"
send_enter_pane
sleep 1.5
snapshot_pane "step3"
send_enter_pane
sleep 1.5
snapshot_pane "step4"
send_enter_pane
sleep 1.5
snapshot_pane "step5"
send_enter_pane
sleep 2
snapshot_pane "post-onboarding"
wait_for_pane "KOSMOS v0\\.[0-9]" 15 || snapshot_pane "no-repl-yet"
snapshot_pane "repl-ready"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
