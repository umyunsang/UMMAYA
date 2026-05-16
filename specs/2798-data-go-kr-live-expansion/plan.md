# Implementation Plan: data.go.kr Live Expansion

**Branch**: `2798-data-go-kr-live-expansion` | **Date**: 2026-05-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/Users/um-yunsang/UMMAYA/specs/2798-data-go-kr-live-expansion/spec.md`

## Summary

Expand `src/ummaya/tools/verified_data_go_kr/` from the Spec 2797 set of 14 direct-curl verified adapters to the full 30 callable API set proven on 2026-05-16. The three provider/key mapping blockers remain excluded and documented. The implementation keeps public read-only data under the current adapter fetch path (`find({"tool_id": ..., "params": ...})`), while allowing resolver-style `locate` calls only when a selected adapter needs normalized place data before the public-data fetch.

The technical approach is deliberately conservative: extend the existing verified adapter manifest/factory/client pattern, add strict Pydantic v2 schemas per new adapter, replay saved sanitized fixtures in default tests, and run a real local UMMAYA terminal smoke after registration so the LLM's own tool-call behavior is inspected.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Pydantic v2, httpx async client, pytest, stdlib `logging`
**Storage**: Versioned fixture/docs/schema files only; no runtime database changes
**Testing**: `uv run pytest` with fixture-only default tests; live probes stay manual/local and out of CI
**Target Platform**: UMMAYA Python backend and terminal/TUI runtime on macOS/Linux
**Project Type**: CLI/backend tool-adapter package
**Performance Goals**: No registry boot regression beyond adding 16 adapter objects; adapter calls keep the existing 10 second HTTP timeout and per-adapter rate limits
**Constraints**: No live public API calls in CI; no hardcoded credentials; no source `Any` in public tool I/O; no `send` mutation; no identity-oriented `check` routing for public status facts; no `tui/src/**` changes planned
**Scale/Scope**: 16 new adapters, 30 total verified public-data adapters, 3 explicit blockers, one real local terminal smoke report

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Reference-Driven Development | PASS | Research maps decisions to `docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`, `.references/claude-code-sourcemap/restored-src/src/Tool.ts`, `.references/.../src/query.ts`, and saved agency/API artifacts. |
| II. Fail-Closed Security | PASS | Only direct-success read-only APIs are registered; blocked `15038392`, `15058923`, `15063444` stay excluded; every adapter keeps agency policy citation. |
| III. Pydantic v2 Strict Typing | PASS | Each new adapter gets a strict `BaseModel` input schema; output remains the verified collection model. |
| IV. Government API Compliance | PASS | Default tests replay saved fixtures; credentials stay in `UMMAYA_` env vars; transport quirks are manifest-level contract data. |
| V. Policy Alignment | PASS | The feature increases Open API / OpenMCP-style public-service tool coverage without changing the primitive surface. |
| VI. Deferred Work Accountability | PASS | The three blocked APIs and operational follow-ups are listed in the spec's deferred table and will be materialized by `/speckit-taskstoissues`. |

## Reference Bootstrap

- UMMAYA thesis/docs: `docs/vision.md § Reference materials`, `docs/vision.md § Layer 2 — Tool System`, `docs/requirements/ummaya-migration-tree.md § L1-B/L1-C`, `docs/onboarding/codex-continuation.md`.
- CC restored-src files: `.references/claude-code-sourcemap/restored-src/src/Tool.ts` for tool validation and permission sequence; `.references/claude-code-sourcemap/restored-src/src/query.ts` for tool-use/tool-result pairing and loop recovery.
- Adapter/API sources: `docs/api/data-go-kr-candidate-docs/LIVE-API-CALL-MATRIX-2026-05-16.md`, `LIVE-API-BLOCKER-RESOLUTION-2026-05-16.md`, per-ID `usage-notes-2026-05-16*.md`, Swagger/DOCX captures, and saved direct-check/blocker-resolution probe artifacts.
- External primary sources: Official data.go.kr catalog URLs saved under per-ID `data-go-kr-catalog.json` / `openapi-schemaorg.json`; provider guide files saved in the candidate folders.
- Implementation constraints: fixture-only CI, direct curl evidence before wrapping, fail-closed validation, strict schemas, secret-free artifacts.
- Unknowns or blocked evidence: provider/key mapping remains unresolved for `15038392`, `15058923`, `15063444`; those are out of implementation scope.

## Project Structure

### Documentation (this feature)

```text
specs/2798-data-go-kr-live-expansion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── dispatch-tree.md
├── real-use-smoke.md
├── contracts/
│   └── adapter-wave.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/ummaya/tools/
├── models.py
└── verified_data_go_kr/
    ├── _client.py
    ├── _factory.py
    ├── _manifest.py
    ├── _models.py
    ├── __init__.py
    └── <16 new thin adapter modules>.py

tests/unit/tools/
├── test_registry_count_breakdown.py
└── verified_data_go_kr/
    ├── test_manifest.py
    ├── test_registration.py
    └── test_fixture_replay.py

docs/api/
├── verified-data-go-kr/README.md
└── schemas/<tool_id>.json
```

**Structure Decision**: Reuse the existing Spec 2797 `verified_data_go_kr` package. Do not create a new adapter family because the 16 additions share the same evidence-gated public-data contract, parser, registry, and fixture replay path.

## Complexity Tracking

No constitution violations are introduced. The only shared-helper changes are contract-preserving extensions:

| Extension | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Allow `http://` endpoint pattern in `VerifiedAdapterSpec` | `15121954` succeeds only through the documented HTTP gateway evidence while HTTPS returns gateway failure. | Forcing HTTPS would knowingly register a non-callable endpoint. |
| Add optional manifest request headers | `15074634` returns normal XML only with browser-like `User-Agent`. | Hardcoding a header in the client would hide the adapter-specific upstream quirk and affect unrelated APIs. |
| Extend `Ministry` enum | New agencies need typed metadata. | Using `OTHER` for all new agencies would weaken routing/search and violate FR-010's preference for typed institutions. |

## Post-Design Constitution Re-check

PASS. The Phase 1 design keeps every live adapter tied to direct evidence, keeps all default tests offline, avoids TUI source changes, keeps read-only public-data calls out of `send`, and preserves UMMAYA's current primitive semantics.
