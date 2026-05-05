#!/usr/bin/env bash
# Wave-3 re-smoke δ2 — KOSMOS_ONBOARDING_AUTO_COMPLETE=1 escape hatch
# Finding: F-delta-02 (G2) — auto-complete escape hatch broken without provider wrap
# Pass condition: with KOSMOS_ONBOARDING_AUTO_COMPLETE=1, TUI advances past onboarding
# into REPL within ~5s (no Enter required).
#
# Note: The scenario script is sourced from tui-tmux-capture.sh.
# The TMUX_SESSION was started WITHOUT KOSMOS_ONBOARDING_AUTO_COMPLETE=1
# so we need to kill the existing session and restart with the env var.
# However, since tui-tmux-capture.sh launches bun run tui directly,
# this scenario is run as a standalone invocation.

set -euo pipefail

export SNAP_SEQ=0
export OUTDIR TMUX_SESSION

echo "=== δ2: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 escape hatch (F-delta-02) ==="

# Kill existing session if running (we need env var injected)
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
sleep 0.5

# Clear onboarding state so escape hatch triggers
rm -f ~/.kosmos/memdir/user/onboarding/state.json 2>/dev/null || true

# Restart with the escape hatch env var
tmux new-session -d -s "$TMUX_SESSION" -x 180 -y 60 \
  'KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui'
tmux set-option -t "$TMUX_SESSION" -s escape-time 0

snapshot_pane "delta2-start"

# With escape hatch, onboarding should auto-complete and REPL should appear
wait_for_pane "tool_registry|KOSMOS|❯|>|Type|chat|message" 20
snapshot_pane "delta2-repl-reached"

echo "=== δ2 PASSED: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 reached REPL without manual Enter ==="
send_ctrlc_pane
sleep 0.5
