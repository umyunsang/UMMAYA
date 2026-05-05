#!/usr/bin/env bash
# Same as scn-donga-univ-poi.sh but with longer reasoning budget for
# K-EXAONE multi-turn agentic loops (resolve_location → hira_hospital_search
# → synthesis can run 90+s).
set -euo pipefail

wait_for_pane "KOSMOS|❯" 25
snapshot_pane 01-boot

send_text_pane "동아대학교 근처 병원 알려줘"
sleep 1
snapshot_pane 02-typed
send_enter_pane

sleep 10
snapshot_pane 03-10s
sleep 30
snapshot_pane 04-40s
sleep 30
snapshot_pane 05-70s
sleep 30
snapshot_pane 06-100s
sleep 30
snapshot_pane 07-130s

# Wait for hira_hospital_search invocation OR final synthesis with citizen-
# visible ⏺ marker on the assistant prose.
wait_for_pane "hira_hospital_search|사하구|하단동|동래구|❯ $" 60 || true
snapshot_pane 08-final

send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 1
snapshot_pane 09-exit
