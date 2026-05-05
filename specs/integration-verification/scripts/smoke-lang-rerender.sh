#!/usr/bin/env bash
# /lang ko after /lang en — verify mounted HelpV2 re-renders to Korean
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-ready"
send_text_pane "/lang en"
sleep 1
send_enter_pane
sleep 2
snapshot_pane "lang-en-applied"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "Session|Permission|Tool|Storage" 10
snapshot_pane "help-en-rendered"
sleep 2
send_keys_pane "Escape"
sleep 1
snapshot_pane "after-escape-en"
send_text_pane "/lang ko"
sleep 1
send_enter_pane
sleep 2
snapshot_pane "lang-ko-applied"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 10 || snapshot_pane "ko-render-fail"
snapshot_pane "help-ko-rendered"
sleep 2
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
