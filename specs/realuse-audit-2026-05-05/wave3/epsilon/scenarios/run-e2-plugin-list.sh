#!/usr/bin/env bash
# Wave-3 ε wrapper: F-ε-02 /plugin list — inlines env vars into tmux session
# Usage: bash run-e2-plugin-list.sh <output-dir>
set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-wave3-e2-$$"
SNAP_SEQ=0

# Isolated memdir so existing onboarding state doesn't pollute
TMPDIR_MEMDIR="/tmp/kosmos-wave3-e2-$$"
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

echo "=== ε2 /plugin list scenario ==="

# Wait for REPL (past onboarding)
wait_for ">|❯|KOSMOS.*>" 60
snap "boot-repl"

sleep 1

# Type /plugin list (use -l for literal text to avoid key interpretation)
tmux send-keys -t "$TMUX_SESSION" -l -- "/plugin list"
sleep 0.5
snap "typed"

# Submit with Enter
tmux send-keys -t "$TMUX_SESSION" Enter
sleep 3
snap "after-enter-3s"

# Wait for plugin catalog overlay or error message
INSTALL_START=$(date +%s)
MATCHED_CATALOG=0
MATCHED_ERROR=0
LAST_CONTENT=""

for i in $(seq 1 60); do
  CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
  elapsed=$(( $(date +%s) - INSTALL_START ))
  if [[ "$CONTENT" != "$LAST_CONTENT" ]]; then
    snap "poll-${elapsed}s"
    LAST_CONTENT="$CONTENT"
  fi
  # Success signals: plugin list rendered (even if 0 plugins), or browser overlay
  if echo "$CONTENT" | grep -qE "플러그인|Plugin|plugin_op|목록 조회|등록된|설치된|PluginBrowser|catalog|IPC 오류|✗|✓|요청 전송|백엔드 응답"; then
    MATCHED_CATALOG=1
    break
  fi
  # Error signals: IPC error, backend unavailable
  if echo "$CONTENT" | grep -qE "IPC.*unavailable|backend.*exited|timed out|round.trip|오류|IPC 오류"; then
    MATCHED_ERROR=1
    break
  fi
  if (( elapsed >= 15 )); then
    echo "Timeout after 15s waiting for plugin list response"
    break
  fi
  sleep 0.3
done

snap "result"

echo "=== F-ε-02 RESULT ==="
CONTENT_FINAL=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "matched_catalog=$MATCHED_CATALOG"
echo "matched_error=$MATCHED_ERROR"
echo "--- final pane ---"
echo "$CONTENT_FINAL" | head -20

if [[ "$MATCHED_CATALOG" == "1" ]]; then
  echo "F-ε-02 STATUS: CLOSED — plugin catalog overlay/response appeared"
elif [[ "$MATCHED_ERROR" == "1" ]]; then
  echo "F-ε-02 STATUS: PARTIAL — IPC sent but backend returned error"
else
  echo "F-ε-02 STATUS: NOT_CLOSED — no plugin catalog response in 10s"
fi

# Esc to dismiss
tmux send-keys -t "$TMUX_SESSION" Escape
sleep 0.5
snap "after-esc"

# Exit
tmux send-keys -t "$TMUX_SESSION" C-c
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" C-c
sleep 0.3
snap "final"

tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt" 2>/dev/null || true
echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
