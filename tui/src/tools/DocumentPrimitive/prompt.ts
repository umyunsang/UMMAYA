// SPDX-License-Identifier: Apache-2.0
// UMMAYA-original — DocumentPrimitive prompt strings.

export const DOCUMENT_TOOL_NAME = 'document'

export const DESCRIPTION =
  'Read, fill, validate, render, and save local public-document files through the document harness primitive.'

export const DOCUMENT_TOOL_PROMPT = `Operate on local public-document files through UMMAYA's document harness.

Use this primitive for HWPX, HWP, DOCX, PDF, XLSX, and PPTX document work when the user asks to understand, write, revise, validate, render, diff, or save a document.

Input:
- correlation_id: stable request id for evidence join.
- document: { path?: string, artifact_id?: string, expected_format?: "hwpx" | "hwp" | "docx" | "pdf" | "xlsx" | "pptx" }.
- operation: "inspect", "extract", "fill", "style", "validate", or "save".
- instruction: natural-language instruction for the document harness.
- destination_path: optional explicit local output path.

Rules:
- For "read only" requests use inspect or extract.
- For "understand and write/fill/save" requests use fill or save; do not split into separate inspect/fill/render tool calls.
- Prefer explicit local paths supplied by the user.
- Do not use workspace file tools for document-format editing; this primitive owns document edits, save evidence, and inline diff rendering.
- The tool result is already rendered inline in the TUI; final answers should only summarize the visible outcome.`
