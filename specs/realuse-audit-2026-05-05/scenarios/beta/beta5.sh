#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-3 re-smoke β5 — "서울 응급실" (NMC emergency search)
# 2026-05-05 correction: NMC coordinate location lookup is read-only public
# metadata, so no permission modal should appear before the NMC HTTP call.
# Sourced by scripts/tui-tmux-capture.sh

# 1. Boot
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "boot"

# 2. Input
send_text_pane "서울 지금 응급실 어디가 가장 가까워?"
sleep 0.5
send_enter_pane
snapshot_pane "input-submitted"

# 3. First tool call — resolve_location expected first
wait_for_pane "● lookup|⏺ lookup|resolve_location" 90
snapshot_pane "first-tool-call"

# 4. NMC lookup should proceed without a permission modal.
wait_for_pane "nmc_emergency_search|응급실|응급의료|병원|NMC|⎿" 300 || true
snapshot_pane "nmc-lookup"

# 5. Wait for NMC result.
wait_for_pane "⎿|응급실|병원|NMC|결과|응급의료|upstream_unavailable|stale_data" 180 || true
snapshot_pane "after-result"

# 6. Full scrollback for ordering analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta5-final-scrollback.txt" 2>/dev/null || true

# 7. Settle — wait for the response to complete (up to 5 min for K-EXAONE)
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 300 ))  # 5 min max for K-EXAONE
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  # Snapshot every 30s during settle to capture transient frames.
  __now=$(date +%s)
  if (( __now % 30 == 0 )); then
    snapshot_pane "settle-$(date +%s)"
  fi
  if (( $(date +%s) - __stable_start >= 5 )); then break; fi
  sleep 0.5
done
snapshot_pane "stable"

# 8. Final scrollback for ordering analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta5-post-settle-scrollback.txt" 2>/dev/null || true

# 9. Quit
send_text_pane "/quit"
send_enter_pane
sleep 2
snapshot_pane "quit" || true
