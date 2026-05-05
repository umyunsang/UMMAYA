#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-15b: PIPA fail-closed (positive case)
# Scenario: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 WITH KOSMOS_PIPA_CONSENT=opt-in-explicit
#           → should fully advance past onboarding to REPL

set -euo pipefail

TMPDIR_MEMDIR="/tmp/kosmos-wave3-alpha-f15b-$$"
mkdir -p "$TMPDIR_MEMDIR"

export KOSMOS_MEMDIR_USER="$TMPDIR_MEMDIR"
export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
export KOSMOS_PIPA_CONSENT=opt-in-explicit

snapshot_pane "boot-with-pipa-consent"

# Should advance past onboarding to REPL
wait_for_pane "tool_registry|>|REPL|✻" 60

snapshot_pane "after-boot"

# Give it a few more seconds to fully boot
sleep 5

snapshot_pane "after-5s-should-be-in-repl"

send_ctrlc_pane
sleep 1
send_ctrlc_pane

# Cleanup
rm -rf "$TMPDIR_MEMDIR"
