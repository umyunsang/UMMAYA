# Dispatch Tree: KMA APIHub OpenAPI Adapters

Phase 1 Setup (T001-T003): Lead solo
Phase 2 Foundational (T004-T010): Lead solo
Phase 3 US1 (T011-T015): Lead solo
Phase 4 US2 (T016-T024): Lead solo
Phase 5 US3 (T025-T030): Lead solo
Phase 6 Polish (T031-T036): Lead solo

## Rationale

AGENTS.md allows Lead solo for coupled work. This feature has 36 tasks but most
implementation work converges on a small set of shared files:

- `src/ummaya/tools/kma/apihub_catalog.py`
- `src/ummaya/tools/kma/apihub_endpoint.py`
- `src/ummaya/tools/kma/apihub_structured_adapter.py`
- `tests/tools/kma/test_apihub_structured_adapter.py`
- `src/ummaya/tools/register_all.py`

Splitting these across Sonnet teammates would create same-file contention and
raise merge risk. The safer execution plan is Lead solo with strict task
checkpoints and focused tests after each story.
