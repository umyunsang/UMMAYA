#!/usr/bin/env bash
# Wave-3 re-smoke δ4 — /help Esc dismiss + arrow keys not leaking
# Finding: F-delta-04 (G2) — /help Esc + arrow keys leak to PromptInput
# Pass condition:
#   1. /help opens the help overlay
#   2. Esc dismisses the overlay and returns to REPL prompt
#   3. After dismiss, arrow keys do NOT modify the chat draft (no leaked input)

set -euo pipefail

export SNAP_SEQ=0
export OUTDIR TMUX_SESSION

echo "=== δ4: /help Esc dismiss + arrow key isolation (F-delta-04) ==="

# Wait for REPL to be ready
wait_for_pane "tool_registry|KOSMOS v|❯|Type a message|>" 30
snapshot_pane "delta4-repl-ready"

# Type /help and hit Enter
send_text_pane "/help"
sleep 0.3
snapshot_pane "delta4-typed-help"

send_enter_pane
sleep 1
snapshot_pane "delta4-help-open"

# Verify help overlay is visible
if ! tmux capture-pane -t "$TMUX_SESSION" -p | grep -qE "help|Help|Esc|닫기|slash|command|Commands"; then
  echo "[WARNING] Help overlay may not be visible"
fi

# Send Esc to dismiss
send_keys_pane Escape
sleep 0.8
snapshot_pane "delta4-after-esc"

# Verify we're back at REPL (help overlay gone)
wait_for_pane "❯|Type a message|>" 5
snapshot_pane "delta4-repl-restored"

# Now test arrow key isolation: send Up arrow (should NOT modify draft)
send_keys_pane Up
sleep 0.3
send_keys_pane Down
sleep 0.3
snapshot_pane "delta4-arrow-keys-test"

echo "=== δ4 scenario complete — check snap files for verdict ==="
send_ctrlc_pane
sleep 0.5
