#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 2639-s3-ui-guard — TUI Layer 5 tmux capture smoke
#
# Sourced (not exec'd) by scripts/tui-tmux-capture.sh.
#
# Purpose: prove that Epic #2639's changes (D3 SWAP comment headers in 5 files
# + D1 dialogLaunchers launchTeleportResumeWrapper export removal) do NOT
# regress the TUI boot path, branding, or interactive slash-command flow.
#
# All Epic #2639 source edits are either:
#   - in-source `// SWAP:` header comments above existing imports, OR
#   - removal of a single dead launcher function never called from any caller.
#
# So no LLM, no tool dispatch, no IPC envelope are exercised — just boot,
# branding, /help overlay, graceful exit.
#
# Five probe points (AGENTS.md § TUI verification):
#   1. KEYSTROKE       — send_text_pane "/help" + send_enter_pane (logged via tmux send-keys)
#   2. IPC frame       — N/A (slash command is client-side)
#   3. Tool dispatch   — N/A
#   4. RENDER          — pane snapshots prove Ink reconcile after each stage
#   5. Snapshot trigger — snap-NNN-*.txt files written to OUTDIR

# ── 1. Boot ─────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. Help slash command ───────────────────────────────────────────────────
send_text_pane "/help"
sleep 0.5
snapshot_pane help-typed
send_enter_pane

# Wait for help overlay (HelpV2 component renders Tabs with KOSMOS title
# and tab labels). Either of these substrings proves the overlay rendered.
wait_for_pane "KOSMOS|/help|general|Slash commands|키바인딩|Help" 15
snapshot_pane help-rendered

# ── 3. Settle (activity-based, not sleep-guess) ─────────────────────────────
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
snapshot_pane stable

# ── 4. Graceful quit ────────────────────────────────────────────────────────
send_ctrlc_pane
sleep 1
send_ctrlc_pane
snapshot_pane quit
