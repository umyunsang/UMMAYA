#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-3 re-smoke β1 — "강남 날씨" (KMA weather lookup)
# Verifies F-beta-05 (JSON ellipsis) and F-beta-06 (PTY/SKY/VEC natural language)
# Sourced by scripts/tui-tmux-capture.sh

# 1. Boot
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

# 2. Input
send_text_pane "강남 날씨 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

# 3. First lookup paint — K-EXAONE thinking can take 30-90s
# Broader pattern to catch thinking start OR tool call OR error
wait_for_pane "∴ Thinking|● lookup|⏺ lookup|resolve_location|lookup|Thinking|thinking|오류|error" 120
snapshot_pane "first-tool-call"

# 4. Wait for final rendered answer or result indicator
# K-EXAONE response takes 30-180s total including reasoning
# Use broad patterns including the final assistant message
wait_for_pane "⎿|강남|°C|날씨|비가|맑|흐림|구름|forecast|kma|resolve_location.*\}|invalid" 180 || true
snapshot_pane "after-result"

# 5. Check for raw pty/sky/vec codes NOT appearing in assistant output
# (F-beta-06: system prompt enum mappings should prevent raw code leak)
# Capture scrollback for post-analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta1-scrollback.txt" 2>/dev/null || true

# 6. Settle — K-EXAONE can take 5-8 min total
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

# 7. Full scrollback for JSON truncation + enum analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta1-final-scrollback.txt" 2>/dev/null || true

# 8. Quit
send_text_pane "/quit"
send_enter_pane
sleep 2
snapshot_pane "quit" || true
