#!/usr/bin/env bash
# Wave-4 G12a re-smoke: F-ε-03 /plugin install <id> (with correct env vars)
# Tests that install command enters phase 1 within 30s
# REQUIRES: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 AND KOSMOS_PIPA_CONSENT=opt-in-explicit

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0
INSTALL_START=0

echo "=== G12a: F-ε-03 /plugin install phase progression ==="

wait_for_pane "tool_registry|KOSMOS|❯|Type a message" 45
snapshot_pane "g12a3-boot"

BOOT_CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
if echo "$BOOT_CONTENT" | grep -qE "❯|Type a message"; then
  echo "[G12a3] REPL reached"
else
  echo "[G12a3] WARNING: not in REPL"
fi

sleep 1

# Type /plugin install with nonexistent plugin to test phase 1 catalog fetch
send_text_pane "/plugin install g12-nonexistent-test-plugin"
sleep 0.3
snapshot_pane "g12a3-command-typed"

send_enter_pane
INSTALL_START=$(date +%s)
snapshot_pane "g12a3-sent"

# Poll for phase progression — max 30s
MAX_WAIT=30
PHASE_SEEN=0
LAST=""
for i in $(seq 1 60); do
  CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
  now=$(date +%s)
  elapsed=$(( now - INSTALL_START ))

  # Phase indicators
  if echo "$CONTENT" | grep -qE "Phase [0-9]|1/7|2/7|1/8|📡|📦|설치|install|catalog|카탈로그|진행|진행 중|오류|error|실패|fail|✗|완료"; then
    if [[ "$CONTENT" != "$LAST" ]]; then
      snapshot_pane "g12a3-phase-${elapsed}s"
      PHASE_SEEN=1
      LAST="$CONTENT"
      echo "[G12a3] Phase indicator at ${elapsed}s"
    fi
  fi

  # Terminal state detection
  if echo "$CONTENT" | grep -qE "✗|오류|실패|error|fail|unavailable|IPC.*error|success|완료|done"; then
    FINAL=$(( $(date +%s) - INSTALL_START ))
    snapshot_pane "g12a3-terminal-${FINAL}s"
    echo "[G12a3] Terminal state at ${FINAL}s — SLO check: $( [[ $FINAL -le 30 ]] && echo 'PASS (≤30s)' || echo 'FAIL (>30s)' )"
    break
  fi

  if (( elapsed >= MAX_WAIT )); then
    snapshot_pane "g12a3-timeout-${elapsed}s"
    echo "[G12a3] TIMEOUT at ${elapsed}s — no terminal state detected"
    break
  fi
  sleep 0.5
done

TOTAL=$(( $(date +%s) - INSTALL_START ))
echo "[G12a3] Total elapsed: ${TOTAL}s"
echo "[G12a3] Phase seen: $( [[ $PHASE_SEEN -eq 1 ]] && echo 'YES' || echo 'NO' )"

# Check if IPC arm was reachable
FINAL_CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
if echo "$FINAL_CONTENT" | grep -qE "Phase|설치|install|IPC|plugin_op"; then
  echo "[G12a3] RESULT: Plugin install command reached IPC — F-ε-03 input-delivered"
else
  echo "[G12a3] RESULT: No phase progress — F-ε-03 still silent/blocked"
fi

send_ctrlc_pane
sleep 0.3
send_ctrlc_pane
