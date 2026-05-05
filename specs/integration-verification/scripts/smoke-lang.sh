#!/usr/bin/env bash
set -euo pipefail
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 10
snapshot_pane "boot-ready"
send_text_pane "/lang en"
sleep 1.5
snapshot_pane "lang-en-typed"
send_enter_pane
sleep 1.5
snapshot_pane "lang-en-applied"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "Session|Permissions|Tools|Storage|Help" 10 || snapshot_pane "help-en-timeout"
snapshot_pane "help-after-en"
send_keys_pane "Escape"
sleep 1
send_text_pane "/lang ko"
sleep 1
send_enter_pane
sleep 1.5
snapshot_pane "lang-ko-applied"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 10 || snapshot_pane "help-ko-timeout"
snapshot_pane "help-after-ko"
send_keys_pane "C-c"
sleep 0.5
send_keys_pane "C-c"
sleep 1
snapshot_pane "exit"
