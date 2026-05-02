#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: debug-infra-rebuild RFC § P2 — first reference scenario
#
# Sourced by scripts/tui-tmux-capture.sh. Uses helpers:
#   wait_for_pane <regex> [deadline]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane
#
# Reproduces the user-reported flow:
#   1. boot
#   2. user types "부산 사하구 날씨 알려줘"
#   3. wait for ● lookup paint (no hardcoded sleep — bounded by deadline)
#   4. wait for either ⎿ result or invalid_params or 한국어 답변
#   5. snapshot final state

# 1. Boot — wait for branding (long deadline; first run cold-starts)
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane boot

# 2. User input
send_text_pane "부산 사하구 날씨 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane input-submitted

# 3. First tool_call paint — give K-EXAONE up to 60s for reasoning
#    (this is K-EXAONE's natural latency, NOT a UI hang).
wait_for_pane "● lookup" 60
snapshot_pane first-tool-call

# 4. Either successful result OR invalid_params OR final answer.
#    Three outcomes captured — the smoke is informational, not assert-style.
wait_for_pane "⎿|검색 오류|invalid|기온|°C|구름|맑|흐림" 90 || true
snapshot_pane after-result

# 5. Settle — wait for the screen to stop changing for 1s, with a 60s
#    overall deadline. This replaces "sleep 8" — the wait is *bounded*
#    by activity, not wall-clock. Sourced into harness scope (no func)
#    so use plain vars without `local`.
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 60 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane stable

# 6. Graceful quit
send_text_pane "/quit"
send_enter_pane
sleep 1
snapshot_pane quit
