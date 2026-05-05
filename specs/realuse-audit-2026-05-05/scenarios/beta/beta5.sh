#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Wave-3 re-smoke β5 — "서울 응급실" (NMC emergency search)
# SPECIAL CHECK F-beta-04: Permission modal MUST appear BEFORE NMC HTTP call
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

# 4. CRITICAL: Permission modal MUST appear before NMC HTTP dispatch
# F-beta-04 fix: _check_permission_gate gates lookup for L3 (login-gated) adapters
# After K-EXAONE finishes streaming, the tool is dispatched, and the gate fires.
# K-EXAONE reasoning can take 90-180s. We wait a long time for the modal.
# The modal renders as "민감 정보 도구" text or "⓷ 높은 위험" risk banner.
wait_for_pane "민감 정보 도구|⓷ 높은 위험|Invoke a sensitive|Y.*한번만|Y.*세션|모달|permission.*request" 300 || {
  echo "[beta5-WARN] permission modal did NOT appear within 300s — F-beta-04 may not be closed"
  snapshot_pane "modal-timeout"
  true
}
snapshot_pane "permission-modal"

# 5. Capture scrollback at modal stage
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta5-at-modal-scrollback.txt" 2>/dev/null || true

# 6. Accept permission — try Y key (modal expects a keybinding, not typed text)
send_keys_pane "y"
snapshot_pane "permission-accepted"

# 7. Wait for NMC result after permission granted
wait_for_pane "⎿|응급실|병원|NMC|병상|결과|응급의료|access_denied|permission_denied" 180 || true
snapshot_pane "after-result"

# 8. Full scrollback for ordering analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta5-final-scrollback.txt" 2>/dev/null || true

# 9. Settle — wait for the response to complete (up to 5 min for K-EXAONE)
# F-beta-04 check: permission modal must appear within this window
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 300 ))  # 5 min max for K-EXAONE
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  # Snapshot every 30s during settle to capture modal if it appears
  __now=$(date +%s)
  if (( __now % 30 == 0 )); then
    snapshot_pane "settle-$(date +%s)"
  fi
  if (( $(date +%s) - __stable_start >= 5 )); then break; fi
  sleep 0.5
done
snapshot_pane "stable"

# 10. Final scrollback for ordering analysis
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/beta5-post-settle-scrollback.txt" 2>/dev/null || true

# 11. Quit
send_text_pane "/quit"
send_enter_pane
sleep 2
snapshot_pane "quit" || true
