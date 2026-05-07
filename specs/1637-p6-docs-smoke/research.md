# Phase 0 Research — P6 · Docs/API specs + Integration smoke

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-04-26

This document resolves all NEEDS CLARIFICATION markers (none in spec — research validates assumptions instead) and grounds each design choice in either `docs/vision.md § Reference materials` or a prior KOSMOS spec.

## Reference materials consulted

Per Constitution Principle I and `AGENTS.md § Spec-driven workflow`, every plan section maps to a concrete reference. The mapping table from `docs/vision.md § Reference materials` (constitution.md lines 13–22) was applied as follows:

| Plan area | Layer (vision.md) | Primary reference | Secondary reference |
|---|---|---|---|
| Adapter spec template structure | Tool System | Pydantic AI (schema-driven registry) | Spec 1636 plugin contracts (`specs/1636-plugin-dx-5tier/contracts/manifest.schema.json`) + existing `docs/tools/koroad.md` |
| JSON Schema export build script | Tool System | Pydantic v2 `model_json_schema()` (official docs) | Spec 022 `MVPSurface.search` Pydantic envelopes |
| Visual-evidence ANSI capture | TUI | Spec 1636 `specs/1636-plugin-dx-5tier/visual-evidence/` convention | macOS BSD `script(1)` (stdlib only) |
| useVirtualScroll fix scope | TUI | Claude Code reconstructed (`tui/` is the port surface) | Ink + Gemini CLI (React for terminals) |
| docs/tools → docs/api migration | Tool System | Spec 1634 (P3 tool-system wiring) registered tool_ids list | Spec 1636 docs/plugins/ Korean-primary precedent |
| CHANGELOG / vision post-merge prose | (cross-cutting) | `docs/requirements/kosmos-migration-tree.md § P6` | Prior P0–P5 entries in `CLAUDE.md § Recent Changes` |

Cross-spec inheritance applied:

- **Spec 1632** (P0 baseline) — supplies the prior `bun test` baseline figure (576 pass) used as a floor reference in spec FR-010.
- **Spec 1633** (P1 + P2) — confirms session JSONL paths (`~/.kosmos/memdir/user/sessions/`) referenced by adapter specs.
- **Spec 1634** (P3 tool wiring) — canonical 14-tool registry (`register_all.py`) is the iteration source for `scripts/build_schemas.py`. Composite removal (`road_risk_score`) sourced from this Epic's `register_all.py:116` comment.
- **Spec 1635** (P4 UI L2) — supplies the onboarding state file path (`~/.kosmos/memdir/user/onboarding/state.json`) referenced in the smoke checklist.
- **Spec 1636** (P5 plugin DX) — supplies the visual-evidence convention (file naming `<slug>.ansi.txt` + `<slug>.txt` pair), the contracts/ directory pattern, and the bilingual-search-hint approach.

## Deferred items validation (Constitution Principle VI)

The "Scope Boundaries & Deferred Items" section in spec.md was scanned per the gate. Results:

- **Out of Scope (Permanent)**: 4 items, all carry brief rationale. No tracking issue required.
- **Deferred to Future Work**: 5 items, all marked `NEEDS TRACKING`. No GitHub issue numbers expected at this stage; `/speckit-taskstoissues` will resolve them.
- **Free-text scan for unregistered patterns**: searched spec.md for "separate epic", "future epic", "Phase 2", "v2", "deferred to", "later release". Every match maps to either an explicit Out-of-Scope or a Deferred-to-Future-Work row. Examples confirmed:
  - "Phase 2 live hardening" → Deferred row 3.
  - "Post-v0.1-alpha plugin DX expansion" → Deferred rows 1, 4.
  - "Future scenarios-coverage Epic" → Deferred row 5.

**Result**: gate PASS. Deferred items conform to Principle VI.

## Research items

### R1 — Stale-doc inventory: precise locations of `road_risk_score` references

**Question**: which exact lines in which docs reference the removed composite tool, and how should each be handled (delete the line, delete the file, rewrite to point at the new chained-primitives flow, or leave as historical record)?

**Decision**: nine non-historical locations, each handled per the matrix below. Historical archives (`docs/release-manifests/`, `docs/adr/`, `docs/release-notes/`) are exempt — references there describe the removal and remain.

| File | Match locations | Action |
|---|---|---|
| `docs/tools/road-risk-score.md` | entire file | DELETE; the file is moved to `docs/api/` only as a deletion record (no replacement spec). |
| `docs/tools/README.md` | rows 16, 89 (table rows) | Migrate file to `docs/api/README.md` and drop the rows during migration. |
| `docs/tools/kma-observation.md` | line 222 (Related-tools backlink) | Migrate to `docs/api/kma/current_observation.md` minus the backlink. |
| `docs/tools/koroad.md` | line 281 (Related-tools backlink) | Migrate to `docs/api/koroad/README.md` (or split per accident_*) minus the backlink. |
| `docs/tools/kma-alert.md` | line 134 (Related-tools backlink) | Migrate to `docs/api/kma/weather_alert_status.md` minus the backlink. |
| `docs/phase1-acceptance.md` | rows 92, 113 | Edit in place: drop both rows; leave a one-line note explaining the removal cites Epic #1634 / migration tree § L1-B B6. |
| `docs/research/tool-system-migration-plan.md` | rows 32, 94, 356 | Edit in place: drop the composite row from the inventory tree, the table, and the task list. |
| `docs/design/mvp-tools.md` | line 625 | Edit in place: rewrite the sentence to drop the `road_risk_score` example and replace with "the LLM chains primitive adapters end-to-end". |
| `docs/requirements/epic-p3-tool-system.md` | line 10 | Edit in place: remove `road_risk_score` from the registered tool_ids list and update the count to 14. |

**Rationale**: directly grep-verified; spec FR-009 enumerates these locations.

**Alternatives considered**: leaving the references as "this used to exist" footnotes was rejected — the docs purport to describe currently-callable tools; footnotes invite confusion. A bulk-rewrite via sed was rejected because four of the nine locations require contextual rewriting, not deletion.

### R2 — Test-fail triage classification

**Question**: how do we classify the 47 fail / 17 errors observed in the current `bun test` run? Spec FR-012 mandates classification per failure as (a) regression, (b) CC-port no longer applicable, or (c) deliberate behavior change.

**Decision**: a classification log is produced at `specs/1637-p6-docs-smoke/test-triage.md` during the implement phase (not authored here). The log is keyed by test file path; each row records the classification (a/b/c), the fix or deletion plan, and the rationale citing prior specs (typically Spec 1635 / 1633). At least one root cause is already known: `tui/src/hooks/useVirtualScroll.ts:273` `new Set(itemKeys)` constructor type error (R7 below).

**Rationale**: defers the per-test classification to the implement phase where the test runner output can be parsed deterministically. Spec authors should not preempt that classification.

**Alternatives considered**: enumerating classifications in this research file was rejected — without running `bun test --reporter=verbose` against a clean tree, the prediction list is speculative and risks locking the implementer into a wrong shape. The triage log lives in the spec directory as a permanent artifact regardless.

### R3 — Adapter spec template structure

**Question**: what concrete Markdown structure satisfies the seven mandatory fields from spec FR-005 while remaining consistent with the existing `docs/tools/*.md` conventions?

**Decision**: the seven-field structure is codified in `contracts/adapter-spec-template.md`. The headings are:

1. **Overview** — one sentence purpose; classification (Live or Mock + permission tier 1/2/3) shown as a key-value table.
2. **Envelope** — Pydantic v2 input and output models cited by file path + line range; render the schema fields as a Markdown table, not as a raw code dump.
3. **Search hints** — bilingual list (Korean primary, English secondary), exactly as registered in `kosmos.tools.<adapter>.search_hint`.
4. **Endpoint** — data.go.kr endpoint identifier + ministry source URL for Live; "fixture-replay only" + public-spec citation for Mock.
5. **Permission tier rationale** — Spec 033 reference + per-adapter explanation (e.g., why `nmc_emergency_search` is L3-gated).
6. **Worked example** — at least one `lookup(mode="fetch")` invocation (or `submit` / `verify` for the corresponding primitive families) showing input envelope JSON, output envelope JSON, and a KOSMOS conversation snippet.
7. **Constraints** — rate limits, freshness windows, fixture coverage gaps, error envelope examples.

The template also includes a YAML front matter block with `tool_id`, `primitive`, `tier`, and `permission_tier` — these are machine-readable so a future linter can automate the SC-001 structural check.

**Rationale**: matches the existing `docs/tools/koroad.md` order (already in production at the time of this research), extends it with explicit permission rationale (post-Spec 033) and formalizes the schema reference (post-Spec 1634). The YAML front matter mirrors the pattern from `specs/1636-plugin-dx-5tier/contracts/manifest.schema.json` for machine-readability.

**Alternatives considered**: an OpenAPI 3.0 YAML per adapter was considered (closer to industry doc tooling) and rejected for first-author cost — Markdown with embedded fences renders better in GitHub and supports the bilingual search hints inline. OpenAPI is deferred per Spec FR-020.

### R4 — JSON Schema generation strategy

**Question**: how does `scripts/build_schemas.py` produce a Draft 2020-12 JSON Schema from each Pydantic v2 envelope, deterministically, with no new dependencies?

**Decision**: walk the registry by importing `kosmos.tools.register_all` and iterating `ToolRegistry._tools` (already populated at import time per Spec 1634). For each adapter, extract `input_schema` and `output_schema` Pydantic v2 model classes. Call `Model.model_json_schema(mode='validation', ref_template='#/$defs/{model}')`. Wrap the result with explicit `$schema` and `$id` keys:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://kosmos.example/api/schemas/<tool_id>.json",
  "title": "<tool_id>",
  "type": "object",
  "properties": { ... },
  "$defs": { ... }
}
```

Sort keys at every level using `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` to guarantee byte-identical output across runs (FR-007 idempotency).

**Rationale**: Pydantic v2 `model_json_schema()` natively targets Draft 2020-12 and supports the `$defs` / `$ref` template required for nested envelopes. `sort_keys=True` plus a fixed indent yields deterministic output (the only non-determinism risk is dict iteration order, eliminated by sorting). `ensure_ascii=False` preserves Korean field descriptions when present.

**Alternatives considered**:

- **`pydantic.TypeAdapter(Model).json_schema()`** — equivalent; `Model.model_json_schema()` is shorter and doesn't require an extra wrapper.
- **`apischema` or `jsonschema-rs`** — new dependency; rejected by AGENTS.md hard rule and FR-022.
- **Hand-rolled JSON Schema authoring** — rejected: schemas drift from Pydantic source; impossible to keep in sync.

### R5 — `docs/tools/` → `docs/api/` migration mapping

**Question**: which existing `docs/tools/*.md` file maps to which `docs/api/<source>/<tool>.md` destination, and where do the legacy ministry-group index files (`kma.md`, `koroad.md`) go?

**Decision**: 1-to-1 file-level mapping per the table below. `kma.md` and `koroad.md` are ministry-group descriptors — content merged into `docs/api/<ministry>/README.md` (a new index per ministry directory). `road-risk-score.md` is deleted outright.

| Source (`docs/tools/`) | Destination (`docs/api/`) | Notes |
|---|---|---|
| `geocoding.md` | `resolve_location/index.md` | Meta-tool spec; juso/sgis/kakao backends as variants. |
| `kma-alert.md` | `kma/weather_alert_status.md` | tool_id = `kma_weather_alert_status`. |
| `kma-observation.md` | `kma/current_observation.md` | tool_id = `kma_current_observation`. |
| `kma-pre-warning.md` | `kma/pre_warning.md` | tool_id = `kma_pre_warning`. |
| `kma-short-term-forecast.md` | `kma/short_term_forecast.md` | tool_id = `kma_short_term_forecast`. |
| `kma-ultra-short-term-forecast.md` | `kma/ultra_short_term_forecast.md` | tool_id = `kma_ultra_short_term_forecast`. |
| `kma.md` | `kma/README.md` | KMA ministry group index; lists 6 KMA adapters. |
| `koroad.md` | `koroad/README.md` | KOROAD group index; lists 2 KOROAD adapters. |
| `nfa119.md` | `nfa119/emergency_info_service.md` | tool_id = `nfa_emergency_info_service`. |
| `README.md` | `api/README.md` | Promoted to docs/api/ root index, expanded to the active-adapter matrix. |
| `road-risk-score.md` | (deleted) | Composite removed per Spec 1634. |
| `ssis.md` | `mohw/welfare_eligibility_search.md` | tool_id = `mohw_welfare_eligibility_search`; renamed source folder from `ssis` to ministry name `mohw` for consistency. |

In addition, **net-new specs** (no source in `docs/tools/`): `kma/forecast_fetch.md`, `hira/hospital_search.md`, `nmc/emergency_search.md`, plus active Mock adapters under `verify/` and `submit/`. Subscribe specs are deferred until KOSMOS has an app/push-notification runtime. These are authored from scratch using the R3 template.

After migration, `docs/tools/` does not exist (FR-008 / SC-006).

**Rationale**: file-level 1-to-1 mapping minimizes information loss; ministry-group READMEs preserve the existing browse pattern; net-new specs match adapter source-tree boundaries.

**Alternatives considered**: keeping `docs/tools/` as a redirect shim was rejected — Markdown has no native redirect, and dual locations confuse external link references.

### R6 — Visual-evidence ANSI capture tooling

**Question**: how does the smoke-checklist runner capture each TUI state as ANSI text without introducing new tooling dependencies, and how is the output named?

**Decision**: use macOS BSD `script(1)` invoked manually per smoke step:

```bash
script -q "specs/1637-p6-docs-smoke/visual-evidence/<slug>.ansi.txt" \
  bun run tui --headless --simulate <step>
```

For interactive steps where `--simulate` is not implemented, the validator drives the TUI manually within the `script` session and types `Ctrl-D` to end the capture. The plain-text companion file `<slug>.txt` is produced from the ANSI capture by `cat <slug>.ansi.txt | sed 's/\x1b\[[0-9;]*m//g' > <slug>.txt`.

File naming follows Spec 1636: `<step-slug>.ansi.txt` (raw escape codes) + `<step-slug>.txt` (plain). Slugs use kebab-case derived from the smoke-checklist step ID (e.g., `onboarding-step-3-pipa.ansi.txt`).

**Rationale**: `script(1)` is part of the macOS base system (and most BSD/Linux variants); zero new dependencies; ANSI-text captures are diff-friendly and reviewable in PR; pairing raw and stripped variants makes both visual replay and grep-based audit possible. Convention exactly mirrors Spec 1636's `specs/1636-plugin-dx-5tier/visual-evidence/` directory.

**Alternatives considered**:

- **`asciinema`** — adds a runtime dependency and produces a binary cast file; rejected per FR-022 / AGENTS.md hard rule.
- **Bun-side `--screenshot`** — does not exist on Ink; would require building it; out of scope.
- **Manual screenshot PNGs** — not diff-friendly; not text-grep-able; rejected.

### R7 — `useVirtualScroll.ts:273` Set type error analysis

**Question**: what is the root cause of the `new Set(itemKeys)` type error reported by `bun test`, and what is the minimal fix that keeps the existing test contract intact?

**Decision**: the Bun TypeScript type-check at line 273 (`const live = new Set(itemKeys)`) fails because `itemKeys` is typed as `ReadonlyArray<K> | undefined` (or a union including `undefined`) at the hook's call site, while `Set<K>`'s constructor requires `Iterable<K> | null` (not `undefined`). The minimal fix is to widen `Set` construction to handle the optional case — either via nullish-coalescing default `new Set(itemKeys ?? [])` or by hoisting the assertion into the hook signature so `itemKeys` arrives as `ReadonlyArray<K>`.

The implementation phase will:

1. Read `useVirtualScroll.ts` lines 240–280 to confirm the actual signature.
2. Apply the minimal nullish-coalescing fix at line 273 (and any sibling `new Set(...)` if present).
3. Re-run only the `tui/tests/components/conversation/overflowToBackbuffer.test.tsx` family to confirm fix.
4. If the type-check still fails after the minimal fix, escalate to a hook-signature widening (still keeping test expectations untouched per FR-011).

**Rationale**: spec FR-011 requires the test contract to be preserved; the fix must therefore happen at the implementation, not the test. The error message in the bun-test output (`error: Type error - at Set (unknown) - <anonymous> (tui/src/hooks/useVirtualScroll.ts:273:22)`) localizes the call. Hook signature surrounding context confirms `itemKeys` is referred to as a stable ref input — the absent-case handling is the missing piece.

**Alternatives considered**:

- **`new Set([...itemKeys])` spread** — same effect but adds an array allocation per render; rejected.
- **Modifying the `VirtualizedList overflowToBackbuffer` test expectations** — explicitly forbidden by FR-011.
- **Suppressing the type error with `as any`** — violates Constitution Principle III (no `Any` in I/O schemas) by analogy and is bad TS practice; rejected.

## Phase 0 outputs

- All R-items resolved; zero NEEDS CLARIFICATION markers.
- Constitution Check (plan.md) passes; Deferred Items conform to Principle VI.
- Reference mapping table grounds every plan section in either `docs/vision.md § Reference materials` or a prior KOSMOS spec.

Ready for Phase 1.
