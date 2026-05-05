#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-15: PIPA fail-closed
# Scenario: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 WITHOUT KOSMOS_PIPA_CONSENT
#           → must freeze at pipa-consent step (not full advance to REPL)
# Required: no live K-EXAONE call needed (tests onboarding state only)

set -euo pipefail

TMPDIR_MEMDIR="/tmp/kosmos-wave3-alpha-f15-$$"
mkdir -p "$TMPDIR_MEMDIR"

export KOSMOS_MEMDIR_USER="$TMPDIR_MEMDIR"
export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
# Explicitly NOT setting KOSMOS_PIPA_CONSENT

snapshot_pane "boot-no-pipa-consent"

# Should show onboarding, stop at pipa-consent step
# Give time for boot
wait_for_pane "KOSMOS|preflight|개인정보|PIPA|pipa|동의|onboarding|환영|✦" 30

snapshot_pane "onboarding-step-visible"

# Must NOT advance to REPL — should be stuck at pipa-consent
# Wait 5s and confirm REPL prompt is NOT present
sleep 5

snapshot_pane "after-5s-should-still-be-at-pipa"

send_ctrlc_pane
sleep 1
send_ctrlc_pane

# Cleanup
rm -rf "$TMPDIR_MEMDIR"
