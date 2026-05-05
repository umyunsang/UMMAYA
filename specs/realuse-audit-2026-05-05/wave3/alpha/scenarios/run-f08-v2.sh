#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-08 v2: longer boot wait + proper session handling
set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

COLS=180; ROWS=60
TMUX_SESSION="kosmos-debug-f08v2-$$"

mkdir -p "$OUTDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
}
trap cleanup EXIT

cd "$REPO_ROOT/tui"

tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_FRIENDLI_TOKEN=$KOSMOS_FRIENDLI_TOKEN KOSMOS_KAKAO_API_KEY=$KOSMOS_KAKAO_API_KEY bun run tui"

tmux set-option -t "$TMUX_SESSION" -s escape-time 0

SNAP_SEQ=0
snap() {
  local label="$1"
  local file="$OUTDIR/snap-$(printf '%03d' "$SNAP_SEQ")-${label}.txt"
  tmux capture-pane -t "$TMUX_SESSION" -p > "$file"
  tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "${file%.txt}-scrollback.txt" 2>/dev/null || true
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

# Wait for REPL prompt with ❯ prompt indicator
wait_for "❯|> $" 30
snap "repl-ready"

sleep 2

# Send query that triggers lookup (KMA weather invokes available_adapters suffix)
tmux send-keys -t "$TMUX_SESSION" -l -- "서울 현재 날씨 알려줘"
tmux send-keys -t "$TMUX_SESSION" Enter

snap "query-sent"

# Wait for assistant response - K-EXAONE reasoning can take 30-90s
wait_for "날씨|기온|°C|맑|흐림|구름|⏺|∴|∎|Thinking" 120

snap "after-response"

# Press Ctrl-O to expand thinking transcript
tmux send-keys -t "$TMUX_SESSION" C-o
sleep 3
snap "after-ctrl-o"

# Check scrollback for any tool_id / available_adapters / adapter ids in thinking
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/thinking-expand-scrollback.txt" 2>/dev/null || true

# Press Ctrl-O again to collapse
tmux send-keys -t "$TMUX_SESSION" C-o
sleep 2
snap "after-ctrl-o-collapse"

tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt" 2>/dev/null || true
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/final-scrollback.txt" 2>/dev/null || true
echo "=== saved to $OUTDIR ==="
ls -la "$OUTDIR"
