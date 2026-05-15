# Implementation Plan: data.go.kr Verified Adapter Wave

**Branch**: `feat/data-go-kr-verified-adapters` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/Users/um-yunsang/UMMAYA/specs/2797-data-go-kr-verified-adapters/spec.md`

## Summary

Wrap only the APIs marked `Confirmed Callable` in `docs/api/data-go-kr-candidate-docs/LIVE-PROBE-RESULTS-2026-05-16.md` as first-class UMMAYA `find` adapters. The 30 newly scoped candidates are explicitly deferred because their service applications are still within the two-hour authorization window and lack direct successful curl evidence.

The implementation will add one shared verified-API helper layer for response parsing, fixture replay, error normalization, and envelope output, then register one thin adapter module per verified agency API family. This preserves UMMAYA's rule that each callable agency module appears as a separate ToolRegistry adapter while avoiding 14 copies of XML/JSON parsing logic.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: Existing `httpx`, Pydantic v2, stdlib `xml.etree.ElementTree`, stdlib `json`; no new dependency  
**Storage**: Recorded fixture files and docs artifacts only; no database  
**Testing**: `uv run pytest` with fixture-only default tests; live tests remain opt-in and skipped by default  
**Target Platform**: UMMAYA Python backend plus existing TUI/stdout primitive dispatch  
**Project Type**: CLI/backend tool-adapter feature inside existing repository  
**Performance Goals**: Adapter discovery stays bounded by the existing BM25/routing index; fixture parsing for each adapter completes within ordinary unit-test time.  
**Constraints**: No live citizen-infrastructure API calls in CI; no hardcoded API keys; Pydantic v2 I/O only; no `Any` in new tool I/O schemas; stdlib logging only; English source text except Korean domain data.  
**Scale/Scope**: 14 verified read-only adapters, grouped internally by agency where useful but registered as individual tool IDs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate Result | Evidence |
|-----------|-------------|----------|
| I. Reference-Driven Development | PASS | Research maps Tool System decisions to `docs/vision.md`, `.references/claude-code-sourcemap/restored-src/src/Tool.ts`, `MCPTool.ts`, and existing UMMAYA adapter modules. |
| II. Fail-Closed Security | PASS | Only direct-success read-only APIs are included. Deferred APIs remain unregistered. Adapter policy citations are agency/portal citations, not UMMAYA-invented classes. |
| III. Pydantic v2 Strict Typing | PASS | Plan requires explicit input/output models and a typed generic public-data item model for heterogeneous records; new I/O schemas must avoid `Any`. |
| IV. Government API Compliance | PASS | Default tests use fixtures only. Credentials remain `UMMAYA_` env vars. Live calls are manual/local only. |
| V. Policy Alignment | PASS | Feature extends official Open API access through the citizen-facing `find` surface without adding side-effecting actions. |
| VI. Deferred Work Accountability | PASS | Spec contains explicit deferred rows for 30 pending candidates and other blocked APIs; `/speckit-taskstoissues` will create/attach tracking issues. |

## Project Structure

### Documentation (this feature)

```text
specs/2797-data-go-kr-verified-adapters/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── adapter-wave.md
│   └── fixture-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/ummaya/tools/
├── verified_data_go_kr/
│   ├── __init__.py
│   ├── _client.py
│   ├── _models.py
│   ├── _parsing.py
│   ├── airkorea_air_quality.py
│   ├── bfc_funeral_cost.py
│   ├── fsc_corporate_finance.py
│   ├── ftc_large_group.py
│   ├── ftc_public_ym.py
│   ├── kcue_finance_status.py
│   ├── kcue_student_status.py
│   ├── kepco_power_usage.py
│   ├── pps_bid_public_info.py
│   ├── reb_real_estate_stats.py
│   ├── tago_bus_arrival.py
│   ├── tago_bus_location.py
│   ├── tago_bus_route.py
│   └── tago_bus_station.py
└── register_all.py

tests/tools/verified_data_go_kr/
├── fixtures/
├── test_adapter_registration.py
├── test_adapter_fixture_replay.py
├── test_error_parsing.py
└── test_no_scoped_new_30_registration.py

docs/api/
├── data-go-kr-candidate-docs/
└── verified-data-go-kr/
```

**Structure Decision**: Use a new `verified_data_go_kr` package because the first wave crosses multiple ministries but shares the same evidence-gated adapter mechanics. This avoids placing unrelated agencies under one ministry folder while preserving individual `tool_id` registration and avoiding a generic LLM-visible catch-all adapter.

## Phase 0 Research Output

Research is captured in [research.md](./research.md). Key decisions:

- All 14 included APIs map to `find`; no `locate`, `send`, or `check` adapter ships in this wave.
- Use a typed common response model with flexible item records rather than hand-writing 14 unrelated full output models.
- Implement provider-key `LINK` APIs (`15101360`, `15134761`) with separate credential env vars.
- Default tests replay saved fixtures only.
- Defer 30 pending candidates and all blocked/reachable-only APIs.

## Phase 1 Design Output

Design artifacts:

- [data-model.md](./data-model.md)
- [contracts/adapter-wave.md](./contracts/adapter-wave.md)
- [contracts/fixture-contract.md](./contracts/fixture-contract.md)
- [quickstart.md](./quickstart.md)

## Post-Design Constitution Check

| Principle | Gate Result | Notes |
|-----------|-------------|-------|
| I. Reference-Driven Development | PASS | Each design decision in research has a reference entry. |
| II. Fail-Closed Security | PASS | Unauthorized and blocked APIs are not registered. |
| III. Pydantic v2 Strict Typing | PASS | Contracts require Pydantic models and no `Any` in I/O schemas. |
| IV. Government API Compliance | PASS | Fixture-only default tests are required. |
| V. Policy Alignment | PASS | Adapters only expose read-only public-service lookups. |
| VI. Deferred Work Accountability | PASS | Deferred rows remain explicit for `/speckit-taskstoissues`. |

## Complexity Tracking

No constitution violations are introduced.
