#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-3 re-smoke β6 — "재난문자" (disaster alert / CBS)
# Verifies F-beta-01 (kma_pre_warning envelope) + F-beta-02 (suffix [primitive=] label
# prevents hallucinated mock_cbs_disaster_v1 via lookup)
# Sourced by scripts/tui-tmux-capture.sh

# 1. Boot
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

# 2. Input — trigger disaster alert query
send_text_pane "지금 재난문자 있어? 기상 특보도 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

# 3. First tool call
wait_for_pane "● lookup|⏺ lookup|resolve_location|subscribe|kma_pre_warning" 90
snapshot_pane "first-tool-call"

# 4. Wait for result — should NOT use lookup(mock_cbs_disaster_v1)
wait_for_pane "⎿|기상특보|재난|경보|kma_pre_warning|특보|없음|결과" 120 || true
snapshot_pane "after-result"

# 5. Capture scrollback for analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta6-scrollback.txt" 2>/dev/null || true

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

tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta6-final-scrollback.txt" 2>/dev/null || true

# 7. Quit
send_text_pane "/quit"
send_enter_pane
sleep 2
snapshot_pane "quit" || true
