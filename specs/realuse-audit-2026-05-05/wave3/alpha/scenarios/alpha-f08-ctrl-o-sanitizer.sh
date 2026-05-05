#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-08: Ctrl-O thinking sanitizer
# Scenario: trigger a lookup call, press Ctrl-O to expand thinking,
#           verify NO adapter ids / tool_id / available_adapters in thinking text.
# Required env: KOSMOS_FRIENDLI_TOKEN set

set -euo pipefail

export KOSMOS_MEMDIR_ROOT="/tmp/kosmos-wave3-alpha-f08-$$"
mkdir -p "$KOSMOS_MEMDIR_ROOT"

export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
export KOSMOS_PIPA_CONSENT=opt-in-explicit

snapshot_pane "boot"

# Wait for REPL ready
wait_for_pane "tool_registry|KOSMOS|✻|>" 60

snapshot_pane "repl-ready"

# Ask something that triggers a lookup (KMA weather — will invoke available_adapters suffix in thinking)
send_text_pane "서울 날씨 알려줘"
send_enter_pane

# Wait for assistant response (up to 120s for K-EXAONE reasoning)
wait_for_pane "날씨|weather|기온|°C|맑음|흐림|⏺|Error|error" 120

snapshot_pane "after-response"

# Press Ctrl-O to expand thinking
send_keys_pane C-o
sleep 2

snapshot_pane "after-ctrl-o-expand"

# Press Ctrl-O again to collapse
send_keys_pane C-o
sleep 1

snapshot_pane "after-ctrl-o-collapse"

send_ctrlc_pane
sleep 1
send_ctrlc_pane

rm -rf "$KOSMOS_MEMDIR_ROOT"
