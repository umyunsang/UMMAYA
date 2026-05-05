#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 7c — /export in isolation
#
# Drives /export without any prior LLM turn so we can isolate whether
# the dialog opens, whether it survives Enter, and whether ~/Downloads
# receives a PDF file.

set -uo pipefail

wait_for_pane "KOSMOS|kosmos" 60 || true
sleep 3
snapshot_pane 0-boot

# Direct /export with no prior turn (turns array will be empty)
send_text_pane '/export'
send_enter_pane
sleep 4
snapshot_pane 1-export-after-slash

# Confirm the PDF write
send_keys_pane Enter
sleep 5
snapshot_pane 2-export-after-enter

# Wait for PDF write completion (or error message)
sleep 5
snapshot_pane 3-after-wait

# Esc dismiss
send_keys_pane Escape
sleep 2
snapshot_pane 4-final
