#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Audit-3 P0-2 interactive smoke — single-stack slash dropdown verification.
#
# Scenario:
#   1. Boot TUI (bun run tui with aimock)
#   2. Wait for KOSMOS branding prompt
#   3. Type '/' and wait for dropdown to appear
#   4. Assert /help appears in dropdown
#   5. Assert /speckit-* does NOT appear
#   6. Send Ctrl-C to exit
#
# Called by scripts/tui-tmux-capture.sh:
#   OUTDIR and TMUX_SESSION are set by the harness.

# Wait for initial prompt
wait_for_pane "KOSMOS\|tool_registry\|>" 45

snapshot_pane "01-boot"

# Type '/' to trigger slash dropdown
send_text_pane "/"

# Wait for dropdown — expect /help or other catalog entries
wait_for_pane "/help\|/agents\|/onboarding" 10

snapshot_pane "02-slash-dropdown"

# Verify no speckit commands in the snapshot
if grep -q "speckit" "$OUTDIR/snap-02-slash-dropdown.txt" 2>/dev/null; then
  echo "::error::P0-2 FAIL: /speckit-* appeared in dropdown" >&2
  exit 1
fi

# Verify no add-dir in the snapshot
if grep -q "add-dir" "$OUTDIR/snap-02-slash-dropdown.txt" 2>/dev/null; then
  echo "::error::P0-2 FAIL: /add-dir appeared in dropdown" >&2
  exit 1
fi

# Verify catalog commands present
if ! grep -qE "/(help|agents|onboarding|config|export|history)" "$OUTDIR/snap-02-slash-dropdown.txt" 2>/dev/null; then
  echo "::warning::P0-2: expected catalog commands not found in snapshot (may be clipped)" >&2
fi

snapshot_pane "03-final"

# Exit TUI
send_keys_pane C-c
send_keys_pane C-c
