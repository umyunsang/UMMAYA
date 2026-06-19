# CC Tool Layer LazyCodex Intake

LazyCodex execution for the CC original tool-layer port must start through
`$start-work` or `$ulw-loop` and use
`.omo/plans/cc-original-tool-layer-port-lazycodex.md` as the execution input.

The research note is planning input only. The LazyCodex plan is the execution
input for this lane. Document-production-hardening 2803 remains closed and must
not be reopened by this work.

Before edits, capture and record dirty worktree state with
`git status -sb --untracked-files=all`. Preserve unrelated dirty worktree paths
as user or parallel-agent work unless the user explicitly scopes them into the
task.

Do not create GitHub issues or a PR in this task unless the user explicitly asks.
