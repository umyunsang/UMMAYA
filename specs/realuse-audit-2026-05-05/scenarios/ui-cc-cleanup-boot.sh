#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Boot-only TUI smoke for CC-aligned network/agent cleanup.
# Sourced by scripts/tui-tmux-capture.sh.

wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

if tmux capture-pane -t "$TMUX_SESSION" -p | grep -qE "네트워크 오류|활성 부처 에이전트|0 agents"; then
  echo "::error::KOSMOS-specific HUD panel appeared during boot" >&2
  snapshot_pane "unexpected-kosmos-hud"
  exit 1
fi

# Leave the session alive; the harness writes final.txt and then kills tmux
# through its EXIT trap.
