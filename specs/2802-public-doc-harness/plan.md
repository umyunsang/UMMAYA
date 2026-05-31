# Implementation Plan: Public AX Document Harness

**Branch**: `2802-public-doc-harness` | **Date**: 2026-06-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/2802-public-doc-harness/spec.md`

## Summary

Build a local UMMAYA document harness that lets the LLM inspect, extract, safely copy, fill, style, render, validate, and save public-administration document artifacts across HWPX, HWP, DOCX, PDF, XLSX, and PPTX. The harness is not a new parser/converter project and not a new root primitive family. It registers concrete tools under the existing ToolRegistry primitive metadata (`find`, `check`, `send`) and follows Claude Code-style typed tool contracts, permission boundaries, artifact storage, and evidence reporting.

The implementation is promotion-gated by format. HWPX, DOCX, XLSX, PDF, and PPTX may be promoted for write only after deterministic round-trip, render, validation, and security gates pass. Binary HWP direct writing is blocked in this epic; HWP may only receive read/extract/render/convert capabilities if evidence proves fidelity and safety.

## Technical Context

**Language/Version**: Python 3.12+ backend. TypeScript is only relevant if later tasks expose richer TUI result rendering.  
**Primary Dependencies**: Existing UMMAYA `ToolRegistry`, `GovAPITool`, Pydantic v2, Evidence Fabric, OTEL, stdlib `zipfile`/`hashlib`/`pathlib` for intake and fixture/test-double handling, pytest, pytest-asyncio, hypothesis. Candidate format engines are evaluated by scorecard before runtime adoption: `python-hwpx` for HWPX, `python-docx` for DOCX, `openpyxl` for XLSX, `pypdf` for AcroForm PDF, and `python-pptx` for PPTX. RHWP, HWP MCP, OpenHWP, pyhwp, hwp.js, and unhwp remain comparative HWP/HWPX references unless a task explicitly justifies a dependency bridge.  
**Storage**: Local file artifact store outside web/public roots at `~/.ummaya/document_artifacts/<session_id>/`, with `sources/`, `working/`, `renders/`, `reports/`, and `exports/`. CI fixtures stay under `tests/fixtures/documents/`. Evidence outputs stay under `.evidence/`.  
**Testing**: `uv run pytest tests/tools/documents tests/evidence tests/ci -q` for feature gates; `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src`, and `uv run pytest -m "not live"` before implementation completion. No live `data.go.kr` or agency calls in CI.  
**Target Platform**: Local macOS/Linux developer runtime used by Codex and UMMAYA CLI/TUI.  
**Project Type**: Backend tool-system package plus evidence fixtures. TUI integration is limited to rendering structured tool results already emitted by the tool loop unless tasks identify a real display gap.  
**Performance Goals**: For representative local fixtures up to 10 MB and 50 logical pages/slides/sheets, inspect/extract should complete within 5 seconds p95; fill/style/save/validate should complete within 15 seconds p95; oversized or decompression-risk artifacts fail closed before full parse.  
**Constraints**: Local-only processing, no external document upload, no original mutation, no hidden overwrite, no path traversal, no hidden-file or public-root writes, no direct HWP binary writing, no new root primitive verbs, Pydantic v2 strict models, and explicit dependency/license justification before adding any new package.  
**Scale/Scope**: Initial fixture matrix covers HWPX, HWP, DOCX, PDF, XLSX, and PPTX, including public-form-like templates, style-heavy templates, malformed/hostile files, and at least one data.go.kr-derived public-administration metadata corpus snapshot for form/schema matching.

## Constitution Check

### Pre-Research Gate

| Gate | Status | Evidence |
|------|--------|----------|
| Reference-first against UMMAYA thesis | PASS | Reviewed `docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`, and Claude Code restored source patterns. |
| Preserve existing primitive model | PASS | Tool IDs are concrete document tools mapped to `find`, `check`, and `send`; no `read/write/edit` root primitives are introduced. |
| Claude Code source parity check | PASS | CC supports document reading and binary output storage adjacent patterns, but not public-document authoring. This feature is a UMMAYA domain harness layered above CC-style tool contracts. |
| Pydantic v2 and no `Any` | PASS | Contracts require strict request/result models and generated JSON Schema. |
| Fail-closed public infrastructure | PASS | The harness does not call agencies or submit forms. It only manipulates local user-provided artifacts and fixture corpora. |
| No live government calls in CI | PASS | data.go.kr is used only as an offline reference corpus/metadata source. |
| Deferred work accountability | PASS | Spec deferred table is back-filled with issue references #3131 through #3137 from `/speckit-taskstoissues`. |

### Post-Design Gate

| Gate | Status | Design Decision |
|------|--------|-----------------|
| Format claims are evidence-backed | PASS | `FormatCapabilityProfile` and `PromotionGateResult` prevent unsupported read/write/style claims. |
| HWP binary risk contained | PASS | HWP direct write is blocked; read-only support must pass fidelity/security gates. |
| Public-form validity is measurable | PASS | Validation combines structural schema extraction, field mapping, round-trip reread, render evidence, and public-form scorecard metrics. |
| Security is first-class | PASS | `DocumentIntakePolicy`, `DocumentArtifact`, and negative tests cover extension allowlists, signature checks, MIME mismatch, archive expansion, paths, macros/active content, and safe derivative naming. |
| Dependency expansion is controlled | PASS | Candidate libraries are not accepted by popularity; tasks must include license, maintenance, schema coverage, and test evidence before adding any package. |

## Project Structure

### Documentation

```text
specs/2802-public-doc-harness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── document-tools.schema.json
├── checklists/
│   └── requirements.md
└── tasks.md
```

`tasks.md` is intentionally not created by this step. It must be generated only after user approval for `/speckit-tasks`.

### Source Code

```text
src/ummaya/tools/documents/
├── __init__.py
├── artifact_store.py
├── capability.py
├── intake.py
├── models.py
├── registry.py
├── render.py
├── scorecard.py
├── validate.py
└── formats/
    ├── __init__.py
    ├── hwp.py
    ├── hwpx.py
    ├── ooxml.py
    └── pdf.py

tests/tools/documents/
├── test_artifact_store.py
├── test_capability_profiles.py
├── test_contract_models.py
├── test_format_adapters.py
├── test_intake_security.py
├── test_public_form_scorecard.py
└── test_tool_registry_document_tools.py

tests/fixtures/documents/
├── corpus_manifest.yaml
├── benign/
├── public_forms/
└── hostile/

evidence/scenarios/
└── document_harness_v1.yaml
```

**Structure Decision**: Use a dedicated `src/ummaya/tools/documents/` package because the feature is a local tool harness, not a government agency adapter and not a generic file utility. The package integrates through the existing `ToolRegistry` and evidence modules instead of creating a separate service.

## Phase 0 Research Summary

Research resolves four design questions:

1. **Harness shape**: CC-style typed tools plus structured output schema are the correct boundary. MCP-style structured results and output schemas validate the same direction, but UMMAYA should keep its native ToolRegistry and permission flow.
2. **Format strategy**: Use a format capability profile per engine and per file type. HWPX is the primary Korean public-document write target because KS X 6101/OWPML is XML/package-based, but UMMAYA does not implement its own HWPX editor. HWP binary write is rejected for this epic because credible OSS support is read/convert-heavy or still maturing.
3. **Public-form validation**: data.go.kr national core data is useful as a corpus anchor and metadata source, but not sufficient alone. It must be combined with local public-form fixtures, field/paragraph/table/image metrics, and render evidence.
4. **Security posture**: Document processing starts with file-upload class controls even though files are local, because HWPX/DOCX/XLSX/PPTX are package formats and PDF can carry active content and misleading metadata.

See [research.md](./research.md) for decisions, alternatives, and source mapping.

## Phase 1 Design Summary

The design introduces:

- `DocumentArtifact`: immutable source metadata plus derivative artifact references.
- `DocumentEngineRegistry`: session-local registry of scorecard-promoted engines that the harness delegates to for real format operations.
- `FormatCapabilityProfile`: observed read/write/style/render/security support for one format/engine.
- `PromotionGateResult`: scorecard and hard-gate result that controls whether a capability is exposed to the model.
- `DocumentToolRequest`/`DocumentToolResult`: strict Pydantic contracts for model-callable tools.
- `PublicFormValidationReport`: public-form structural, semantic, round-trip, render, and security validation.
- `DocumentEvidenceRecord`: joinable evidence output for `.evidence/run.json` and feature-specific document reports.

The contract surface is documented in [contracts/document-tools.schema.json](./contracts/document-tools.schema.json). The domain model is documented in [data-model.md](./data-model.md).

## Plan Self-Evaluation

The selected implementation layer is **engine-backed harness + capability-profile + promotion-gate + concrete ToolRegistry tools**. This scored higher than first-party parser implementation, direct library wrapping, external MCP adoption, or generic file-edit abstraction because it gives the LLM an honest operation surface per format and blocks unsupported public-form writes before mutation.

| Criterion | Weight | Score | Rationale |
|-----------|--------|-------|-----------|
| UMMAYA architecture fit | 20 | 20 | Uses existing ToolRegistry, permission, evidence, and primitive metadata; no new root primitive family. |
| Format-specific evidence depth | 20 | 17 | HWPX/OOXML/PDF/HWP risks are separated; remaining engine selection is intentionally task-scoped and issue-backed. |
| Public-form conformance measurability | 20 | 18 | Defines structural, round-trip, render, and public-form metrics; exact fixture pack remains a tracked task. |
| Security and privacy posture | 20 | 20 | Local-only artifact store, immutable originals, derivative writes, upload-class controls, and hostile fixtures are mandatory. |
| Implementation specificity | 20 | 17 | Provides module layout, contracts, models, tests, and evidence path; dependency additions still require task-level justification. |
| **Total** | **100** | **92** | Suitable to advance to `/speckit-tasks` after user approval. |

Residual risks:

- HWPX write promotion depends on fixture evidence, not library claims.
- Binary HWP remains read-only or blocked until evidence proves extraction/render safety.
- PDF appearance validation needs a final renderer/oracle selection before write promotion.
- Fixture licensing and data.go.kr-derived metadata snapshots must be issue-backed before implementation.

## Phase 2 Planning Handoff

`/speckit-tasks` should generate dependency-ordered tasks in this order:

1. Build model/contracts and artifact store before any format engine code.
2. Build intake/security gates and negative tests before parsing hostile files.
3. Implement capability profiles and promotion scorecard.
4. Implement engine-backed HWPX/DOCX/XLSX/PDF/PPTX adapter boundaries behind capability gates; direct parser/editor implementation is out of scope.
5. Implement copy/fill/style/save as an engine-backed mutation harness: UMMAYA owns ordered patches, artifact lineage, style bounds, typed blocked results, and diffs; promoted engines own file-format mutation.
6. Implement HWP read-only probe behind an explicit blocked-write contract.
7. Register concrete tools in `ToolRegistry`.
8. Add fixture corpus, data.go.kr-derived metadata manifest, evidence scenario, and CI gates.
9. Add documentation and PR reference mapping.

No implementation starts until `/speckit-tasks`, `/speckit-analyze`, and `/speckit-taskstoissues` complete.

## Complexity Tracking

No constitution violation is introduced by this plan.
