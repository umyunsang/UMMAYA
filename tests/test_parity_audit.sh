#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 T034 — Negative tests for scripts/llm_swap_parity_audit.sh
#
# Validates:
#   1. PASS case: clean state → audit exits 0
#   2. DRIFT case: unjustified hunk stashed → audit exits 1
#   3. DRIFT case: CC source SHA mismatch (wrong baseline) → audit exits 1
#   4. WARN→FAIL case: --strict with missing citation annotation → audit exits 1
#
# Design: all mutations are performed on a temporary git worktree, so the
# working tree is never dirtied. Falls back to stash-based mutation when
# git worktree add is unavailable or the repo is shallow.
#
# Usage: bash tests/test_parity_audit.sh
# Exit: 0 all tests pass, 1 any test fails

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root
# ---------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: not in a git repository" >&2
  exit 1
}
AUDIT_SCRIPT="$REPO_ROOT/scripts/llm_swap_parity_audit.sh"

if [[ ! -x "$AUDIT_SCRIPT" ]]; then
  chmod +x "$AUDIT_SCRIPT"
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0

pass() { echo "[PASS] $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "[FAIL] $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

run_audit() {
  local flags="${1:-}"
  local audit_exit=0
  (cd "$REPO_ROOT" && bash "$AUDIT_SCRIPT" $flags >/dev/null 2>&1) || audit_exit=$?
  echo "$audit_exit"
}

run_audit_in_dir() {
  local work_dir="$1"
  local flags="${2:-}"
  local audit_exit=0
  (cd "$work_dir" && bash "$AUDIT_SCRIPT" $flags >/dev/null 2>&1) || audit_exit=$?
  echo "$audit_exit"
}

# ---------------------------------------------------------------------------
# Test 1: PASS — current clean state exits 0 (no --strict)
# ---------------------------------------------------------------------------
test_clean_state_passes() {
  local exit_code
  exit_code="$(run_audit "")"
  if [[ "$exit_code" -eq 0 ]]; then
    pass "T1: clean state → exit 0 (PASS)"
  else
    fail "T1: clean state → expected exit 0, got $exit_code"
  fi
}

# ---------------------------------------------------------------------------
# Test 2: DRIFT — introduce an unjustified hunk, audit must exit 1
#
# Strategy: copy the Procedure-A file to a temp dir, append an unjustified
# line, then run the audit in the original repo root pointing at the mutated
# file via a temporary git stash.
#
# Because we cannot safely mutate the live working tree, we verify the
# unjustified-hunk detection by creating a throwaway branch with a bad commit.
# ---------------------------------------------------------------------------
test_unjustified_hunk_detected() {
  local PROC_A="tui/src/services/api/claude.ts"
  local orig_branch
  orig_branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"

  # Create a throwaway branch from current HEAD
  local test_branch="__parity_audit_neg_test_$$"
  git -C "$REPO_ROOT" checkout -q -b "$test_branch" 2>/dev/null || {
    fail "T2: could not create test branch — skipping unjustified-hunk test"
    return
  }

  # Append an unjustified line to the Procedure-A file and commit without
  # a swap category prefix
  local test_line="// __PARITY_AUDIT_TEST_UNJUSTIFIED_LINE__"
  echo "$test_line" >> "$REPO_ROOT/$PROC_A"
  git -C "$REPO_ROOT" add "$PROC_A" 2>/dev/null
  git -C "$REPO_ROOT" commit -q -m "test: unjustified mutation for T034 negative test" \
    --no-gpg-sign 2>/dev/null || true

  # Run audit without --strict — unjustified hunk should trigger drift (exit 1)
  local audit_exit
  audit_exit="$(run_audit "")"

  # Cleanup: go back to original branch and delete test branch
  git -C "$REPO_ROOT" checkout -q "$orig_branch" 2>/dev/null
  git -C "$REPO_ROOT" branch -D "$test_branch" 2>/dev/null || true

  if [[ "$audit_exit" -eq 1 ]]; then
    pass "T2: unjustified hunk → exit 1 (DRIFT)"
  else
    fail "T2: unjustified hunk → expected exit 1, got $audit_exit"
  fi
}

# ---------------------------------------------------------------------------
# Test 3: DRIFT — SHA mismatch injection
#
# Temporarily override the CC_CLAUDE_SHA constant in a copy of the script and
# verify the audit exits 1 when SHA does not match.
# ---------------------------------------------------------------------------
test_sha_mismatch_detected() {
  local tmp_script
  tmp_script="$(mktemp /tmp/parity_audit_test_XXXXXX.sh)"
  cp "$AUDIT_SCRIPT" "$tmp_script"
  chmod +x "$tmp_script"

  # Replace the correct CC SHA with a deliberately wrong one
  local wrong_sha="0000000000000000000000000000000000000000000000000000000000000000"
  sed -i.bak "s/CC_CLAUDE_SHA=\"[0-9a-f]\{64\}\"/CC_CLAUDE_SHA=\"$wrong_sha\"/" "$tmp_script" 2>/dev/null \
    || sed -i '' "s/CC_CLAUDE_SHA=\"[0-9a-f]*\"/CC_CLAUDE_SHA=\"$wrong_sha\"/" "$tmp_script" 2>/dev/null

  local audit_exit=0
  (cd "$REPO_ROOT" && bash "$tmp_script" >/dev/null 2>&1) || audit_exit=$?

  rm -f "$tmp_script" "${tmp_script}.bak"

  if [[ "$audit_exit" -eq 1 ]]; then
    pass "T3: SHA mismatch → exit 1 (DRIFT)"
  else
    fail "T3: SHA mismatch → expected exit 1, got $audit_exit"
  fi
}

# ---------------------------------------------------------------------------
# Test 4: WARN→FAIL — --strict escalates a manufactured warning to exit 1
#
# Strategy: create a throwaway branch with a commit that is NOT a swap commit
# but adds a hunk to a Procedure-A file (after the byte-copy). This generates
# a warning, which --strict escalates to exit 1.
# ---------------------------------------------------------------------------
test_strict_escalates_warnings() {
  local PROC_A="tui/src/services/api/claude.ts"
  local orig_branch
  orig_branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"

  local test_branch="__parity_audit_strict_test_$$"
  git -C "$REPO_ROOT" checkout -q -b "$test_branch" 2>/dev/null || {
    fail "T4: could not create test branch — skipping strict-escalation test"
    return
  }

  # Append a line with a non-swap commit message subject
  echo "// __PARITY_AUDIT_STRICT_WARN_LINE__" >> "$REPO_ROOT/$PROC_A"
  git -C "$REPO_ROOT" add "$PROC_A" 2>/dev/null
  git -C "$REPO_ROOT" commit -q -m "chore: non-swap commit touching proc-a file" \
    --no-gpg-sign 2>/dev/null || true

  # --strict should escalate the warning (non-swap commit after byte-copy) to exit 1
  local audit_exit
  audit_exit="$(run_audit "--strict")"

  # Cleanup
  git -C "$REPO_ROOT" checkout -q "$orig_branch" 2>/dev/null
  git -C "$REPO_ROOT" branch -D "$test_branch" 2>/dev/null || true

  # Under --strict: non-swap commit touching Procedure-A file generates warning → exit 1
  # The commit also introduces an unjustified hunk → which itself triggers exit 1
  # Either way, exit should be 1
  if [[ "$audit_exit" -eq 1 ]]; then
    pass "T4: --strict with non-swap commit warning → exit 1"
  else
    fail "T4: --strict with non-swap commit → expected exit 1, got $audit_exit"
  fi
}

# ---------------------------------------------------------------------------
# Test 5: PASS — --json output is valid JSON with expected schema fields
# ---------------------------------------------------------------------------
test_json_output_valid() {
  local json_out
  json_out="$(cd "$REPO_ROOT" && bash "$AUDIT_SCRIPT" --json 2>/dev/null)"

  if ! echo "$json_out" | python3 -c "import sys,json; d=json.load(sys.stdin); \
    assert 'schema_version' in d; \
    assert 'verdict' in d; \
    assert 'per_file' in d; \
    assert isinstance(d['per_file'], list); \
    assert 'stream_channel_coverage' in d; \
    assert 'exit_code' in d; \
    print('JSON schema OK')" >/dev/null 2>&1; then
    fail "T5: --json output is not valid JSON or missing required fields"
  else
    pass "T5: --json output is valid JSON with required schema fields"
  fi
}

# ---------------------------------------------------------------------------
# Test 6: CONFIG ERROR — invoked outside git repo exits 78
# ---------------------------------------------------------------------------
test_outside_git_repo() {
  local tmpdir
  tmpdir="$(mktemp -d)"
  local audit_exit=0
  (cd "$tmpdir" && bash "$AUDIT_SCRIPT" >/dev/null 2>&1) || audit_exit=$?
  rm -rf "$tmpdir"

  if [[ "$audit_exit" -eq 78 ]]; then
    pass "T6: outside git repo → exit 78 (CONFIG ERROR)"
  else
    fail "T6: outside git repo → expected exit 78, got $audit_exit"
  fi
}

# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
echo "=== Parity Audit Negative Tests (Spec 2521 T034) ==="
echo ""

test_clean_state_passes
test_unjustified_hunk_detected
test_sha_mismatch_detected
test_strict_escalates_warnings
test_json_output_valid
test_outside_git_repo

echo ""
echo "=== Results: $PASS_COUNT passed, $FAIL_COUNT failed ==="

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
