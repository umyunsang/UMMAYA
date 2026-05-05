#!/usr/bin/env bash
# S4: 운전자 — koroad lookup x2 + nfa_119 + verify(modid) + submit(traffic_fine_pay) + permission ⓶
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "강남구 사고 위험지역"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 01-koroad-accident

send_text_pane "강남구 사고 다발 지역"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 02-koroad-hazard

send_text_pane "서울 강남구 119 구급 통계"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 03-nfa-119

send_text_pane "모바일ID 로 본인확인"; sleep 1; send_enter_pane; sleep 60
snapshot_pane 04-verify-modid

send_text_pane "교통과태료 납부해줘"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 05-submit-traffic-fine
send_text_pane "y"; sleep 1; send_enter_pane; sleep 30
snapshot_pane 06-permission-fine
