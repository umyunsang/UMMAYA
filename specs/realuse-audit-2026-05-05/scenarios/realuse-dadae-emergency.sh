#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Real-use regression for the user-reported flow:
# "다대1동 근처 응급실 알려줘"
# Sourced by scripts/tui-tmux-capture.sh.

wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

send_text_pane "다대1동 근처 응급실 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

wait_for_pane "resolve_location|lookup|Thinking|thinking|오류|error" 120
snapshot_pane "first-tool-call"

# NMC emergency lookup must proceed as read-only public lookup, without a
# permission/login modal.
wait_for_pane "nmc_emergency_search|응급실|응급의료|병원|NMC|⎿" 300 || true
snapshot_pane "nmc-lookup"

wait_for_pane "⎿|응급실|병원|NMC|결과|응급의료|upstream_unavailable|stale_data" 180 || true
snapshot_pane "after-result"

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

if tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 | grep -qE "permission_timeout|auth_required|로그인|권한 문제"; then
  echo "::error::NMC read-only lookup regressed into permission/auth path" >&2
  snapshot_pane "unexpected-permission"
  exit 1
fi

if tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 | grep -qE "네트워크 오류|활성 부처 에이전트|0 agents"; then
  echo "::error::Obsolete KOSMOS HUD rendered during real-use flow" >&2
  snapshot_pane "unexpected-obsolete-hud"
  exit 1
fi
