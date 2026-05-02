#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 1979-plugin-dx-tui-integration — tmux capture-pane smoke scenario (debug-help)
#
# Ported from: specs/1979-plugin-dx-tui-integration/scripts/debug-help.expect
# Port date: 2026-05-01
# Harness: scripts/tui-tmux-capture.sh (RFC debug-infra-rebuild § P2 / Phase 3)
#
# Sourced (not exec'd) by tui-tmux-capture.sh — helpers available:
#   wait_for_pane <regex> [deadline_s]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane
#   send_keys_pane <key...>
#
# Original scenario:
#   Sanity check: boot TUI → wait KOSMOS branding → send "/help" → wait 8s
#   → Ctrl-C exit.
#
# Migration notes:
#   1. `spawn script -q $log_path bash -c "cd tui && bun run tui"` — harness
#      already spawns `bun run tui` in the tmux pane; script(1) wrapper dropped.
#   2. `sleep 3` (post-boot settle) → replaced with a second wait_for_pane
#      checking for `tool_registry:` which signals the TUI is past splash.
#   3. `sleep 8` (post-help wallclock) → activity-based settle loop capped 8s.
#      `/help` is a local render (no LLM round-trip) so 8s is generous.
#   4. `expect eof` → send_ctrlc_pane + sleep 1 (process-termination settle).
#
# Deadline map:
#   boot          60s
#   branding      15s
#   /help render   8s  (local render, no network)

# ── 1. Boot ──────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. Send /help ────────────────────────────────────────────────────────────
echo "Sending /help"
send_text_pane "/help"
sleep 0.5
send_enter_pane
snapshot_pane help-submitted

# Wait for /help overlay to render (local; replaces sleep 8).
# Predicate: any of the canonical help section headers.
wait_for_pane "slash.commands|Slash Commands|/help|session|permission|Session|Permission" 8
snapshot_pane help-rendered

# Activity-based settle to catch any repaint after help overlay appears.
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 5 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane help-stable

# ── 3. Graceful exit ─────────────────────────────────────────────────────────
echo "Sending Ctrl-C"
send_ctrlc_pane
sleep 1
send_ctrlc_pane
snapshot_pane quit
