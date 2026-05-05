#!/usr/bin/env bash
# Lead-FU-5 (S7 /agents data wire) — subscribe ×3 with permission auto-grant
# + /agents inspection.
#
# Variant of scn-S7-subscribe-agents.sh that ALSO presses '1' to grant the
# permission prompt that the subscribe primitive raises. Without grant, the
# primitive never returns and the subscription registry stays empty —
# masking the data wire we are validating.

set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

# --- Subscription #1: 재난문자 (CBS broadcast) ---
send_text_pane "재난문자 알림 구독해줘"
sleep 1
send_enter_pane
# Wait for permission prompt then grant once
wait_for_pane "구독 권한 요청|allow_once|한 번만 허용" 90 || true
snapshot_pane 01-prompt-cbs
send_text_pane "y"
sleep 1
sleep 30
snapshot_pane 02-after-grant-cbs

# --- Subscription #2: RSS 공지 ---
send_text_pane "공공기관 RSS 공지 구독해줘"
sleep 1
send_enter_pane
wait_for_pane "구독 권한 요청|allow_once|한 번만 허용" 90 || true
snapshot_pane 03-prompt-rss
send_text_pane "y"
sleep 1
sleep 30
snapshot_pane 04-after-grant-rss

# --- Subscription #3: REST pull ---
send_text_pane "주기적 데이터 풀링 구독"
sleep 1
send_enter_pane
wait_for_pane "구독 권한 요청|allow_once|한 번만 허용" 90 || true
snapshot_pane 05-prompt-pull
send_text_pane "y"
sleep 1
sleep 30
snapshot_pane 06-after-grant-pull

# --- /agents inspection ---
send_text_pane "/agents"
sleep 1
send_enter_pane
sleep 5
snapshot_pane 07-agents-summary
send_keys_pane Escape
sleep 1
snapshot_pane 08-after-summary-dismiss

send_text_pane "/agents --detail"
sleep 1
send_enter_pane
sleep 5
snapshot_pane 09-agents-detail
send_keys_pane Escape
sleep 1
snapshot_pane 10-after-detail-dismiss
