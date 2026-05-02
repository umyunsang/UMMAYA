#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 1979-plugin-dx-tui-integration — tmux capture-pane smoke scenario (debug-direct)
#
# Ported from: specs/1979-plugin-dx-tui-integration/scripts/debug-direct.expect
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
#   Boot TUI → wait for KOSMOS branding → send "/plugin install seoul-subway"
#   → wait 12 s → Ctrl-C exit.
#
# Migration notes:
#   1. `log_file` (expect PTY byte capture) — tmux captures are pane-state
#      snapshots. Legacy .expect is kept for offline pyte replay.
#   2. `sleep 12` (wallclock wait) → state-driven settle loop: we poll until
#      the pane stops changing for 1s, capped at 15s. Avoids timing-sensitive
#      false failures on slow machines.
#   3. `expect eof` → send_ctrlc_pane + sleep 1 + final snapshot (tmux
#      sessions persist after the spawned process exits).
#
# Deadline map:
#   boot          60s  (first run cold-starts bun + node_modules)
#   branding      15s
#   plugin-settle 15s  (activity-based, not wallclock)

# ── 1. Boot ──────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. Send /plugin install command ─────────────────────────────────────────
echo "STAGE-1: send /plugin install seoul-subway"
send_text_pane "/plugin install seoul-subway"
sleep 0.5
send_enter_pane
snapshot_pane plugin-submitted

# ── 3. Activity-based settle (replaces sleep 12) ────────────────────────────
# Poll until pane stops changing for 1s, capped at 15s.
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 15 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane plugin-settled

# Capture whether the plugin command was accepted or rendered an error.
# wait_for_pane has no negation so we use inline grep for diagnosis.
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qiE "error|not found|unknown command|failed"; then
  echo "[SMOKE NOTE] error/not-found indicator visible after /plugin install" >&2
  snapshot_pane plugin-error-detected
fi

# ── 4. Graceful quit ─────────────────────────────────────────────────────────
echo "STAGE-2: capture done; sending Ctrl-C"
send_ctrlc_pane
# sleep 1: process-termination settle only — no predicate fits pane freeze.
sleep 1
send_ctrlc_pane
snapshot_pane quit
