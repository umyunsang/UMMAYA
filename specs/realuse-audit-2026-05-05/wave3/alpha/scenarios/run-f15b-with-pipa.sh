#!/usr/bin/env bash
# Wrapper: sets env before calling tui-tmux-capture.sh for F-alpha-15b
set -euo pipefail

TMPDIR_MEMDIR="/tmp/kosmos-wave3-alpha-f15b-$$"
mkdir -p "$TMPDIR_MEMDIR"

export KOSMOS_MEMDIR_USER="$TMPDIR_MEMDIR"
export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
export KOSMOS_PIPA_CONSENT=opt-in-explicit

OUTDIR="${1:?usage: $0 <output-dir>}"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-debug-f15b-$$"

mkdir -p "$OUTDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  rm -rf "$TMPDIR_MEMDIR"
}
trap cleanup EXIT

cd "$REPO_ROOT/tui"

tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_MEMDIR_USER=$TMPDIR_MEMDIR KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit bun run tui"

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
# Should advance past onboarding to REPL
wait_for "tool_registry|>|❯" 60
snap "after-boot"
sleep 3
snap "after-3s"

tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt"
echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
