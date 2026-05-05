#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 7d — full session lifecycle, accounting for the
# CLAUDE.md external-imports consent modal that appears on first boot.

set -uo pipefail

# Stage 0a — wait for the consent modal (or branding) to appear
wait_for_pane "Allow external CLAUDE.md|KOSMOS v" 60 || true
sleep 2
snapshot_pane 0a-boot-or-modal

# If the consent modal is up, accept it
if tmux capture-pane -t "$TMUX_SESSION" -p | grep -q "Allow external CLAUDE.md"; then
  send_keys_pane Enter
  sleep 2
  snapshot_pane 0b-after-consent-enter
fi

wait_for_pane "KOSMOS v|❯" 30 || true
sleep 2
snapshot_pane 0c-prompt-ready

# Stage 1 — first turn → CC-shape JSONL write
send_text_pane '서울 강남구 좌표 알려줘'
send_enter_pane
wait_for_pane "Worked for|위도|경도|coords|resolve_location" 120 || true
sleep 3
snapshot_pane 1-first-turn

# Stage 2 — /export
send_text_pane '/export'
send_enter_pane
sleep 5
snapshot_pane 2-export-dialog
# Confirm Enter
send_keys_pane Enter
sleep 8
snapshot_pane 2b-export-after-enter
# Esc dismiss
send_keys_pane Escape
sleep 2
snapshot_pane 2c-export-after-esc

# Stage 3 — /migrate-sessions --dry-run
send_text_pane '/migrate-sessions --dry-run'
send_enter_pane
sleep 5
snapshot_pane 3-migrate-dry-run

# Stage 4 — /fork
send_text_pane '/fork audit-fork'
send_enter_pane
sleep 5
snapshot_pane 4-fork

# Stage 5 — /resume picker
send_text_pane '/resume'
send_enter_pane
sleep 4
snapshot_pane 5-resume-picker
send_keys_pane Escape
sleep 2
snapshot_pane 5b-resume-after-esc

# Stage 6 — /history (LAST due to known overlay-stuck behaviour)
send_text_pane '/history'
send_enter_pane
sleep 4
snapshot_pane 6-history

sleep 2
snapshot_pane 7-final
