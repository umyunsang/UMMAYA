# Phase 0 Research: KMA APIHub OpenAPI Adapters

## Decision 1: Scope is only structured `typ02/openApi`

**Decision**: This feature wraps the 85 KMA APIHub operations whose sample URLs
match `/api/typ02/openApi/<service>/<operation>`.

**Rationale**: The official KMA APIHub pages expose 235 sample URLs across the
category pages, but only 85 share the structured OpenAPI envelope and `authKey`
query parameter pattern. The remaining URL families include text URL endpoints,
graphics, image/binary, GRIB/NetCDF-like outputs, and special surfaces that need
different contracts.

**Alternatives considered**:

- Wrap all 235 sample URLs now: rejected because non-structured outputs do not
  share the same request/response contract and would violate fail-closed schema
  expectations.
- Keep only the existing VilageFcst adapters: rejected because the user asked
  for the full APIHub OpenAPI surface.

## Decision 2: Register one `GovAPITool` per operation, backed by shared code

**Decision**: Create distinct operation-level `GovAPITool` definitions from a
typed catalog, while sharing endpoint resolution, request execution, and
response decoding.

**Rationale**: Claude Code's restored `Tool.ts` and `toolOrchestration.ts`
represent tools as individually registered callable units, with concurrency
safety evaluated per tool. UMMAYA's Tool System mirrors this with `GovAPITool`
and `ToolRegistry`. A single mega-tool would hide the operation boundary from
BM25 discovery, permissions, and telemetry.

**Alternatives considered**:

- 85 hand-written adapter files: rejected as repetitive and drift-prone.
- One generic `kma_apihub_call` tool with `service` and `operation` fields:
  rejected because it weakens discovery, per-operation metadata, and user-visible
  auditability.

## Decision 3: Preserve existing citizen-weather adapters

**Decision**: Keep the current `kma_current_observation`,
`kma_short_term_forecast`, `kma_ultra_short_term_forecast`, and related
citizen-weather adapters intact unless a focused regression requires changing
them.

**Rationale**: These adapters already include domain-specific timing rules,
grid-coordinate guidance, output flattening, and real-use validation. Replacing
them with generic wrappers would reduce answer quality for the most common
citizen weather path.

**Alternatives considered**:

- Replace existing KMA adapters with generated tools: rejected because it would
  discard specialized parsing and prompt guidance that already works.

## Decision 4: APIHub credential boundary is `authKey` only

**Decision**: APIHub operations use `UMMAYA_KMA_API_HUB_AUTH_KEY` and query
parameter `authKey`. The resolver must not silently use `UMMAYA_DATA_GO_KR_API_KEY`.

**Rationale**: Official KMA APIHub sample URLs show `authKey`, while data.go.kr
uses `serviceKey`. Prior live debugging showed that conflating those credentials
causes misleading diagnoses.

**Alternatives considered**:

- Accept either key for convenience: rejected because it hides provider identity
  and can send credentials to the wrong host.

## Decision 5: Live approval state is separate from key presence

**Decision**: The catalog records whether an operation is approved, approval
pending, or outside structured scope. A present key is not enough to claim every
operation live-working.

**Rationale**: The logged-in APIHub My Page showed only a subset of approved
utilization applications. KMA APIHub can reject a catalog operation until that
operation's utilization application is approved.

**Alternatives considered**:

- Mark all 85 operations live because they share an API key: rejected as
  factually wrong and unsafe.

## Decision 6: Default tests use fixtures only

**Decision**: Unit and integration tests use fixture XML/JSON and mocked httpx
clients. Live probes remain opt-in via existing live-test conventions.

**Rationale**: Constitution Principle IV and AGENTS.md forbid live public API
calls from CI tests. Fixture tests can validate credential handling,
authorization failures, XML/default decoding, and operation-specific parameters
without hitting KMA.

**Alternatives considered**:

- Live-test every operation by default: rejected because it would require
  approvals, secrets, and external citizen-infrastructure availability.

## Deferred Item Validation

The spec contains three deferred rows:

| Item | Tracking State | Validation |
|---|---|---|
| Non-structured APIHub URL families | #3037 | Valid deferral; converted to a GitHub placeholder issue. |
| `specialApiList.do` 산업특화 sample URLs | #3038 | Valid deferral; it has no structured `typ02/openApi` operation. |
| Live validation for every unapproved APIHub operation | #3039 | Valid deferral; blocked by per-operation APIHub approval. |

No unregistered deferral phrases remain outside the spec table.
