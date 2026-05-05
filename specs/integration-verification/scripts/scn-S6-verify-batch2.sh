#!/usr/bin/env bash
# S6: 모바일 인증 5종 — mobile_id + mydata + module_simple_auth + module_geumyung + module_any_id_sso
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "모바일ID 로 인증"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 01-verify-mobile-id

send_text_pane "마이데이터 인증"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 02-verify-mydata

send_text_pane "간편 인증 모듈"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 03-verify-module-simple

send_text_pane "금융 인증 모듈"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 04-verify-module-geumyung

send_text_pane "통합 SSO 인증"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 05-verify-module-sso

send_text_pane "/consent list"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 06-consent-list-final
