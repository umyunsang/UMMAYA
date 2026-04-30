# PR — Spec 2521 Procedure-A + Audit + Cleanup (follow-up to PR #2577)

Closes #2520

## Summary

Spec 2521 follow-up PR completing the remaining 36 tasks left open after PR #2577 (which delivered Phase 1+2 + US1 Procedure-B, but stopped before the high-risk 3419-LOC byte-copy and the audit/replay infrastructure). This PR brings Epic #2520 to closure as a single integrated delivery — same Spec, same Epic, no new dependencies.

## Tasks delivered (36 of 36 remaining)

### Procedure-A — `tui/src/services/api/claude.ts` (5 tasks · Lead solo, high-risk)

| Commit | Category | Description |
|---|---|---|
| `3175862` | byte-copy | T010 — overwrite 1101 LOC → CC 3419 LOC; SHA-256 `6d3fd16e…f977a999` verified |
| `4d6b9a1` | swap/llm-provider | T011 — 5× `@anthropic-ai/sdk` imports → `'../../sdk-compat.js'` re-exports |
| `3139e4c` | swap/anti-anthropic-1p | T012 — file-header documentation of 1P call-graph deadening (KOSMOS support modules already inert via Spec 1633 stubs) |
| `07d23f8` | swap/identifier-rename | T013 — 2 doc-comment brand tokens (Anthropic/Claude Code → upstream/KOSMOS) |
| (verified) | n/a | T014 — `bun typecheck` clean, `bun test tests/ipc` 98 pass / 0 fail |

### Audit script — `scripts/llm_swap_parity_audit.sh` (9 tasks · sonnet teammate)

| Commit | Description |
|---|---|
| `d4b3d32` | Full implementation — T026 byte-copy SHA · T027 swap-commit categories · T028 unjustified hunks · T029 Procedure-B citations · T030 14 channel coverage · T031 `--json` schema · T032 `--strict` / `--verbose` · T033 CI integration via `.github/workflows/ci.yml` `parity-audit` job · T034 6-case negative test in `tests/test_parity_audit.sh` |
| `9d532d5` | empty-array JSON serialization fix |

Final audit run (committed as `parity-audit-final-report.md`):

```
Result: PASS
Total unjustified hunks: 0
Missing CC citations: 0
Warnings: 0
exit_code: 0
```

### Replay script — `specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh` (3 tasks · sonnet teammate + Lead fix)

| Commit | Description |
|---|---|
| `e78141e` | Full implementation — T035 byte-copy + cherry-pick chain · T036 `--self-test` · T037 quickstart `Replay refresh handling` section |
| `e66e150` | Fix — non-mutating self-test (the original mutating self-test stranded users on a temp branch when cherry-pick of the byte-copy commit conflicted with the manually-cp'd patch). New self-test verifies the same invariants without git mutation. |

Self-test verified: `--self-test` exit 0, `--dry-run` exit 0.

### Spec 1633 cleanup remediation — `specs/2292-cc-parity-audit/cc-parity-audit.md` (4 tasks · sonnet teammate)

| Commit | Classification of 30 cleanup-needed entries |
|---|---|
| `d8aa3d0` | (a) **Resolved by Spec 2521 byte-copy**: 1 — `tui/src/services/api/claude.ts` row 97; (b) **Resolved by Spec 2521 swap commit**: 0; (c) **Deferred (out of Spec 2521 scope)**: 29 — all 29 mapped to Epic β #2293 follow-ups (with 2 entries possibly overlapping Epic δ #2295) |

T041 `## 10. Follow-up cleanup tracking (post-Spec-2521)` section appended to the audit doc with all 29 deferred entries grouped into 4 categories and primary-Epic recommendations.

### Polish — parity-matrix.md final population (2 tasks · Lead solo)

| Commit | Description |
|---|---|
| `faa6cf5` | T042 + T043 — every (TBD) cell replaced with concrete `<file>:<line>` citations; Procedure-A Step A + Step B commits table populated with real SHAs (3175862 / 4d6b9a1 / 3139e4c / 07d23f8) and per-commit line ranges |

### Final verification (5 tasks · Lead solo)

- T044 `prompts/manifest.yaml` SHA — already updated in PR #2577 (no prompt changes here)
- T045 `uv run pytest` — 3475 passed / 36 skipped / 2 xfailed
- T046 `bun --cwd tui test` (CI subset) — 273 pass / 1 skip / 2 todo / 0 fail
- T047 `git diff main -- pyproject.toml tui/package.json` — zero new dependencies
- T048 `scripts/llm_swap_parity_audit.sh --strict` — exit 0, full PASS report committed
- T049 user-flow regression — keyframes from PR #2577 (`smoke-wait-keyframe-2-thinking-visible.png`) cover the same scenario; the byte-copy path is dead code (no callers), so no live behavioral surface changed
- T050 — this document

## Channel coverage (parity-matrix.md verification)

| CC stream-event | KOSMOS handler | Status |
|---|---|---|
| `message_start` (1980) | `tui/src/services/api/claude.ts:1980` (byte-copy) + `tui/src/ipc/llmClient.ts:344-358` (live) | byte-copied + live |
| `content_block_start` text (2019) | byte-copy + `tui/src/ipc/llmClient.ts:371-378` | byte-copied + live |
| `content_block_start` thinking (2030) | byte-copy + `tui/src/ipc/llmClient.ts:387-395` | byte-copied + live |
| `content_block_start` tool_use (1997) | byte-copy + `tui/src/ipc/llmClient.ts:491-521` | byte-copied + live |
| `content_block_delta` text_delta (2113) | byte-copy + `tui/src/ipc/llmClient.ts:411-415` + `src/kosmos/llm/client.py:786` | byte-copied + live |
| `content_block_delta` thinking_delta (2148) | byte-copy + `tui/src/ipc/llmClient.ts:398-407` + `src/kosmos/llm/client.py:802` | byte-copied + live |
| `content_block_delta` input_json_delta (2087) | byte-copy + `src/kosmos/llm/client.py:805` | byte-copied (collapsed at IPC) |
| `content_block_stop` (2171) | byte-copy + `tui/src/ipc/llmClient.ts:466,511-513` | byte-copied + live |
| `message_delta` (2213) | byte-copy + `tui/src/ipc/llmClient.ts:469-474` | byte-copied + live |
| `message_stop` (2295) | byte-copy + `tui/src/ipc/llmClient.ts:476-477` | byte-copied + live |
| `server_tool_use` (2003) | (skipped) | KOSMOS-N/A |
| `signature_delta` (2127) | (skipped) | KOSMOS-N/A |
| `citations_delta` (2084) | (skipped) | KOSMOS-N/A |
| `connector_text_delta` (2068) | (skipped) | KOSMOS-N/A |

## Test plan

- [x] `uv run pytest` → 3475 passed / 36 skipped / 2 xfailed
- [x] `bun --cwd tui test` (CI subset) → 273 pass / 0 fail
- [x] `bun --cwd tui run typecheck` → clean
- [x] `bash scripts/llm_swap_parity_audit.sh --strict` → exit 0, PASS
- [x] `bash specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh --self-test` → exit 0
- [x] `bash specs/2521-llm-swap-cc-rebuild/scripts/replay_rebuild.sh --dry-run` → exit 0
- [x] `bash tests/test_parity_audit.sh` → 6/6 PASS
- [x] `git diff main -- pyproject.toml tui/package.json` → 0 dependency changes

## Dispatch tree

```
Phase A · Procedure-A (Lead solo)               T010-T014  ✓
Phase B · sonnet teammates (parallel)
   sonnet-audit    (Backend Architect)          T026-T034  ✓ (d4b3d32 + 9d532d5)
   sonnet-replay   (Backend Architect)          T035-T037  ✓ (e78141e + e66e150)
   sonnet-cleanup  (Backend Architect)          T038-T041  ✓ (d8aa3d0)
Phase C · Polish (Lead solo)                    T042-T050  ✓
```

## Sub-issues closed by this PR

T010-T014 + T026-T050 (36 sub-issues under Epic #2520) — closure via `gh issue close` after merge.

## Constitution / methodology compliance

- **§I Reference-Driven** — every task cites FR + parity-matrix row + CC reference (verified by audit T029)
- **§II Fail-Closed** — zero new permission classifications
- **§III Pydantic v2** — no schema changes in this PR
- **§VI Deferred Work** — 29 cc-parity-audit cleanup-needed entries explicitly logged with target Epic mapping (Epic β #2293 / Epic δ #2295)
- **AGENTS.md sub-issue cap** — Epic #2520 stays at 56 sub-issues (within ≤ 100)
- **AGENTS.md SC-008** — zero new runtime dependencies (verified by `git diff main -- pyproject.toml tui/package.json`)
- **AGENTS.md `feedback_integrated_pr_only`** — single integrated PR for the remaining Epic 2520 surface (apology + course-correction after PR #2577 was merged with partial delivery)
