# Implementation Notes: Public AX Document Harness

Date: 2026-06-01

## Scope Correction

This feature implements a document harness, not a parser/converter project.
UMMAYA owns the model-facing tool contracts, artifact lineage, permission
payloads, render/re-read evidence, public-form validation, and capability
promotion loop. Format-specific parsing, mutation, rendering, and validation
behavior is delegated to promoted engines behind `DocumentEngineRegistry`.

## Implemented Layers

1. Foundation: strict Pydantic models, immutable local artifact store, intake
   security checks, contract loader, engine registry, and package exports.
2. Inspection: engine-backed read-only inspection for HWPX, HWP, DOCX, PDF,
   XLSX, and PPTX fixture boundaries with unsafe-file blocking.
3. Mutation: copy-for-edit, ordered fill/style patches, derivative diffs, and
   HWP direct-write blocking.
4. Validation: public-form baselines, structural metrics, hard-rule findings,
   readiness decisions, and data.go.kr-derived metadata snapshots for semantic
   coverage only.
5. Evidence: render artifacts, derivative re-read checks, validation downgrade
   on mismatch, and Evidence Fabric records joinable by `correlation_id`.
6. Tool loop: nine concrete `GovAPITool` definitions registered under existing
   `find`, `check`, and `send` primitives with write/export auth gates.
7. Evaluation loop: candidate profile scorecards, dependency/license gates,
   promotion/deferral persistence, and documented rejected alternatives.
8. Runtime promotion: default local runtime now registers read-only DOCX
   inspection through `python-docx` after fixture-backed read promotion, plus
   bounded HWPX text-node read/write through `hwpx-package-text` for local
   public-form smoke tests.

## Parallel Development Record

The safe dispatch boundary was file ownership. US3 validation, US4 evidence,
US6 candidate evaluation, and Polish tests were parallel-safe because each
owned mostly disjoint files. US5 ToolRegistry integration was not broadly
parallel-safe because tool definitions, executor wiring, permissions, and boot
registration form one model-facing contract. The Lead integrated US5 while
subagents wrote only isolated test files.

## Evaluation Criteria Applied

The implementation follows the C1-C12 criteria in
[`parallel-evaluation-plan.md`](./parallel-evaluation-plan.md). The hard gates
are standards mapping, controlled mutation, strict tool schemas, upload safety,
unsupported-feature blocking, and headless operation. Write promotion requires
all hard gates plus scorecard evidence; read-only promotion requires security
hard gates plus read/extract evidence.

## Reference Bootstrap

- KS X 6101/OWPML and the HWPX ecosystem anchor Korean public-document format
  evidence. HWP binary direct writing remains blocked in this epic.
- ECMA-376 anchors DOCX/XLSX/PPTX package semantics; `python-docx` is promoted
  for default read-only DOCX inspection, while DOCX write and the remaining
  `openpyxl`/`python-pptx` operations stay candidate-gated until fixture
  evidence promotes each operation.
- PDF support is AcroForm- and evidence-gated; scanned/static/XFA/signature
  preserving mutation remains blocked unless future evidence promotes it.
- OWASP file-upload guidance defines intake safety: extension allowlists,
  MIME distrust, signatures, safe filenames, decompression limits, and isolated
  storage.
- MCP tool structured-output patterns validate the schema-bound harness shape,
  but UMMAYA keeps its native ToolRegistry and permission pipeline.
- data.go.kr public document/core-data metadata helps choose representative
  administrative scenarios; it is not treated as a file-level submission-form
  layout oracle.

## Current Limitations

- HWPX default write support is intentionally bounded to text-node replacement
  in existing package structure. It does not claim full style/layout/render
  fidelity and must be reread after mutation before external handoff.
- DOCX write/style/render fidelity is not promoted yet. The default
  `python-docx` engine is read-only and extracts top-level paragraphs, tables,
  and core properties; nested tables and revision-mark content remain an
  explicit warning boundary.
- HWP binary write remains blocked.
- Tool execution is local only. `document_save` writes an export artifact for
  review or handoff; it does not submit to Government24, Hometax, or another
  agency channel.
