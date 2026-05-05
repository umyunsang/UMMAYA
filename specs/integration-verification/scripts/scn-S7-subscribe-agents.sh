#!/usr/bin/env bash
# S7: 재난 알림 구독 3종 + /agents --detail
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "재난문자 알림 구독해줘"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 01-subscribe-cbs-disaster

send_text_pane "공공기관 RSS 공지 구독해줘"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 02-subscribe-rss-public

send_text_pane "주기적 데이터 풀링 구독"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 03-subscribe-rest-pull

send_text_pane "/agents"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 04-agents-summary

send_text_pane "/agents --detail"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 05-agents-detail
send_keys_pane Escape; sleep 1
snapshot_pane 06-agents-dismissed
