# Dispatch Tree — Epic #2766

## Decision: Lead solo

**Rationale**: The 4 issues are small (≤ 4 file edits each) and tightly
correlated by render-pipeline understanding. Parallel teammate dispatch
overhead exceeds the implementation cost. Lead Opus already completed
diagnostic reading of all relevant files. Per AGENTS.md "1-2 tasks → Lead
solo", and the user's standing 2026-04-23 instruction `feedback_integrated_pr_only`
("integrated PR only, single bun test pass + 사용자 시각 검증").

```text
Phase 1 Setup (T001-T002): Lead solo
Phase 3 US1 KST (T010-T016): Lead solo (working-dir patch already exists)
Phase 4 US2 StreamGate (T020-T024): Lead solo (diagnostic-first)
Phase 5 US3 HIRA (T030-T035): Lead solo (diagnostic-first)
Phase 6 US4 Ctrl+O (T040-T044): Lead solo (chord-registry trace)
Phase 7 Polish (T050-T056): Lead solo (commit/push/PR/CI)
```

If diagnostics reveal a deeper issue requiring 3+ independent investigation
threads, escalate to parallel teammates at that boundary.
