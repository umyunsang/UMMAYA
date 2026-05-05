#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-4-permission — Permission Gauntlet + Consent lifecycle smoke
#
# Scope (per Lead-Opus prod audit instructions, 2026-05-04):
#   1. /consent list                 — empty + populated render
#   2. verify  → Layer ⓵ Y/A/N      — receipt + ledger
#   3. submit  → Layer ⓶ irreversible= false then true → Layer ⓷
#   4. /consent revoke <rcpt-id>     — confirm dialog + ledger withdraw
#   5. Y vs A wire-decision check    — does A actually cache session-grant?
#   6. N (deny)                      — does LLM gracefully recover?
#
# This script is sourced from scripts/tui-tmux-capture.sh which exports
# wait_for_pane / snapshot_pane / send_text_pane / send_keys_pane / etc.
#
# Run from repo root:
#   KOSMOS_BACKEND_LOG_FILE=/tmp/audit-4.log \
#     bash scripts/tui-tmux-capture.sh \
#       specs/audit-prod/audit-4-permission \
#       specs/audit-prod/scripts/audit-4-permission.sh
set -euo pipefail

# ---------------------------------------------------------------------------
# Stage 0 — boot
# ---------------------------------------------------------------------------
wait_for_pane "tool_registry: [0-9]+ entries verified" 90
snapshot_pane "00-boot"

# ---------------------------------------------------------------------------
# Stage 1 — /consent list (EMPTY)
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
send_enter_pane
sleep 1.5
snapshot_pane "01-consent-list-empty"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 2 — verify primitive (Layer ⓵ — should mount KosmosPrimitive Layer1)
#   Citizen prompt asks the LLM to verify identity for Mobile ID.
#   Expected: Layer ⓵ green modal, Y/A/N selector, PIPA §22-2/§26 footer,
#   receipt ID line.  We pick Y (allow_once).
# ---------------------------------------------------------------------------
send_text_pane "모바일 신분증으로 신원 확인을 진행해 주세요"
send_enter_pane
# K-EXAONE thinking latency 30-90 s — wait for the gauntlet modal to mount.
# Modal title "신원 확인 권한 요청" (verifyModalTitle in permission.ko.ts).
wait_for_pane "(신원 확인 권한 요청|verify|primitive|allow|허용|Layer)" 120 || true
snapshot_pane "02-verify-modal-mounted"
# Capture an extra snapshot 2s later in case modal is still painting.
sleep 2
snapshot_pane "03-verify-modal-stable"

# Pick Y (allow_once).  PermissionPrompt is a Select component; first option
# is "Y  한 번만 허용", default focus.  Press Enter to commit.
send_enter_pane
sleep 2
snapshot_pane "04-verify-after-Y"

# Wait for the LLM to continue / tool to dispatch.
sleep 8
snapshot_pane "05-verify-after-dispatch"

# ---------------------------------------------------------------------------
# Stage 3 — /consent list (POPULATED — should show 1 receipt with Layer ⓵)
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
send_enter_pane
sleep 2
snapshot_pane "06-consent-list-after-verify"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 4 — submit primitive (Layer ⓶ for non-irreversible).
#   Cite a Mock submit adapter (welfare benefit application).  Pick A
#   (allow_session) to test the session-grant cache wiring.
# ---------------------------------------------------------------------------
send_text_pane "복지 급여 신청을 제출해 주세요"
send_enter_pane
wait_for_pane "(제출 권한 요청|submit|허용|Layer ⓶|Layer ⓷)" 120 || true
snapshot_pane "07-submit-modal-mounted"
sleep 2
snapshot_pane "08-submit-modal-stable"

# Press DownArrow once to move from "Y" → "A", then Enter to pick allow_session.
send_keys_pane "Down"
sleep 0.3
send_enter_pane
sleep 2
snapshot_pane "09-submit-after-A"

sleep 8
snapshot_pane "10-submit-after-dispatch"

# ---------------------------------------------------------------------------
# Stage 5 — same submit again to test allow_session cache (should NOT prompt)
# ---------------------------------------------------------------------------
send_text_pane "같은 복지 급여 신청을 한 번 더 제출해 주세요"
send_enter_pane
sleep 8
snapshot_pane "11-submit-second-call"
sleep 4
snapshot_pane "12-submit-second-stable"

# ---------------------------------------------------------------------------
# Stage 6 — /consent list (should now show 2 receipts)
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
send_enter_pane
sleep 2
snapshot_pane "13-consent-list-after-submit"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 7 — /consent revoke <rcpt-id>
#   We do NOT know the exact receipt_id at script time, so use a placeholder
#   and rely on the snapshot to capture the "invalid_id" or "not_found"
#   error path — and then verify the regex / format mismatch (CRITICAL #6).
# ---------------------------------------------------------------------------
send_text_pane "/consent revoke rcpt-DOES-NOT-EXIST-12345"
send_enter_pane
sleep 2
snapshot_pane "14-consent-revoke-not-found"
send_keys_pane "Escape"
sleep 0.5

# Extract the actual receipt_id from the kosmos memdir, then attempt revoke.
# We do this AFTER the prior snapshots so the output is clean.
LATEST_RECEIPT="$(ls -t ~/.kosmos/memdir/user/consent/*.json 2>/dev/null \
  | grep -v 'jsonl$' | head -1 | xargs -I{} basename {} .json || true)"
echo "[stage 7] LATEST_RECEIPT='${LATEST_RECEIPT}'"
if [[ -n "${LATEST_RECEIPT}" ]]; then
  send_text_pane "/consent revoke ${LATEST_RECEIPT}"
  send_enter_pane
  sleep 2
  snapshot_pane "15-consent-revoke-real-id"
  # Confirm dialog — press Enter to confirm (default focus = Y).
  send_enter_pane
  sleep 2
  snapshot_pane "16-consent-revoke-confirmed"
fi

# ---------------------------------------------------------------------------
# Stage 8 — /consent list (should show [REVOKED] tag)
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
send_enter_pane
sleep 2
snapshot_pane "17-consent-list-after-revoke"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 9 — verify with N (deny) → LLM fallback
# ---------------------------------------------------------------------------
send_text_pane "정부24 신원 확인을 한 번 더 시도해 주세요"
send_enter_pane
wait_for_pane "(신원 확인 권한 요청|verify|허용|Layer)" 120 || true
snapshot_pane "18-verify-modal-for-deny"
sleep 2

# Press DownArrow twice to move to "N", then Enter.
send_keys_pane "Down" "Down"
sleep 0.3
send_enter_pane
sleep 4
snapshot_pane "19-verify-after-N-deny"

sleep 8
snapshot_pane "20-verify-after-N-llm-fallback"

# ---------------------------------------------------------------------------
# Stage 10 — exit
# ---------------------------------------------------------------------------
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "21-exit"
