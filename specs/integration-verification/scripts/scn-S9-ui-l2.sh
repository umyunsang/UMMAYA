#!/usr/bin/env bash
# S9: UI L2 전체 — /onboarding 재실행 + /agents + plugin browser + /config + /history + /export
set -euo pipefail
wait_for_pane "KOSMOS|❯" 30
snapshot_pane 00-boot

send_text_pane "/onboarding"; sleep 1; send_enter_pane; sleep 5
snapshot_pane 01-onboarding-rerun
send_keys_pane Escape; sleep 1
snapshot_pane 02-onboarding-dismissed

send_text_pane "/agents"; sleep 1; send_enter_pane; sleep 4
snapshot_pane 03-agents
send_keys_pane Escape; sleep 1

send_text_pane "/plugin"; sleep 1; send_enter_pane; sleep 4
snapshot_pane 04-plugin-browser
send_keys_pane Escape; sleep 1
snapshot_pane 05-plugin-dismissed

send_text_pane "/config"; sleep 1; send_enter_pane; sleep 4
snapshot_pane 06-config-overlay
send_keys_pane Escape; sleep 1
snapshot_pane 07-config-dismissed

send_text_pane "/history"; sleep 1; send_enter_pane; sleep 4
snapshot_pane 08-history-search
send_keys_pane Escape; sleep 1
snapshot_pane 09-history-dismissed

# Single tool call to populate context
send_text_pane "오늘 강남역 날씨"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 10-tool-call

send_text_pane "/export"; sleep 1; send_enter_pane; sleep 8
snapshot_pane 11-export-pdf
