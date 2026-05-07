# Phase 1 Data Model — P6 · Docs/API specs + Integration smoke

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Date**: 2026-04-26

P6's "data model" is the schema of every artifact this Epic produces. Because the Epic is documentation-and-tooling-heavy, the entities are filesystem objects and Markdown structures rather than runtime types.

## Entity catalog

### 1. AdapterSpec

A Markdown document describing a single active registered adapter.

**Location**: `docs/api/<source>/<tool>.md`. The `<source>` segment matches `kosmos.tools.<source>` directory naming with normalization noted in research.md § R5 (e.g., `ssis` → `mohw`).

**Required structure** (verbatim heading text, in order):

| Section | Heading | Content |
|---|---|---|
| Front matter | (YAML block) | `tool_id`, `primitive` (one of `lookup` / `submit` / `verify` / `resolve_location`), `tier` (one of `live` / `mock`), `permission_tier` (1 / 2 / 3) |
| 1. Overview | `## Overview` | One sentence purpose; classification key-value table |
| 2. Envelope | `## Envelope` | Pydantic v2 input/output model citation: file path + line range; field table per envelope |
| 3. Search hints | `## Search hints` | Bilingual list; Korean primary, English secondary |
| 4. Endpoint | `## Endpoint` | `data.go.kr` endpoint ID + ministry source URL (Live) OR "Fixture-replay only" + public-spec citation (Mock) |
| 5. Permission tier rationale | `## Permission tier rationale` | Per-adapter justification; cites Spec 033 |
| 6. Worked example | `## Worked example` | At least one `lookup(mode="fetch")` (or `submit` / `verify`) invocation: input JSON, output JSON, KOSMOS conversation snippet |
| 7. Constraints | `## Constraints` | Rate limits, freshness windows, fixture coverage gaps, error-envelope examples |

**Validation rules**:

- All seven sections present (structural lint script gates SC-001).
- YAML front matter parses successfully and contains all four required keys.
- Search-hints section contains at least one Korean string and at least one English string.
- For Live tier: Endpoint section MUST contain a `data.go.kr` endpoint ID matching the regex `[A-Za-z0-9_-]+`.
- For Mock tier: Endpoint section MUST contain "Fixture-replay only" verbatim AND a public-spec citation URL or document title.

**State transitions**: none. AdapterSpec is a static document authored once and updated when the underlying adapter changes.

### 2. AdapterIndex

The single root index document mapping every AdapterSpec into two cross-cutting matrices.

**Location**: `docs/api/README.md`.

**Required structure**:

1. One-paragraph introduction: what this catalog is and how to read it.
2. Matrix A — by source: rows are sources (KOROAD, KMA, HIRA, NMC, NFA119, MOHW, mock-verify, mock-submit, resolve_location). Columns: tool_id, primitive, tier, permission_tier, schema link.
3. Matrix B — by primitive: rows are primitives (`lookup` × N, `submit` × N, `verify` × N, `resolve_location` × 1). Columns: tool_id, source, tier, permission_tier.
4. "How to use this catalog" section: 3-step recipe (find adapter → read spec → consume schema).

**Validation rules**:

- Every row in either matrix MUST link to an AdapterSpec that exists.
- Every link to `docs/api/schemas/<tool_id>.json` MUST resolve to an existing file.
- Both matrices MUST sum to the active registered adapter set. Deferred subscription adapters are excluded.

### 3. JSONSchema

A Draft 2020-12 JSON Schema document describing one adapter's input or output Pydantic envelope.

**Location**: `docs/api/schemas/<tool_id>.json`. Per FR-006: one file per tool_id; the schema combines input and output models under top-level keys (the script flattens both into `$defs`).

**Required keys**:

| Key | Value |
|---|---|
| `$schema` | `https://json-schema.org/draft/2020-12/schema` (verbatim) |
| `$id` | `https://kosmos.example/api/schemas/<tool_id>.json` (the example domain is a placeholder; FR-007 idempotency needs only stability, not resolvability) |
| `title` | The tool_id |
| `type` | `object` (the schema describes the input envelope at root; the output envelope lives under `$defs.<output_model_name>`) |
| `properties` | Pydantic-derived properties of the input envelope |
| `required` | Pydantic-derived required-list of the input envelope |
| `$defs` | Nested model definitions, including the output envelope keyed by its model class name |

**Validation rules**:

- `$schema` value MUST be exactly the Draft 2020-12 URI.
- The file MUST validate as JSON (no parse errors).
- The file MUST validate against a generic Draft 2020-12 meta-schema validator.
- Re-running `python scripts/build_schemas.py` MUST produce a byte-identical file (FR-007).

### 4. SchemaBuildScript (`scripts/build_schemas.py`)

The deterministic builder that produces every JSONSchema entity above.

**Inputs**: registry instance constructed by importing `kosmos.tools.register_all`.

**Outputs**: `docs/api/schemas/<tool_id>.json` × N (where N = registry size).

**Behavior contract**:

1. Import the registry.
2. Iterate adapters in **alphabetical order** by tool_id (deterministic).
3. For each adapter: extract input and output Pydantic models, call `model_json_schema(mode='validation', ref_template='#/$defs/{model}')`.
4. Wrap as the JSONSchema entity above.
5. Write with `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` and a trailing newline.
6. On exit, print the count of files written and the count of files unchanged. Non-zero exit only on hard errors (registry import failure, write failure).

**No new dependencies**: stdlib (`json`, `pathlib`, `argparse`, `sys`) + Pydantic v2 (existing). The `argparse` parser supports a `--check` flag that exits non-zero if any output file would change — used by CI to gate "schemas are out of date" PRs.

### 5. SmokeChecklist

The hand-driven validation document recording each TUI smoke step.

**Location**: `specs/1637-p6-docs-smoke/contracts/smoke-checklist-template.md` is the template; the populated artifact lives at `specs/1637-p6-docs-smoke/smoke-checklist.md` after implement.

**Required rows** (minimum active smoke set per FR-013):

| Step ID | Description | Input | Expected | Evidence file |
|---|---|---|---|---|
| `onboarding-1-preflight` | Onboarding step 1: preflight check | (auto on TUI start) | Preflight panel renders, all checks green | `<step-id>.ansi.txt` + `<step-id>.txt` |
| `onboarding-2-theme` | Onboarding step 2: theme selection | Arrow keys + Enter | Theme tokens applied | (same naming) |
| `onboarding-3-pipa` | Onboarding step 3: PIPA consent | "Y" | Consent receipt rendered | (same naming) |
| `onboarding-4-ministry` | Onboarding step 4: ministry scope | Arrow + Space + Enter | Selected scope persisted | (same naming) |
| `onboarding-5-terminal` | Onboarding step 5: terminal setup | Enter | TUI enters main REPL | (same naming) |
| `primitive-lookup-search` | `lookup` primitive search mode | Citizen query "이 길 안전해?" | BM25 candidates surfaced | (same naming) |
| `primitive-lookup-fetch` | `lookup` primitive fetch mode | Selected adapter | Adapter response in conversation | (same naming) |
| `primitive-submit` | `submit` primitive (mock) | Mock adapter selection | Submission receipt | (same naming) |
| `primitive-verify` | `verify` primitive (mock) | Mock adapter | Verification result | (same naming) |
| `slash-agents` | `/agents` command | Type slash command | Agent panel renders | (same naming) |
| `slash-plugins` | `/plugins` command | Type slash command | Plugin browser renders | (same naming) |
| `slash-consent-list` | `/consent list` command | Type slash command | Consent receipts list | (same naming) |
| `slash-help` | `/help` command | Type slash command | Help V2 panel | (same naming) |
| `error-llm-4xx` | LLM 4xx error envelope | Force 4xx | Spec 035 envelope rendered | (same naming) |
| `error-tool-fail-closed` | Tool fail-closed error | L3 unauthenticated | Fail-closed envelope | (same naming) |
| `error-network-timeout` | Network timeout error | Force timeout | Network envelope | (same naming) |
| `pdf-inline-render` | PDF inline render path | `/export pdf` | Inline render (Kitty/iTerm2) or `open` fallback | (same naming) |

Validation rule: every row MUST cite an evidence file present in `specs/1637-p6-docs-smoke/visual-evidence/`. Step IDs MUST match the slug convention.

### 6. VisualEvidenceArtifact

A pair of files (`<step-id>.ansi.txt` + `<step-id>.txt`) capturing one smoke step.

**Location**: `specs/1637-p6-docs-smoke/visual-evidence/`.

**Required pair**:

- `<step-id>.ansi.txt` — raw `script(1)` output with ANSI escape codes preserved.
- `<step-id>.txt` — same content with escape codes stripped (`sed 's/\x1b\[[0-9;]*m//g'`).

**Validation rules**:

- Both files of a pair MUST exist for every step in the smoke checklist.
- Each `.ansi.txt` MUST be non-empty.
- File naming MUST match the step ID.

### 7. CompositeRemovalAudit

An implicit deliverable: zero non-historical references to `road_risk_score` across the documentation tree after merge.

**Verification command** (per spec SC-004):

```bash
grep -rn 'road_risk_score' docs/ \
  | grep -vE '(release-manifests|adr|release-notes)' \
  | wc -l
```

Expected output: `0`.

This is not a file but an audit invariant; the equivalent verification is recorded as the SC-004 success criterion check in the PR body.

### 8. ChangeLogEntry

The KOSMOS v0.1-alpha entry in `CHANGELOG.md`.

**Location**: `CHANGELOG.md` (top of file, prepend-style).

**Required structure**:

```markdown
## v0.1-alpha — KOSMOS Migration Completion

**Released**: 2026-MM-DD (filled at PR merge)
**Initiative**: #1631 (closed)
**Phases shipped**: P0 (#1632) · P1+P2 (#1633) · P3 (#1634) · P4 (#1847) · P5 (#1927) · P6 (#1637)

### Highlights

- KOSMOS now routes a Korean citizen's request through the migrated Claude Code harness:
  EXAONE function call → active primitives (`lookup` · `resolve_location` · `submit` · `verify`) →
  registered adapter → permission gauntlet → response rendered in the migrated TUI.
- Active registry-bundled adapters documented with bilingual search hints under `docs/api/`.
- 5-tier plugin DX (P5) onboards external contributors via `kosmos plugin init`.

### Aligned with

- Korea AI Action Plan (2026-2028) Principles 8 (single conversational surface), 9 (Open API),
  and 5 (consent-based access).
- PIPA §26 trustee model (memory `project_pipa_role`).

### Out of v0.1-alpha

- Live API regression coverage for the 12 Live-tier adapters (Phase 2).
- OPAQUE-tier shape-mirror adapters (`barocert/`, `npki_crypto/`, `omnione/`).
- OpenAPI 3.0 specification for `/agent-delegation`.
```

**Validation rules**:

- The entry MUST be the topmost section of `CHANGELOG.md`.
- All six phase Epic numbers MUST appear and resolve to merged PRs at the time of merge.
- Initiative #1631 MUST be referenced and MUST be closeable upon merge.

## Relationships

```text
AdapterIndex (docs/api/README.md)
  │
  ├─ links active adapters ─→  AdapterSpec (docs/api/<source>/<tool>.md)
  │                   │
  │                   └─ cites Pydantic models in src/kosmos/tools/<source>/...
  │
  └─ links active adapters ─→  JSONSchema (docs/api/schemas/<tool_id>.json)
                       │
                       └─ generated by  SchemaBuildScript (scripts/build_schemas.py)
                                            │
                                            └─ walks registry from kosmos.tools.register_all

SmokeChecklist (smoke-checklist.md)
  │
  └─ each step references → VisualEvidenceArtifact pair (.ansi.txt + .txt)

CompositeRemovalAudit ──→ verifies absence across docs/

ChangeLogEntry ──→ closes Initiative #1631 references
```

No state transitions; everything is materialized once at the close of P6 and persists as the canonical record of the KOSMOS migration.
