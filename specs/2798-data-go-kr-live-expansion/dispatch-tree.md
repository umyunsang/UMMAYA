# Dispatch Tree: data.go.kr Live Expansion

User approval on 2026-05-16 allows the full Spec Kit cycle without additional approval prompts.
Originating Epic: #2832.

Current Codex tool policy allows subagents only when explicitly requested. The user approved autonomous work, but did not explicitly request parallel subagents. Lead therefore executes solo while preserving task grouping.

```text
Phase 1 Setup: Lead solo
Phase 2 Foundational tests/helpers: Lead solo
Phase 3 US1 registry/catalog: Lead solo
Phase 4 US2 primitive/transport contracts: Lead solo
Phase 5 US3 terminal smoke: Lead solo
Phase 6 US4 docs/evidence: Lead solo
Phase 7 Polish: Lead solo
```

Parallel-safe task groups, if later dispatched by an explicit user request:

- New adapter module group A: safety/medical (`15000652`, `15001699`, `15155046`, `15075057`)
- New adapter module group B: transport/location/public status (`15158794`, `15096040`, `15127779`, `15149906`)
- New adapter module group C: notices/transparency (`15156780`, `15157820`, `15074634`, `15140950`, `15158905`, `15129471`, `15121954`, `15073554`)
