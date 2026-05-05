# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 2 — verify/submit/subscribe permission modal smoke
#
# Goal: confirm that
#   - verify primitive emits Layer 1 ⓵ (green) modal
#   - submit primitive emits Layer 2 ⓶ (orange) or Layer 3 ⓷ (red) modal
#   - subscribe primitive emits Layer 2 ⓶ (orange) modal
#   - Y/N decision is wired through ipcPermissionBridge → backend
#   - receipt_id surfaces in the consent ledger
#
# Run sequentially with long waits to avoid TUI input queueing seen in audit-1.

set -uo pipefail

wait_for_pane "KOSMOS|kosmos" 60 || true
snapshot_pane boot

# ---------------------------------------------------------------------------
# verify — Layer 1 (mock gongdong_injeungseo, AAL1)
# ---------------------------------------------------------------------------
send_text_pane '공동인증서로 본인 인증을 진행해줘. verify 도구 사용.'
send_enter_pane
# Wait specifically for permission modal markers, not echoed input keywords.
wait_for_pane "레이어 1|⓵|낮은 위험|Y 한번만|승인" 180 || true
snapshot_pane t01-verify-modal-shown

# Approve once
send_text_pane 'y'
sleep 1
snapshot_pane t02-verify-modal-decision

# Wait for completion
wait_for_pane "VerifyOutput|status|family|gongdong|approved|허용" 90 || true
snapshot_pane t03-verify-completed
sleep 5

# ---------------------------------------------------------------------------
# submit — Layer 2 or 3 (mock gov24_minwon)
# ---------------------------------------------------------------------------
send_text_pane '정부24에 주민등록등본 발급 민원을 제출해줘. submit 도구 사용.'
send_enter_pane
wait_for_pane "레이어 2|레이어 3|⓶|⓷|중간 위험|높은 위험|Y 한번만|돌이킬" 240 || true
snapshot_pane t04-submit-modal-shown

send_text_pane 'y'
sleep 1
snapshot_pane t05-submit-modal-decision

wait_for_pane "SubmitOutput|receipt|transaction_id|접수|gov24_minwon" 90 || true
snapshot_pane t06-submit-completed
sleep 5

# ---------------------------------------------------------------------------
# subscribe — Layer 2 (mock disaster CBS)
# ---------------------------------------------------------------------------
send_text_pane '재난문자 CBS 알림을 30분간 구독해줘. subscribe 도구 사용.'
send_enter_pane
wait_for_pane "레이어 2|⓶|중간 위험|구독|Y 한번만" 240 || true
snapshot_pane t07-subscribe-modal-shown

send_text_pane 'y'
sleep 1
snapshot_pane t08-subscribe-modal-decision

wait_for_pane "SubscriptionHandle|subscription_id|opened|handle_id" 90 || true
snapshot_pane t09-subscribe-completed
sleep 5

# Final
send_text_pane '/exit'
send_enter_pane
sleep 2
snapshot_pane final
