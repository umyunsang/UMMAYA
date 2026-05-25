# SPDX-License-Identifier: Apache-2.0
# TUI Layer 5 smoke for the 0.2.2 mid-loop painting regression.
#
# Sourced by scripts/tui-tmux-capture.sh. The invariant under test is the
# 0.2.1/Claude-Code loop surface: assistant progress text paints before the
# first tool row, and tool-result follow-up turns can paint before later tools.

wait_for_pane "UMMAYA|❯" 60
snapshot_pane "boot"

send_text_pane "부산 사하구 다대1동 현재 날씨와 오늘 저녁 예보 알려줘"
send_enter_pane

wait_for_pane "먼저|위치|확인|조회" 150
snapshot_pane "assistant-preamble"

wait_for_pane "locate\\(|kakao_address_search|kakao_keyword_search" 180
snapshot_pane "first-tool"

wait_for_pane "kma_current_observation|kma_short_term_forecast" 240
snapshot_pane "weather-tool-or-answer"

send_ctrlc_pane
send_ctrlc_pane
