#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-3 re-smoke β7 — "소상공인 복지" (MOHW welfare eligibility)
# Verifies F-beta-03 (dedup guard — should not retry-loop)
# Sourced by scripts/tui-tmux-capture.sh

# 1. Boot
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

# 2. Input
send_text_pane "소상공인 복지 지원 받을 수 있어?"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

# 3. First tool call
wait_for_pane "● lookup|⏺ lookup|resolve_location|mohw|welfare" 90
snapshot_pane "first-tool-call"

# 4. Wait for result — dedup should block retry loops
wait_for_pane "⎿|복지|지원|mohw|MOHW|결과|없음|repeat_call_blocked" 120 || true
snapshot_pane "after-result"

# 5. Full scrollback for retry count analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta7-scrollback.txt" 2>/dev/null || true

# 6. Settle — K-EXAONE takes up to 8 min
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 600 ))
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

tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta7-final-scrollback.txt" 2>/dev/null || true

# 7. Quit
send_text_pane "/quit"
send_enter_pane
sleep 2
snapshot_pane "quit" || true
