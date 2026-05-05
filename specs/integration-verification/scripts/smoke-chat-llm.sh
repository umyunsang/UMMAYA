#!/usr/bin/env bash
# 실제 K-EXAONE chat — Korean trivial query.
set -euo pipefail
wait_for_pane "KOSMOS v0\\.[0-9]" 30
snapshot_pane "boot-ready"
send_text_pane "안녕하세요"
sleep 1
snapshot_pane "user-typed"
send_enter_pane
# Wait for assistant response start (any non-prompt output)
wait_for_pane "✻|⏺|EXAONE|assistant|답변|반갑" 90 || snapshot_pane "no-response-yet"
snapshot_pane "response-starting"
sleep 5
snapshot_pane "response-mid"
sleep 10
snapshot_pane "response-final"
send_keys_pane "C-c" "C-c"
sleep 1
snapshot_pane "exit"
