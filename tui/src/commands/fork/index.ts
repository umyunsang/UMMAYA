// SPDX-License-Identifier: Apache-2.0
// KOSMOS — /fork as a first-class session-fork command (decision:
// docs/decisions/fork-command-decision.md, 2026-05-04).
//
// Honors `docs/requirements/kosmos-migration-tree.md § L1-A · A5` which
// promises four distinct citizen-facing session-lifecycle modes:
// `--continue / --resume / --fork / new`.
//
// CC's `FORK_SUBAGENT` feature flag (tui/src/stubs/bun-bundle.ts:5) is a
// permanent stub returning `false` in KOSMOS — that flag gates a different
// concept (parallel subagent dispatch with prompt-cache-aligned prefix,
// `tui/src/tools/AgentTool/forkSubagent.ts`). KOSMOS's `/fork` is the
// session-fork variant: copy the current transcript JSONL with a new
// `sessionId` and resume into the copy. The handler is byte-identical to
// `/branch`'s handler (`tui/src/commands/branch/branch.ts:call`) so we
// re-use it via `load()` rather than duplicating the JSONL-copy logic.
//
// The `branch` command keeps `aliases: ['fork']` as belt-and-suspenders;
// the registry deduplicates on canonical name, so the alias never shadows
// this entry.
import type { Command } from '../../commands.js'

const fork = {
  type: 'local-jsx',
  name: 'fork',
  // Citizen-facing description in English.
  description: 'Fork the current conversation into a new session',
  argumentHint: '[name]',
  // Re-use the branch handler. branch.ts:createFork() generates a new UUID,
  // copies all transcript entries, preserves content-replacement metadata,
  // saves under getTranscriptPathForSession(forkId), and resumes via
  // context.resume(sessionId, forkLog, 'fork'). No code path differs
  // between /fork and /branch at runtime.
  load: () => import('../branch/branch.js'),
} satisfies Command

export default fork
