#!/usr/bin/env bash
# Live K-EXAONE + KMA forecast tool call (날씨 조회)
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-ready"
send_text_pane "서울 날씨 알려줘"
sleep 1
snapshot_pane "user-typed"
send_enter_pane
# Wait for LLM thinking start
wait_for_pane "Thinking|∴|⏺" 60 || snapshot_pane "no-thinking"
snapshot_pane "thinking"
sleep 8
snapshot_pane "post-thinking"
# Wait for tool call (resolve_location → kma_short_term_forecast)
wait_for_pane "resolve_location|kma|lookup|forecast|temperature|기온|°C|날씨|허용|allow|permission" 90 || snapshot_pane "no-tool-call"
snapshot_pane "tool-or-permission"
sleep 5
snapshot_pane "stage-2"
# If permission prompt appeared, try Y to allow
send_text_pane "y"
sleep 1
send_enter_pane
sleep 8
snapshot_pane "after-allow"
sleep 10
snapshot_pane "response-mid"
sleep 15
snapshot_pane "response-final"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
