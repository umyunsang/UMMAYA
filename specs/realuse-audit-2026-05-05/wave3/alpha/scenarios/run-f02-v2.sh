#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-02 v2: more aggressive enter + longer waits

set -euo pipefail

TMPDIR_MEMDIR="/tmp/kosmos-wave3-alpha-f02v2-$$"
mkdir -p "$TMPDIR_MEMDIR"

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-debug-f02v2-$$"

mkdir -p "$OUTDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  rm -rf "$TMPDIR_MEMDIR"
}
trap cleanup EXIT

cd "$REPO_ROOT/tui"

tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_MEMDIR_USER=$TMPDIR_MEMDIR bun run tui"

tmux set-option -t "$TMUX_SESSION" -s escape-time 0

SNAP_SEQ=0
snap() {
  local label="$1"
  local file="$OUTDIR/snap-$(printf '%03d' "$SNAP_SEQ")-${label}.txt"
  tmux capture-pane -t "$TMUX_SESSION" -p > "$file"
  SNAP_SEQ=$(( SNAP_SEQ + 1 ))
  echo "[snap $file]"
}

wait_for() {
  local pattern="$1"; local deadline="${2:-30}"
  local start; start=$(date +%s)
  while true; do
    if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qE -- "$pattern"; then
      echo "[MATCH $pattern after $(( $(date +%s) - start ))s]"; return 0; fi
    if (( $(date +%s) - start >= deadline )); then
      echo "[TIMEOUT $pattern after ${deadline}s]" >&2
      tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/timeout-$(date +%s).txt" 2>/dev/null || true
      return 1; fi
    sleep 0.3
  done
}

snap "boot"

# Wait for CC onboarding/trust screens to complete (they run via showSetupScreens first)
# Watch for KOSMOS 5-step onboarding step 1/5
wait_for "1 / 5|환경 점검|preflight" 30
snap "step1-visible"

# Wait a moment for the React tree to fully stabilize
sleep 2

snap "step1-stable"

# Now press Enter
tmux send-keys -t "$TMUX_SESSION" Enter
sleep 2
snap "after-enter-1"

# Check if step changed
tmux send-keys -t "$TMUX_SESSION" Enter
sleep 2
snap "after-enter-2"

tmux send-keys -t "$TMUX_SESSION" Enter
sleep 2
snap "after-enter-3"

# Final state
tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt" 2>/dev/null || true
echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
