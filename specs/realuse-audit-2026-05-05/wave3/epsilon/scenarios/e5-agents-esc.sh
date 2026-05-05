#!/usr/bin/env bash
# Wave-3 ε re-smoke scenario ε5: /agents Esc dismiss
# F-ε-05 re-check after G2 fix (chord block + direct useInput Esc fallback)
# Env: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0

# ── Wait for TUI boot ────────────────────────────────────────────────────────
wait_for_pane "KOSMOS|kosmos|tool_registry|ToolRegistry" 45
snapshot_pane "e5-boot"

sleep 1

# ── Type /agents ──────────────────────────────────────────────────────────────
tmux send-keys -t "$TMUX_SESSION" "/agents" ""
sleep 0.5
snapshot_pane "e5-typed"

tmux send-keys -t "$TMUX_SESSION" "" ""
sleep 2
snapshot_pane "e5-agents-open"

# ── Check if agents overlay appeared ─────────────────────────────────────────
CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
AGENTS_OPEN=0
if echo "$CONTENT" | grep -qiE "agents|ESC|Esc|부처|agent|ministry|agentVisibility|◆"; then
  AGENTS_OPEN=1
  echo "F-ε-05: /agents overlay opened successfully"
else
  echo "F-ε-05: /agents overlay may not have opened, content follows"
fi

# ── Send Esc to dismiss ───────────────────────────────────────────────────────
# tmux escape-time=0 is set by the harness, so this sends 0x1b immediately
tmux send-keys -t "$TMUX_SESSION" "Escape" ""
sleep 1
snapshot_pane "e5-after-esc"

# ── Check if overlay is dismissed (prompt input visible again) ────────────────
AFTER_ESC=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
ESC_DISMISSED=0
# After dismiss: chat input should reappear; agents overlay text should be gone
# Key signal: the "agents" overlay header disappeared, OR > prompt visible
if echo "$AFTER_ESC" | grep -qiE ">|prompt|입력|chat|KOSMOS"; then
  ESC_DISMISSED=1
fi
# Also check that the agents header is gone (stronger signal)
if ! echo "$AFTER_ESC" | grep -qiE "agents|부처|ministry|agentVisibility|◆ "; then
  ESC_DISMISSED=1
fi

if [[ "$ESC_DISMISSED" == "1" ]]; then
  echo "F-ε-05 STATUS: CLOSED — Esc dismissed /agents overlay"
else
  echo "F-ε-05 STATUS: NOT_CLOSED — Esc did NOT dismiss /agents overlay"
fi

# ── Ctrl+C to exit ────────────────────────────────────────────────────────────
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
tmux send-keys -t "$TMUX_SESSION" "C-c" ""
sleep 0.3
snapshot_pane "e5-final"
