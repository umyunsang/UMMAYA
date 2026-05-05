#!/usr/bin/env bash
# Spec 035 Epic 1 — Permission Gauntlet Modal interactive verification.
#
# Goal: confirm that K-EXAONE's verify(mock_verify_gongdong_injeungseo) call
# actually triggers a citizen-visible PermissionGauntletModal (Layer 1
# green ⓵ + Korean body + [Y][A][N] selector + receipt id), the citizen's Y
# press dismisses the modal, addReceipt fires, and `/consent list` later
# renders the new receipt row.
#
# Backed by:
#   src/kosmos/ipc/stdio.py:1372  _check_permission_gate (verify ∈ GATED_PRIMITIVES)
#   src/kosmos/primitives/__init__.py:62  GATED_PRIMITIVES = {verify, submit, subscribe}
#   src/kosmos/tools/mock/verify_gongdong_injeungseo.py  registered Mock adapter
#   tui/src/query/deps.ts:523-587  IPC permission_request handler
#   tui/src/components/permissions/KosmosPrimitivePermissionRequest/  modal
set -euo pipefail

# ---------------------------------------------------------------------------
# 0. Boot — wait for KOSMOS branding
# ---------------------------------------------------------------------------
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "00-boot-branding"

# ---------------------------------------------------------------------------
# 1. Pre-verify baseline
# ---------------------------------------------------------------------------
snapshot_pane "01-pre-verify"

# ---------------------------------------------------------------------------
# 2. Trigger verify(mock_verify_gongdong_injeungseo)
#    The user prompt is Korean-natural: K-EXAONE should pick gongdong_injeungseo
#    family (공동인증서 = joint certificate) automatically via verify_canonical_map.
# ---------------------------------------------------------------------------
send_text_pane "공동인증서로 본인확인 해줘"
sleep 1
snapshot_pane "02-user-typed"
send_enter_pane

# K-EXAONE reasoning latency on FriendliAI: 30-90 s typical.
# Wait for ANY of: thinking spinner / verify call printed / modal markers.
wait_for_pane "Thinking|∴|⏺ verify|verify\\(|Layer|⓵|⓶|⓷|허용|allow|권한 위임|일반 위험" 120 \
  || { snapshot_pane "02-no-llm-response"; }
snapshot_pane "03-llm-thinking-or-call"
sleep 5
snapshot_pane "04-stage-2"

# Now wait specifically for permission modal markers.
# Layer 1 (verify) glyph = ⓵, label = 일반 위험 (레이어 1) per i18n/permission.ko.ts.
# OR the question line "...실행을 허용하시겠습니까?" if the modal mounted.
# OR the [Y][A][N] selector buttons.
wait_for_pane "⓵|⓶|⓷|일반 위험|중간 위험|높은 위험|허용하시겠|한 번만 허용|세션 자동|거부|Layer\\s*[123]|\\[Y\\]|\\[A\\]|\\[N\\]" 90 \
  || { snapshot_pane "05-NO-MODAL-shown"; echo "[FAIL: permission modal never appeared after 90s]" >&2; }
snapshot_pane "05-modal-or-not"
sleep 3
snapshot_pane "06-modal-stable"

# ---------------------------------------------------------------------------
# 3. Press Y (allow once) — should dismiss modal + emit permission_response
# ---------------------------------------------------------------------------
send_text_pane "y"
sleep 1
snapshot_pane "07-y-typed"
send_enter_pane
sleep 5
snapshot_pane "08-after-y-press"

# Wait for receipt id (rcpt-...) or downstream verify completion
wait_for_pane "rcpt-|receipt|영수증|성공|completed|completed|⏺ verify|tool_result" 60 \
  || snapshot_pane "09-no-receipt-marker"
snapshot_pane "10-post-y-press"
sleep 8
snapshot_pane "11-post-verify-result"

# ---------------------------------------------------------------------------
# 4. /consent list — verify receipt persisted to PermissionReceiptContext
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
sleep 1
snapshot_pane "12-consent-list-typed"
send_enter_pane
sleep 4
snapshot_pane "13-consent-list-result"
sleep 3
snapshot_pane "14-consent-list-final"

# ---------------------------------------------------------------------------
# 5. Clean exit
# ---------------------------------------------------------------------------
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "15-exit"
