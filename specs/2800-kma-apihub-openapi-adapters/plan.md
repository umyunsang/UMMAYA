# Implementation Plan: KMA APIHub OpenAPI Adapters

**Branch**: `[2800-kma-apihub-openapi-adapters]` | **Date**: 2026-05-24 | **Spec**: [spec.md](./spec.md) | **Originating Epic**: #3000
**Input**: Feature specification from `/Users/um-yunsang/UMMAYA/specs/2800-kma-apihub-openapi-adapters/spec.md`

## Summary

Represent the complete KMA APIHub structured `typ02/openApi` catalog as UMMAYA
read-only tools while preserving the existing working current-weather and
forecast behavior. The implementation will use a generated official-catalog
artifact, one distinct `GovAPITool` per structured operation, a shared KMA
APIHub credential resolver, and a common XML/JSON response decoder. Live calls
remain approval-aware: only approved operations may be claimed live-working;
authorization-pending operations fail closed with official-source context.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Pydantic v2, httpx, existing UMMAYA `GovAPITool`, `ToolRegistry`, `ToolExecutor`, and KMA response decoding helpers
**Storage**: Versioned source metadata under `src/ummaya/tools/kma/`; fixture JSON/XML under `tests/tools/kma/fixtures/`; no database
**Testing**: `uv run pytest` focused KMA tests, non-live by default; live tests remain marked `@pytest.mark.live`
**Target Platform**: UMMAYA Python backend and TUI stdio/MCP runtime on macOS/Linux
**Project Type**: CLI/TUI-backed Python tool-adapter layer
**Performance Goals**: Register 85 additional read-only tool definitions without materially slowing boot or prompt construction; avoid default live network calls in tests
**Constraints**: No committed secrets; no live citizen-infrastructure calls from CI; Pydantic v2 input/output schemas; stdlib logging only; English source text except Korean official domain labels; no fallback to data.go.kr credentials for APIHub endpoints
**Scale/Scope**: 85 structured KMA APIHub `typ02/openApi` operations, excluding 150 non-structured `typ01`, `typ03`, `typ05`, `typ06`, and `typ09` sample URLs

## Reference Bootstrap

- **UMMAYA thesis/docs**: `docs/onboarding/codex-continuation.md`; `docs/vision.md` lines covering active `find`/`locate`/`send`/`check` primitives, Tool System, KMA APIHub as the agency-owned `authKey` boundary, and reference-before-invention.
- **CC restored-src files**: `.references/claude-code-sourcemap/restored-src/src/Tool.ts`; `.references/claude-code-sourcemap/restored-src/src/services/tools/toolOrchestration.ts`; `.references/claude-code-sourcemap/restored-src/src/services/tools/toolExecution.ts`.
- **Adapter/API sources**: `docs/api/kma/apihub-openapi-inventory.md`; existing `src/ummaya/tools/kma/*`; `src/ummaya/tools/models.py`; `src/ummaya/tools/registry.py`; `src/ummaya/tools/register_all.py`; `specs/2800-kma-apihub-openapi-adapters/evidence/apihub-catalog-2026-05-24.md`.
- **External primary sources**: official KMA APIHub category pages verified through the user's logged-in Chrome tab and repeatable public HTTP fetches on 2026-05-24.
- **Implementation constraints**: APIHub key issuance and per-operation utilization approval are separate; unapproved operations cannot be represented as proven live; non-structured URL/image/binary families are deferred.
- **Unknowns or blocked evidence**: Live success cannot be proven for the 81 currently unapproved structured operations without additional APIHub utilization approvals.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Reference-Driven Development | PASS | Plan cites CC restored source, `docs/vision.md`, migration tree, local KMA docs, and official APIHub pages. |
| II. Fail-Closed Security | PASS | API key is not recorded; authorization-pending APIs fail closed; agency policy citation remains required per adapter. |
| III. Pydantic v2 Strict Typing | PASS | Operation inputs and structured outputs use Pydantic v2 models; no `Any` in I/O schema. |
| IV. Government API Compliance | PASS | Live calls are excluded from default CI; fixtures and authorization errors are tested locally. |
| V. Policy Alignment | PASS | Read-only public weather data stays inside `find`; no citizen submission or invented permission classes. |
| VI. Deferred Work Accountability | PASS | Spec lists three deferred items tracked as #3037, #3038, and #3039. |

## Project Structure

### Documentation (this feature)

```text
specs/2800-kma-apihub-openapi-adapters/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── kma-apihub-adapter-contract.md
├── evidence/
│   └── apihub-catalog-2026-05-24.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/ummaya/tools/kma/
├── apihub_catalog.py
├── apihub_endpoint.py
├── apihub_structured_adapter.py
├── response_payload.py
├── vilage_fcst_endpoint.py
└── existing KMA adapters

tests/tools/kma/
├── test_apihub_catalog.py
├── test_apihub_endpoint.py
├── test_apihub_structured_adapter.py
└── fixtures/
    └── kma_apihub_*.xml/json

docs/api/kma/
└── apihub-openapi-inventory.md
```

**Structure Decision**: Keep existing hand-authored high-value KMA citizen-weather
adapters for current and forecast workflows, and add a structured APIHub adapter
factory for the rest of the 85-operation catalog. This preserves CC-style
operation-level tool registration while avoiding a brittle 85-file copy/paste
surface.

## Phase 0: Research

See [research.md](./research.md).

## Phase 1: Design

See [data-model.md](./data-model.md), [contracts/kma-apihub-adapter-contract.md](./contracts/kma-apihub-adapter-contract.md), and [quickstart.md](./quickstart.md).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Post-Design Constitution Check

| Principle | Status | Design Evidence |
|---|---|---|
| I. Reference-Driven Development | PASS | Research maps each design decision to CC restored source, UMMAYA docs, and official APIHub evidence. |
| II. Fail-Closed Security | PASS | Authorization state is explicit and missing credentials raise configuration errors without fallback. |
| III. Pydantic v2 Strict Typing | PASS | Data model defines typed operation metadata, input schema generation, and structured output envelopes. |
| IV. Government API Compliance | PASS | Quickstart and tasks use fixtures for default tests; live probes remain manual/local only. |
| V. Policy Alignment | PASS | All adapters are read-only `find` tools and cite KMA/public-data policy. |
| VI. Deferred Work Accountability | PASS | Deferred items are tracked as #3037, #3038, and #3039. |
