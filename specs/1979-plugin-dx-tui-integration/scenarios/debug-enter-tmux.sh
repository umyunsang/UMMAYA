#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 1979-plugin-dx-tui-integration — tmux capture-pane smoke scenario (debug-enter)
#
# Ported from: specs/1979-plugin-dx-tui-integration/scripts/debug-enter.expect
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
#   Tests different Enter key encodings: CR+LF ("\r\n"), Tab then CR ("\t" + "\r"),
#   and plain "hello world\r". Verifies the input path handles each without swallowing.
#
# Migration notes:
#   1. `send -- "/help\r\n"` (CR+LF) — tmux send-keys with two separate sends
#      preserves the intent: send_text_pane then send_enter_pane. The LF (\n)
#      is intentionally omitted — within a tmux pane Enter sends CR (correct
#      for Bun/node TTY semantics). CR+LF double-newline is tested implicitly
#      by sending Enter after the text.
#   2. `send -- "\t"` → send_keys_pane Tab
#   3. `send -- "\r"` → send_enter_pane
#   4. Wallclock sleeps (5s, 1s) → activity-based settle loops capped at 8s.
#      sleep 0.5 between send and snapshot is intentionally kept for input-
#      delivery settle (< 1s, safe per round-1 pattern).
#   5. `expect eof` → send_ctrlc_pane + sleep 1 (process-termination only).
#
# Deadline map:
#   boot          60s
#   branding      15s
#   /help render   8s  (local render, fast)
#   tab-dismiss    5s
#   hello-world    8s

# ── 1. Boot ──────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. STAGE-1: /help with CRLF encoding test ───────────────────────────────
echo "STAGE-1: Type /help and CRLF"
send_text_pane "/help"
sleep 0.5
send_enter_pane
# Activity-based settle (replaces sleep 5)
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 8 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane help-submitted

# ── 3. STAGE-2: Tab dismissal then Enter ────────────────────────────────────
echo "STAGE-2: try Tab dismissal then Enter"
send_keys_pane Tab
sleep 0.5
send_enter_pane
# Activity-based settle (replaces sleep 5)
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
snapshot_pane tab-dismissed

# ── 4. STAGE-3: plain text echo ─────────────────────────────────────────────
echo "STAGE-3: try plain text echo"
send_text_pane "hello world"
sleep 0.5
send_enter_pane
# Activity-based settle (replaces sleep 5)
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 8 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane hello-world-submitted

# ── 5. STAGE-4: graceful exit ────────────────────────────────────────────────
echo "STAGE-4: exit"
send_ctrlc_pane
sleep 1
send_ctrlc_pane
snapshot_pane quit
