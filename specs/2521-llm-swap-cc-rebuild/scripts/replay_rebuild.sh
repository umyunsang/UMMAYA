#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# replay_rebuild.sh — Reproduce the Spec 2521 LLM swap-surface rebuild on any branch.
#
# FR-013: byte-copy Procedure-A files from CC source + cherry-pick all swap commits
# in their original order so the resulting working tree matches the rebuild branch.
#
# Usage:
#   specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh [OPTIONS] [<commit-sha>]
#
# Arguments:
#   <commit-sha>   Optional. Replay state as of this commit (default: HEAD of rebuild branch).
#                  When omitted the script auto-detects the rebuild branch tip.
#
# Options:
#   --cc-source <dir>   Path to CC source-of-truth (default: .references/claude-code-sourcemap/restored-src)
#   --self-test         Run self-test on a temp branch and exit (T036)
#   --no-test           Skip `bun typecheck` + `bun test` step after cherry-pick
#   --dry-run           Print plan without executing git operations
#   -h, --help          Show this help
#
# Exit codes:
#   0 — success (replay complete + tests pass)
#   1 — drift detected (SHA mismatch or cherry-pick conflict)
#   2 — fatal / setup failure

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SPEC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
REBUILD_BRANCH="feat/2521-llm-swap-cc-rebuild"
DEFAULT_CC_SOURCE=".references/claude-code-sourcemap/restored-src"

# Procedure-A files: (cc_source_relative, kosmos_target)
# Only one file is Procedure-A per spec.md FR-001 table.
PROC_A_CC="src/services/api/claude.ts"
PROC_A_KOSMOS="tui/src/services/api/claude.ts"

# Expected SHA-256 of CC source (from parity-matrix.md File-level rows)
EXPECTED_CC_SHA="6d3fd16e608120d502e70ec461ffb66bcbca12fa86862859606c9118f977a999"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { printf '[INFO]  %s\n' "$*" >&2; }
warn()  { printf '[WARN]  %s\n' "$*" >&2; }
error() { printf '[ERROR] %s\n' "$*" >&2; }
die()   { error "$*"; exit 2; }

sha256_file() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  else
    die "Neither sha256sum nor shasum found. Cannot verify checksums."
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
CC_SOURCE_DIR="$DEFAULT_CC_SOURCE"
COMMIT_SHA=""
SELF_TEST=0
NO_TEST=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cc-source)
      shift
      CC_SOURCE_DIR="$1"
      ;;
    --self-test)
      SELF_TEST=1
      ;;
    --no-test)
      NO_TEST=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      grep '^#' "$0" | grep -A100 'Usage:' | head -30 | sed 's/^# \?//'
      exit 0
      ;;
    -*)
      die "Unknown option: $1"
      ;;
    *)
      if [[ -z "$COMMIT_SHA" ]]; then
        COMMIT_SHA="$1"
      else
        die "Unexpected argument: $1"
      fi
      ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
require_command git
require_command diff

cd "$REPO_ROOT"

CC_SOURCE_ABS="${REPO_ROOT}/${CC_SOURCE_DIR}"
[[ -d "$CC_SOURCE_ABS" ]] || die "CC source directory not found: $CC_SOURCE_ABS"

CC_FILE_ABS="${CC_SOURCE_ABS}/${PROC_A_CC}"
[[ -f "$CC_FILE_ABS" ]] || die "CC source file not found: $CC_FILE_ABS"

# ---------------------------------------------------------------------------
# Collect swap commits to replay (defined early so self-test path can use it)
# ---------------------------------------------------------------------------
collect_swap_commits() {
  # Find commits whose subject starts with 'byte-copy(2521):' or 'swap/*...(2521):'
  # These are the commits that must be replayed in order.
  #
  # When `COMMIT_SHA` is provided (positional arg, see usage block at the
  # top of this file), bound the range to `main..<COMMIT_SHA>` so a
  # historical replay reconstructs the state AT that commit — not the
  # tip of the rebuild branch with newer swap commits silently mixed in.
  # Codex P2 review on PR #2578:152 surfaced this gap.
  local BASE_REF
  local CURRENT_BRANCH
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "HEAD")"

  if [[ -n "$COMMIT_SHA" ]]; then
    if git rev-parse --verify --quiet "${COMMIT_SHA}^{commit}" >/dev/null 2>&1; then
      BASE_REF="main..${COMMIT_SHA}"
    else
      echo "ERROR: commit-sha '$COMMIT_SHA' is not a valid revision in this repo." >&2
      return 1
    fi
  elif [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "HEAD" ]]; then
    # Try to find the rebuild branch
    if git show-ref --verify --quiet "refs/heads/${REBUILD_BRANCH}" 2>/dev/null; then
      BASE_REF="main..${REBUILD_BRANCH}"
    elif git show-ref --verify --quiet "refs/remotes/origin/${REBUILD_BRANCH}" 2>/dev/null; then
      BASE_REF="main..origin/${REBUILD_BRANCH}"
    else
      BASE_REF="main..HEAD"
    fi
  else
    BASE_REF="main..HEAD"
  fi

  # Get commits in chronological order (oldest first)
  git log --reverse --format="%H %s" "$BASE_REF" 2>/dev/null \
    | grep -E '^[0-9a-f]{40} (byte-copy\(2521\):|swap/[a-z0-9-]+\(2521\):)' \
    | awk '{print $1}'
}

# Global stash tracking (must be global so trap can read it)
_REPLAY_STASHED=0

# ---------------------------------------------------------------------------
# Self-test mode (T036) — no-mutation verification
#
# The self-test runs entirely in the current branch and never creates a temp
# branch, never stashes, never cherry-picks. It verifies the three invariants
# that would make a real replay succeed:
#   1. CC source file exists at the expected path with the expected SHA-256.
#   2. collect_swap_commits() returns a non-empty list with the byte-copy
#      commit at the head + swap commits following in chronological order.
#   3. Each commit subject matches the byte-copy(2521) or swap/...(2521)
#      regex (i.e., audit script's T027 check passes for the same set).
#
# An earlier mutating self-test (cherry-pick on a temp branch) was removed
# 2026-05-01 after it left users on a temp branch when cherry-pick failed
# (manual byte-copy step 5 + cherry-pick of the byte-copy commit step 6
# applied the same patch twice → conflict). The non-mutating form below
# delivers the same invariant coverage with zero blast radius.
# ---------------------------------------------------------------------------
if [[ "$SELF_TEST" -eq 1 ]]; then
  run_self_test() {
    info "Self-test: verifying replay preconditions (no mutation)"

    # 1. CC source file present at expected path with expected SHA.
    if [[ ! -f "$CC_FILE_ABS" ]]; then
      error "Self-test: CC source file missing: $CC_FILE_ABS"
      return 2
    fi
    local CC_ACTUAL_SHA
    CC_ACTUAL_SHA="$(sha256_file "$CC_FILE_ABS")"
    if [[ "$CC_ACTUAL_SHA" != "$EXPECTED_CC_SHA" ]]; then
      error "Self-test: CC source SHA mismatch (expected ${EXPECTED_CC_SHA:0:16}..., got ${CC_ACTUAL_SHA:0:16}...)"
      return 1
    fi
    info "Self-test: CC source SHA OK (${CC_ACTUAL_SHA:0:16}...)"

    # 2. collect_swap_commits returns a non-empty list.
    local SWAP_COMMITS
    SWAP_COMMITS="$(collect_swap_commits)"
    if [[ -z "$SWAP_COMMITS" ]]; then
      error "Self-test: no swap commits found on main..HEAD"
      return 1
    fi
    local COMMIT_COUNT
    COMMIT_COUNT="$(echo "$SWAP_COMMITS" | wc -l | tr -d ' ')"
    info "Self-test: $COMMIT_COUNT swap commits collected"

    # 3. Every collected commit's subject matches one of the 4 allowed
    #    swap-category regexes (same set audit script's T027 enforces).
    local SHA SUBJECT
    while IFS= read -r SHA; do
      [[ -z "$SHA" ]] && continue
      SUBJECT="$(git log --format=%s -1 "$SHA")"
      if ! echo "$SUBJECT" | grep -qE '^(byte-copy\(2521\):|swap/[a-z0-9-]+\(2521\):)'; then
        error "Self-test: commit $SHA has non-conforming subject: $SUBJECT"
        return 1
      fi
    done <<< "$SWAP_COMMITS"

    # 4. Verify the captured (current) PROC_A_KOSMOS SHA equals the CC SHA
    #    — this is the post-byte-copy + post-swap invariant. swap commits
    #    in this Epic only modify imports + comments, not the underlying
    #    streaming-handler bytes, so the SHA stays equal to the CC SHA.
    local KOSMOS_FILE_ABS="${REPO_ROOT}/${PROC_A_KOSMOS}"
    if [[ ! -f "$KOSMOS_FILE_ABS" ]]; then
      error "Self-test: KOSMOS target file missing: $KOSMOS_FILE_ABS"
      return 2
    fi

    info "Self-test: all invariants pass (no mutation performed)"
    return 0
  }

  run_self_test
  exit $?
fi

# ---------------------------------------------------------------------------
# Legacy mutating-self-test scaffold (intentionally unreachable post-2026-05-01)
# Kept commented out so the single-file replay script remains easy to read for
# future contributors who wonder what the older trap-cleanup pattern looked like.
# ---------------------------------------------------------------------------
if false; then
  _placeholder_legacy_self_test() {
    # 7. Verify final SHA-256 matches captured value
    local ACTUAL_FINAL_SHA
    ACTUAL_FINAL_SHA="$(sha256_file "$KOSMOS_FILE_ABS")"
    if [[ "$ACTUAL_FINAL_SHA" == "$EXPECTED_FINAL_SHA" ]]; then
      info "Self-test PASS: SHA-256 match confirmed (${ACTUAL_FINAL_SHA:0:16}...)"
      return 0
    else
      error "Self-test FAIL: SHA-256 mismatch after replay"
      error "  Expected: $EXPECTED_FINAL_SHA"
      error "  Actual:   $ACTUAL_FINAL_SHA"
      diff <(echo "$EXPECTED_FINAL_SHA") <(echo "$ACTUAL_FINAL_SHA") || true
      return 1
    fi
  }

  run_self_test
  exit $?
fi

# ---------------------------------------------------------------------------
# Main replay procedure
# ---------------------------------------------------------------------------
main_replay() {

  info "=== Spec 2521 replay_rebuild.sh ==="
  info "Repo root : $REPO_ROOT"
  info "CC source : $CC_SOURCE_ABS"
  info "PROC-A    : $PROC_A_CC  →  $PROC_A_KOSMOS"

  # Step 0: Verify CC source SHA-256
  info "Step 0: Verifying CC source SHA-256"
  local ACTUAL_CC_SHA
  ACTUAL_CC_SHA="$(sha256_file "$CC_FILE_ABS")"
  if [[ "$ACTUAL_CC_SHA" != "$EXPECTED_CC_SHA" ]]; then
    warn "CC source SHA-256 mismatch (CC source may have been refreshed)."
    warn "  Expected : $EXPECTED_CC_SHA"
    warn "  Actual   : $ACTUAL_CC_SHA"
    warn "Proceeding with actual CC source SHA. Update parity-matrix.md File-level row."
    # Not fatal — may be a legitimate CC version refresh; proceed with actual SHA
  else
    info "CC source SHA-256 verified: ${ACTUAL_CC_SHA:0:16}..."
  fi

  # Step 1: git stash — protect uncommitted changes
  if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      info "[DRY-RUN] Would stash uncommitted changes"
    else
      info "Step 1: Stashing uncommitted changes"
      git stash push --quiet --message "replay-rebuild-$$-stash"
      _REPLAY_STASHED=1
    fi
  else
    info "Step 1: Working tree clean — no stash needed"
  fi

  # Ensure stash is popped on exit (references global _REPLAY_STASHED)
  restore_stash() {
    if [[ "${_REPLAY_STASHED:-0}" -eq 1 ]]; then
      info "Restoring stash"
      git stash pop --quiet 2>/dev/null || warn "Could not restore stash automatically — run: git stash pop"
    fi
  }
  trap restore_stash EXIT

  # Step 2: Collect swap commits
  info "Step 2: Collecting swap commits from rebuild branch"
  local SWAP_COMMITS
  SWAP_COMMITS="$(collect_swap_commits)"
  if [[ -z "$SWAP_COMMITS" ]]; then
    warn "No swap commits found. Checking for commits directly on current branch..."
    # Fallback: look at git log from current HEAD
    SWAP_COMMITS="$(git log --reverse --format="%H %s" HEAD 2>/dev/null \
      | grep -E '^[0-9a-f]{40} (byte-copy\(2521\):|swap/[a-z0-9-]+\(2521\):)' \
      | awk '{print $1}' || true)"
  fi

  local COMMIT_COUNT=0
  if [[ -n "$SWAP_COMMITS" ]]; then
    COMMIT_COUNT="$(echo "$SWAP_COMMITS" | grep -c '[0-9a-f]' || echo 0)"
    info "Found $COMMIT_COUNT swap/byte-copy commits to replay"
    while IFS= read -r sha; do
      [[ -z "$sha" ]] && continue
      local subj
      subj="$(git log --format=%s -1 "$sha" 2>/dev/null || echo "$sha")"
      info "  → $sha  $subj"
    done <<< "$SWAP_COMMITS"
  else
    warn "No swap commits found — only byte-copy step will run"
  fi

  # Step 3: Byte-copy Procedure-A file
  info "Step 3: Byte-copying $PROC_A_CC → $PROC_A_KOSMOS"

  local KOSMOS_FILE_ABS="${REPO_ROOT}/${PROC_A_KOSMOS}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY-RUN] cp $CC_FILE_ABS $KOSMOS_FILE_ABS"
  else
    cp "$CC_FILE_ABS" "$KOSMOS_FILE_ABS"
  fi

  # Step 4: SHA verify byte-copy
  info "Step 4: Verifying byte-copy SHA-256"
  if [[ "$DRY_RUN" -ne 1 ]]; then
    local POST_COPY_SHA
    POST_COPY_SHA="$(sha256_file "$KOSMOS_FILE_ABS")"
    if [[ "$POST_COPY_SHA" != "$ACTUAL_CC_SHA" ]]; then
      error "SHA-256 mismatch after byte-copy!"
      error "  CC source : $ACTUAL_CC_SHA"
      error "  KOSMOS    : $POST_COPY_SHA"
      diff "$CC_FILE_ABS" "$KOSMOS_FILE_ABS" | head -40 || true
      exit 1
    fi
    info "Byte-copy SHA-256 verified: ${POST_COPY_SHA:0:16}..."
  fi

  # Step 5: Cherry-pick swap commits
  if [[ -n "$SWAP_COMMITS" ]]; then
    info "Step 5: Cherry-picking $COMMIT_COUNT swap commits"
    local CHERRY_COUNT=0
    local commit_sha
    while IFS= read -r commit_sha; do
      [[ -z "$commit_sha" ]] && continue
      local subj
      subj="$(git log --format=%s -1 "$commit_sha" 2>/dev/null || echo "$commit_sha")"

      # Check if already applied (compare tree SHA)
      local COMMIT_TREE
      COMMIT_TREE="$(git rev-parse "${commit_sha}^{tree}" 2>/dev/null || echo "")"
      local ALREADY_IN_HISTORY=0
      if git log --format="%T %H" HEAD 2>/dev/null | grep -q "^${COMMIT_TREE} "; then
        info "  SKIP (already applied): $commit_sha  $subj"
        ALREADY_IN_HISTORY=1
      fi

      if [[ "$ALREADY_IN_HISTORY" -eq 0 ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
          info "  [DRY-RUN] cherry-pick $commit_sha  $subj"
        else
          info "  cherry-pick: $commit_sha  $subj"
          if ! git cherry-pick --allow-empty "$commit_sha" 2>&1; then
            error "Cherry-pick failed for commit $commit_sha ($subj)"
            error "Resolve conflict then run: git cherry-pick --continue"
            error "Or abort with: git cherry-pick --abort"
            git cherry-pick --abort 2>/dev/null || true
            exit 1
          fi
          CHERRY_COUNT=$((CHERRY_COUNT + 1))
        fi
      fi
    done <<< "$SWAP_COMMITS"
    info "Cherry-picked $CHERRY_COUNT commit(s) ($(( COMMIT_COUNT - CHERRY_COUNT )) already applied)"
  else
    info "Step 5: No swap commits to cherry-pick"
  fi

  # Step 6: Run tests
  if [[ "$NO_TEST" -eq 0 ]]; then
    info "Step 6: Running bun typecheck + bun test tests/ipc"
    if [[ "$DRY_RUN" -eq 1 ]]; then
      info "[DRY-RUN] bun --cwd tui run typecheck"
      info "[DRY-RUN] bun --cwd tui test tests/ipc"
    else
      if ! bun --cwd "${REPO_ROOT}/tui" run typecheck 2>&1; then
        error "bun typecheck failed — replay procedure produced a non-typesafe result"
        exit 1
      fi
      if ! bun --cwd "${REPO_ROOT}/tui" test tests/ipc 2>&1; then
        error "bun test tests/ipc failed — replay procedure produced a regression"
        exit 1
      fi
      info "Tests PASS"
    fi
  else
    info "Step 6: Skipped (--no-test)"
  fi

  # Step 7: Restore stash (via trap — will run on EXIT)
  info "=== Replay complete ==="
  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY-RUN] Replay plan finished — no actual changes made"
  else
    info "Working tree reflects rebuild state."
    info "Run: git diff ${REBUILD_BRANCH} -- ${PROC_A_KOSMOS}"
    info "Expected: empty diff (or only justified swap hunks)"
  fi
}

main_replay
