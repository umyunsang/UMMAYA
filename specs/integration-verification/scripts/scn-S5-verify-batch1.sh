#!/usr/bin/env bash
# S5: 인증서 4종 — gongdong + geumyung_injeungseo + ganpyeon + module_kec verify + /consent revoke
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "공동인증서로 본인확인"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 01-verify-gongdong

send_text_pane "금융인증서로 본인확인"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 02-verify-geumyung-injeungseo

send_text_pane "간편인증으로 본인확인"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 03-verify-ganpyeon

send_text_pane "KEC 인증으로 본인확인"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 04-verify-kec

send_text_pane "/consent list"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 05-consent-list

send_text_pane "/consent revoke"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 06-consent-revoke-modal
send_keys_pane Escape; sleep 1
snapshot_pane 07-revoke-cancelled
