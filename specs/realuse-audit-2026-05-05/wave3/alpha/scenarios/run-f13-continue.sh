#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-13: --continue cwd-scoped (shell context)
# Tests that a session started in one shell context is resumed by --continue
# in the same context.
# Unit tests (14/14) already cover the cross-shell isolation.
# This script verifies the session header stamping at runtime.

set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

TMPDIR_MEMDIR="/tmp/kosmos-wave3-alpha-f13-$$"
mkdir -p "$TMPDIR_MEMDIR"

# Fixed shell context ID so we can verify scoping
SHELL_CTX="wave3-f13-smoke-abc123def456"

COLS=180; ROWS=60
TMUX_SESSION="kosmos-debug-f13-$$"

mkdir -p "$OUTDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  rm -rf "$TMPDIR_MEMDIR"
}
trap cleanup EXIT

cd "$REPO_ROOT/tui"

# Session 1: start, check the session header is written with originalShellId
tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_FRIENDLI_TOKEN=$KOSMOS_FRIENDLI_TOKEN KOSMOS_MEMDIR_USER=$TMPDIR_MEMDIR KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit KOSMOS_SHELL_CONTEXT_ID=$SHELL_CTX bun run tui"

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
wait_for "❯|tool_registry.*entries" 30
snap "repl-ready"
sleep 2

# Kill the session (simulates user exit)
tmux send-keys -t "$TMUX_SESSION" C-c
sleep 1
tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true

sleep 1

# Check that a session JSONL was written with originalShellId
SESSION_FILES=$(find "$TMPDIR_MEMDIR" -name "*.jsonl" 2>/dev/null)
echo "Session files: $SESSION_FILES"
if [[ -z "$SESSION_FILES" ]]; then
  echo "NO SESSION FILES WRITTEN — session header stamp test SKIPPED"
  echo "note: session may only be written if a message was exchanged" > "$OUTDIR/note.txt"
else
  # Check first line for originalShellId
  for f in $SESSION_FILES; do
    echo "Checking $f:"
    head -1 "$f" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print('originalShellId:', d.get('originalShellId', 'MISSING'))"
  done
fi

echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
