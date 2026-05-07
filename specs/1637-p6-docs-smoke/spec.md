# Feature Specification: P6 · Docs/API specs + Integration smoke

**Feature Branch**: `feat/1637-p6-docs-smoke`
**Created**: 2026-04-26
**Status**: Draft
**Input**: User description: P6 · Docs/API specs + Integration smoke — KOSMOS migration's terminal Epic. (a) Author Markdown specifications for every active adapter registered in `kosmos.tools.register_all` under a new `docs/api/` directory, (b) export each Pydantic envelope as a JSON Schema Draft 2020-12 file under `docs/api/schemas/`, (c) absorb the legacy `docs/tools/` directory into the new layout, (d) clean up the 9 stale `road_risk_score` (composite) references left over from the P3 #1758 adapter removal, (e) recover `bun test` to 0 fail / 0 errors (≥ 830 tests), (f) gate the release on a hand-driven `bun run tui` visual smoke covering 5 UI states + active primitive flows + slash commands + 3 error envelopes + PDF inline render, and (g) ship a single integrated PR `Closes #1637` that closes Initiative #1631 alongside KOSMOS v0.1-alpha CHANGELOG. Canonical sources: Epic #1637, `docs/requirements/kosmos-migration-tree.md § L1-B B7 + § P6`, `docs/vision.md § Reference materials` (Claude Code primary), `AGENTS.md § Spec-driven workflow + § Hard rules`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Citizen developer discovers and understands every registered KOSMOS adapter from a single index (Priority: P1)

A citizen developer (or external plugin contributor reviewing KOSMOS conventions before submitting to `kosmos-plugin-store`) wants to learn what tools KOSMOS already ships, what each adapter requires as input, what permission tier it lives at, and how to invoke it through the `lookup(mode="fetch")` envelope. Today this knowledge is fragmented — half is in `docs/tools/` (P3-era, partial), half in `docs/design/mvp-tools.md` (planning artifact), half in `docs/plugins/` (external-author guides), and the rest is buried inside Pydantic source files under `src/kosmos/tools/`. There is no single canonical catalog.

**Why this priority**: This is the entire reason P6 exists. The migration tree § L1-B B7 explicitly mandates "어댑터별 Markdown + JSON Schema/OpenAPI + index" as the closing deliverable for the Tool System pillar. Without a single canonical `docs/api/` index, every external contributor has to re-discover the conventions by reading source code, every QA review has to cross-check four directories, and the public-facing claim that KOSMOS "orchestrates Korean public APIs" stays unverifiable from the documentation alone. P1 because it dominates the Epic's file scope and unblocks every other story.

**Independent Test**: Open `docs/api/README.md` cold (no prior KOSMOS knowledge). Within 30 seconds, locate the row for `koroad_accident_search`. Click through to the adapter spec. Read the seven-field structure (Tier · Envelope · Search hints · Endpoint · Permission tier · Example call · Constraints). Open the linked JSON Schema file under `docs/api/schemas/koroad_accident_search.json`. Validate it against a Draft 2020-12 validator. Repeat for one Mock-tier adapter (e.g., `mock_traffic_fine_pay_v1`). Success: the same seven fields render with the same headings; the Mock entry visibly carries the `[Mock]` classification; the JSON Schema imports cleanly into a generic schema viewer.

**Acceptance Scenarios**:

1. **Given** a contributor reading `docs/api/README.md`, **When** they scan the matrix, **Then** they see all active adapters indexed by ministry/source AND by primitive (`lookup` · `submit` · `verify` · `resolve_location`), with each row linking to the adapter's Markdown spec.
2. **Given** an adapter Markdown spec, **When** any reviewer opens it, **Then** they find the seven mandatory fields (classification, input/output envelope reference, search hints in Korean + English, endpoint identifier, permission tier 1/2/3, worked example, constraints) populated — no field left as a placeholder.
3. **Given** a JSON Schema file under `docs/api/schemas/<tool_id>.json`, **When** a generic Draft 2020-12 validator parses it, **Then** the schema validates structurally and every property in the corresponding Pydantic envelope is reflected with type, required-ness, and field description.
4. **Given** the legacy `docs/tools/` directory, **When** the merge lands, **Then** every file in `docs/tools/` has either moved to `docs/api/` (with its content updated to the new seven-field structure) or been deleted as superseded — no orphan remains under `docs/tools/`.

---

### User Story 2 - Release validator confirms KOSMOS v0.1-alpha is integration-ready before tagging (Priority: P1)

The release validator (project lead in this case) needs to confirm that the assembled migration — P0 baseline + P1/P2 dead-code/Friendli + P3 tool wiring + P4 UI L2 + P5 plugin DX + P6 docs — actually runs end-to-end on a fresh checkout, with no test regressions and no broken UI flows, before the v0.1-alpha tag is cut and Initiative #1631 is closed.

**Why this priority**: Without an objective integration gate, "it compiled" becomes the de facto release criterion. The migration tree § P6 explicitly bundles "통합 bun test 회귀 없음" + "`bun run tui` 사용자 시각 검증" as paired gates. The current baseline measurement (P5 head: 776 pass / 47 fail / 17 errors out of 830 tests) shows real regressions accumulated across the migration — most prominently a `tui/src/hooks/useVirtualScroll.ts:273` `Set` constructor type error attributable to P4 #1847. Shipping with these regressions means future contributors cannot trust the test suite as a refactor-safety net. P1 (tied with US1) because release readiness is non-negotiable.

**Independent Test**: On a clean checkout of `feat/1637-p6-docs-smoke`, run `bun test` and observe the final tally line. Then run `bun run tui` and walk through the documented smoke checklist (onboarding 5-step → active primitive flows → `/agents` `/plugins` `/consent list` `/help` → 3 error envelopes → PDF inline render in Kitty/iTerm2). Success: bun test reports 0 fail / 0 errors with the prior pass count preserved or grown; every smoke step renders without crash, with the visual result captured as ANSI text under `specs/1637-p6-docs-smoke/visual-evidence/`.

**Acceptance Scenarios**:

1. **Given** the head of `feat/1637-p6-docs-smoke`, **When** `bun test` runs, **Then** the final summary reports 0 fail and 0 errors across at least 830 tests; pre-existing skip and todo counts remain unchanged.
2. **Given** the `tui/src/hooks/useVirtualScroll.ts:273` `Set` constructor type error, **When** the fix lands, **Then** the `VirtualizedList overflowToBackbuffer` test family passes without modification of test expectations (the test fixture is the contract).
3. **Given** a fresh `bun run tui` session, **When** the validator completes the 5-step onboarding flow, **Then** every step renders, accepts input, and persists state to `~/.kosmos/memdir/user/onboarding/state.json`; resuming with `/onboarding` returns to the recorded step.
4. **Given** the running TUI, **When** the validator triggers each active primitive flow (`lookup` search/fetch · `submit` mock · `verify` mock), **Then** the request lands at the corresponding adapter, the permission-gauntlet modal fires for tier-2 / tier-3 adapters, and the response renders in the conversation pane with the documented envelope shape.
5. **Given** the running TUI, **When** the validator forces each of the three error envelopes (LLM 4xx, tool fail-closed, network timeout), **Then** the rendered error follows the Spec 035 envelope with the documented error icon, classification line, and remediation hint — no raw exception traces leak into the visible frame.

---

### User Story 3 - Maintainer confirms zero residual references to the removed composite tool (Priority: P2)

A maintainer or downstream agent reading KOSMOS docs or grepping for examples of how composite tools work expects the documentation to match the code. Today, `road_risk_score` (composite) was removed from the registry by P3 #1758 (per migration tree § L1-B B6 "Composite 제거"), but nine documentation locations still describe it as a registered, callable tool. Anyone trusting the docs will hit `tool not found` and lose trust in the documentation as a whole.

**Why this priority**: This is a consistency story, not a feature story — without it, the new `docs/api/` catalog cannot be trusted because the surrounding documentation contradicts it. P2 because it is straightforward cleanup work whose value is unlocked only when US1 has landed.

**Independent Test**: Run `grep -rn "road_risk_score" docs/` after the cleanup. Run `grep -rn "composite/road_risk_score.py" docs/`. Both must return zero non-historical hits (entries inside `docs/release-manifests/`, ADRs, or release notes that describe the removal itself are exempt — this is permitted historical record). Open the four `docs/tools/{README,kma-observation,koroad,kma-alert}.md` files and confirm none of them link to a deleted file.

**Acceptance Scenarios**:

1. **Given** the merged work, **When** a maintainer runs `grep -rn "road_risk_score" docs/`, **Then** every remaining match is inside historical archive directories (`docs/release-manifests/`, `docs/adr/`, `docs/release-notes/`) or explicitly documents the removal — zero matches inside reference documentation that purports to describe currently-callable tools.
2. **Given** `docs/tools/road-risk-score.md`, **When** the maintainer checks, **Then** the file no longer exists; any backlink that used to point at it has either been deleted or rewritten to reference its replacement (e.g., the documentation note explaining how the LLM now chains `koroad_accident_search` + `kma_*` directly).
3. **Given** `docs/requirements/epic-p3-tool-system.md`, **When** the maintainer reads the registered-tool-id list, **Then** the count reads 14 (composite removed), not 15.

---

### Edge Cases

- **L3-gated adapter (`nmc_emergency_search`)**: spec must distinguish the unauthenticated `LookupError(auth_required)` path from the authenticated success path; the freshness sub-tool (`tools/nmc/freshness.py`) is documented inside the same Markdown file, not as a separate adapter, because it is a quality signal not a citizen-facing tool.
- **`resolve_location` is a meta-tool, not an adapter**: it dispatches across three backends (juso · sgis · kakao) and is invoked by other adapters during input normalization. Its spec lives at `docs/api/resolve_location/index.md` and documents the three backends as variants, not as separate registered tool_ids.
- **Empty mock stubs (`barocert/`, `npki_crypto/`, `omnione/`)**: per memory `feedback_mock_vs_scenario`, OPAQUE-tier items belong in `docs/scenarios/`, not in `docs/api/`. The directories exist as code-side placeholders only.
- **`docs/tools/` migration vs deletion**: most `docs/tools/*.md` files map 1-to-1 to a `docs/api/<source>/<tool>.md` destination, but legacy files describing tools that no longer exist (`road-risk-score.md`) are deleted outright, not migrated.
- **Test-fail triage classification**: each of the 47 fails / 17 errors must be classified as either (a) a real regression to fix, (b) a CC-port test whose contract is no longer applicable and which must be deleted with rationale, or (c) a test whose expectation needs updating to match a deliberate behavior change. The classification log lives in the spec's plan artifact.
- **CHANGELOG framing**: KOSMOS v0.1-alpha is the migration-completion release, not a feature release. Entries describe the migration end-state, not a feature-by-feature changelog.
- **PDF inline render**: depends on terminal-graphics-protocol detection (Kitty / iTerm2). On terminals without graphics support, the smoke checklist accepts the documented `open` fallback as the success criterion — visual inline rendering is not asserted on incompatible terminals.

## Requirements *(mandatory)*

### Functional Requirements

#### Documentation surface — `docs/api/`

- **FR-001**: System MUST expose a single index file at `docs/api/README.md` that catalogs active registered adapters in two cross-cutting matrices: by source (KOROAD, KMA, HIRA, NMC, NFA119, MOHW, mock-verify, mock-submit, resolve_location) and by primitive (`lookup` · `submit` · `verify` · `resolve_location`). Each row MUST link to the adapter's Markdown spec and to its JSON Schema export.
- **FR-002**: System MUST publish 12 Live-tier adapter specs covering `koroad_accident_search`, `koroad_accident_hazard_search`, `kma_current_observation`, `kma_short_term_forecast`, `kma_ultra_short_term_forecast`, `kma_weather_alert_status`, `kma_pre_warning`, `kma_forecast_fetch`, `hira_hospital_search`, `nmc_emergency_search` (with freshness sub-tool documented inline), `nfa_emergency_info_service`, and `mohw_welfare_eligibility_search`.
- **FR-003**: System MUST publish active Mock-tier adapter specs covering verify and submit adapters. Mock entries MUST cite their public-spec source per memory `feedback_mock_evidence_based`. Subscribe mock specs are deferred until KOSMOS owns an app/push delivery runtime.
- **FR-004**: System MUST publish 1 meta-tool spec for `resolve_location` at `docs/api/resolve_location/index.md` covering the juso, sgis, and kakao backends as variants of a single dispatch surface.
- **FR-005**: Every adapter spec MUST populate the seven mandatory fields: (1) classification (Live or Mock + permission tier 1/2/3), (2) Pydantic input/output envelope reference (with file path and line range to the model definition), (3) search hints in Korean and English, (4) endpoint identifier (data.go.kr endpoint ID, ministry source URL, or "fixture-replay only" for Mock), (5) permission tier rationale referencing Spec 033, (6) at least one worked invocation example using `lookup(mode="fetch")` envelope, (7) constraints (rate limits, freshness windows, fixture coverage gaps).
- **FR-006**: System MUST export each adapter's input and output Pydantic models as a JSON Schema Draft 2020-12 document under `docs/api/schemas/<tool_id>.json`. The export MUST validate against a generic Draft 2020-12 validator without manual edits.
- **FR-007**: System MUST provide an automated build script `scripts/build_schemas.py` that walks the registry from `kosmos.tools.register_all`, invokes Pydantic v2's `model_json_schema()` per envelope, and writes the resulting JSON files into `docs/api/schemas/`. Re-running the script on an unchanged tree MUST produce a byte-identical output (deterministic).

#### Documentation migration — legacy `docs/tools/` absorption

- **FR-008**: System MUST migrate every relevant file under `docs/tools/` into the corresponding `docs/api/<source>/<tool>.md` location, rewriting the content to match the seven-field structure. Files describing removed tools MUST be deleted. After migration, `docs/tools/` MUST not exist.
- **FR-009**: System MUST remove all references to the removed `road_risk_score` (composite) tool from the documentation set, covering at least these nine locations: `docs/tools/road-risk-score.md` (file deletion), `docs/tools/README.md` (rows 16 and 89 in the pre-migration file), `docs/tools/{kma-observation, koroad, kma-alert}.md` Related-tools sections, `docs/phase1-acceptance.md` table rows, `docs/research/tool-system-migration-plan.md` adapter inventory and task table, `docs/design/mvp-tools.md` composite example sentence, and `docs/requirements/epic-p3-tool-system.md` tool_ids list (must drop to 14). Historical archives (`docs/release-manifests/`, `docs/adr/`, `docs/release-notes/`) are exempt and may retain references that explicitly describe the removal.

#### Quality gate — bun test recovery

- **FR-010**: System MUST recover the `bun test` suite to 0 fail and 0 errors with the total test count at or above 830. Pre-existing skip and todo counts MAY remain. Achievement MUST be verifiable from the local CLI without environment-specific configuration.
- **FR-011**: System MUST resolve the `tui/src/hooks/useVirtualScroll.ts:273` `Set` constructor type error that surfaced after P4 #1847 merged, and MUST do so without modifying the contracts asserted by the affected `VirtualizedList overflowToBackbuffer` test family — the tests are the contract.
- **FR-012**: For each remaining test failure or error not covered by FR-011, the work MUST classify it as (a) regression to fix, (b) CC-port contract no longer applicable and deleted with rationale, or (c) deliberate behavior change requiring expectation update. The classification list MUST be recorded in the plan artifact, not in the spec.

#### Quality gate — bun run tui visual smoke

- **FR-013**: System MUST publish a hand-driven smoke checklist that the release validator executes against `bun run tui`, covering at minimum: the 5-step onboarding flow (preflight → theme → pipa-consent → ministry-scope → terminal-setup), the active primitive invocations (`lookup` search and fetch, `submit` mock, `verify` mock), the slash commands (`/agents`, `/plugins`, `/consent list`, `/help`), the 3 error envelopes (LLM 4xx, tool fail-closed, network timeout), and the PDF inline render path (Kitty / iTerm2 graphics protocol with `open` fallback for incompatible terminals). `subscribe` smoke is deferred until an app/push-notification runtime exists.
- **FR-014**: System MUST capture ANSI-text evidence from each smoke step into `specs/1637-p6-docs-smoke/visual-evidence/` following the precedent established in `specs/1636-plugin-dx-5tier/visual-evidence/`. The release validator MUST be able to replay the recorded session by reading the captured ANSI files alongside a brief textual narration.

#### Cross-cutting documentation updates

- **FR-015**: System MUST update `docs/vision.md § L1-A`, `§ L1-B`, and `§ L1-C` to reflect the realized migration outcome (previous text described the migration as planned; the post-merge text describes it as shipped, with date and Epic reference).
- **FR-016**: System MUST update `CLAUDE.md § Active Technologies` to reflect the post-P6 surface and `CLAUDE.md § Recent Changes` with a P6 entry that mirrors the prose convention used by the prior P0–P5 entries.
- **FR-017**: System MUST add a `CHANGELOG.md` entry tagged "KOSMOS v0.1-alpha" describing the migration completion. The entry MUST be a release-readiness-grade summary, not a feature-by-feature changelog — it is the closing note for Initiative #1631.

#### Release packaging

- **FR-018**: All work MUST land in a single integrated PR whose body uses `Closes #1637` exclusively (Task sub-issues are closed after merge per the project's PR-closing convention).
- **FR-019**: The PR MUST be authored under a Conventional Commits subject `feat(1637): p6 docs/api specs + integration smoke` and MUST present a body that lists the smoke-checklist visual-evidence artifacts and the bun-test recovery summary.
- **FR-020**: The OpenAPI 3.0 reference under `docs/api/openapi.yaml` MAY be authored as a thin wrapper over the JSON Schema export for the `/agent-delegation` meta-tool surface, but is OPTIONAL — the JSON Schema export under FR-006 is the primary contract; OpenAPI is documentation polish that can defer.

#### Hard constraints inherited from project policy

- **FR-021**: All adapter specs and JSON Schema exports MUST be authored in English. Search hints inside the specs MUST appear bilingually (Korean primary + English secondary). This complies with `AGENTS.md § Hard rules` "All source text in English. Korean domain data is the only exception" while preserving search-hint Korean for citizen discovery.
- **FR-022**: The build script and any test or CI helper introduced by this Epic MUST not introduce new runtime dependencies beyond the already-pinned set in `pyproject.toml`. Documentation generation may rely on stdlib + Pydantic v2 only on the Python side; on the TS side it MUST not introduce new packages.

### Key Entities *(include if feature involves data)*

- **AdapterSpec**: a Markdown document under `docs/api/<source>/<tool_id>.md` with seven mandatory fields (classification, envelope reference, bilingual search hints, endpoint identifier, permission tier, worked example, constraints). One per active registered adapter.
- **AdapterIndex**: the single `docs/api/README.md` document that cross-tabulates all adapters by source and by primitive, linking to each AdapterSpec and to the corresponding JSONSchema.
- **JSONSchema**: a JSON Schema Draft 2020-12 document under `docs/api/schemas/<tool_id>.json`, machine-generated by `scripts/build_schemas.py` from the Pydantic envelopes registered in `kosmos.tools.register_all`. Deterministic.
- **SchemaBuildScript**: the `scripts/build_schemas.py` Python module that performs the deterministic export. Inputs: the live registry. Output: the schemas directory. Idempotent.
- **SmokeChecklist**: the hand-driven validation document recording the bun-run-tui visual-smoke flow. Captures: every state checked, the visual evidence file, pass / fail / blocked state, and any edge-case observations.
- **VisualEvidenceArtifact**: an ANSI-text capture under `specs/1637-p6-docs-smoke/visual-evidence/`, one per smoke step, mirroring the file-naming convention from Spec 1636.
- **CompositeRemovalAudit**: the implicit deliverable confirming zero non-historical references to the removed `road_risk_score` tool, verifiable by `grep`.
- **ChangeLogEntry**: the single `CHANGELOG.md` entry tagged "KOSMOS v0.1-alpha" closing out Initiative #1631.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All active registered adapters have a Markdown spec under `docs/api/` with all seven mandatory fields populated. Verification: `find docs/api -name '*.md' -not -name 'README.md' -not -path 'docs/api/schemas/*' | wc -l` returns the active adapter count, and a structural lint script rejecting any missing field returns exit code 0 across all of them.
- **SC-002**: All active adapters have a JSON Schema Draft 2020-12 file under `docs/api/schemas/<tool_id>.json` that validates against a generic Draft 2020-12 schema validator. Verification: re-running `python scripts/build_schemas.py` on the merged tree produces zero diff.
- **SC-003**: `bun test` reports 0 fail and 0 errors across at least 830 tests, with skip and todo counts at or above the pre-merge baseline. Verification: the bun-test summary line captured into the PR body.
- **SC-004**: Searching the documentation tree for the removed composite tool returns zero non-historical references. Verification: `grep -rn 'road_risk_score' docs/ | grep -vE '(release-manifests|adr|release-notes)' | wc -l` returns 0.
- **SC-005**: A release validator can complete the full bun-run-tui smoke checklist (5 onboarding steps + active primitive flows + slash commands + 3 error envelopes + PDF render path) without any unrecoverable error or visual crash. Verification: every smoke-checklist row has a corresponding `visual-evidence/<slug>.ansi.txt` artifact and a pass mark.
- **SC-006**: The legacy `docs/tools/` directory does not exist after the merge. Verification: `test ! -d docs/tools && echo gone` prints "gone".
- **SC-007**: A new contributor with no prior KOSMOS knowledge can locate the spec for an arbitrarily named adapter (provided as a string) starting from `docs/api/README.md` in under 30 seconds. Verification: a documented walk-through (project-lead self-test) recorded in the smoke checklist.
- **SC-008**: The integrated PR `Closes #1637` merges cleanly to `main`, the Copilot Review Gate transitions to `completed` with zero CRITICAL findings, and the resulting commit on `main` lets `bun test` and `bun run tui` start without bootstrap errors on a fresh clone. Verification: PR-merge state recorded by GitHub.
- **SC-009**: After the PR merges, Initiative #1631 (KOSMOS TUI Migration) can be closed because all six Phase Epics (#1632, #1633, #1634, #1847, #1927, #1637) are in MERGED / CLOSED state. Verification: GitHub issue state.
- **SC-010**: KOSMOS v0.1-alpha CHANGELOG entry exists and reads as a coherent migration-completion summary. Verification: prose review by project lead documented in PR body.

## Assumptions

- The active adapter count is derived from `kosmos.tools.register_all`. Any adapter added or removed between the spec freeze and PR submission updates the count and triggers a spec amendment.
- External plugin contributors host their own `docs/` content inside `kosmos-plugin-store/<repo>` and are out of scope. The post-P5 plugin DX (Spec 1636) covers their authoring path.
- The 47 fail / 17 errors current bun-test baseline is largely traceable to P4 #1847 (TUI L2 citizen port). Fix work concentrates on that surface; CC-port tests whose contract no longer applies are deleted with explicit rationale rather than skipped.
- Visual-evidence capture follows the same ANSI-text convention introduced by Spec 1636 (`specs/1636-plugin-dx-5tier/visual-evidence/`). No new tooling required.
- KOSMOS-only tests are preserved; tests that were ports of Claude Code internals describing CC-only abstractions are eligible for deletion when KOSMOS no longer contains the corresponding abstraction.
- OpenAPI 3.0 export is treated as polish; the JSON Schema export is the primary machine-readable contract. If OpenAPI authoring would lengthen the Epic by a meaningful margin, it is deferred.
- The Initiative-close action is performed manually by the project lead after PR merge — this Epic does not automate Initiative closure.
- Search-hint translations follow the conventions already established in `src/kosmos/tools/*/search_hint` Python literals; the spec author transcribes them, does not retranslate.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **External plugin documentation**: every plugin published under `kosmos-plugin-store/<repo>` carries its own `README.ko.md` + `manifest.yaml` + per-repo docs. KOSMOS core repo `docs/api/` covers only registry-bundled adapters. (Reason: ownership boundary; trying to mirror external repo docs centrally would invert the Spec 1636 plugin DX model.)
- **OPAQUE mock stubs (`barocert/`, `npki_crypto/`, `omnione/`)**: per memory `feedback_mock_vs_scenario`, OPAQUE-tier subjects belong in `docs/scenarios/`, not in `docs/api/`. The empty `__init__.py` placeholder directories under `src/kosmos/tools/mock/` exist for future shape-mirrored Mock work and are intentionally excluded from this catalog.
- **Live API key acquisition or live regression coverage**: live data.go.kr calls remain `@pytest.mark.live` skip-by-default per `AGENTS.md § Hard rules`. P6 verifies fixture-replay paths only.
- **Constitution / vision rewrite**: `docs/vision.md` Layer names are fixed by ADR; this Epic updates phase-realization prose only, not architectural definitions.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Full OpenAPI 3.0 specification for `/agent-delegation` meta-tool | JSON Schema is the primary contract; OpenAPI is polish that requires its own design pass for authentication and error-shape conventions | Post-v0.1-alpha plugin DX expansion or a dedicated docs-tooling Epic | #1972 |
| Permanent removal of the `ministries_for_composite()` API surface in `src/kosmos/tools/main_router.py` | The function is unused after the composite removal but is retained as an extension point per its in-code comment; removing it requires confirming no future composite tool is planned | Post-v0.1-alpha refactor pass once primitive-only invariant is firmly established | #1973 |
| Live-mode regression coverage for the 12 Live-tier adapters | Requires API-key acquisition agreements with each ministry; orthogonal to the docs+smoke release gate | Phase 2 live hardening (post-v0.1-alpha) | #1974 |
| Auto-generated adapter spec stubs from Pydantic docstrings | Out of scope for first authoring pass; once active manual specs land, a generator can replace the manual maintenance burden | Post-v0.1-alpha docs-tooling Epic | #1975 |
| Migration of OPAQUE mock stubs into `docs/scenarios/` shape-mirror entries | OPAQUE items need scenario-level evidence research first (memory `feedback_mock_evidence_based`) | Future scenarios-coverage Epic, when shape-mirror evidence is ready | #1976 |
