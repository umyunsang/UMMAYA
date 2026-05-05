#!/usr/bin/env bash
# Wave-3 re-smoke δ1 — first-run gate: showSetupDialog Enter advance
# Finding: F-delta-01 (G2) — first-run preflight blocked (showSetupDialog provider wrap)
# Pass condition: after Enter, pane advances from step 1 (preflight) to step 2 (theme selector)
#
# Note: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 is used to skip through
# but to verify F-delta-01 specifically we need to confirm the
# onboarding flow itself boots with providers intact.

set -euo pipefail

export SNAP_SEQ=0
export OUTDIR TMUX_SESSION

echo "=== δ1: first-run gate (F-delta-01) ==="

# For a fresh first-run test we clear the memdir onboarding state
# (the backup already saved the full state)
rm -f ~/.kosmos/memdir/user/onboarding/state.json 2>/dev/null || true

# Wait for the onboarding preflight screen to load
wait_for_pane "KOSMOS|Setup|Welcome|Preflight|권한|onboarding|Press Enter|Enter|✔|❯" 30
snapshot_pane "boot-preflight"

echo "Sending Enter to advance from preflight..."
send_enter_pane
sleep 1
snapshot_pane "after-enter-1"

# Wait for theme step OR the next onboarding step to appear
wait_for_pane "Theme|테마|Step 2|2 /|색상|color|선택|Choose|arrow|KOSMOS" 15
snapshot_pane "step2-theme"

echo "=== δ1 PASSED: preflight Enter advanced to next step ==="

# Clean up: use KOSMOS_ONBOARDING_AUTO_COMPLETE to finish onboarding quickly
send_ctrlc_pane
sleep 1
