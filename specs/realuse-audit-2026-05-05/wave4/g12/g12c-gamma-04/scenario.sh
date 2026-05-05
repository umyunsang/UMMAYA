#!/usr/bin/env bash
# Wave-4 G12c re-smoke: F-gamma-04 consent receipt TUI display
# Uses aimock (instant LLM) instead of K-EXAONE (60-90s reasoning delay)
# Verifies: after a verified tool call + Y grant → /consent list shows ≥1 receipt
# REQUIRES: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 KOSMOS_PIPA_CONSENT=opt-in-explicit
#           KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1

set -euo pipefail

OUTDIR="${OUTDIR:?OUTDIR must be set}"
TMUX_SESSION="${TMUX_SESSION:?TMUX_SESSION must be set}"

SNAP_SEQ=0

echo "=== G12c: F-gamma-04 consent receipt TUI display (aimock) ==="

wait_for_pane "tool_registry|KOSMOS|❯" 45
snapshot_pane "g12c-boot"

sleep 1

# Step 1: Send a request that triggers a lookup (kma_short_term_forecast)
# The aimock fixture matches "g12c-lookup-test"
send_text_pane "g12c-lookup-test"
sleep 0.2
snapshot_pane "g12c-typed"

send_enter_pane
sleep 2
snapshot_pane "g12c-after-submit"

# Wait for permission modal or response (aimock is fast)
# kma_short_term_forecast may or may not trigger modal depending on policy
wait_for_pane "permission|허용|⓵|⓶|⓷|Y|N|한 번만|세션|Beaming|Razzmatazz|Loading|result|날씨|결과|✗|error" 20

snapshot_pane "g12c-after-llm-resp"

PANE1=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)

# If permission modal shown, press Y
if echo "$PANE1" | grep -qE "⓵|⓶|⓷|permission|허용|한 번만"; then
  echo "[G12c] Permission modal detected — pressing Y"
  send_text_pane "y"
  sleep 2
  wait_for_pane "Beaming|result|날씨|tool|완료|receipt|영수증|loading|Loading" 30
  snapshot_pane "g12c-after-Y"
else
  echo "[G12c] No permission modal (auto-allowed or error)"
fi

# Step 2: Run /consent list and check for receipts
sleep 1
send_text_pane "/consent list"
sleep 0.3
snapshot_pane "g12c-consent-typed"

send_enter_pane
sleep 2
snapshot_pane "g12c-consent-after-enter"

# Check receipt count
wait_for_pane "receipts|영수증|rcpt-|receipt|총.*건|0건|발급된" 10
snapshot_pane "g12c-consent-result"

PANE2=$(tmux capture-pane -t "$TMUX_SESSION" -p 2>/dev/null)
echo "--- /consent list content ---"
echo "$PANE2" | grep -iE "receipt|영수증|rcpt|총|건|발급" || echo "[no receipt lines]"

RECEIPT_COUNT=$(echo "$PANE2" | grep -cE "rcpt-|receipt_id|rcpt_" 2>/dev/null || echo 0)
echo "[G12c] Receipt entries in viewport: $RECEIPT_COUNT"

if echo "$PANE2" | grep -qE "rcpt-|총 [1-9]|[1-9]건"; then
  echo "[G12c] PASS: receipts visible in /consent list TUI — F-gamma-04 CLOSED"
elif echo "$PANE2" | grep -qE "0건|아직 발급된|No receipts"; then
  echo "[G12c] FAIL: 0 receipts — TUI-disk sync issue confirmed (F-gamma-04 NOT_CLOSED)"
else
  echo "[G12c] AMBIGUOUS: check snap file"
fi

# Also check disk receipts to confirm they exist
RECEIPT_FILE=~/.kosmos/memdir/user/consent/$(date +%Y-%m-%d).jsonl
if [[ -f "$RECEIPT_FILE" ]]; then
  DISK_COUNT=$(wc -l < "$RECEIPT_FILE")
  echo "[G12c] Disk receipts today: $DISK_COUNT"
else
  echo "[G12c] No disk receipt file for today"
fi

send_keys_pane Escape
sleep 0.5
snapshot_pane "g12c-final"

send_ctrlc_pane
sleep 0.3
send_ctrlc_pane
echo "=== G12c scenario complete ==="
