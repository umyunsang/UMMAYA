#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Real-use regression for the user-reported flow:
# "지금 부산 사하구 다대1동 날씨 알려줘"
# Sourced by scripts/tui-tmux-capture.sh.

wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

send_text_pane "지금 부산 사하구 다대1동 날씨 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

wait_for_pane "resolve_location|lookup|Thinking|thinking|오류|error" 120
snapshot_pane "first-tool-call"

wait_for_pane "kma|KMA|기상청|날씨|°C|강수|맑|흐림|구름|⎿" 240 || true
snapshot_pane "weather-result"

__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 300 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 5 )); then break; fi
  sleep 0.5
done

snapshot_pane "stable"
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/final-scrollback.txt" 2>/dev/null || true

if tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 | grep -qE "네트워크 오류|활성 부처 에이전트|0 agents|Cannot find module|TungstenTool"; then
  echo "::error::Obsolete KOSMOS HUD or stale import rendered during real-use flow" >&2
  snapshot_pane "unexpected-obsolete-hud"
  exit 1
fi
