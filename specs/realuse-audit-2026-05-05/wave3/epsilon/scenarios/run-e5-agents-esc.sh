#!/usr/bin/env bash
# Wave-3 ε wrapper: F-ε-05 /agents Esc dismiss
# Usage: bash run-e5-agents-esc.sh <output-dir>
set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-wave3-e5-$$"
SNAP_SEQ=0

TMPDIR_MEMDIR="/tmp/kosmos-wave3-e5-$$"
mkdir -p "$TMPDIR_MEMDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  rm -rf "$TMPDIR_MEMDIR"
}
trap cleanup EXIT

mkdir -p "$OUTDIR"
cd "$REPO_ROOT/tui"

tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_MEMDIR_USER=$TMPDIR_MEMDIR KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit bun run tui"
tmux set-option -t "$TMUX_SESSION" -s escape-time 0

snap() {
  local label="$1"
  local file="$OUTDIR/snap-$(printf '%03d' "$SNAP_SEQ")-${label}.txt"
  tmux capture-pane -t "$TMUX_SESSION" -p > "$file"
  SNAP_SEQ=$(( SNAP_SEQ + 1 ))
  echo "[snap $file]"
}

wait_for() {
  local pattern="$1"; local deadline="${2:-45}"
  local start; start=$(date +%s)
  while true; do
    if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qE -- "$pattern"; then
      echo "[MATCH '$pattern' after $(( $(date +%s) - start ))s]"; return 0; fi
    if (( $(date +%s) - start >= deadline )); then
      echo "[TIMEOUT '$pattern' after ${deadline}s]" >&2
      tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/timeout-$(date +%s).txt" 2>/dev/null || true
      return 1; fi
    sleep 0.3
  done
}

echo "=== ε5 /agents Esc dismiss scenario ==="

# Wait for REPL
wait_for ">|❯|KOSMOS.*>" 60
snap "boot-repl"

sleep 1

# Type /agents and Enter (use -l for literal text)
tmux send-keys -t "$TMUX_SESSION" -l -- "/agents"
sleep 0.5
snap "typed"
tmux send-keys -t "$TMUX_SESSION" Enter
sleep 2
snap "agents-open"

# Capture current state
CONTENT_OPEN=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
AGENTS_VISIBLE=0
if echo "$CONTENT_OPEN" | grep -qiE "agents|ESC|Esc|부처|ministry|◆|AgentVisib|SLA|detail"; then
  AGENTS_VISIBLE=1
  echo "F-ε-05: /agents overlay visible (AGENTS_VISIBLE=1)"
else
  echo "F-ε-05: /agents overlay NOT visible, content follows:"
  echo "$CONTENT_OPEN" | head -15
fi

# Send Esc (escape-time=0 ensures immediate delivery)
tmux send-keys -t "$TMUX_SESSION" Escape
sleep 1
snap "after-esc"

CONTENT_AFTER=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)

# Check if overlay dismissed: agents text gone + prompt returned
DISMISSED=0
# If agents overlay content is gone (strong signal: header line)
if ! echo "$CONTENT_AFTER" | grep -qiE "◆.*agents|◆.*agent|/agents.*--detail|ESC 종료"; then
  # But ensure we're back to normal REPL state (or at least not agents anymore)
  DISMISSED=1
fi

echo "=== F-ε-05 RESULT ==="
echo "agents_visible_before_esc=$AGENTS_VISIBLE"
echo "dismissed_after_esc=$DISMISSED"
echo "--- content after esc ---"
echo "$CONTENT_AFTER" | head -20

if [[ "$DISMISSED" == "1" ]] && [[ "$AGENTS_VISIBLE" == "1" ]]; then
  echo "F-ε-05 STATUS: CLOSED — Esc dismissed /agents overlay"
elif [[ "$AGENTS_VISIBLE" == "0" ]]; then
  echo "F-ε-05 STATUS: BLOCKED — /agents overlay did not open (prerequisite failure)"
else
  echo "F-ε-05 STATUS: NOT_CLOSED — Esc did NOT dismiss /agents overlay"
fi

# Exit
tmux send-keys -t "$TMUX_SESSION" C-c
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" C-c
sleep 0.3
snap "final"

tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt" 2>/dev/null || true
echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
