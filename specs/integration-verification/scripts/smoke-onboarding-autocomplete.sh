#!/usr/bin/env bash
# Onboarding KOSMOS_ONBOARDING_AUTO_COMPLETE=1 escape hatch verification
# Wipes prior state.json + relies on env var to mark all 5 steps complete
# without requiring keyboard input. Must arrive at REPL prompt.
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]|환경 점검" 30
snapshot_pane "boot-or-onboarding"
sleep 4
snapshot_pane "after-autocomplete"
wait_for_pane "KOSMOS v0\\.[0-9]" 15 || snapshot_pane "no-repl-yet"
snapshot_pane "repl-arrived"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 10 || snapshot_pane "help-fail"
snapshot_pane "help-after-autocomplete"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
