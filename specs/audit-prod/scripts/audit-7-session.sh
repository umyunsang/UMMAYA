#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 7 — Session lifecycle + Export PDF + History
#
# Scope:
#   - Session JSONL canonical-path write (~/.kosmos/memdir/user/sessions/)
#   - /resume picker (KOSMOS + CC-legacy dual-path enumeration, dedup, sort)
#   - /fork (creates fork session JSONL with parent_session_id preserved)
#   - /continue (legacy CC alias)
#   - /migrate-sessions --dry-run (CC leak enumeration, no destructive write)
#   - /history search (3-filter AND composition: date · session · layer)
#   - /export PDF (executeExport with toolInvocations + receipts wired —
#                 Lead-Fix7), Esc dismiss respects parent useInput
#                 (Infrastructure insight #3)
#
# Helpers exported by scripts/tui-tmux-capture.sh:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_keys_pane <key1> [key2...]
#   send_ctrlc_pane

set -uo pipefail

# ---------------------------------------------------------------------------
# Stage 0 — Boot + branding
# ---------------------------------------------------------------------------
wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane 0-boot

# ---------------------------------------------------------------------------
# Stage 1 — first turn → JSONL canonical path auto-create
# ---------------------------------------------------------------------------
send_text_pane '서울 지금 날씨 어때?'
send_enter_pane
wait_for_pane "kma_current_observation|°C|관측|tool_call|날씨" 120 || true
snapshot_pane 1-first-turn-jsonl-create
sleep 2

# ---------------------------------------------------------------------------
# Stage 2 — /history (no filter) → enumerate all sessions
# ---------------------------------------------------------------------------
send_text_pane '/history'
send_enter_pane
wait_for_pane "history|session|sessions|filter|날짜|Layer|레이어" 30 || true
snapshot_pane 2-history-no-filter
sleep 1
# Esc dismiss
send_keys_pane Escape
sleep 1
snapshot_pane 2b-history-after-esc

# ---------------------------------------------------------------------------
# Stage 3 — /history with date + layer filters
# ---------------------------------------------------------------------------
send_text_pane '/history --date 2026-05-04..2026-05-05 --layer 1'
send_enter_pane
wait_for_pane "history|session|filter|2026-05" 30 || true
snapshot_pane 3-history-filtered
sleep 1
send_keys_pane Escape
sleep 1

# ---------------------------------------------------------------------------
# Stage 4 — /export → PDF generation + receipts/toolInvocations live data
# ---------------------------------------------------------------------------
send_text_pane '/export'
send_enter_pane
wait_for_pane "export|PDF|pdf|kosmos-export|Downloads|영수증|generate" 30 || true
snapshot_pane 4-export-dialog
sleep 2
# Confirm with Enter (writes the PDF) — best-effort
send_keys_pane Enter
wait_for_pane "wrote|written|saved|complete|kosmos-export.*\.pdf|성공|완료|error|fail" 90 || true
snapshot_pane 4b-export-after-enter
sleep 1
# Dismiss (Esc) — the wrong-flag fix (isLocalJSXCommand:false) means Esc
# must propagate to dialog's own useInput; absent a redirect this is
# also tested by the post-Enter onDone path.
send_keys_pane Escape
sleep 1
snapshot_pane 4c-export-after-esc

# ---------------------------------------------------------------------------
# Stage 5 — /migrate-sessions --dry-run → enumerate CC leak (24 dirs)
# ---------------------------------------------------------------------------
send_text_pane '/migrate-sessions --dry-run'
send_enter_pane
wait_for_pane "migrate-sessions|copied|skipped|dry-run|KB|files" 60 || true
snapshot_pane 5-migrate-dry-run
sleep 2

# ---------------------------------------------------------------------------
# Stage 6 — /fork → creates fork session JSONL, preserves parent_session_id
# ---------------------------------------------------------------------------
send_text_pane '/fork'
send_enter_pane
wait_for_pane "fork|forked|새 분기|Forked|parent|copied" 30 || true
snapshot_pane 6-fork
sleep 2

# ---------------------------------------------------------------------------
# Stage 7 — Ctrl+C × 2 to exit, then /resume picker (next process boot)
# Note: /resume launches a new picker process. Inside this same tmux
# session we instead drive /resume from the slash command — the picker
# overlays the prompt subtree. This validates Ctrl+A/B/W/V/R footer hints.
# ---------------------------------------------------------------------------
send_text_pane '/resume'
send_enter_pane
wait_for_pane "Ctrl\+A|Ctrl\+V|Ctrl\+R|preview|rename|Type to search|conversations" 30 || true
snapshot_pane 7-resume-picker

# Verify Ctrl+A / Ctrl+V / Ctrl+R footer hints visible
sleep 1
snapshot_pane 7b-resume-footer-hints

# Cancel
send_keys_pane Escape
sleep 1
snapshot_pane 7c-resume-after-esc

# ---------------------------------------------------------------------------
# Stage 8 — final state
# ---------------------------------------------------------------------------
sleep 1
snapshot_pane 8-final
