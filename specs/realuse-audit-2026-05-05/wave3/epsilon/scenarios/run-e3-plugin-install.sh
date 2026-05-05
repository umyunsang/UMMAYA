#!/usr/bin/env bash
# Wave-3 ε wrapper: F-ε-03/04 /plugin install phase progression
# Usage: bash run-e3-plugin-install.sh <output-dir>
set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir>}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-wave3-e3-$$"
SNAP_SEQ=0

TMPDIR_MEMDIR="/tmp/kosmos-wave3-e3-$$"
mkdir -p "$TMPDIR_MEMDIR"

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  rm -rf "$TMPDIR_MEMDIR"
}
trap cleanup EXIT

mkdir -p "$OUTDIR"
cd "$REPO_ROOT/tui"

# SLSA skip for install to bypass slsa-verifier not installed
tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" \
  "KOSMOS_MEMDIR_USER=$TMPDIR_MEMDIR KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit KOSMOS_PLUGIN_SLSA_SKIP=1 bun run tui"
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

echo "=== ε3 /plugin install phase progression scenario ==="

# Wait for REPL
wait_for ">|❯|KOSMOS.*>" 60
snap "boot-repl"

sleep 1

# Use a nonexistent plugin name → phase 1 fires → catalog lookup fails → exit 1
# This is sufficient to verify: phase 1 fires, counter format shows, elapsed time
tmux send-keys -t "$TMUX_SESSION" -l -- "/plugin install wave3-epsilon-test-nonexistent"
sleep 0.5
snap "typed"

INSTALL_START=$(date +%s)
tmux send-keys -t "$TMUX_SESSION" Enter
snap "sent"

echo "Polling for phase progression (max 30s)..."

PHASE_LINES=()
LAST_CONTENT=""
TERMINAL_SEEN=0
MAX_WAIT=30

for i in $(seq 1 100); do
  CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
  elapsed=$(( $(date +%s) - INSTALL_START ))

  if [[ "$CONTENT" != "$LAST_CONTENT" ]]; then
    snap "poll-${elapsed}s"
    # Capture any phase-related lines
    PHASE_LINE=$(echo "$CONTENT" | grep -E "Phase|⏳|📡|📦|🔐|🧪|📝|🔄|📜|/[0-9]" 2>/dev/null | head -3 || true)
    if [[ -n "$PHASE_LINE" ]]; then
      PHASE_LINES+=("${elapsed}s | $PHASE_LINE")
      echo "  [${elapsed}s] PHASE: $PHASE_LINE"
    fi
    LAST_CONTENT="$CONTENT"
  fi

  # Terminal state detection
  if echo "$CONTENT" | grep -qE "✗|✓|카탈로그.*실패|catalog.*fail|오류|error|exit|fail|성공|완료|unavailable|IPC.*unavail|요청을 backend|backend.*요청"; then
    TERMINAL_ELAPSED=$(( $(date +%s) - INSTALL_START ))
    snap "terminal-${TERMINAL_ELAPSED}s"
    echo "Terminal state at ${TERMINAL_ELAPSED}s"
    TERMINAL_SEEN=1
    break
  fi

  if (( elapsed >= MAX_WAIT )); then
    echo "Timeout at ${elapsed}s"
    snap "timeout"
    break
  fi
  sleep 0.3
done

TOTAL_ELAPSED=$(( $(date +%s) - INSTALL_START ))
snap "result"

echo "=== F-ε-03 / F-ε-04 PHASE TIMELINE ==="
for line in "${PHASE_LINES[@]:-}"; do
  echo "  $line"
done
echo "total_elapsed=${TOTAL_ELAPSED}s"
echo "terminal_seen=$TERMINAL_SEEN"

# Determine phase counter format from all captured snaps
PHASE_FORMAT=$(grep -rh "Phase\|⏳.*Phase\|/7\|/8" "$OUTDIR"/*.txt 2>/dev/null | grep -E "Phase [0-9]+|/[0-9]" | head -5 || echo "(no Phase N/M pattern found)")
echo "phase_counter_format: $PHASE_FORMAT"

# F-ε-03: Did Phase 2 progress?
PHASE2_SEEN=0
if grep -rqE "Phase 2|2/7|2/8|📦" "$OUTDIR"/*.txt 2>/dev/null; then
  PHASE2_SEEN=1
fi
echo "phase2_seen=$PHASE2_SEEN"

echo "=== F-ε-03 STATUS ==="
if [[ "$TERMINAL_SEEN" == "1" ]] && [[ "$TOTAL_ELAPSED" -le 30 ]]; then
  echo "  Install phase flow reached terminal state in ${TOTAL_ELAPSED}s (SLO ≤ 30s: OK)"
elif [[ "$TERMINAL_SEEN" == "1" ]]; then
  echo "  Install phase flow reached terminal state in ${TOTAL_ELAPSED}s (SLO ≤ 30s: EXCEEDED)"
else
  echo "  Install phase flow did NOT reach terminal state in ${MAX_WAIT}s (P1 perf finding)"
fi

echo "=== F-ε-04 STATUS ==="
# The TUI shows "Phase N/7" per PluginInstallFlow.tsx:373 (7 phases)
# Spec 1636 contracts show phases 1-7 in IPC contract
# architecture.md says "8-phase" which is the doc discrepancy
if [[ "$PHASE_FORMAT" == *"/7"* ]]; then
  echo "  Phase counter shows /7 — consistent with IPC contract (1-7)"
  echo "  F-ε-04 STATUS: CLOSED — TUI shows 7 phases matching IPC contract"
elif [[ "$PHASE_FORMAT" == *"/8"* ]]; then
  echo "  Phase counter shows /8 — inconsistency (TUI out of sync with IPC contract)"
  echo "  F-ε-04 STATUS: NOT_CLOSED — TUI shows 8 phases but IPC contract has 1-7"
else
  echo "  No phase counter visible yet (no phase 1+ progress)"
  echo "  F-ε-04 STATUS: PARTIAL — cannot determine from this run"
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
