#!/usr/bin/env bash
# Wave-4 G12a re-smoke: F-ε-02 /plugin list (with correct env vars)
# REQUIRES: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 AND KOSMOS_PIPA_CONSENT=opt-in-explicit
# Env must be set BEFORE tui-tmux-capture.sh spawns `bun run tui`

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0

echo "=== G12a: F-ε-02 /plugin list (plugin browser) ==="

# Wait for REPL (onboarding must be auto-completed so we land in REPL)
wait_for_pane "tool_registry|KOSMOS|❯|Type a message" 45
snapshot_pane "g12a-boot"

# Confirm we are in REPL (not onboarding)
BOOT_CONTENT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
if echo "$BOOT_CONTENT" | grep -qE "❯|Type a message"; then
  echo "[G12a] REPL reached — onboarding bypassed correctly"
else
  echo "[G12a] WARNING: may still be in onboarding"
fi

sleep 1

# Type /plugins (the catalog name, not /plugin)
send_text_pane "/p"
sleep 0.5
snapshot_pane "g12a-slash-p-dropdown"

# Check if dropdown shows
PANE1=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
if echo "$PANE1" | grep -qE "plugins|▶|plugin"; then
  echo "[G12a/1] Autocomplete dropdown appeared for /p"
else
  echo "[G12a/1] No dropdown for /p — autocomplete NOT firing"
fi

# Add 'lugins' to complete '/plugins'
send_text_pane "lugins"
sleep 0.3
snapshot_pane "g12a-slash-plugins-typed"

# Submit
send_enter_pane
sleep 3
snapshot_pane "g12a-after-enter"

# Check for PluginBrowser/catalog overlay
PANE2=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
if echo "$PANE2" | grep -qE "플러그인|Plugin|plugin|설치된|catalog|IPC|Browser|PluginBrowser|등록된"; then
  echo "[G12a/2] PASS: Plugin overlay/browser appeared"
else
  echo "[G12a/2] FAIL: No plugin browser — command silent"
fi

snapshot_pane "g12a-result"

# Dismiss with Esc
send_keys_pane Escape
sleep 0.5
snapshot_pane "g12a-after-esc"

send_ctrlc_pane
sleep 0.3
send_ctrlc_pane
