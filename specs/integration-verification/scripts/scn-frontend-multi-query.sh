#!/usr/bin/env bash
# Multi-query frontend stress — exercises 3 distinct citizen scenarios
# back-to-back to verify dynamic tool render + chain handling across
# different adapter classes.
set -euo pipefail

wait_for_pane "KOSMOS|❯" 25
snapshot_pane 01-boot

# Scenario 1: weather (KMA chain)
send_text_pane "강남역 날씨 알려줘"
sleep 1
send_enter_pane
sleep 60
snapshot_pane 02-weather-60s

# Scenario 2: emergency room (NMC chain)
send_text_pane "서울시청 근처 응급실 알려줘"
sleep 1
send_enter_pane
sleep 60
snapshot_pane 03-er-60s

# Final wait + capture
sleep 30
snapshot_pane 04-final

send_ctrlc_pane
sleep 1
send_ctrlc_pane
sleep 1
snapshot_pane 05-exit
