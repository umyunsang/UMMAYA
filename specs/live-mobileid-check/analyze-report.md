# Analyze Report: Live MobileID Check Adapter

**Date**: 2026-05-18
**Scope**: `specs/live-mobileid-check/`

## Summary

The spec, plan, contracts, and tasks are internally consistent for a narrow v1 live MobileID check adapter. The main implementation risk is the shared verify dispatch path: the live and mock MobileID adapters have the same logical family, so the plan requires additive tool-id-specific dispatch. That risk is explicitly covered by tasks T011-T018.

## Consistency Checks

| Check | Result | Evidence |
|-------|--------|----------|
| User stories map to tasks | PASS | US1: T004-T010, US2: T011-T018, US3: T019-T021, US4: T022-T024. |
| Acceptance criteria covered by tests | PASS | Registry, redaction, malformed envelope, upstream failure, expired status, and live-test skip behavior all have explicit tasks. |
| No unsupported primitive changes | PASS | Plan and tasks only touch `check` registry/dispatch; `find`, `locate`, and `send` are non-goals. |
| Mock preservation covered | PASS | T012, T014, and T018 require proof that existing mock MobileID behavior remains unchanged. |
| PII/identity non-persistence covered | PASS | T004, T008, T020, T023, and T030 cover redaction and scans. |
| CI live-call prohibition covered | PASS | T022, T024, T028, and T029 cover opt-in live testing and default non-live verification. |
| Official source references included | PASS | Spec, research, and docs tasks cite MobileID development support center daemon/use-procedure URLs. |

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| Family-only verify dispatch would let live override mock or vice versa. | Add optional `tool_id` registration and `_verify_tool_id` dispatch context; test both selected live and default mock paths. |
| Upstream status vocabulary may differ by operator daemon version. | Treat only explicit success indicators as verified; unsupported states fail closed with sanitized messages. |
| VP encrypted `data` may accidentally leak through fixture snapshots. | Redaction tests scan serialized outputs and committed fixtures; docs require sanitized evidence only. |
| Live test accidentally calls network in CI. | Mark with `@pytest.mark.live`; skip before client creation unless all env vars exist. |
| Official pages do not define downstream delegation-token exchange. | Keep `send:*` delegation in existing mock `mock_verify_module_modid`; document deferral. |

## Taskstoissues Mapping Plan

Created GitHub task sub-issues for implementation phases only and linked them under Epic #2886:

- #2910: T004-T006 MIP envelope/client foundation
- #2908: T007-T010 MobileID adapter success/redaction
- #2909: T011-T018 Registry, canonical map, and dispatch wiring
- #2912: T019-T021 Fail-closed negative behavior
- #2911: T022-T024 Docs and opt-in live test
- #2913: T025-T032 Validation and PR completion

Each issue should link back to Epic #2886 as a sub-issue. The PR body should use `Closes #2886` for the Epic only and avoid task issue close keywords.
