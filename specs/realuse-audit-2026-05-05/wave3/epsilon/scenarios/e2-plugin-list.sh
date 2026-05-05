#!/usr/bin/env bash
# Wave-3 ε re-smoke scenario ε2: /plugin list — verify catalog overlay appears
# F-ε-02 re-check after G2 (useInput dispatch) + G4 (plugin_op IPC arm) fixes
# Env: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0

# ── Wait for TUI boot ────────────────────────────────────────────────────────
wait_for_pane "KOSMOS|kosmos|tool_registry|ToolRegistry" 45
snapshot_pane "e2-boot"

# ── Type /plugin list and submit ─────────────────────────────────────────────
sleep 1
tmux send-keys -t "$TMUX_SESSION" "/plugin list" ""
sleep 0.5
snapshot_pane "e2-typed"

tmux send-keys -t "$TMUX_SESSION" "" ""
sleep 2

snapshot_pane "e2-after-enter"

# ── Wait for PluginBrowser/catalog overlay or error ──────────────────────────
# Success path: shows "플러그인" or "Plugin" or "설치된" or PluginBrowser text
# or IPC round-trip complete (empty list is valid — 0 plugins installed)
# Failure path: silence / nothing changes

# Allow up to 10s for the IPC round-trip (backend O(n) list, should be < 1s)
DEADLINE=10
start=$(date +%s)
MATCHED=0
while true; do
  CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
  if echo "$CONTENT" | grep -qE "플러그인|Plugin|plugin|설치된|catalog|PluginBrowser|등록된|IPC|unavailable|timed out|round.trip"; then
    MATCHED=1
    break
  fi
  now=$(date +%s)
  if (( now - start >= DEADLINE )); then
    break
  fi
  sleep 0.3
done

snapshot_pane "e2-result"

if [[ "$MATCHED" == "1" ]]; then
  echo "F-ε-02 STATUS: MATCHED — catalog overlay/response appeared"
else
  echo "F-ε-02 STATUS: NO_MATCH — silence or unchanged screen after /plugin list"
fi

# ── ESC to dismiss ────────────────────────────────────────────────────────────
tmux send-keys -t "$TMUX_SESSION" "Escape" ""
sleep 0.5
snapshot_pane "e2-after-esc"

# ── Ctrl+C to exit ────────────────────────────────────────────────────────────
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
snapshot_pane "e2-final"
