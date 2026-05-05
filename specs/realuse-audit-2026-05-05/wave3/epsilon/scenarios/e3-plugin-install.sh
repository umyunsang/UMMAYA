#!/usr/bin/env bash
# Wave-3 ε re-smoke scenario ε3: /plugin install — phase progression capture
# F-ε-03 (phase count 7 vs 8) + F-ε-04 (phase counter "2/7" vs Spec 1636 phases)
# F-ε-03 special check: capture each phase + total elapsed time
# Env: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0
INSTALL_START=0

# ── Wait for TUI boot ────────────────────────────────────────────────────────
wait_for_pane "KOSMOS|kosmos|tool_registry|ToolRegistry" 45
snapshot_pane "e3-boot"

sleep 1

# ── Type /plugin install (with a fake name — we want to see phase 1 catalog fail)
# We use a non-existent name so it fails fast at phase 1 (catalog lookup fail → exit 1)
# This lets us observe: (a) phase 1 fires, (b) phase counter format, (c) elapsed time
tmux send-keys -t "$TMUX_SESSION" "/plugin install kosmos-test-nonexistent-e3" ""
sleep 0.5
snapshot_pane "e3-typed"

tmux send-keys -t "$TMUX_SESSION" "" ""
INSTALL_START=$(date +%s)
snapshot_pane "e3-sent"

# ── Poll for phase progression (phase 1 fires, then fails) ────────────────────
# Max 30s deadline — phase 1 is catalog lookup (network) but with no real catalog
# it should fail quickly. We capture each distinct state.
MAX_WAIT=30
PHASE_DETECTED=()
LAST_CONTENT=""
POLL_START=$(date +%s)

for i in $(seq 1 60); do
  CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
  now=$(date +%s)
  elapsed=$(( now - INSTALL_START ))

  # Detect phase progression
  if echo "$CONTENT" | grep -qE "Phase [0-9]+/[0-9]|phase.*[0-9]+|1/7|2/7|Phase 1|Phase 2|📡|📦|🔐|🧪|📝|🔄|📜"; then
    if [[ "$CONTENT" != "$LAST_CONTENT" ]]; then
      snapshot_pane "e3-phase-${elapsed}s"
      PHASE_LINE=$(echo "$CONTENT" | grep -E "Phase|📡|📦|🔐|🧪|📝|🔄|📜" | head -3)
      PHASE_DETECTED+=("${elapsed}s: $PHASE_LINE")
      LAST_CONTENT="$CONTENT"
    fi
  fi

  # Detect terminal states
  if echo "$CONTENT" | grep -qE "✗|오류|실패|catalog|카탈로그.*실패|exit|error|fail|unavailable|IPC|성공|완료|/7"; then
    FINAL_ELAPSED=$(( $(date +%s) - INSTALL_START ))
    snapshot_pane "e3-terminal-${FINAL_ELAPSED}s"
    echo "e3: Terminal state detected at ${FINAL_ELAPSED}s"
    break
  fi

  if (( now - POLL_START >= MAX_WAIT )); then
    echo "e3: TIMEOUT after ${MAX_WAIT}s, no terminal state"
    snapshot_pane "e3-timeout"
    break
  fi
  sleep 0.5
done

TOTAL_ELAPSED=$(( $(date +%s) - INSTALL_START ))

echo "=== F-ε-03 / F-ε-04 PHASE TIMELINE ==="
for line in "${PHASE_DETECTED[@]:-}"; do
  echo "  $line"
done
echo "Total elapsed: ${TOTAL_ELAPSED}s"

# Extract phase counter format from captures
PHASE_FORMAT=$(grep -rh "Phase\|/7\|/8" "$OUTDIR"/snap-*-e3-*.txt 2>/dev/null | grep -E "Phase [0-9]+/[0-9]" | head -3 || echo "no Phase N/M pattern found")
echo "Phase counter format found: $PHASE_FORMAT"

# ── Ctrl+C to exit ────────────────────────────────────────────────────────────
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
snapshot_pane "e3-final"
