#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# /agents should use the Claude Code original AgentsMenu path, not the
# KOSMOS AgentVisibilityPanel empty-state HUD.
# Sourced by scripts/tui-tmux-capture.sh.

wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

send_text_pane "/agents "
sleep 1
snapshot_pane "agents-typed"
send_enter_pane

wait_for_pane "Create new agent|Built-in|Press .*navigate|Software Architect|Code Writer|Agents dialog" 30
snapshot_pane "agents-menu"

if tmux capture-pane -t "$TMUX_SESSION" -p | grep -qE "활성 부처 에이전트|0 agents"; then
  echo "::error::KOSMOS AgentVisibilityPanel rendered for /agents" >&2
  snapshot_pane "unexpected-agent-visibility-panel"
  exit 1
fi
