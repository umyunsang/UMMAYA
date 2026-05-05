#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: debug-infra-rebuild RFC § P2 — tmux capture-pane harness
#
# Replaces scripts/tui-text-debug.sh's asciinema-in-asciinema PTY
# nesting (asciinema/asciinema#250). Outputs plain UTF-8 (no ANSI
# interpretation gymnastics) so grep / diff / git is friendly.
#
# Pattern source:
# - https://jmlago.github.io/skills/debug-tuis-with-tmux.html
# - https://news.ycombinator.com/item?id=46570397 (Claude Code internal)
# - patternmatched.substack.com/p/testing-bubble-tea-interfaces (WaitFor)
#
# Usage:
#   scripts/tui-tmux-capture.sh <output-dir> <scenario-script>
#
# The scenario script is sourced (not exec'd) so it inherits the
# helpers below. Required env in scenario:
#   TMUX_SESSION   — session name (export'd here)
#   OUTDIR         — output dir (export'd here)
# Helpers available to scenario:
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_keys_pane <key1> [key2...]
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane

set -euo pipefail

OUTDIR="${1:?usage: $0 <output-dir> <scenario>}"
SCENARIO="${2:?usage: $0 <output-dir> <scenario>}"
COLS="${KOSMOS_DEBUG_COLS:-180}"
ROWS="${KOSMOS_DEBUG_ROWS:-60}"
TMUX_SESSION="kosmos-debug-$$"

# Resolve scenario absolute path before any cd
SCENARIO_ABS="$(cd "$(dirname "$SCENARIO")" && pwd)/$(basename "$SCENARIO")"
[[ -f "$SCENARIO_ABS" ]] || { echo "::error::scenario not found: $SCENARIO_ABS" >&2; exit 1; }

mkdir -p "$OUTDIR"
OUTDIR="$(cd "$OUTDIR" && pwd)"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$REPO_ROOT/tui"

if ! command -v tmux >/dev/null 2>&1; then
  echo "::error::tmux not on PATH (brew install tmux)" >&2
  exit 1
fi

cleanup() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
}
trap cleanup EXIT

# Spawn detached tmux session running the TUI
tmux new-session -d -s "$TMUX_SESSION" -x "$COLS" -y "$ROWS" 'bun run tui'

# Disable tmux's 500 ms escape-time timer.
# `tmux send-keys Escape` sends `^[` (0x1b). tmux normally waits up to
# escape-time ms before delivering it to the program, in case the byte is
# the prefix of a Meta-/function-key sequence (Modifier-Keys wiki). With
# the default 500 ms, automated scenarios that send Escape immediately
# followed by another byte trigger the Meta-prefix branch — the program
# never sees a standalone Escape, and overlay dismiss handlers never fire
# (integration-verification frame 19/20 root cause).  escape-time=0
# delivers Escape immediately and matches what an interactive human's
# keystroke produces.  Must run AFTER new-session so the tmux server
# exists.
tmux set-option -t "$TMUX_SESSION" -s escape-time 0

# Helper: poll-with-deadline wait (replaces every Sleep <wallclock>)
wait_for_pane() {
  local pattern="${1:?wait_for_pane <regex>}"
  local deadline="${2:-30}"
  local start now
  start=$(date +%s)
  while true; do
    if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qE -- "$pattern"; then
      local elapsed=$(( $(date +%s) - start ))
      echo "[wait_for_pane MATCH \"$pattern\" after ${elapsed}s]"
      return 0
    fi
    now=$(date +%s)
    if (( now - start >= deadline )); then
      echo "[wait_for_pane TIMEOUT \"$pattern\" after ${deadline}s]" >&2
      tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/timeout-$(date +%s).txt" 2>/dev/null || true
      return 1
    fi
    sleep 0.3
  done
}

snapshot_pane() {
  local label="${1:?snapshot_pane <label>}"
  local file="$OUTDIR/snap-$(printf '%03d' "${SNAP_SEQ:-0}")-${label}.txt"
  local scrollback_file="$OUTDIR/snap-$(printf '%03d' "${SNAP_SEQ:-0}")-${label}-scrollback.txt"
  SNAP_SEQ=$(( ${SNAP_SEQ:-0} + 1 ))
  tmux capture-pane -t "$TMUX_SESSION" -p > "$file"
  # Also dump the scrollback buffer so prior turns of the conversation are
  # preserved even when the viewport has scrolled past them. -S -10000
  # captures the last 10k history lines (tmux default history-limit is
  # 2000; that's what the session uses unless tmux.conf overrides it).
  tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$scrollback_file" 2>/dev/null || true
  echo "[snapshot_pane $file (+ scrollback)]"
}

send_keys_pane() {
  tmux send-keys -t "$TMUX_SESSION" "$@"
}

send_text_pane() {
  # -l = literal mode: bytes are sent as-is, so spaces in the string are
  # transmitted as space characters (not parsed as the "Space" key name).
  # Without -l, "/lang en" would be split on whitespace and "en" would
  # follow a "Space" key event, which the TUI input layer may discard.
  tmux send-keys -t "$TMUX_SESSION" -l -- "$1"
}

send_enter_pane() {
  tmux send-keys -t "$TMUX_SESSION" Enter
}

send_ctrlc_pane() {
  tmux send-keys -t "$TMUX_SESSION" C-c
}

# Export the helpers + state to the scenario script
export TMUX_SESSION OUTDIR
export -f wait_for_pane snapshot_pane send_keys_pane send_text_pane \
          send_enter_pane send_ctrlc_pane
SNAP_SEQ=0

# Source the scenario — it can use the helpers directly
echo "=== running scenario: $SCENARIO_ABS ==="
# shellcheck disable=SC1090
source "$SCENARIO_ABS"

# Final dump
tmux capture-pane -t "$TMUX_SESSION" -p > "$OUTDIR/final.txt"
echo "=== captures saved to $OUTDIR ==="
ls -la "$OUTDIR"
