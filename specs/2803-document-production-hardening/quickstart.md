# Quickstart: Document Production Hardening

This quickstart defines the developer workflow for the active document production hardening spec.
The feature keeps one model-facing `document` primitive and treats inspection, Socratic evidence
collection, draft approval, derivative writing, validation, render comparison, and save/export as
internal workflow stages.

## 1. Verify Environment

```bash
uv sync --frozen --all-extras --dev
uv run python --version
```

Expected:

- Python is 3.12 or newer.
- No document-processing dependency is added without task-level justification, license review, local-only execution proof, and focused tests.

## 2. Confirm Feature Artifacts

```bash
test -f specs/2803-document-production-hardening/spec.md
test -f specs/2803-document-production-hardening/contracts/document-tools.schema.json
test -f .omo/plans/document-production-hardening-2803.md
```

## 3. Validate Contract Schema

```bash
uv run python -m json.tool specs/2803-document-production-hardening/contracts/document-tools.schema.json >/tmp/document-tools.schema.normalized.json
```

Expected:

- JSON parses successfully.
- Tool contracts include one model-facing `document` primitive.
- Inspect, extract, form-schema, copy-for-edit, fill, style, render, validate, and save remain internal workflow stages surfaced through result evidence.

## 4. Build Fixture Corpus

The fixture and baseline corpus lives under:

```text
tests/fixtures/documents/
├── candidate_profiles.yaml
├── public_forms/
│   ├── baselines.yaml
│   └── data_go_kr_metadata.yaml
└── ...
```

Fixture manifests and baseline records must preserve:

- source/license/provenance
- format
- expected extraction counts
- expected form fields and narrative prompts
- expected style assertions
- expected render/validation outcome
- whether the file is official/public metadata, a locally created fixture, or a hostile negative fixture

No live `data.go.kr` request is allowed in CI.

## 5. Run Focused Feature Tests

After implementation:

```bash
uv run pytest tests/tools/documents tests/evidence tests/ci -q
```

Expected:

- HWPX, DOCX, XLSX, PDF, and PPTX happy paths pass only for promoted capabilities.
- HWP direct write returns a structured blocked result unless a promotion gate passes.
- Hostile fixtures fail closed before unsafe parse or write.
- Broad requests such as "대충 그럴듯하게 써줘" ask for evidence rather than fabricating content.
- Write/export operations are document operations and require the existing permission/auth gate before creating derivatives or exports.

## 6. Run General Gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not live"
```

Expected:

- No `Any` in new tool I/O models.
- No live public-infrastructure calls.
- No source original mutation.

## 7. Evidence Run

After implementation:

```bash
uv run python -m ummaya.evidence --source-ref local --dataset-ref ummaya/national-ax-core@local --out .evidence/run.json
```

Expected:

- `.evidence/run.json` includes document scenario results joinable by `correlation_id`.
- Document validation reports point to artifact IDs, not raw untrusted paths.
- Render outputs and reports are stored under safe artifact/evidence paths.
- Evidence records carry artifact IDs, SHA-256 hashes, report IDs, render IDs, and correlation IDs only; raw document bytes and user source paths are excluded.

## 8. Manual Tool-Loop Smoke

Use a local public-form-like fixture and ask UMMAYA to:

1. inspect the file,
2. ask for missing evidence,
3. draft supported field or section content,
4. request approval,
5. copy for edit,
6. fill a field,
7. apply an approved font/style patch,
8. render or validate the derivative,
9. save the derivative.

Expected:

- The model sees only promoted operations.
- Permission is requested before derivative writes.
- The final answer reports artifact IDs, validation decision, and blocked limitations.
- Unsupported format/capability paths return typed `blocked` results rather than silent best-effort conversion.
