#!/usr/bin/env bash
# Audit-7 P0-3 + P0-4 smoke: /migrate-sessions wiring + history dual-walk + stub-skip.
# Usage: scripts/tui-tmux-capture.sh <outdir> specs/audit-7-p0/scenario-migrate-sessions.sh
set -euo pipefail

# Wait for boot banner.
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 5
snapshot_pane snap-001-banner

# /migrate-sessions --dry-run (P0-3 wiring proof).
send_text_pane "/migrate-sessions --dry-run"
send_enter_pane
sleep 2
wait_for_pane "migrate-sessions" 8 || true
snapshot_pane snap-002-migrate-dryrun

# /migrate-sessions --prune (without --confirmed → must show hint, NOT execute).
send_text_pane "/migrate-sessions --prune"
send_enter_pane
sleep 2
wait_for_pane "confirmed|먼저|--confirmed" 6 || true
snapshot_pane snap-003-prune-hint

# /history (P0-4 stub-skip + dual-walk proof).
send_text_pane "/history"
send_enter_pane
sleep 2
snapshot_pane snap-004-history

# Esc to dismiss.
send_keys_pane Escape
sleep 1
snapshot_pane snap-005-after-esc

# Exit.
send_ctrlc_pane
sleep 0.5
send_ctrlc_pane
sleep 0.5
