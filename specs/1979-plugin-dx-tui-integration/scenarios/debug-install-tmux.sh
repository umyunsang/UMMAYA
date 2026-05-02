#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 1979-plugin-dx-tui-integration — tmux capture-pane smoke scenario (debug-install)
#
# Ported from: specs/1979-plugin-dx-tui-integration/scripts/debug-install.expect
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
# Original scenario (set timeout 45):
#   Diagnostic: verify whether /plugin install seoul-subway (a) is accepted
#   by the slash command router, (b) renders a consent modal with Layer glyph,
#   (c) is not intercepted by a PR banner. Uses a 30s wallclock wait for TUI
#   to "do whatever it does" — no specific assertion.
#
# Migration notes:
#   1. `spawn script -q $log_path ...` — harness already handles the pane;
#      script(1) dropped. `set timeout 45` global is replaced by per-step
#      deadlines in wait_for_pane.
#   2. `sleep 2` (pre-command settle) → second wait_for_pane with tool_registry
#      predicate. Safer: TUI must finish registry boot before input lands.
#   3. `sleep 30` (no-assertion wallclock wait) → activity-based settle loop
#      capped at 30s. Preserves the original "let TUI do whatever it does"
#      spirit without burning 30s unconditionally on fast machines.
#   4. Post-settle diagnostic snapshots added: consent modal presence check
#      (positive) and PR-banner / error check (negative inline grep).
#   5. `expect eof` → send_ctrlc_pane + sleep 1 (process-termination settle).
#
# Deadline map:
#   boot          60s
#   branding      15s
#   install-settle 30s  (activity-based; original was sleep 30)

# ── 1. Boot ──────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── 2. Pre-command settle (replaces sleep 2) ─────────────────────────────────
# Wait until the splash animation clears — poll until pane stable 1s.
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
snapshot_pane pre-command

# ── 3. STAGE-2: send /plugin install seoul-subway ────────────────────────────
echo "STAGE-2: sending /plugin install seoul-subway"
send_text_pane "/plugin install seoul-subway"
sleep 0.5
send_enter_pane
snapshot_pane install-submitted

# ── 4. STAGE-3: activity-based settle (replaces sleep 30) ────────────────────
# Capture whatever the TUI renders (consent modal, error, slash-command list).
# Capped at 30s to match the original timeout budget.
echo "STAGE-3: waiting for TUI activity to settle (max 30s)"
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 30 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 2 )); then break; fi
  sleep 0.3
done
snapshot_pane install-settled

# ── 5. Diagnostic checks (original goal: identify what actually rendered) ─────
# Check A: consent modal with Layer glyph (positive — non-fatal missing is OK
#           since plugin may not be in catalog, producing a different UI).
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | \
   grep -qE "⓵|⓶|⓷ |consent|Consent|permission|Permission|Y 한번만|Y once|Deny|Y/N"; then
  echo "[SMOKE NOTE] consent modal / permission indicator detected"
  snapshot_pane consent-modal
else
  echo "[SMOKE NOTE] consent modal NOT present (plugin may not be in catalog)"
  snapshot_pane no-consent-modal
fi

# Check B: PR banner / build intercept (negative — unexpected during install)
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qiE "PR #|pull request|build.*fail|update.*available"; then
  echo "[SMOKE NOTE] PR banner or build-intercept indicator visible — may have blocked /plugin install" >&2
  snapshot_pane pr-banner-detected
fi

# Check C: slash command not recognized
if tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null | grep -qiE "unknown command|not found|unrecognized"; then
  echo "[SMOKE NOTE] command not recognized by slash-command router" >&2
  snapshot_pane cmd-not-recognized
fi

# ── 6. STAGE-4: graceful exit ─────────────────────────────────────────────────
echo "STAGE-4: sending Ctrl-C to exit"
send_ctrlc_pane
sleep 2
send_ctrlc_pane
snapshot_pane quit
