#!/usr/bin/env bash
# S8: 정부24 + 홈택스 통합 — gov24_certificate/hometax_simplified lookup + 3 submit + verify(modid) + slash autocomplete
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

# Slash autocomplete probe (type "/" without enter)
send_text_pane "/"; sleep 2
snapshot_pane 01-slash-autocomplete-dropdown
send_keys_pane Escape; sleep 1

send_text_pane "정부24 증명서 발급내역"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 02-gov24-cert-lookup

send_text_pane "홈택스 간편조회"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 03-hometax-simplified-lookup

send_text_pane "정부24 민원 신청"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 04-gov24-minwon-submit
send_text_pane "y"; sleep 1; send_enter_pane; sleep 30
snapshot_pane 05-gov24-permission

send_text_pane "홈택스 세금신고"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 06-hometax-taxreturn-submit
send_text_pane "y"; sleep 1; send_enter_pane; sleep 30
snapshot_pane 07-hometax-permission

send_text_pane "마이데이터 액션 제출"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 08-mydata-action-submit
send_text_pane "y"; sleep 1; send_enter_pane; sleep 30
snapshot_pane 09-mydata-permission
