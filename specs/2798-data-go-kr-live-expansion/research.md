# Phase 0 Research: data.go.kr Live Expansion

## Decision 1: Reuse the Spec 2797 verified adapter package

**Decision**: Add the 16 newly callable APIs to `src/ummaya/tools/verified_data_go_kr/` instead of creating a parallel package.

**Rationale**: The existing package already implements the desired one-agency-module-to-one-tool pattern: a manifest entry, strict input schema, `GovAPITool` metadata, registry binding, fixture replay, and JSON/XML parser normalization. This matches `docs/vision.md § Layer 2 — Tool System` and `docs/requirements/ummaya-migration-tree.md § L1-B`.

**Alternatives considered**: A second package for the "new 30" was rejected because the final target is one verified public-data catalog of 30 callable adapters, not two competing registries.

## Decision 2: Public-data adapters remain on the adapter fetch path

**Decision**: Register the included APIs as read-only public-data adapters and expose them through the current `find({"tool_id": ..., "params": ...})` fetch path. Use `locate` only as a preceding resolver when a selected schema needs coordinates, administrative codes, station codes, or place-derived region filters. Do not use `check` for public read-only status facts in this feature.

**Rationale**: Current UMMAYA runtime code routes adapter fetches through the root primitive and target `tool_id` contract (`src/ummaya/engine/query.py::_dispatch_root_primitive`, `src/ummaya/ipc/stdio.py::_build_available_adapters_message`). `src/ummaya/tools/resolve_location.py` and `src/ummaya/tools/location_adapters.py` show `locate` as a location resolver. `src/ummaya/primitives/verify.py` shows `check` as identity delegation. Public-data status facts such as air quality, subway fare/time, marine water quality, and immigration aggregate counts do not require identity delegation.

**Alternatives considered**: Marking status-like APIs as `check` was rejected because it would trigger the permission/identity semantics intended for authentication families. Marking facility datasets as root `locate` outputs was deferred because the current `locate` primitive returns resolver bundles, not public-data collections.

## Decision 3: Model transport quirks in manifest metadata

**Decision**: Extend `VerifiedAdapterSpec` with optional `request_headers` and allow `http://` endpoints, then use those fields only where direct probe evidence requires them.

**Rationale**: `LIVE-API-CALL-MATRIX-2026-05-16.md` and `LIVE-API-BLOCKER-RESOLUTION-2026-05-16.md` prove three contract quirks:

- `15149906` requires uppercase `ServiceKey` despite Swagger showing lowercase.
- `15074634` returns normal XML only when called with a browser-like `User-Agent`.
- `15121954` succeeds through the HTTP gateway while HTTPS evidence fails.

Putting these in manifest metadata keeps the behavior auditable and avoids hidden fallback routing.

**Alternatives considered**: Client-global headers or retrying alternate schemes were rejected because they would blur root cause and affect unrelated adapters.

## Decision 4: Extend typed ministry metadata

**Decision**: Extend the `Ministry` literal set in `src/ummaya/tools/models.py` for the new agencies represented by the 16 adapters.

**Rationale**: The existing type is a closed routing/search enum. Typed agency metadata is better than `OTHER` for search hints, docs, and registry breakdowns. This satisfies `spec.md` FR-010 without introducing a new dependency.

**Alternatives considered**: Using `OTHER` for every new institution was rejected because it would be a temporary shortcut with weaker audit value.

## Decision 5: Default tests replay saved fixtures only

**Decision**: Update existing manifest/registration/fixture tests and add special transport contract tests, but keep all live API calls out of default test execution.

**Rationale**: Constitution Principle IV and `AGENTS.md` both prohibit live public API calls from CI. Saved probe bodies under `docs/api/data-go-kr-candidate-docs/<id>/probes/...` are sufficient for parser and adapter replay tests. Live terminal smoke is local/manual and recorded under this spec.

**Alternatives considered**: `@pytest.mark.live` regression tests were deferred because the user asked for a terminal UMMAYA validation path, and default CI must remain offline.

## Deferred Item Validation

The spec contains five deferred rows. Three are concrete API blockers proven by direct controls:

- `15038392`: approved key recognized as real, but legacy service access denied.
- `15058923`: official sample calls and fake-key controls return the same unregistered-key error.
- `15063444`: provider endpoint reachable, but approved and fake keys return the same unregistered-key envelope.

The two non-API follow-ups are explicit operational/design follow-ups: public facility `locate` output reclassification and adapter health monitoring. `/speckit-taskstoissues` must create placeholder issues for all `NEEDS TRACKING` rows and link them to originating Epic #2832.
