#!/usr/bin/env bash
# S1: 신규 시민 첫 사용 — onboarding 5-step + /help + lookup(kma) + permission ⓵
set -euo pipefail
wait_for_pane "KOSMOS|❯|환영|preflight" 30
snapshot_pane 00-boot

# Onboarding handled by KOSMOS_ONBOARDING_AUTO_COMPLETE=1 env (set by
# run-all-S1-S10.sh wrapper). Standalone interactive verification of the
# 5-step wizard is performed by scn-S0-onboarding-deep.sh (separate agent).
snapshot_pane 01-post-onboarding

# /help slash command
send_text_pane "/help"; sleep 1; send_enter_pane; sleep 4
snapshot_pane 02-help-overlay
send_keys_pane Escape; sleep 1
snapshot_pane 03-help-dismissed

# First lookup — KMA
send_text_pane "지금 부산 사하구 다대1동 날씨"; sleep 1; send_enter_pane; sleep 90
snapshot_pane 04-kma-current

# Ctrl+O transcript expand
send_keys_pane C-o; sleep 2
snapshot_pane 05-ctrlo-expanded
send_keys_pane C-o; sleep 1
snapshot_pane 06-ctrlo-collapsed
