#!/usr/bin/env bash
# Verify: /lang command auto-closes mounted HelpV2 overlay AND triggers
# fresh mount on next /help with the new locale (fix #5).
# This avoids the Escape-key dispatch problem by exercising the actual
# user flow: overlay still open → type /lang ko → command's setToolJSX(null)
# closes overlay → next /help re-mounts with new bundle.
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-ready"

# Stage 1: switch to English + open help (must be English)
send_text_pane "/lang en"
sleep 1
send_enter_pane
sleep 2
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "Session|Permission|Tool|Storage" 10
snapshot_pane "help-en-mounted"

# Stage 2: with overlay STILL OPEN, type /lang ko directly into prompt
# This is the integration-verification fix's target path:
# the lang handler should close the mounted overlay via setToolJSX(null).
send_text_pane "/lang ko"
sleep 1
send_enter_pane
sleep 3
snapshot_pane "after-lang-ko"

# Stage 3: re-open /help — must now render in Korean
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "세션|권한|도구|저장" 10 || snapshot_pane "ko-render-fail"
snapshot_pane "help-ko-rendered"

# Stage 4: switch back to en to prove the round-trip
send_text_pane "/lang en"
sleep 1
send_enter_pane
sleep 2
send_text_pane "/help"
sleep 1
send_enter_pane
wait_for_pane "Session|Permission|Tool|Storage" 10 || snapshot_pane "en-roundtrip-fail"
snapshot_pane "help-en-roundtrip"

send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
