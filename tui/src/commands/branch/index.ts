import type { Command } from '../../commands.js'

// KOSMOS: in CC the `['fork']` alias was conditional on
// `feature('FORK_SUBAGENT')` (alias only when subagent fork is OFF, so the
// noun 'fork' wouldn't collide with the experimental subagent variant).
// KOSMOS hard-codes that flag to `false` (tui/src/stubs/bun-bundle.ts) AND
// promotes /fork to a first-class command (tui/src/commands/fork/index.ts,
// per docs/decisions/fork-command-decision.md). The standalone /fork takes
// precedence in the registry — this `aliases: ['fork']` array is preserved
// as belt-and-suspenders so external callers that look up `cmd.aliases`
// (e.g. analytics, tests) still see the historical CC mapping. Registry
// deduplication on canonical name (tui/src/commands.ts:registerCommand)
// guarantees no shadowing.
const branch = {
  type: 'local-jsx',
  name: 'branch',
  aliases: ['fork'],
  description: 'Create a branch of the current conversation at this point',
  argumentHint: '[name]',
  load: () => import('./branch.js'),
} satisfies Command

export default branch
