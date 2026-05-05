#!/usr/bin/env bash
# Wave-4 G12b re-smoke: F-delta-08 slash autocomplete /pl → dropdown
# Uses aimock so no real K-EXAONE needed
# Requires KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0

echo "=== G12b: F-delta-08 slash autocomplete prefix filter ==="

wait_for_pane "tool_registry|KOSMOS|❯" 45
snapshot_pane "g12b-boot"

sleep 0.5

# Test 1: /p should show autocomplete dropdown with 'plugins'
send_text_pane "/p"
sleep 0.4
snapshot_pane "g12b-slash-p"

P1=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- After /p ---"
echo "$P1" | grep -iE "plugin|plugins|export|help|branch|▶|consent|history|fork|config" || echo "[no suggestion lines]"

if echo "$P1" | grep -qiE "plugin|plugins"; then
  echo "[G12b/1] PASS: /p shows plugin suggestions"
else
  echo "[G12b/1] FAIL: /p shows no plugin suggestions — autocomplete not firing"
fi

# Test 2: /pl should show /plugins
send_text_pane "l"
sleep 0.4
snapshot_pane "g12b-slash-pl"

P2=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- After /pl ---"
echo "$P2" | grep -iE "plugin|plugins|▶|help|export|branch" || echo "[no suggestion lines]"

if echo "$P2" | grep -qiE "plugins"; then
  echo "[G12b/2] PASS: /pl shows /plugins"
else
  echo "[G12b/2] FAIL: /pl shows no /plugins candidate"
fi

# Check ▶ glyph
if echo "$P2" | grep -q "▶"; then
  echo "[G12b/▶] PASS: ▶ glyph present"
else
  echo "[G12b/▶] FAIL: ▶ glyph absent"
fi

# Esc clears
send_keys_pane Escape
sleep 0.3
snapshot_pane "g12b-after-esc"

send_keys_pane C-u
sleep 0.2

# Test 3: /he → only /help (not /branch /fork /export)
send_text_pane "/he"
sleep 0.4
snapshot_pane "g12b-slash-he"

P3=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- After /he ---"
echo "$P3" | grep -iE "help|history|branch|fork|export|▶" || echo "[no suggestion lines]"

if echo "$P3" | grep -qiE "help|history"; then
  echo "[G12b/3] PASS: /he shows /help (or /history)"
else
  echo "[G12b/3] FAIL: /he shows no help"
fi

if echo "$P3" | grep -qiE "\bbranch\b|\bfork\b|\bexport\b"; then
  echo "[G12b/3] FAIL: spurious /branch/fork/export in /he results"
else
  echo "[G12b/3] PASS: no spurious suggestions for /he"
fi

send_keys_pane Escape
sleep 0.2
send_keys_pane C-u
sleep 0.2

# Test 4: /fork → /fork only (not /branch via alias)
send_text_pane "/fork"
sleep 0.4
snapshot_pane "g12b-slash-fork"

P4=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- After /fork ---"
echo "$P4" | grep -iE "fork|branch|▶" || echo "[no suggestion lines]"

if echo "$P4" | grep -qi "\bbranch\b"; then
  echo "[G12b/4] FAIL: /branch alias still colliding with /fork"
else
  echo "[G12b/4] PASS: /branch NOT shown for /fork"
fi

send_keys_pane Escape
sleep 0.2
send_keys_pane C-u

send_ctrlc_pane
sleep 0.3
send_ctrlc_pane
echo "=== G12b scenario complete ==="
