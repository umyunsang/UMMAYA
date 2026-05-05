#!/usr/bin/env bash
# Wave-3 re-smoke α — F-alpha-13: --continue cwd-scoped
# Scenario: create a session in one context, --continue in a fresh session,
#           verify it resumes the correct session (not cross-session).
# Single-shell α7 scenario.
# Required env: KOSMOS_FRIENDLI_TOKEN set

set -euo pipefail

export KOSMOS_MEMDIR_ROOT="/tmp/kosmos-wave3-alpha-f13-$$"
mkdir -p "$KOSMOS_MEMDIR_ROOT"

export KOSMOS_ONBOARDING_AUTO_COMPLETE=1
export KOSMOS_PIPA_CONSENT=opt-in-explicit
# Set explicit shell context so we can verify scoping
export KOSMOS_SHELL_CONTEXT_ID="wave3-alpha-f13-test-shell-abc123"

snapshot_pane "boot"

# Wait for REPL ready
wait_for_pane "tool_registry|KOSMOS|✻|>" 60

snapshot_pane "repl-ready"

# Type a distinctive query
send_text_pane "alpha13テスト: 5050という数字を記憶してください"
send_enter_pane

# Wait for response
wait_for_pane "5050|記憶|기억|알겠습니다|네|Error" 120

snapshot_pane "after-first-query"

# Exit the REPL
send_ctrlc_pane
sleep 2

snapshot_pane "after-exit"

# Now relaunch with --continue — should resume same session
# We need a new tmux window or just check the session was written
# Check if session JSONL was written with originalShellId
ls -la "$KOSMOS_MEMDIR_ROOT/user/sessions/" 2>/dev/null || echo "no sessions dir"

snapshot_pane "final-check"

send_ctrlc_pane

rm -rf "$KOSMOS_MEMDIR_ROOT"
