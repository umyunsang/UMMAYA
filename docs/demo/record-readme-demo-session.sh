#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Internal session runner for the README demo.
#
# It launches the real ummaya CLI wrapper in a PTY. By default the prompt is
# typed manually by the person recording, so the captured flow matches the
# product's normal terminal UX. Set UMMAYA_DEMO_MANUAL=0 to use the legacy
# expect-driven prompt entry.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COLS="${UMMAYA_DEMO_COLS:-120}"
ROWS="${UMMAYA_DEMO_ROWS:-34}"
TEXT_OUT="${UMMAYA_DEMO_TEXT_OUT:-$ROOT_DIR/assets/ummaya-demo.txt}"
RUN_LOG="${UMMAYA_DEMO_RUN_LOG:-$ROOT_DIR/package-evidence/readme-demo/session.log}"
SCENARIO_DELAY="${UMMAYA_DEMO_SCENARIO_DELAY:-0.7}"
ANSWER_WAIT="${UMMAYA_DEMO_ANSWER_WAIT:-75}"
ANSWER_HOLD="${UMMAYA_DEMO_ANSWER_HOLD:-5}"
PROMPT="${UMMAYA_DEMO_PROMPT:-오늘 저녁 동아대학교 승학캠퍼스 근처에 비 올까?}"
MANUAL="${UMMAYA_DEMO_MANUAL:-1}"

require_cmd() {
  local cmd="${1:?}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing required command: $cmd" >&2
    exit 127
  fi
}

capture_text_evidence() {
  mkdir -p "$(dirname "$TEXT_OUT")"
  {
    printf 'UMMAYA README demo terminal evidence\n'
    printf 'Generated: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'Recorder: PTY-driven live ummaya CLI\n'
    printf 'Backend: release CLI flow with Friendli login and operator-managed live adapter gateway\n\n'
    printf '=== scripted turns ===\n'
    cat "$RUN_LOG"
  } > "$TEXT_OUT"
}

require_cmd bun
require_cmd uv

mkdir -p "$(dirname "$RUN_LOG")"
: > "$RUN_LOG"

if [[ "$MANUAL" != "0" ]]; then
  {
    printf 'MODE: live ummaya CLI; manual prompt entry\n'
    printf 'PROMPT_HINT: %s\n' "$PROMPT"
    printf 'EXIT_HINT: type /exit and press Enter after the answer finishes\n'
  } > "$RUN_LOG"
  stty columns "$COLS" rows "$ROWS" || true
  set +e
  bash "$ROOT_DIR/docs/demo/run-readme-demo.sh"
  status=$?
  set -e
  {
    printf 'DONE: manual session exited with status %s\n' "$status"
    printf '\n'
  } >> "$RUN_LOG"
  capture_text_evidence
  exit "$status"
fi

require_cmd expect

export ROOT_DIR COLS ROWS RUN_LOG SCENARIO_DELAY ANSWER_WAIT ANSWER_HOLD PROMPT

expect <<'EXPECT'
set timeout 45
fconfigure stdout -encoding utf-8
fconfigure stderr -encoding utf-8

proc log_turn {prompt status} {
  set fd [open $::env(RUN_LOG) a]
  if {$status eq "start"} {
    puts $fd "PROMPT: $prompt"
    puts $fd "MODE: live ummaya CLI; model-selected tools"
  } else {
    puts $fd "DONE: waited $::env(ANSWER_WAIT)s for live response, then held $::env(ANSWER_HOLD)s"
    puts $fd ""
  }
  close $fd
}

proc run_turn {prompt} {
  log_turn $prompt start
  sleep $::env(SCENARIO_DELAY)
  send "\025"
  sleep 0.1
  send -- "$prompt\r"
  sleep $::env(ANSWER_WAIT)
  sleep $::env(ANSWER_HOLD)
  log_turn $prompt done
}

set root $::env(ROOT_DIR)
set cols $::env(COLS)
set rows $::env(ROWS)
set launch "cd \"$root\" && export PATH=\"/opt/homebrew/opt/bun/bin:/opt/homebrew/opt/uv/bin:\$PATH\" && stty columns $cols rows $rows && exec bash docs/demo/run-readme-demo.sh"

spawn -noecho bash -c $launch
set child_pid [exp_pid]
expect {
  -re "for shortcuts" {
    sleep 2
  }
  eof {
    puts stderr "ummaya exited before the main UI rendered"
    exit 1
  }
  timeout {
    puts stderr "timed out waiting for the main UI"
    catch {exec kill -TERM $child_pid}
    exit 1
  }
}
sleep 1

run_turn $::env(PROMPT)

catch {exec kill -TERM $child_pid}
sleep 0.3
catch {close}
catch {wait}
EXPECT

capture_text_evidence
