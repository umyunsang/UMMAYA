#!/usr/bin/env bash
# Scenario 1 — boot + branding + /help dropdown rendering
# Sourced by scripts/tui-tmux-capture.sh

set -euo pipefail

# Stage 0: boot (wait for tool registry verification)
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
snapshot_pane "boot-tool-registry"

# Stage 1: KOSMOS branding visible
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "branding-visible"

# Stage 2: type / to open slash command dropdown
send_text_pane "/"
sleep 1.5
snapshot_pane "slash-dropdown"

# Stage 3: type 'help' to filter
send_text_pane "help"
sleep 1
snapshot_pane "slash-help-typed"

# Stage 4: enter to invoke /help
send_enter_pane
wait_for_pane "세션|권한|도구|저장|Available commands|Help" 10
snapshot_pane "help-overlay-rendered"

# Stage 5: stable state
sleep 2
snapshot_pane "stable"

# Stage 6: graceful exit
send_keys_pane "C-c"
sleep 0.5
send_keys_pane "C-c"
sleep 1
snapshot_pane "exit"
