# Dispatch Tree: data.go.kr Verified Adapter Wave

Feature: `2797-data-go-kr-verified-adapters`
Epic: #2797

## Execution Mode

Lead solo. The user instructed autonomous continuation without approval gates, and the current implementation slice is tightly coupled through one shared helper package plus one central registration point.

## Task Map

- Phase 1 Setup: T001-T004
- Phase 2 Tests First: T005-T007, T012-T013, T018-T019, T023
- Phase 3 Core Helper: T008-T011, T020-T024
- Phase 4 Adapter Wave: T014-T017
- Phase 5 Documentation/Schema: T025-T026
- Phase 6 Verification: T027-T032
- Phase 7 Bookkeeping: T033

## Parallel-Safe Notes

T016 contains thirteen independent adapter wrappers, but they share the manifest, parsing helper, registration helper, and schema generation flow. They are kept in one Lead-owned patch to avoid contradictory public contracts across modules.
