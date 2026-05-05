#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 7b — Isolated session-lifecycle smoke
#
# Reorders Audit 7 so each surface gets a clean slot: history is LAST
# because its overlay was found to be Esc-stuck (P0-A documented in
# audit findings).
#
# Sequence:
#   0. boot
#   1. first turn (JSONL canonical-path write)
#   2. /export → PDF write to ~/Downloads
#   3. /migrate-sessions --dry-run
#   4. /fork (creates fork JSONL + parent_session_id)
#   5. /resume picker (Ctrl+A/B/W/V/R footer hints)
#   6. /history (LAST — known overlay sticks)

set -uo pipefail

wait_for_pane "KOSMOS|kosmos" 60 || true
sleep 2
snapshot_pane 0-boot

# Stage 1 — first turn → CC-shape JSONL write
send_text_pane '서울 강남구 좌표 알려줘'
send_enter_pane
wait_for_pane "Worked for|좌표|coords|resolve_location|lookup\(" 120 || true
snapshot_pane 1-first-turn
sleep 3

# Stage 2 — /export PDF
send_text_pane '/export'
send_enter_pane
wait_for_pane "내보내기|export|PDF|Downloads|kosmos-export|영수증" 30 || true
snapshot_pane 2-export-dialog-open
sleep 2
# Confirm with Enter (writes the PDF)
send_keys_pane Enter
wait_for_pane "saved|wrote|성공|완료|kosmos-export.*\.pdf|error|fail" 90 || true
snapshot_pane 2b-export-after-enter
sleep 2
send_keys_pane Escape
sleep 1
snapshot_pane 2c-export-after-esc

# Stage 3 — /migrate-sessions --dry-run
send_text_pane '/migrate-sessions --dry-run'
send_enter_pane
wait_for_pane "migrate-sessions|copied|skipped|dry-run|KB|files" 60 || true
snapshot_pane 3-migrate-dry-run
sleep 2

# Stage 4 — /fork
send_text_pane '/fork audit-fork'
send_enter_pane
wait_for_pane "fork|forked|새 분기|Forked|parent|copied|created" 30 || true
snapshot_pane 4-fork
sleep 2

# Stage 5 — /resume picker (open + footer hints + Esc)
send_text_pane '/resume'
send_enter_pane
wait_for_pane "Ctrl\+A|Ctrl\+V|Ctrl\+R|preview|rename|Type to search|conversations|이력|세션 검색" 30 || true
snapshot_pane 5-resume-picker
sleep 1
send_keys_pane Escape
sleep 1
snapshot_pane 5b-resume-after-esc

# Stage 6 — /history (LAST — overlay-stuck behaviour)
send_text_pane '/history'
send_enter_pane
wait_for_pane "history|session|sessions|filter|날짜|Layer|레이어|과거 세션 검색" 30 || true
snapshot_pane 6-history-no-filter

sleep 2
snapshot_pane 7-final
