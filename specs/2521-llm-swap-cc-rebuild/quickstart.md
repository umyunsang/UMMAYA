# Quickstart: LLM Swap-Surface CC Byte-Copy + Bounded Swap Migration

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Data Model**: [data-model.md](./data-model.md)
**Date**: 2026-05-01

This document describes how to execute and verify the rebuild procedure.

## Prerequisites

- Clean working tree on `main` branch (or rebase target).
- `.references/claude-code-sourcemap/restored-src/` present (CC 2.1.88 source-of-truth).
- Bun 1.2.x + Python 3.12+ + uv installed.
- `KOSMOS_FRIENDLI_TOKEN` + `KOSMOS_DATA_GO_KR_API_KEY` set in `.env` for live smoke.

## Step 1 — Switch to rebuild branch

```sh
git checkout 2521-llm-swap-cc-rebuild
```

## Step 2 — Inspect the canonical parity matrix

```sh
$EDITOR specs/2521-llm-swap-cc-rebuild/parity-matrix.md
```

The matrix lists per file:
- `procedure` (A or B)
- `cc_source_path` or `cc_analog_path`
- byte-copy commit SHA
- subsequent swap commits with categories
- coverage of the CC stream-event channels

## Step 3 — Run the parity audit (CI gate)

```sh
scripts/llm_swap_parity_audit.sh
```

Expected output: `**Result**: ✅ PASS`. See `contracts/parity-audit-cli.md` for full output spec.

If FAIL: stdout names the failing file + reason (unjustified hunk / byte-copy mismatch / missing citation). The Epic is not mergeable until 0 failures.

## Step 4 — Replay the rebuild from clean main (optional, reproducibility check)

```sh
# In a scratch worktree, on a clean main:
git worktree add /tmp/2521-replay main
cd /tmp/2521-replay
specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh
git diff 2521-llm-swap-cc-rebuild
# Expected: empty diff (replay produces same tree as the branch)
```

Replay script applies, in order:
1. Step A byte-copy commits per Procedure-A file (using `cp <cc_source_path> <kosmos_path>` then `git commit -m "byte-copy(2521): import CC <path>"`)
2. Step B swap commits in their original order, each with their category-prefixed subject

## Step 5 — Verify the user-visible thinking display (Layer 4 vhs smoke)

```sh
pkill -f "bun.*tui|kosmos.*ipc" 2>/dev/null
find src/kosmos/ipc/__pycache__ src/kosmos/llm/__pycache__ -name '*.pyc' -delete 2>/dev/null

# Run vhs scenario
vhs specs/2521-llm-swap-cc-rebuild/scripts/smoke-thinking-render.tape

# Expected artifacts (vision-verified by Lead Opus):
ls specs/2521-llm-swap-cc-rebuild/
#   smoke-keyframe-1-boot.png
#   smoke-keyframe-2-thinking.png    ← MUST show "∴ Thinking" dim italic
#   smoke-keyframe-3-result.png
```

## Step 6 — Run regression tests

```sh
# Backend Python
uv run pytest tests/llm tests/integration tests/ipc -x

# TUI Bun
bun --cwd tui test
```

Expected: ≥1660 passed Python tests + bun test baseline green.

## Step 7 — Optional: spot-check individual swap categories

Inspect commits by category:

```sh
# llm-provider swaps (Anthropic SDK → KOSMOS IPC)
git log --oneline 2521-llm-swap-cc-rebuild --grep '^swap/llm-provider:'

# anti-anthropic-1p deletions
git log --oneline 2521-llm-swap-cc-rebuild --grep '^swap/anti-anthropic-1p:'

# identifier renames (brand tokens)
git log --oneline 2521-llm-swap-cc-rebuild --grep '^swap/identifier-rename:'

# tool-domain (CC dev tools → KOSMOS primitives) — likely 0 commits in this Epic
git log --oneline 2521-llm-swap-cc-rebuild --grep '^swap/tool-domain:'
```

## Troubleshooting

### Audit fails: byte-copy SHA mismatch

Cause: byte-copy commit was amended, or `.references/claude-code-sourcemap/restored-src/` changed.

Fix:
```sh
# Re-byte-copy from current CC source:
cp .references/claude-code-sourcemap/restored-src/src/services/api/claude.ts \
   tui/src/services/api/claude.ts
git add tui/src/services/api/claude.ts
git commit --amend --no-edit
# Re-apply swap commits via interactive rebase
git rebase -i <byte-copy-sha>
```

### Audit fails: unjustified hunk

Cause: a recent commit modified an in-scope file without a `swap/<category>:` subject prefix.

Fix:
```sh
git rebase -i HEAD~N
# Edit the offending commit's subject to start with `swap/<category>:`
# Add a `Refs: <cc-path>:<line-range>` line in the body
git rebase --continue
```

### Audit fails: missing CC citation in Procedure-B file

Cause: a function in a Procedure-B file (e.g., `src/kosmos/llm/client.py`) lacks `CC reference: ...` in its docstring.

Fix: add a comment like:
```python
def _stream_response(self, ...):
    """Stream chat completion response.

    CC reference: services/api/claude.ts:1980-2295 (streaming handler).
    Behavior-mirror: emits AssistantChunkFrame fields matching CC's
    content_block_delta event taxonomy.
    """
```

## Replay refresh handling

When the CC source-of-truth is updated to a newer CC release (e.g. CC 2.1.88 → CC 2.2.0),
the byte-copy commit's SHA will become stale and `scripts/llm_swap_parity_audit.sh` will
report a SHA mismatch. Use this step-by-step procedure to bring KOSMOS back in sync.

### Step R-1 — Update the CC source directory

Fetch the new CC release into `.references/claude-code-sourcemap/restored-src/`.
Exact fetch procedure is out of scope for this spec (see `.references/` directory conventions
and Deferred Item #2576); the canonical expectation is that the directory is replaced in place.

```sh
# Verify the new CC source is in place:
sha256sum .references/claude-code-sourcemap/restored-src/src/services/api/claude.ts
# Record the new SHA — you will need it for Step R-3.
```

### Step R-2 — Run parity audit to see the drift

```sh
scripts/llm_swap_parity_audit.sh --strict
```

The audit output will show:
- `byte_copy_sha_match=false` for `tui/src/services/api/claude.ts`
- Possibly new unjustified hunks if the CC file changed in regions that were previously
  byte-identical (i.e., no KOSMOS swap was needed there before, but now the CC and KOSMOS
  files differ)

Save the drift report:

```sh
scripts/llm_swap_parity_audit.sh --strict > specs/2521-llm-swap-cc-rebuild/drift-report-$(date +%Y%m%d).md 2>&1 || true
```

### Step R-3 — Update parity-matrix.md File-level row

Open `specs/2521-llm-swap-cc-rebuild/parity-matrix.md` and update the
`tui/src/services/api/claude.ts` File-level row:

| column | old value | new value |
|--------|-----------|-----------|
| CC SHA-256 / lines | previous CC SHA | new SHA from Step R-1 |
| Expected post-byte-copy SHA-256 | previous CC SHA | new SHA from Step R-1 |
| Drift evidence | prior note | add `CC refreshed to vX.Y.Z on <date>` |

Also update `EXPECTED_CC_SHA` constant in
`specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh`:

```sh
# Replace the hard-coded SHA near the top of replay_rebuild.sh:
# EXPECTED_CC_SHA="<old-sha>"
# → EXPECTED_CC_SHA="<new-sha>"
```

### Step R-4 — Re-run the replay script; resolve cherry-pick conflicts

Run the replay script on a scratch worktree to see which swap commits apply cleanly and
which conflict:

```sh
git worktree add /tmp/2521-replay-refresh main
cd /tmp/2521-replay-refresh
specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh --no-test 2>&1 | tee /tmp/replay-log.txt
```

**If cherry-pick succeeds** for all 4 swap commits: the CC change did not touch any of the
swap points — no further action needed except a follow-up commit to record the new baseline.

**If cherry-pick fails (conflict)**:

1. The conflict is in one of the swap-point regions (a hunk that was previously swapped but
   the CC file changed that region in the new version).
2. Resolve the conflict by editing the conflicted file:
   - Accept the CC change if the new CC code still compiles with the existing swap (e.g. a
     refactor that does not affect the IPC call site) — result is still a `SWAP/llm-provider`
     diff, just against new CC lines.
   - Reject the CC change if KOSMOS's IPC bridge already handles the new CC behavior through
     a different code path — result is a `SWAP/anti-anthropic-1p` or `SWAP/llm-provider`
     deletion with updated citation.
3. After resolving, stage the file and continue:

```sh
git add tui/src/services/api/claude.ts
git cherry-pick --continue
```

4. Update the swap commit's body to change the `Refs:` line citation to the new CC line
   numbers:

```sh
git commit --amend
# Edit the commit body: change Refs: services/api/claude.ts:<old-lines> to <new-lines>
```

### Step R-5 — PR procedure

Create a dedicated PR for the CC refresh using the per-file swap commit convention:

1. **One byte-copy commit** (re-applies the new CC source verbatim):
   ```
   byte-copy(2521): import CC services/api/claude.ts byte-identical [CC vX.Y.Z]
   ```

2. **One swap commit per changed swap point** (re-applies each SWAP category with updated
   citations):
   ```
   swap/llm-provider(2521): route claude.ts through KOSMOS IPC adapter [CC vX.Y.Z refresh]
   Refs: services/api/claude.ts:<new-line-range>
   ```

3. Open a single PR combining all the refresh commits. Title:
   ```
   chore(2521): refresh CC byte-copy baseline to vX.Y.Z + reapply bounded swaps
   ```

4. Run the full audit before pushing:
   ```sh
   scripts/llm_swap_parity_audit.sh --strict
   ```
   Expected: exit 0, all swap commits classified, new SHA verified.

5. Commit the updated `specs/2521-llm-swap-cc-rebuild/parity-matrix.md` and updated
   `EXPECTED_CC_SHA` in `replay_rebuild.sh` as part of the same PR.

### Summary table

| Step | Command | Expected outcome |
|------|---------|-----------------|
| R-1 | fetch new CC source | `.references/` updated |
| R-2 | `llm_swap_parity_audit.sh --strict` | shows drift |
| R-3 | edit parity-matrix + replay_rebuild.sh | new SHA recorded |
| R-4 | `replay_rebuild.sh --no-test` on scratch worktree | cherry-picks succeed or conflict resolved |
| R-5 | single PR: 1 byte-copy + N swap commits | audit exits 0 |

## What this Epic does NOT do

Per spec § Out of Scope:
- Does not modify backend tool adapters (Korean public APIs)
- Does not modify TUI components beyond IPC/streaming layer
- Does not switch LLM provider or model
- Does not apply this methodology project-wide (only the 4 LLM-bridge files)

For project-wide application of this methodology, see the NEEDS TRACKING entry in spec § Deferred to Future Work.
