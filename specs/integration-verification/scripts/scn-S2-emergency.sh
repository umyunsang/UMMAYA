#!/usr/bin/env bash
# S2: 응급 — verify(mobile_id) + lookup(nmc/hira) + subscribe(cbs_disaster) + Shift+Tab
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

# Shift+Tab mode switch
send_keys_pane BTab; sleep 1
snapshot_pane 01-shift-tab-mode
send_keys_pane BTab; sleep 1
snapshot_pane 02-shift-tab-back

# nmc emergency search
send_text_pane "지금 종로구 가까운 응급실"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 03-nmc-emergency

# hira hospital
send_text_pane "강남역 근처 내과"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 04-hira-hospital

# verify mobile_id (mock)
send_text_pane "verify(tool_id=mock_verify_mobile_id, params={\"id_number\":\"900101-1234567\"})"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 05-verify-mobile-id

# subscribe CBS disaster (mock)
send_text_pane "재난 알림 구독해줘"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 06-subscribe-cbs
