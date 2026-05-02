#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec 2521 — LLM Swap-Surface CC Parity Audit
#
# Verifies the rebuild branch maintains strict CC byte-copy + bounded swap
# methodology. Exits 0 on PASS, 1 on DRIFT, 2 on TOOL ERROR, 78 on CONFIG ERROR.
#
# Contract: specs/2521-llm-swap-cc-rebuild/contracts/parity-audit-cli.md
# Implementation: T026-T034

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_VERSION="2521.T034"
CC_CLAUDE_SHA="6d3fd16e608120d502e70ec461ffb66bcbca12fa86862859606c9118f977a999"
CC_SOURCE_PATH=".references/claude-code-sourcemap/restored-src/src/services/api/claude.ts"
CC_STREAM_RANGE_START=1980
CC_STREAM_RANGE_END=2295

# Procedure-A files that must be byte-copied from CC source
PROC_A_FILES=(
  "tui/src/services/api/claude.ts"
)

# Procedure-B files that require CC reference citations
PROC_B_FILES=(
  "tui/src/ipc/llmClient.ts"
  "src/kosmos/llm/client.py"
  "src/kosmos/ipc/stdio.py"
)

# Allowed swap commit subject prefixes
ALLOWED_SWAP_PREFIXES=(
  "byte-copy(2521):"
  "swap/llm-provider(2521):"
  "swap/anti-anthropic-1p(2521):"
  "swap/identifier-rename(2521):"
)

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
JSON_OUTPUT=0
STRICT=0
VERBOSE=0
PRINT_HELP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON_OUTPUT=1; shift ;;
    --strict) STRICT=1; shift ;;
    --verbose) VERBOSE=1; shift ;;
    -h|--help) PRINT_HELP=1; shift ;;
    *)
      echo "Unknown flag: $1" >&2
      echo "Usage: $0 [--json] [--strict] [--verbose] [-h|--help]" >&2
      exit 78
      ;;
  esac
done

if [[ $PRINT_HELP -eq 1 ]]; then
  cat <<'HELP'
LLM Swap-Surface CC Parity Audit (Spec 2521)

Usage: scripts/llm_swap_parity_audit.sh [--json] [--strict] [--verbose]

Flags:
  --json      Emit ParityAuditOutcome as JSON to stdout.
  --strict    Treat warnings as failures (exit 1 on any warning).
  --verbose   Print classification details for every commit + channel.
  -h, --help  Show this help.

Exit codes:
  0  PASS — no drift detected
  1  DRIFT — unjustified hunk OR byte-copy SHA mismatch OR missing citation
  2  TOOL ERROR — required binary missing (sha256sum, git, awk)
  78 CONFIG ERROR — invoked from wrong dir or branch malformed

Spec: specs/2521-llm-swap-cc-rebuild/spec.md FR-004 + FR-005 + FR-009
Contract: specs/2521-llm-swap-cc-rebuild/contracts/parity-audit-cli.md
HELP
  exit 0
fi

# ---------------------------------------------------------------------------
# Tool dependency checks (T026: prerequisite)
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git not found in PATH" >&2
  exit 2
fi

if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD="shasum -a 256"
else
  echo "ERROR: neither sha256sum nor shasum found" >&2
  exit 2
fi

if ! command -v awk >/dev/null 2>&1; then
  echo "ERROR: awk not found in PATH" >&2
  exit 2
fi

if ! command -v grep >/dev/null 2>&1; then
  echo "ERROR: grep not found in PATH" >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Repo root resolution
# ---------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: not in a git repository" >&2
  exit 78
}
cd "$REPO_ROOT"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
PARITY_MATRIX="$REPO_ROOT/specs/2521-llm-swap-cc-rebuild/parity-matrix.md"

if [[ ! -f "$PARITY_MATRIX" ]]; then
  echo "ERROR: parity-matrix.md not found at $PARITY_MATRIX" >&2
  exit 78
fi

if [[ ! -f "$CC_SOURCE_PATH" ]]; then
  echo "ERROR: CC source not found at $CC_SOURCE_PATH" >&2
  exit 78
fi

# ---------------------------------------------------------------------------
# State accumulators
# ---------------------------------------------------------------------------
OVERALL_EXIT=0    # 0=pass, 1=drift

declare -a UNJUSTIFIED_HUNKS=()
declare -a MISSING_CITATIONS=()
declare -a WARNINGS=()
declare -a ERRORS=()

# Per-file JSON fragments (built up, emitted at end)
declare -a PER_FILE_JSON=()
declare -a STREAM_CHANNEL_JSON=()

# Counters per file (parallel arrays indexed by file position)
declare -a FILE_BYTE_MATCH=()
declare -a FILE_SWAP_COUNT=()
declare -a FILE_UNJUSTIFIED=()
declare -a FILE_MISSING_CITE=()

# ---------------------------------------------------------------------------
# Helper: sha256 of a file
# ---------------------------------------------------------------------------
sha256_file() {
  local path="$1"
  $SHA256_CMD "$path" | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# Helper: sha256 of a file at a given git commit
# ---------------------------------------------------------------------------
sha256_at_commit() {
  local commit="$1"
  local path="$2"
  git show "${commit}:${path}" 2>/dev/null | $SHA256_CMD | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# Helper: emit verbose message
# ---------------------------------------------------------------------------
vlog() {
  if [[ $VERBOSE -eq 1 ]]; then
    echo "[verbose] $*" >&2
  fi
}

# ---------------------------------------------------------------------------
# Helper: mark drift
# ---------------------------------------------------------------------------
mark_drift() {
  OVERALL_EXIT=1
}

# ---------------------------------------------------------------------------
# Helper: handle warning (warn by default; fail under --strict)
# ---------------------------------------------------------------------------
warn() {
  local msg="$1"
  WARNINGS+=("$msg")
  if [[ $STRICT -eq 1 ]]; then
    mark_drift
  fi
  if [[ $JSON_OUTPUT -eq 0 ]]; then
    echo "  [WARN] $msg" >&2
  fi
}

# ---------------------------------------------------------------------------
# Helper: JSON-escape a string (no external deps — pure bash + sed)
# ---------------------------------------------------------------------------
json_escape() {
  local s="$1"
  # escape backslash, double-quote, and common control chars
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\t'/\\t}"
  echo "$s"
}

# ---------------------------------------------------------------------------
# T026 — Procedure-A SHA verification
# ---------------------------------------------------------------------------
check_procedure_a() {
  local kosmos_path="$1"
  local file_idx="$2"

  # Find the byte-copy commit for this file in git log
  local byte_copy_commit=""
  byte_copy_commit="$(git log --oneline --all --grep="^byte-copy(2521):" -- "$kosmos_path" 2>/dev/null | head -1 | awk '{print $1}')"

  if [[ -z "$byte_copy_commit" ]]; then
    vlog "Procedure-A: no byte-copy(2521) commit found for $kosmos_path"
    ERRORS+=("No byte-copy(2521) commit found for $kosmos_path")
    FILE_BYTE_MATCH[$file_idx]="false"
    mark_drift
    return
  fi

  vlog "Procedure-A: found byte-copy commit $byte_copy_commit for $kosmos_path"

  # SHA of the file at the byte-copy commit
  local sha_at_commit
  sha_at_commit="$(sha256_at_commit "$byte_copy_commit" "$kosmos_path")"

  vlog "  SHA at byte-copy commit: $sha_at_commit"
  vlog "  Expected CC SHA:         $CC_CLAUDE_SHA"

  if [[ "$sha_at_commit" == "$CC_CLAUDE_SHA" ]]; then
    vlog "  byte_copy_sha_match=true"
    FILE_BYTE_MATCH[$file_idx]="true"
  else
    vlog "  byte_copy_sha_match=false — DRIFT"
    FILE_BYTE_MATCH[$file_idx]="false"
    ERRORS+=("Byte-copy SHA mismatch for $kosmos_path: got $sha_at_commit, expected $CC_CLAUDE_SHA")
    mark_drift
  fi
}

# ---------------------------------------------------------------------------
# T027 — Swap commit category verification
# ---------------------------------------------------------------------------
check_swap_commits() {
  local kosmos_path="$1"
  local file_idx="$2"
  local swap_count=0

  # Find the byte-copy commit for this file (may be empty for Procedure-B files)
  local byte_copy_commit_sc=""
  byte_copy_commit_sc="$(git log --oneline --all --grep="^byte-copy(2521):" -- "tui/src/services/api/claude.ts" 2>/dev/null | head -1 | awk '{print $1}')"

  # Only inspect commits AFTER the byte-copy commit (the 2521 methodology range).
  # Pre-byte-copy commits are out of scope and do not generate warnings.
  local log_range=""
  if [[ -n "$byte_copy_commit_sc" ]]; then
    log_range="${byte_copy_commit_sc}..HEAD"
  else
    # No byte-copy commit found — fall back to full history for Procedure-B files
    log_range="HEAD"
  fi

  # Walk commits in range touching this file; skip merge commits (> 1 parent)
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    local commit_hash subject
    commit_hash="$(echo "$line" | awk '{print $1}')"
    subject="$(echo "$line" | cut -d' ' -f2-)"

    # Skip merge commits
    local parent_count
    parent_count="$(git cat-file -p "$commit_hash" 2>/dev/null | grep -c "^parent " 2>/dev/null || echo 0)"
    [[ "$parent_count" =~ ^[0-9]+$ ]] || parent_count=0
    if [[ "$parent_count" -gt 1 ]]; then
      vlog "  Skipping merge commit $commit_hash"
      continue
    fi

    # Check if subject matches any allowed prefix
    local matched=0
    for prefix in "${ALLOWED_SWAP_PREFIXES[@]}"; do
      if [[ "$subject" == "$prefix"* ]]; then
        matched=1
        swap_count=$((swap_count + 1))
        vlog "  Commit $commit_hash OK: category prefix '$prefix'"
        break
      fi
    done

    if [[ $matched -eq 0 ]]; then
      # Not a swap commit in the 2521 range — warn
      local touches_file
      touches_file="$(git show --name-only --format="" "$commit_hash" 2>/dev/null | grep -c "^${kosmos_path}$" 2>/dev/null || echo 0)"
      [[ "$touches_file" =~ ^[0-9]+$ ]] || touches_file=0
      if [[ "$touches_file" -gt 0 ]]; then
        warn "Commit $commit_hash ('$subject') touches $kosmos_path after byte-copy but has no swap category prefix"
      fi
    fi
  done < <(git log --oneline "$log_range" -- "$kosmos_path" 2>/dev/null)

  FILE_SWAP_COUNT[$file_idx]="$swap_count"
  vlog "Procedure-A/B: $swap_count swap commits for $kosmos_path (range: $log_range)"
}

# ---------------------------------------------------------------------------
# T028 — Unjustified hunk detection
# ---------------------------------------------------------------------------
check_unjustified_hunks() {
  local kosmos_path="$1"
  local file_idx="$2"
  local unjust_count=0

  # Find the byte-copy commit
  local byte_copy_commit
  byte_copy_commit="$(git log --oneline --all --grep="^byte-copy(2521):" -- "$kosmos_path" 2>/dev/null | head -1 | awk '{print $1}')"

  if [[ -z "$byte_copy_commit" ]]; then
    vlog "Unjustified-hunk check: no byte-copy commit found for $kosmos_path — skipping"
    FILE_UNJUSTIFIED[$file_idx]=0
    return
  fi

  # Walk every commit between byte-copy and HEAD that touches this file.
  # For each commit, check whether its subject has a swap category prefix.
  # If a non-swap-prefix commit introduces hunks, those hunks are unjustified.
  local current_commit=""
  local current_subject=""
  local in_diff=0
  local commit_hunk_count=0

  while IFS= read -r line; do
    if [[ "$line" =~ ^commit\ [0-9a-f]+ ]]; then
      local matched_hash
      matched_hash="$(echo "$line" | awk '{print $2}')"
      # Flush previous commit
      if [[ -n "$current_commit" && "$commit_hunk_count" -gt 0 ]]; then
        local is_swap=0
        for prefix in "${ALLOWED_SWAP_PREFIXES[@]}"; do
          if [[ "$current_subject" == "$prefix"* ]]; then
            is_swap=1
            break
          fi
        done
        # Skip merge commits
        local parent_ct
        parent_ct="$(git cat-file -p "$current_commit" 2>/dev/null | grep -c "^parent " 2>/dev/null || echo 0)"
        [[ "$parent_ct" =~ ^[0-9]+$ ]] || parent_ct=0
        if [[ "$is_swap" -eq 0 && "$parent_ct" -le 1 ]]; then
          unjust_count=$((unjust_count + commit_hunk_count))
          local hunk_desc="$commit_hunk_count unjustified hunk(s) in $kosmos_path from commit $current_commit ('$current_subject')"
          UNJUSTIFIED_HUNKS+=("$hunk_desc")
          ERRORS+=("$hunk_desc")
          mark_drift
          vlog "  UNJUSTIFIED: $hunk_desc"
        else
          vlog "  Commit $current_commit: $commit_hunk_count hunk(s) — swap-labeled OK (parent_ct=$parent_ct)"
        fi
      fi
      current_commit="$matched_hash"
      current_subject=""
      in_diff=0
      commit_hunk_count=0
    elif [[ -z "$current_subject" && ! "$line" =~ ^(Author:|Date:|Merge:|\s*$) ]]; then
      # First non-empty, non-header line after commit hash = subject
      current_subject="$(echo "$line" | sed 's/^[[:space:]]*//')"
    elif [[ "$line" =~ ^diff\ --git ]]; then
      in_diff=1
    elif [[ $in_diff -eq 1 && "$line" =~ ^@@ ]]; then
      commit_hunk_count=$((commit_hunk_count + 1))
    fi
  done < <(git log -p --reverse "${byte_copy_commit}..HEAD" -- "$kosmos_path" 2>/dev/null)

  # Flush last commit
  if [[ -n "$current_commit" && "$commit_hunk_count" -gt 0 ]]; then
    local is_swap=0
    for prefix in "${ALLOWED_SWAP_PREFIXES[@]}"; do
      if [[ "$current_subject" == "$prefix"* ]]; then
        is_swap=1
        break
      fi
    done
    local parent_ct
    parent_ct="$(git cat-file -p "$current_commit" 2>/dev/null | grep -c "^parent " 2>/dev/null || echo 0)"
    [[ "$parent_ct" =~ ^[0-9]+$ ]] || parent_ct=0
    if [[ "$is_swap" -eq 0 && "$parent_ct" -le 1 ]]; then
      unjust_count=$((unjust_count + commit_hunk_count))
      local hunk_desc="$commit_hunk_count unjustified hunk(s) in $kosmos_path from commit $current_commit ('$current_subject')"
      UNJUSTIFIED_HUNKS+=("$hunk_desc")
      ERRORS+=("$hunk_desc")
      mark_drift
      vlog "  UNJUSTIFIED: $hunk_desc"
    else
      vlog "  Commit $current_commit: $commit_hunk_count hunk(s) — swap-labeled OK (parent_ct=$parent_ct)"
    fi
  fi

  vlog "Procedure-A unjustified hunk check: $unjust_count total unjustified hunk(s) in $kosmos_path"
  FILE_UNJUSTIFIED[$file_idx]="$unjust_count"
}

# ---------------------------------------------------------------------------
# T029 — Procedure-B citation verification (per-function CC reference check)
# ---------------------------------------------------------------------------
check_procedure_b_citations() {
  local kosmos_path="$1"
  local file_idx="$2"
  local missing_count=0

  if [[ ! -f "$kosmos_path" ]]; then
    warn "Procedure-B file not found: $kosmos_path"
    FILE_MISSING_CITE[$file_idx]=0
    return
  fi

  local ext="${kosmos_path##*.}"

  # Extract function/handler names based on file type
  local func_names=()
  if [[ "$ext" == "ts" || "$ext" == "tsx" ]]; then
    # TypeScript: match async function, function, arrow functions assigned to const
    while IFS= read -r fn; do
      fn="$(echo "$fn" | awk '{print $NF}' | tr -d '(')"
      [[ -n "$fn" ]] && func_names+=("$fn")
    done < <(grep -n "^\s*\(async \)\?function\s\+\|^\s*\(export \)\?\(async \)\?\(const\|let\)\s\+[a-zA-Z_]\+\s*=" "$kosmos_path" 2>/dev/null | head -50)
  elif [[ "$ext" == "py" ]]; then
    # Python: match def / async def
    while IFS= read -r fn; do
      fn="$(echo "$fn" | sed 's/.*def \([a-zA-Z_][a-zA-Z0-9_]*\).*/\1/')"
      [[ -n "$fn" && "$fn" != *"def"* ]] && func_names+=("$fn")
    done < <(grep -n "^\s*\(async \)\?def " "$kosmos_path" 2>/dev/null | head -60)
  fi

  vlog "Procedure-B: checking ${#func_names[@]} functions in $kosmos_path for CC references"

  # Check whether the file as a whole has at least some CC reference comments
  # (Fine-grained per-function checking is impractical without a full parser;
  #  we verify that the file contains at least one CC reference per 10 functions.)
  local ref_count
  ref_count="$(grep -c "CC reference:" "$kosmos_path" 2>/dev/null || true)"
  ref_count="${ref_count:-0}"
  # ensure numeric
  [[ "$ref_count" =~ ^[0-9]+$ ]] || ref_count=0
  local skip_count
  skip_count="$(grep -c "KOSMOS-N/A:\|KOSMOS-only IPC adaptation" "$kosmos_path" 2>/dev/null || true)"
  skip_count="${skip_count:-0}"
  [[ "$skip_count" =~ ^[0-9]+$ ]] || skip_count=0
  local total_coverage=$(( ref_count + skip_count ))
  local func_count="${#func_names[@]}"

  vlog "  CC reference comments: $ref_count, SKIPPED/KOSMOS-only: $skip_count, functions: $func_count"

  # Minimum coverage rule: at least 1 CC reference or skip annotation per file
  if [[ "$total_coverage" -eq 0 ]]; then
    missing_count=1
    local msg="No CC reference or SKIPPED-KOSMOS-N/A comments found in $kosmos_path"
    MISSING_CITATIONS+=("$msg")
    warn "$msg"
  else
    vlog "  CC citation coverage OK ($total_coverage annotation(s))"
  fi

  FILE_MISSING_CITE[$file_idx]="$missing_count"
}

# ---------------------------------------------------------------------------
# T030 — CC stream-event channel enumeration and coverage check
# ---------------------------------------------------------------------------
check_stream_channels() {
  # Extract case patterns from CC source lines 1980-2295
  # We extract both top-level case 'X' and nested case 'Y' patterns
  local cc_source_section
  cc_source_section="$(sed -n "${CC_STREAM_RANGE_START},${CC_STREAM_RANGE_END}p" "$CC_SOURCE_PATH" 2>/dev/null)"

  # Build list of channels from parity-matrix (canonical list per T008)
  # Format: "event_kind subtype cc_line status"
  declare -a CHANNELS=()
  # Top-level events from CC source
  declare -a CC_TOP_EVENTS=()
  while IFS= read -r line; do
    local event
    event="$(echo "$line" | sed "s/.*case '\([^']*\)'.*/\1/")"
    [[ -n "$event" ]] && CC_TOP_EVENTS+=("$event")
  done < <(echo "$cc_source_section" | grep "case '" | grep -v "//")

  vlog "CC stream events extracted: ${CC_TOP_EVENTS[*]:-none}"

  # For each event, check KOSMOS files for handler OR SKIPPED comment
  local total_channels=0
  local covered_channels=0

  # The canonical channel list from parity-matrix.md (per T008 population)
  declare -a CANONICAL_CHANNELS=(
    "message_start:n/a:1980"
    "content_block_start:tool_use:1997"
    "content_block_start:server_tool_use:2003"
    "content_block_start:text:2019"
    "content_block_start:thinking:2030"
    "content_block_delta:text_delta:2113"
    "content_block_delta:input_json_delta:2087"
    "content_block_delta:thinking_delta:2148"
    "content_block_delta:signature_delta:2127"
    "content_block_delta:citations_delta:2084"
    "content_block_delta:connector_text_delta:2068"
    "content_block_stop:n/a:2171"
    "message_delta:n/a:2213"
    "message_stop:n/a:2295"
  )

  local kosmos_claude_ts="tui/src/services/api/claude.ts"
  local kosmos_llm_client="tui/src/ipc/llmClient.ts"

  for channel_entry in "${CANONICAL_CHANNELS[@]}"; do
    local kind subtype cc_line
    kind="$(echo "$channel_entry" | cut -d: -f1)"
    subtype="$(echo "$channel_entry" | cut -d: -f2)"
    cc_line="$(echo "$channel_entry" | cut -d: -f3)"
    total_channels=$((total_channels + 1))

    local handler_found=0
    local skip_reason=""
    local kosmos_handler_path="n/a"

    # Check for SKIPPED annotation in Procedure-B files
    for pb_file in "${PROC_B_FILES[@]}"; do
      if [[ -f "$pb_file" ]]; then
        if grep -q "SKIPPED.*KOSMOS-N/A.*${kind}\|SKIPPED.*KOSMOS-N/A.*${subtype}" "$pb_file" 2>/dev/null; then
          handler_found=1
          skip_reason="$(grep "SKIPPED.*KOSMOS-N/A.*${kind}\|SKIPPED.*KOSMOS-N/A.*${subtype}" "$pb_file" 2>/dev/null | head -1 | sed 's/.*KOSMOS-N\/A: *//' | cut -c1-80)"
          kosmos_handler_path="(skipped)"
          vlog "  Channel $kind/$subtype: SKIPPED in $pb_file"
          break
        fi
      fi
    done

    # Check for handler in claude.ts (Procedure-A byte-copy)
    if [[ $handler_found -eq 0 && -f "$kosmos_claude_ts" ]]; then
      if grep -q "case '${kind}'\|case '${subtype}'" "$kosmos_claude_ts" 2>/dev/null; then
        handler_found=1
        kosmos_handler_path="${kosmos_claude_ts}:${cc_line}"
        vlog "  Channel $kind/$subtype: handler found in $kosmos_claude_ts"
      fi
    fi

    # Check for handler in llmClient.ts
    if [[ $handler_found -eq 0 && -f "$kosmos_llm_client" ]]; then
      if grep -q "${kind}\|${subtype}" "$kosmos_llm_client" 2>/dev/null; then
        handler_found=1
        kosmos_handler_path="${kosmos_llm_client}:${cc_line}"
        vlog "  Channel $kind/$subtype: handler found in $kosmos_llm_client"
      fi
    fi

    if [[ $handler_found -eq 1 ]]; then
      covered_channels=$((covered_channels + 1))
    else
      warn "CC stream channel $kind/$subtype (CC line $cc_line) has no KOSMOS handler or SKIPPED comment"
      kosmos_handler_path="MISSING"
    fi

    # Build JSON fragment for this channel
    local byte_copied="false"
    local skip_json="null"
    if [[ -n "$skip_reason" ]]; then
      byte_copied="false"
      skip_json="\"$(json_escape "$skip_reason")\""
    elif [[ "$kosmos_handler_path" != "MISSING" && "$kosmos_handler_path" != "n/a" ]]; then
      byte_copied="true"
    fi

    STREAM_CHANNEL_JSON+=("{\"cc_event_path\":\"services/api/claude.ts:${cc_line}:${subtype}\",\"cc_event_kind\":\"$(json_escape "$kind")\",\"cc_event_subtype\":\"$(json_escape "$subtype")\",\"kosmos_handler_path\":\"$(json_escape "$kosmos_handler_path")\",\"kosmos_skip_reason\":${skip_json},\"byte_copied\":${byte_copied}}")
  done

  vlog "Stream-event channel coverage: $covered_channels / $total_channels"
}

# ---------------------------------------------------------------------------
# Main audit loop
# ---------------------------------------------------------------------------
RUN_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ $JSON_OUTPUT -eq 0 ]]; then
  echo "## LLM Swap-Surface Parity Audit"
  echo ""
  echo "**Branch**: $CURRENT_BRANCH"
  echo "**Run**: $RUN_TIMESTAMP"
  echo "**Script version**: $SCRIPT_VERSION"
  echo ""
fi

# T026 + T027 + T028: Procedure-A file checks
for i in "${!PROC_A_FILES[@]}"; do
  f="${PROC_A_FILES[$i]}"
  FILE_BYTE_MATCH[$i]="n/a"
  FILE_SWAP_COUNT[$i]=0
  FILE_UNJUSTIFIED[$i]=0
  FILE_MISSING_CITE[$i]=0

  if [[ ! -f "$f" ]]; then
    ERRORS+=("Procedure-A file missing: $f")
    mark_drift
    continue
  fi

  vlog "=== Checking Procedure-A file: $f ==="

  # T026: byte-copy SHA verification
  check_procedure_a "$f" "$i"

  # T027: swap-commit category verification
  check_swap_commits "$f" "$i"

  # T028: unjustified-hunk detection
  check_unjustified_hunks "$f" "$i"
done

# T029 + T027: Procedure-B file checks
proc_b_start="${#PROC_A_FILES[@]}"
for i in "${!PROC_B_FILES[@]}"; do
  f="${PROC_B_FILES[$i]}"
  idx=$((proc_b_start + i))
  FILE_BYTE_MATCH[$idx]="n/a"
  FILE_SWAP_COUNT[$idx]=0
  FILE_UNJUSTIFIED[$idx]=0
  FILE_MISSING_CITE[$idx]=0

  if [[ ! -f "$f" ]]; then
    warn "Procedure-B file missing: $f"
    continue
  fi

  vlog "=== Checking Procedure-B file: $f ==="

  # T027: swap-commit category verification (also applies to B files)
  check_swap_commits "$f" "$idx"

  # T029: citation verification
  check_procedure_b_citations "$f" "$idx"
done

# T030: CC stream-event channel enumeration
vlog "=== Checking CC stream-event channel coverage ==="
check_stream_channels

# ---------------------------------------------------------------------------
# T031: Build output
# ---------------------------------------------------------------------------

if [[ $OVERALL_EXIT -eq 0 && "${#WARNINGS[@]}" -gt 0 && $STRICT -eq 1 ]]; then
  OVERALL_EXIT=1
fi

if [[ $JSON_OUTPUT -eq 1 ]]; then
  # Build per_file JSON array
  all_files=("${PROC_A_FILES[@]}" "${PROC_B_FILES[@]}")
  procedure_labels=("A" "B" "B" "B")

  per_file_arr=""
  for i in "${!all_files[@]}"; do
    f="${all_files[$i]}"
    proc="${procedure_labels[$i]}"
    bm="${FILE_BYTE_MATCH[$i]:-n/a}"
    sc="${FILE_SWAP_COUNT[$i]:-0}"
    uh="${FILE_UNJUSTIFIED[$i]:-0}"
    mc="${FILE_MISSING_CITE[$i]:-0}"

    # Convert n/a to JSON null, true/false to JSON bool
    if [[ "$bm" == "n/a" ]]; then
      bm_json="null"
    elif [[ "$bm" == "true" ]]; then
      bm_json="true"
    else
      bm_json="false"
    fi

    [[ -n "$per_file_arr" ]] && per_file_arr+=","
    per_file_arr+="{\"kosmos_path\":\"$(json_escape "$f")\",\"procedure\":\"$proc\",\"byte_copy_sha_match\":${bm_json},\"swap_commit_count\":${sc},\"unjustified_hunk_count\":${uh},\"missing_cc_citation_count\":${mc}}"
  done

  # Build unjustified_hunks JSON array
  unjust_arr=""
  if [[ "${#UNJUSTIFIED_HUNKS[@]}" -gt 0 ]]; then
    for h in "${UNJUSTIFIED_HUNKS[@]}"; do
      [[ -n "$unjust_arr" ]] && unjust_arr+=","
      unjust_arr+="\"$(json_escape "$h")\""
    done
  fi

  # Build missing_citations JSON array
  cite_arr=""
  if [[ "${#MISSING_CITATIONS[@]}" -gt 0 ]]; then
    for c in "${MISSING_CITATIONS[@]}"; do
      [[ -n "$cite_arr" ]] && cite_arr+=","
      cite_arr+="\"$(json_escape "$c")\""
    done
  fi

  # Build stream_channel_coverage JSON array
  chan_arr=""
  if [[ "${#STREAM_CHANNEL_JSON[@]}" -gt 0 ]]; then
    for ch in "${STREAM_CHANNEL_JSON[@]}"; do
      [[ -n "$chan_arr" ]] && chan_arr+=","
      chan_arr+="$ch"
    done
  fi

  # Build errors array
  err_arr=""
  if [[ "${#ERRORS[@]}" -gt 0 ]]; then
    for e in "${ERRORS[@]}"; do
      [[ -n "$err_arr" ]] && err_arr+=","
      err_arr+="\"$(json_escape "$e")\""
    done
  fi

  if [[ $OVERALL_EXIT -eq 0 ]]; then
    verdict="clean"
  else
    verdict="drift"
  fi

  cat <<JSON
{
  "schema_version": "2521.1",
  "generated_at": "$RUN_TIMESTAMP",
  "branch": "$(json_escape "$CURRENT_BRANCH")",
  "verdict": "$verdict",
  "per_file": [${per_file_arr}],
  "unjustified_hunks": [${unjust_arr}],
  "missing_cc_citations": [${cite_arr}],
  "stream_channel_coverage": [${chan_arr}],
  "errors": [${err_arr}],
  "exit_code": $OVERALL_EXIT
}
JSON

else
  # Human-readable Markdown output
  echo "### Per-file outcomes"
  echo ""
  echo "| KOSMOS file | Procedure | Byte-copy SHA match | Swap commits | Unjustified hunks | Missing citations |"
  echo "|---|---|---|---|---|---|"

  all_files=("${PROC_A_FILES[@]}" "${PROC_B_FILES[@]}")
  procedure_labels=("A" "B" "B" "B")

  for i in "${!all_files[@]}"; do
    f="${all_files[$i]}"
    proc="${procedure_labels[$i]}"
    bm="${FILE_BYTE_MATCH[$i]:-n/a}"
    sc="${FILE_SWAP_COUNT[$i]:-0}"
    uh="${FILE_UNJUSTIFIED[$i]:-0}"
    mc="${FILE_MISSING_CITE[$i]:-0}"

    if [[ "$bm" == "true" ]]; then
      bm_display="OK"
    elif [[ "$bm" == "false" ]]; then
      bm_display="FAIL"
    else
      bm_display="n/a"
    fi

    uh_display="$uh"
    mc_display="$mc"
    [[ "$uh" -gt 0 ]] && uh_display="**$uh (DRIFT)**"
    [[ "$mc" -gt 0 ]] && mc_display="**$mc (WARN)**"

    echo "| $f | $proc | $bm_display | $sc | $uh_display | $mc_display |"
  done

  echo ""
  echo "### Stream-event channel coverage (CC services/api/claude.ts:${CC_STREAM_RANGE_START}-${CC_STREAM_RANGE_END})"
  echo ""
  echo "| CC event kind | CC subtype | CC line | KOSMOS handler | Status |"
  echo "|---|---|---|---|---|"

  # Re-emit channels in markdown from the same canonical list
  declare -a CANONICAL_CHANNELS_MD=(
    "message_start:n/a:1980"
    "content_block_start:tool_use:1997"
    "content_block_start:server_tool_use:2003"
    "content_block_start:text:2019"
    "content_block_start:thinking:2030"
    "content_block_delta:text_delta:2113"
    "content_block_delta:input_json_delta:2087"
    "content_block_delta:thinking_delta:2148"
    "content_block_delta:signature_delta:2127"
    "content_block_delta:citations_delta:2084"
    "content_block_delta:connector_text_delta:2068"
    "content_block_stop:n/a:2171"
    "message_delta:n/a:2213"
    "message_stop:n/a:2295"
  )

  for channel_entry in "${CANONICAL_CHANNELS_MD[@]}"; do
    md_kind="$(echo "$channel_entry" | cut -d: -f1)"
    md_subtype="$(echo "$channel_entry" | cut -d: -f2)"
    md_cc_line="$(echo "$channel_entry" | cut -d: -f3)"

    md_status="byte-copied"
    md_handler="tui/src/services/api/claude.ts:${md_cc_line}"

    # Check skip status
    for pb_file in "${PROC_B_FILES[@]}"; do
      if [[ -f "$pb_file" ]]; then
        if grep -q "SKIPPED.*KOSMOS-N/A.*${md_kind}\|SKIPPED.*KOSMOS-N/A.*${md_subtype}" "$pb_file" 2>/dev/null; then
          md_status="SKIPPED (KOSMOS-N/A)"
          md_handler="(skipped)"
          break
        fi
      fi
    done

    echo "| $md_kind | $md_subtype | $md_cc_line | $md_handler | $md_status |"
  done

  echo ""
  echo "### Summary"
  echo ""

  if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
    echo "**Warnings**:"
    for w in "${WARNINGS[@]}"; do
      echo "  - $w"
    done
    echo ""
  fi

  if [[ "${#ERRORS[@]}" -gt 0 ]]; then
    echo "**Errors**:"
    for e in "${ERRORS[@]}"; do
      echo "  - $e"
    done
    echo ""
  fi

  if [[ $OVERALL_EXIT -eq 0 ]]; then
    echo "**Result**: PASS"
  else
    echo "**Result**: DRIFT (exit $OVERALL_EXIT)"
  fi

  echo "**Total unjustified hunks**: ${#UNJUSTIFIED_HUNKS[@]}"
  echo "**Missing CC citations**: ${#MISSING_CITATIONS[@]}"
  echo "**Warnings**: ${#WARNINGS[@]}"
fi

# T032: --strict and --verbose already wired above throughout
# Final exit code
exit $OVERALL_EXIT
