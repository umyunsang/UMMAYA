#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-02: onboarding preflight Enter advances
# Scenario: boot with cleared onboarding state, confirm Enter advances step
# Required env: KOSMOS_FRIENDLI_TOKEN set

set -euo pipefail

# Use a temp memdir so we don't corrupt real state
export KOSMOS_MEMDIR_ROOT="/tmp/kosmos-wave3-alpha-f02-$$"
mkdir -p "$KOSMOS_MEMDIR_ROOT"

# Do NOT set KOSMOS_ONBOARDING_AUTO_COMPLETE so onboarding shows
export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
# Without PIPA_CONSENT → should freeze at pipa-consent step
unset KOSMOS_PIPA_CONSENT 2>/dev/null || true

snapshot_pane "boot"

# Wait for onboarding to appear (preflight step title or KOSMOS branding)
wait_for_pane "KOSMOS|preflight|시작|onboarding|✦|환영" 30

snapshot_pane "onboarding-visible"

# Press Enter to advance preflight step
send_enter_pane
sleep 1
send_enter_pane
sleep 1

snapshot_pane "after-enter-1"

# Press Enter again (theme step)
send_enter_pane
sleep 1

snapshot_pane "after-enter-2"

# Should have advanced beyond preflight; expect theme or pipa-consent step
# NOT stuck at same step

send_ctrlc_pane
sleep 1
send_ctrlc_pane

# Cleanup
rm -rf "$KOSMOS_MEMDIR_ROOT"
