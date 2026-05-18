# Implementation Plan: Live MobileID Check Adapter

**Branch**: `feat/live-mobileid-check` | **Date**: 2026-05-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/Users/um-yunsang/.codex/worktrees/281d/UMMAYA/specs/live-mobileid-check/spec.md`

## Summary

Add one explicitly selectable live `check` adapter, `live_verify_mobile_id`, around the MobileID verification daemon contract. The adapter verifies an existing MobileID transaction reference using fixture-backed default tests and opt-in live tests, then returns a `MobileIdContext`-compatible authentication context with an opaque external session reference. Raw VP payloads, CI/DI, resident identifiers, phone numbers, birthdate-like identity data, and decrypted identity attributes are never returned, logged, snapshotted, or persisted.

The implementation is intentionally narrow: add a small MIP envelope/client module, add the live adapter and registry wiring, add tool-id-specific verify dispatch so the live adapter does not replace the existing `mock_verify_mobile_id`, and document live-readiness evidence separately from CI.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Pydantic v2, httpx async client, pytest, stdlib `base64`/`json`/`logging`
**Storage**: Versioned docs/tests/fixtures only; no runtime database changes
**Testing**: TDD with fixture-only unit/integration tests; live tests require `@pytest.mark.live` and complete `UMMAYA_MOBILEID_*` env vars
**Target Platform**: UMMAYA Python backend and terminal/TUI runtime on macOS/Linux
**Project Type**: CLI/backend tool-adapter package
**Performance Goals**: Registry boot remains constant time; adapter calls use one status call and an optional VP verification call with bounded httpx timeout
**Constraints**: No live identity/government/payment calls in CI; no hardcoded credentials; no source `Any` in public tool I/O; no `find`/`locate`/`send` behavior changes; no raw identity persistence; no `tui/src/**` changes planned
**Scale/Scope**: One live check adapter, one client module, focused dispatch/registry tests, one docs page, one opt-in live test

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Reference-Driven Development | PASS | Research cites `docs/vision.md`, current verify/mock/registry code, and the MobileID development support center pages. |
| II. Fail-Closed Security | PASS | Missing transaction references, malformed envelopes, non-2xx upstream responses, failed VP verification, and expired statuses return errors rather than verified contexts. |
| III. Pydantic v2 Strict Typing | PASS | Public tool input/output use strict Pydantic models; raw upstream JSON is normalized in the client boundary before producing typed context. |
| IV. Government API Compliance | PASS | Default tests use synthetic/sanitized fixtures; live tests are explicit and credential-gated. |
| V. Policy Alignment | PASS | The feature expands identity infrastructure under the existing active `check` primitive without adding a new root verb. |
| VI. Deferred Work Accountability | PASS | Live `send:*` delegation exchange, full ceremony orchestration, and real sanitized curl evidence are tracked separately from this v1 adapter. |

## Reference Bootstrap

- UMMAYA thesis/docs: `docs/vision.md` for the active `find`/`locate`/`send`/`check` surface, Layer 2 tool-system rules, fail-closed PIPA handling, and identity infrastructure scope.
- Existing verify model: `src/ummaya/primitives/verify.py` for `MobileIdContext`, `AuthContext`, and adapter dispatch behavior.
- Existing mock scaffolding: `src/ummaya/tools/mock/verify_mobile_id.py` and `src/ummaya/tools/mock/verify_module_modid.py` for preserving mock MobileID and mock delegation behavior.
- Registry/discovery path: `src/ummaya/tools/register_all.py`, `src/ummaya/tools/discovery_bridge.py`, `src/ummaya/tools/verify_canonical_map.py`, `src/ummaya/tools/mvp_surface.py`, and `src/ummaya/ipc/stdio.py`.
- External primary sources:
  - `https://dev.mobileid.go.kr/mip/dfs/useguide/mdGuide.do?guide=demonapiguide`
  - `https://dev.mobileid.go.kr/mip/dfs/apiuse/apiusestep.do`
- Unknowns or blocked evidence: the public pages do not define an official MobileID-to-UMMAYA `send:*` delegation-token exchange. That remains out of scope.

## Project Structure

### Documentation (this feature)

```text
specs/live-mobileid-check/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── dispatch-tree.md
├── analyze-report.md
├── contracts/
│   └── mobileid-check.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/ummaya/
├── primitives/
│   └── verify.py
└── tools/
    ├── discovery_bridge.py
    ├── register_all.py
    ├── verify_canonical_map.py
    └── live/
        ├── __init__.py
        ├── mobileid_client.py
        └── verify_mobile_id.py

tests/
├── live/
│   └── test_live_mobileid.py
├── integration/
│   └── test_live_mobileid_registration.py
└── unit/
    ├── ipc/
    │   └── test_stdio_verify_dispatch.py
    ├── primitives/
    │   └── test_verify_family_mismatch.py
    └── tools/
        └── live/
            ├── test_mobileid_client.py
            └── test_verify_mobile_id_live_adapter.py

docs/api/verify/
└── live_verify_mobile_id.md
```

**Structure Decision**: Create `src/ummaya/tools/live/` because the adapter is real-service-backed and should not be colocated with mock identity adapters. Keep shared verify-model changes minimal and additive.

## Complexity Tracking

No constitution violations are introduced. Two shared paths need narrow changes:

| Extension | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Tool-id-specific verify adapter dispatch | Both `mock_verify_mobile_id` and `live_verify_mobile_id` resolve to `family="mobile_id"`; selecting by family alone would make one overwrite the other. | Overriding the family adapter would break existing mock behavior and violate FR-003. |
| Direct live adapter registration before bridge registration | The live adapter needs an executor handler, not only a discovery entry. | Bridge-only registration would make the tool discoverable but not safely callable through the engine path. |

## Post-Design Constitution Re-check

PASS. The Phase 1 design keeps all default tests offline, preserves mock behavior, exposes the live adapter only as `check`, returns a typed safe context, and records live evidence requirements separately from fixture-backed implementation.
