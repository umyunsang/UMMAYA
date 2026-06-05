# Save/Export Hardening Deep Research Migration Note — 2026-06-03

Scope: promote a reviewed document derivative from the session artifact store to a
user-visible local output path when, and only when, the user explicitly asks to
save/export the completed document. This checkpoint follows the live TUI finding
that the document primitive could edit and render a diff, but the resulting bytes
remained only in `.ummaya/document_artifacts`.

## Reference Bootstrap

- UMMAYA thesis/docs: `docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`,
  and `specs/2802-public-doc-harness/data-model.md`.
- Active local contract: the model-facing unit remains one `document` primitive;
  inspect, fill, render, validate, and save are internal runtime stages.
- Claude Code restored-source status: no first-class public-document save tool is
  present in `.references/claude-code-sourcemap/restored-src/`; the relevant
  analog is CC file-edit behavior, where mutation is visible through a tool result
  and a structured diff, not a hidden artifact-only state.
- CC integrity classification: document save is `not present in CC`; tool-loop and
  diff-result ordering are `intact` analogs.
- UMMAYA divergence: document artifacts are binary/package formats, so source files
  stay immutable by default. A user-visible save is a separate explicit export
  boundary with path/hash evidence.

## 2026-Current Sources

- Model Context Protocol schema, 2025-11-25: tool results carry
  `structuredContent`, and tool annotations such as `readOnlyHint`,
  `destructiveHint`, `idempotentHint`, and `openWorldHint` are only hints; clients
  must not rely on untrusted annotations alone for safety decisions. Adopted as a
  reason to keep save/export as an explicit result field and fail-closed runtime
  check, not a prompt-only hint.
- Language Server Protocol 3.17 `WorkspaceEdit`: resource edits can include
  versioned document changes and create/rename/delete operations; clients execute
  ordered resource operations and define failure handling. Adopted as the
  conceptual shape: derivative write, render/diff, then ordered local export.
- Python 3.14 `os.replace`: same-filesystem replacement is atomic on POSIX when
  successful. Adopted for final local-path write.
- Python 3.14 `tempfile`: secure temporary-file creation should avoid insecure
  `mktemp`; `NamedTemporaryFile`/`mkstemp` create the file immediately. Adopted via
  `tempfile.mkstemp` in the destination directory before `os.replace`.

## Candidate Scorecard

Weights: correctness 25, safety/privacy 20, UMMAYA thesis fit 15,
testability/evidence 15, user-visible quality 15, migration cost 10.

| Candidate | Score | Decision | Notes |
| --- | ---: | --- | --- |
| Artifact-store only | 63 | Reject as final | Safe, but the user cannot find the saved file without reading artifact metadata. |
| Always overwrite source path | 61 | Reject | Looks CC-like, but unsafe for binary public forms and contradicts immutable source artifact rules. |
| Explicit `destination_path` local export via temp file + atomic replace | 94 | Adopt | Preserves immutable source, gives the user a real local file, and records path/hash evidence. |
| Separate `document_save` model-facing tool | 70 | Reject for default | Reintroduces tool confusion; keep save as an internal stage of the single `document` primitive. |

## Selected Migration Boundary

- Add `destination_path` to `DocumentPrimitiveRequest` and `DocumentSaveRequest`.
- Add `DocumentSavedExport` and `DocumentToolResult.saved_exports` as structured
  result evidence.
- Keep artifact-store export creation for lineage and hash joinability.
- If `destination_path` is present, write the same reviewed derivative payload to
  the explicit local path using a same-directory temp file and `os.replace`.
- Validate extension compatibility, hidden path components, and directory targets
  before writing. Invalid local export paths return blocked tool results instead
  of pretending the document was saved.

## Tests/Evidence

- RED test:
  `tests/tools/documents/test_document_tool_flow.py::test_document_save_promotes_reviewed_derivative_to_explicit_local_path`
  first failed because `DocumentSaveRequest` rejected `destination_path`.
- GREEN tests:
  - explicit `document_save(destination_path=...)` writes the local file and records
    `saved_exports`;
  - single `document` primitive saves when only `destination_path` is provided;
  - mismatched local export extension is blocked and writes no file.
- Focused verification:
  - `uv run pytest tests/tools/documents/test_contract_schema.py tests/tools/documents/test_contract_models.py tests/tools/documents/test_models.py tests/tools/documents/test_document_tool_flow.py::test_document_save_promotes_reviewed_derivative_to_explicit_local_path tests/tools/documents/test_document_tool_flow.py::test_document_primitive_saves_to_destination_path_without_separate_stage tests/tools/documents/test_document_tool_flow.py::test_document_save_blocks_explicit_local_path_extension_mismatch -q`
  - `uv run ruff check ...`
  - `uv run mypy ...`

## Remaining Gate

The next live TUI alpha should use natural Korean phrasing that asks the model to
understand the document, write the next week automatically, and save the completed
file to an explicit Downloads path. Pass requires tool-call painting, inline diff,
final changed-value answer, and a real file existing at the requested path.

## Live Alpha Correction

First live replay exposed a critical false-positive path:

- User requested save to
  `/Users/um-yunsang/Downloads/ummaya-save-export-alpha-14.hwpx`.
- The model included that path in `instruction`, but omitted top-level
  `destination_path`.
- The tool edited and rendered the document, but `saved_exports` was empty and no
  local file existed.
- The assistant still claimed the file was saved.

Correction:

- `document` now derives an explicit save path from the instruction when the user
  includes a local document path and save intent, excluding the source path and
  requiring matching extension.
- The primitive merges the save workflow step back into the rendered document
  result so `save=completed` is visible in the structured result.
- TUI completion repair now has a dedicated changed-content-plus-save-location
  prompt. It may cite a save location only from `saved_exports`; otherwise it
  emits no saved-path claim.

Second live replay passed:

- TUI session: `b83af15f-5913-4997-bd1f-967ae1c4f2b7`.
- `saved_exports[0].local_path`:
  `/Users/um-yunsang/Downloads/ummaya-save-export-alpha-14.hwpx`.
- File hash:
  `23e8590b66e544d0b842ca547d83c40c0aba907d45d297354179b4885f22b01e`.
- Final answer contained only the two changed paths and the saved local path.
