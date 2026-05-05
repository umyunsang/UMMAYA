#!/usr/bin/env bash
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-default-ko"
# Stage A — open /help in the default ko locale
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 10
snapshot_pane "default-help-ko"
send_keys_pane "Escape"
sleep 2
snapshot_pane "after-escape"
# Stage B — switch to en
send_text_pane "/lang en"
sleep 1
send_enter_pane
sleep 2
snapshot_pane "after-lang-en"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "Session|Permission|Tool|Storage" 10
snapshot_pane "help-en-after-switch"
send_keys_pane "Escape"
sleep 2
snapshot_pane "after-escape-en"
# Stage C — switch back to ko
send_text_pane "/lang ko"
sleep 1
send_enter_pane
sleep 2
snapshot_pane "after-lang-ko"
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 15 || snapshot_pane "ko-roundtrip-fail"
snapshot_pane "help-ko-roundtrip"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
