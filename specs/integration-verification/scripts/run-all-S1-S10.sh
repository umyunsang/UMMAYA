#!/usr/bin/env bash
# Sequential capture S1..S10 — fresh memdir per scenario.
# ~6-15 min each, total ~80-100 min. Logs to /tmp/scn-S{N}/...
set -uo pipefail

ROOT=/Users/um-yunsang/KOSMOS
CAPTURE=$ROOT/scripts/tui-tmux-capture.sh

for sn in S1 S2 S3 S4 S5 S6 S7 S8 S9 S10; do
  outdir=/tmp/scn-${sn}
  memdir=/tmp/scn-${sn}-memdir
  case $sn in
    S1) script=$ROOT/specs/integration-verification/scripts/scn-S1-onboarding-weather.sh ;;
    S2) script=$ROOT/specs/integration-verification/scripts/scn-S2-emergency.sh ;;
    S3) script=$ROOT/specs/integration-verification/scripts/scn-S3-welfare-submit.sh ;;
    S4) script=$ROOT/specs/integration-verification/scripts/scn-S4-driver.sh ;;
    S5) script=$ROOT/specs/integration-verification/scripts/scn-S5-verify-batch1.sh ;;
    S6) script=$ROOT/specs/integration-verification/scripts/scn-S6-verify-batch2.sh ;;
    S7) script=$ROOT/specs/integration-verification/scripts/scn-S7-subscribe-agents.sh ;;
    S8) script=$ROOT/specs/integration-verification/scripts/scn-S8-gov24-hometax.sh ;;
    S9) script=$ROOT/specs/integration-verification/scripts/scn-S9-ui-l2.sh ;;
    S10) script=$ROOT/specs/integration-verification/scripts/scn-S10-session-lifecycle.sh ;;
  esac
  rm -rf "$outdir"
  echo "=== [$(date +%H:%M:%S)] Starting $sn → $outdir (default memdir, auto_complete=1) ==="
  # Use host's default memdir (already-onboarded state) + auto-complete env so
  # the 5-step onboarding wizard never blocks the scenario script. S1 is the
  # only scenario that needs onboarding verification — handled separately by a
  # dedicated agent that interacts with each step explicitly.
  KOSMOS_ONBOARDING_AUTO_COMPLETE=1 \
    bash "$CAPTURE" "$outdir" "$script" 2>&1 | tail -5
  echo "=== [$(date +%H:%M:%S)] Done $sn ==="
done

echo "=== ALL S1..S10 complete at $(date +%H:%M:%S) ==="
