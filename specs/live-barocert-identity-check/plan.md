# Implementation Plan: Live BaroCert Identity Check

**Branch**: `feat/live-barocert-identity-check` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/live-barocert-identity-check/spec.md`

## Summary

Add an explicit live check tool id, `live_verify_ganpyeon_injeung`, for BaroCert
simple identity verification. The implementation adds a small provider client,
an opt-in live adapter that returns the existing `GanpyeonInjeungContext`, and
registry/dispatch metadata so the live tool id is discoverable and maps to the
canonical `ganpyeon_injeung` family. Default tests use sanitized fixtures only;
live tests are gated by `@pytest.mark.live` and `UMMAYA_BAROCERT_*` credentials.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Existing Pydantic v2, pytest, httpx/respx for tests; optional official `barocert` SDK at live runtime
**Storage**: None; no identity payload persistence
**Testing**: pytest, pytest-asyncio, fixture replay, `@pytest.mark.live` opt-in tests
**Target Platform**: UMMAYA Python backend and Codex desktop/local developer environment
**Project Type**: Python package with primitive tool adapters
**Performance Goals**: No default live calls; fixture tests complete within the normal targeted pytest budget
**Constraints**: CI/DI and raw identity fields redacted; no default CI live traffic; check-only scope
**Scale/Scope**: One live check adapter plus fixture-backed provider client variants

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Spec-driven workflow | PASS | Epic #2887 created; spec, plan, tasks, analyze, taskstoissues precede implementation. |
| Source code language | PASS | Source code and test strings will be English; Korean domain terms remain only where domain data requires them. |
| Fail-closed security | PASS | Missing credentials, missing SDK, malformed provider responses, repeated verify, and upstream errors all fail closed. |
| Pydantic v2 strict typing | PASS | Client request/status/result models use Pydantic v2 with `extra="forbid"` for external contract inputs. |
| No live calls in CI | PASS | Live tests are `@pytest.mark.live` and skip without env credentials. |
| Privacy | PASS | CI/DI, phone, birthday, name, signedData, and encrypted identity payloads are redacted. |
| Primitive boundary | PASS | Changes touch only check adapter surfaces and supporting docs/tests. |

## Project Structure

### Documentation (this feature)

```text
specs/live-barocert-identity-check/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── barocert-identity-client.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code

```text
src/ummaya/tools/live/
├── __init__.py
├── barocert_identity_client.py
└── verify_barocert_identity.py

src/ummaya/tools/
├── discovery_bridge.py
├── register_all.py
└── verify_canonical_map.py

src/ummaya/ipc/
└── stdio.py

tests/unit/tools/live/
├── test_barocert_identity_client.py
└── test_verify_barocert_identity.py

tests/integration/
├── test_live_barocert_discovery.py
└── test_tool_id_to_family_hint_translation.py

tests/live/
└── test_live_barocert_identity.py

tests/fixtures/barocert/
├── toss_request_receipt.json
├── toss_status_complete.json
├── toss_verify_complete.json
├── kakao_status_complete.json
└── naver_status_complete.json

docs/api/verify/
└── live_verify_ganpyeon_injeung.md
```

**Structure Decision**: Add a new `src/ummaya/tools/live/` package for live check
adapters that are not public-data `find`/`locate` adapters. Keep BaroCert
client logic separate from the adapter so fixture tests can validate provider
parsing without dispatching through the check primitive.

## Phase 0: Research

See [research.md](./research.md).

## Phase 1: Design & Contracts

See [data-model.md](./data-model.md), [contracts/barocert-identity-client.md](./contracts/barocert-identity-client.md), and [quickstart.md](./quickstart.md).

## Implementation Notes

- `live_verify_ganpyeon_injeung` and `mock_verify_ganpyeon_injeung` both resolve
  to `family_hint="ganpyeon_injeung"`.
- The stdio boundary must preserve selected `tool_id` in `session_context` so
  the family adapter can distinguish explicit live selection from the existing
  mock default.
- The live adapter must not import the optional BaroCert SDK at module import
  time. Runtime invocation may attempt the import and fail closed if unavailable.

## Complexity Tracking

No constitution violations require justification.
