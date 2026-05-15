# Research: data.go.kr Verified Adapter Wave

## Reference Bootstrap

- UMMAYA thesis/docs:
  - `docs/vision.md` § Reference materials and Layer 2 Tool System.
  - `docs/requirements/ummaya-migration-tree.md` L1-B and L1-C.
  - `docs/onboarding/five-primitive-harness.md` active primitive guidance.
  - `docs/api/README.md` adapter catalog and fixture-first testing conventions.
- CC restored-src files:
  - `.references/claude-code-sourcemap/restored-src/src/Tool.ts`
  - `.references/claude-code-sourcemap/restored-src/src/tools/MCPTool/MCPTool.ts`
  - `.references/claude-code-sourcemap/restored-src/src/tools/ToolSearchTool/ToolSearchTool.ts`
  - `.references/claude-code-sourcemap/restored-src/src/tools/GrepTool/GrepTool.ts`
- Adapter/API sources:
  - `docs/api/data-go-kr-candidate-docs/LIVE-PROBE-RESULTS-2026-05-16.md`
  - `docs/api/data-go-kr-candidate-docs/P0-P1-WRAPPING-NOTES.md`
  - `docs/api/data-go-kr-candidate-docs/P2-WRAPPING-NOTES.md`
  - `docs/api/data-go-kr-candidate-docs/SCOPED-NEW-30-manifest.json`
  - Per-candidate `data-go-kr-inline-swagger.json`, provider guides, and saved probe artifacts.
- External primary sources:
  - Official data.go.kr detail pages captured under `docs/api/data-go-kr-candidate-docs/<id>/data-go-kr-detail.html`.
  - KEPCO and REB provider portal pages captured under their candidate folders for `LINK` APIs.
- Implementation constraints:
  - No default CI live calls.
  - No new dependency.
  - New adapter I/O schemas must use Pydantic v2 and avoid `Any`.
  - Permission policy must cite agency/portal source text.
- Unknowns or blocked evidence:
  - 30 newly scoped candidates are not authorized yet and are out of scope.
  - APIs in `Reachable But Not Yet Callable` and `Not Live-Probed` are out of scope.

## Deferred Item Validation

The spec contains a complete `Scope Boundaries & Deferred Items` section. All `NEEDS TRACKING` rows are intentional and will be resolved through `/speckit-taskstoissues` before implementation tasks are treated as fully issue-backed.

No unregistered deferral language was found outside the deferred-items table after the spec was generated.

## Decision: Map all included APIs to `find`

**Decision**: The 14 `Confirmed Callable` APIs in the live probe report are registered under the active `find` primitive.

**Rationale**: Their observed operations are read-only lookup/statistics/catalog calls. They do not resolve addresses into administrative codes, mutate agency state, or verify an identity/status assertion. UMMAYA's active primitive harness keeps domain specialization in adapters while exposing only `find`, `locate`, `send`, and `check` to the LLM.

**Alternatives considered**:

- `locate`: rejected because bus station, facility, and public-data records may contain addresses or coordinates but do not perform address/coordinate resolution.
- `send`: rejected because no included API creates, submits, pays, cancels, or signs anything.
- `check`: rejected because the included set excludes the NTS business-status API; aggregate public statistics are not identity/status verification.

## Decision: Use one shared verified-API helper package plus individual adapter modules

**Decision**: Add `src/ummaya/tools/verified_data_go_kr/` with shared request, parser, fixture, and output helpers, and keep one module per registered adapter.

**Rationale**: The wave crosses several agencies but repeats the same concerns: API-key params, XML/JSON normalization, result-code extraction, fixture replay, and `find` envelope output. A shared helper prevents 14 copies of fragile parsing code while each adapter still has its own `tool_id`, input schema, search hints, policy citation, and registration.

**Alternatives considered**:

- A single generic LLM-visible adapter: rejected because it would hide the agency module boundaries from ToolRegistry and weaken BM25 discovery.
- Full bespoke parser per API: rejected because it duplicates error handling and creates inconsistent envelope behavior.

## Decision: Use typed flexible public-data records for heterogeneous responses

**Decision**: Use a common Pydantic output model with `VerifiedPublicDataItem` records whose values are constrained to JSON-like scalar/list/map unions instead of `Any`.

**Rationale**: The verified APIs expose unrelated fields: finance summaries, air-quality stations, FTC groups, bus records, REB statistics, university statistics, and funeral fee rows. The user value is reliable tool-call wrapping and source-grounded record delivery, not immediate domain-specific analytics. A typed flexible record keeps strict Pydantic v2 boundaries without inventing lossy common fields.

**Alternatives considered**:

- Full field-by-field output model for each API: deferred because it would make the first wave too large before real-use smoke proves the tool-call flow.
- `dict[str, Any]`: rejected by constitution and AGENTS.md strict typing rules.

## Decision: Provider-key `LINK` APIs keep separate credential families

**Decision**: `15101360` KEPCO and `15134761` REB use provider-specific credential env vars instead of `UMMAYA_DATA_GO_KR_API_KEY`.

**Rationale**: The intake notes and live probe report identify these as provider endpoints with separate keys. Treating them as data.go.kr service-key calls would make live invocation fail and obscure root cause during debugging.

**Alternatives considered**:

- Route through the shared data.go.kr key: rejected because it contradicts the saved evidence.
- Defer all `LINK` APIs: rejected because direct successful probes already exist.

## Decision: Default tests replay fixtures only

**Decision**: CI/default pytest uses recorded fixtures and parser/registration tests; live contract probes are excluded unless marked live and explicitly requested.

**Rationale**: The constitution and AGENTS.md forbid live government/citizen-infrastructure calls in default CI. Saved body/header artifacts are sufficient to prove parser and envelope behavior.

**Alternatives considered**:

- Re-probe during tests: rejected by project rule.
- Skip parser fixture tests: rejected because response-shape regressions would reach the LLM surface.

## Decision: First-wave grouping

**Decision**: Implement the 14 adapters as thin modules, with related modules allowed to share local constants:

| Group | Adapters |
|-------|----------|
| finance/corporate | `fsc_corporate_finance`, `kepco_power_usage`, `reb_real_estate_stats` |
| environment/safety | `airkorea_air_quality` |
| public administration | `ftc_large_group`, `ftc_public_ym`, `pps_bid_public_info` |
| transportation | `tago_bus_route`, `tago_bus_arrival`, `tago_bus_location`, `tago_bus_station` |
| welfare/civic cost | `bfc_funeral_cost` |
| education | `kcue_finance_status`, `kcue_student_status` |

**Rationale**: These groups mirror agency/domain boundaries while keeping task slices manageable.

**Alternatives considered**:

- Implement only the smallest adapter first: rejected because the user requested proceeding through the verified APIs before PR.
- Implement all as one file: rejected because it would make ownership, testing, and future deprecation harder.
