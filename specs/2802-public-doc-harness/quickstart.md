# Quickstart: Public AX Document Harness

This quickstart defines the implemented developer workflow for the Public AX
document harness. The feature exposes local, engine-backed document tools
through UMMAYA's existing ToolRegistry; it does not add a first-party parser,
converter, office editor, or new root primitive family.

## 1. Verify Environment

```bash
uv sync --frozen --all-extras --dev
uv run python --version
```

Expected:

- Python is 3.12 or newer.
- No document-processing dependency is added without a task-level justification, license note, and focused tests.

## 2. Confirm Feature Artifacts

```bash
test -f specs/2802-public-doc-harness/spec.md
test -f specs/2802-public-doc-harness/plan.md
test -f specs/2802-public-doc-harness/research.md
test -f specs/2802-public-doc-harness/data-model.md
test -f specs/2802-public-doc-harness/contracts/document-tools.schema.json
```

## 3. Validate Contract Schema

```bash
uv run python -m json.tool specs/2802-public-doc-harness/contracts/document-tools.schema.json >/tmp/document-tools.schema.normalized.json
```

Expected:

- JSON parses successfully.
- Tool contracts include `document_inspect`, `document_extract`, `document_form_schema`, `document_copy_for_edit`, `document_apply_fill`, `document_apply_style`, `document_render`, `document_validate_public_form`, and `document_save`.

## 4. Build Fixture Corpus

The implemented fixture and baseline corpus lives under:

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
- expected form fields
- expected style assertions
- expected render/validation outcome
- whether the file is data.go.kr-derived metadata, a locally created fixture, or a hostile negative fixture

No live `data.go.kr` request is allowed in CI.

## 5. Run Focused Feature Tests

After implementation:

```bash
uv run pytest tests/tools/documents tests/evidence tests/ci -q
```

Expected:

- HWPX, DOCX, XLSX, PDF, and PPTX happy paths pass only for promoted capabilities.
- HWP direct write returns a structured blocked result.
- Hostile fixtures fail closed before unsafe parse or write.
- Public-form validation computes paragraph, table, image, metadata, aggregate, round-trip, render, and security results.
- `document_inspect`, `document_extract`, `document_form_schema`, `document_copy_for_edit`, `document_apply_fill`, `document_apply_style`, `document_render`, `document_validate_public_form`, and `document_save` register as concrete `GovAPITool` definitions.
- Write/export operations are `send` tools and require the existing permission/auth gate before creating derivatives or exports.

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
uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json
```

Expected:

- `.evidence/run.json` includes document harness scenario results joinable by `correlation_id`.
- Document validation reports point to artifact IDs, not raw untrusted paths.
- Render outputs and reports are stored under safe artifact/evidence paths.
- Evidence records carry artifact IDs, SHA-256 hashes, report IDs, render IDs, and correlation IDs only; raw document bytes and user source paths are excluded.

## 8. Manual Tool-Loop Smoke

Use a local public-form-like fixture and ask UMMAYA to:

1. inspect the file,
2. extract form fields,
3. copy for edit,
4. fill a field,
5. apply a font/style patch,
6. render or validate the derivative,
7. save the derivative.

Expected:

- The model sees only promoted operations.
- Permission is requested before derivative writes.
- The final answer reports artifact IDs, validation decision, and blocked limitations.
- Unsupported format/capability paths return typed `blocked` results rather than silent best-effort conversion.
