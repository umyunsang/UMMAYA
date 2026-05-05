#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-4-p0-fix-smoke — Audit-4 P0-2 / P0-3 / P0-8 / P0-9 verification.
#
# Pre-fix snapshots (specs/audit-prod/audit-4-permission/snap-014, snap-013,
# snap-017, snap-020) showed raw IPC NDJSON
# (`{"version":"1.0","session_id":...}`) bleeding into the citizen
# terminal whenever /consent revoke was attempted. This scenario
# reproduces the same input sequence and asserts the NDJSON wire frame is
# NOT visible in the captured pane snapshots.
#
# Run:
#   bash scripts/tui-tmux-capture.sh \
#     specs/audit-prod/audit-4-p0-fix \
#     specs/audit-prod/scripts/audit-4-p0-fix-smoke.sh
set -euo pipefail

# ---------------------------------------------------------------------------
# Stage 0 — boot
# ---------------------------------------------------------------------------
wait_for_pane "tool_registry: [0-9]+ entries verified" 90
snapshot_pane "00-boot"

# ---------------------------------------------------------------------------
# Stage 1 — /consent list (empty before any grants).
# ---------------------------------------------------------------------------
send_text_pane "/consent list"
send_enter_pane
sleep 1.5
snapshot_pane "01-consent-list-empty"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 2 — /consent revoke <unknown-id> (Audit-4 P0-8 reproducer).
# Pre-fix: the TUI wrote `process.stdout.write(encodeFrame(responseFrame))`
# from `_sendPermissionResponse`; the citizen saw the raw JSON line.
# Post-fix: routes via bridgeSingleton.send() — the citizen sees only the
# Korean error banner.
# ---------------------------------------------------------------------------
send_text_pane "/consent revoke rcpt-DOES-NOT-EXIST-AUDIT4-12345"
send_enter_pane
sleep 2
snapshot_pane "02-consent-revoke-not-found"
send_keys_pane "Escape"
sleep 0.5

# ---------------------------------------------------------------------------
# Stage 3 — /consent revoke <obviously bad scope> (sanity follow-up).
# ---------------------------------------------------------------------------
send_text_pane "/consent revoke rcpt-bad-2"
send_enter_pane
sleep 2
snapshot_pane "03-consent-revoke-not-found-2"
send_keys_pane "Escape"

snapshot_pane "99-final"
