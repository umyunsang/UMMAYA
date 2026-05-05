#!/usr/bin/env bash
# Wave-3 re-smoke β1 wrapper — sets KOSMOS onboarding bypass vars
REPO=/Users/um-yunsang/KOSMOS
OUTDIR="$REPO/specs/realuse-audit-2026-05-05/wave3/beta/beta1"
SCENARIO="$REPO/specs/realuse-audit-2026-05-05/scenarios/beta/beta1.sh"
mkdir -p "$OUTDIR"
export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
export KOSMOS_PIPA_CONSENT=opt-in-explicit
exec "$REPO/scripts/tui-tmux-capture.sh" "$OUTDIR" "$SCENARIO"
