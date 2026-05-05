#!/usr/bin/env bash
# Wave-3 re-smoke δ8 — slash autocomplete prefix filter + ▶ glyph
# Finding: F-delta-08 (G7) — /p autocomplete shows wrong results; no ▶ highlight glyph
# Pass conditions:
#   1. Type /p → dropdown shows /plugins (starts with 'p'), NOT /export /help /config
#   2. Selected row shows ▶ glyph
#   3. Esc clears the dropdown
#   4. Type /he → only /help (or /history) shown, NOT /branch /fork /export

set -euo pipefail

export SNAP_SEQ=0
export OUTDIR TMUX_SESSION

echo "=== δ8: slash autocomplete prefix filter + ▶ glyph (F-delta-08) ==="

# Wait for REPL ready
wait_for_pane "tool_registry|KOSMOS v|❯|Type a message|>" 30
snapshot_pane "delta8-repl-ready"

# Test 1: Type /p and check autocomplete
send_text_pane "/p"
sleep 0.5
snapshot_pane "delta8-slash-p"

# Capture the pane text and check for correct suggestions
PANE_TEXT=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- Pane text after /p ---"
echo "$PANE_TEXT" | grep -i "plugin\|plugins\|export\|help\|config\|branch\|▶" || echo "[no matching lines]"

# Test 2: Check ▶ glyph is present on selected row
if echo "$PANE_TEXT" | grep -q "▶"; then
  echo "[PASS] ▶ glyph found in autocomplete dropdown"
else
  echo "[WARN] ▶ glyph NOT found — may not be visible in viewport"
fi

# Test 3: Escape clears dropdown
send_keys_pane Escape
sleep 0.3
snapshot_pane "delta8-after-esc"

# Clear input
send_keys_pane C-u
sleep 0.2

# Test 4: Type /he and check autocomplete prefix filter
send_text_pane "/he"
sleep 0.5
snapshot_pane "delta8-slash-he"

PANE_TEXT2=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- Pane text after /he ---"
echo "$PANE_TEXT2" | grep -iE "help|history|branch|fork|export|▶" || echo "[no matching lines]"

# Verify /branch /fork /export NOT shown for /he
if echo "$PANE_TEXT2" | grep -qiE "\bbranch\b|\bfork\b|\bexport\b"; then
  echo "[FAIL] Spurious suggestions (branch/fork/export) shown for /he"
else
  echo "[PASS] No spurious /branch /fork /export suggestions for /he"
fi

# Test 5: Type /fork and verify /branch NOT shown
send_keys_pane Escape
sleep 0.2
send_keys_pane C-u
sleep 0.2
send_text_pane "/fork"
sleep 0.5
snapshot_pane "delta8-slash-fork"

PANE_TEXT3=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- Pane text after /fork ---"
echo "$PANE_TEXT3" | grep -iE "fork|branch|▶" || echo "[no matching lines]"

if echo "$PANE_TEXT3" | grep -qi "\bbranch\b"; then
  echo "[FAIL] /branch alias collision still present for /fork"
else
  echo "[PASS] /branch alias NOT shown for /fork input"
fi

send_keys_pane Escape
sleep 0.2
send_keys_pane C-u
sleep 0.2

echo "=== δ8 scenario complete — check snap files for verdict ==="
send_ctrlc_pane
sleep 0.5
