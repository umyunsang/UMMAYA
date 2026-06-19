# Public Document Harness — `document` Primitive

> The `document` primitive is UMMAYA's public-form authoring harness: it lets the
> agent open a Korean administrative form, understand its fields, fill and style
> them, validate against public-form rules, and render a result — without ever
> silently writing a government document. Authoring is gated on Evidence Fabric
> coverage plus an explicit in-session approval.
>
> Source: `src/ummaya/tools/documents/`. Evidence: `src/ummaya/evidence/document_*`.
> Related decisions: [ADR-011 (HWP conversion bridge)](../adr/ADR-011-hwp-conversion-bridge.md),
> [ADR-012 (LibreOffice derivative bridge)](../adr/ADR-012-legacy-office-libreoffice-bridge.md),
> [ADR-010 (`workspace_bash` permission boundary)](../adr/ADR-010-workspace-bash-permission-boundary.md).

## Why a document primitive

Korean administrative work frequently ends in a *filled form* — 전입신고서, 복지
신청서, 민원 서식 — distributed as HWP/HWPX, PDF AcroForm, or Office/ODF documents.
A citizen-facing agent that can only read public data still leaves the hardest
step (correctly filling and submitting the form) to the person. `document` closes
that gap as a first-class primitive, while keeping the same fail-closed, citation,
and permission discipline as the other four families (`find`, `locate`, `send`,
`check`). It is **not** a generic file editor: it is scoped to public-form
authoring and is one of the heavy permission gates alongside `send`.

## Model-facing surface

The harness registers **one** model-facing tool, `document` (a `GovAPITool`; see
`src/ummaya/tools/documents/tool_defs.py` → `build_document_tool_definitions()`).
The five-family canonical name is `document`; there is no separate `subscribe`
family (deprecated). Internally the tool dispatches a request to a pipeline of
operations (`DocumentToolRouter.handle`, `src/ummaya/tools/documents/registry.py`):

| Operation | Purpose | Mutates? |
|---|---|---|
| `inspect` | Detect format, structure, and capability of a source form | No |
| `extract` | Pull text/content from the form | No |
| `form_schema` | Derive the fillable field schema | No |
| `copy_for_edit` | Create a safe **derivative** copy for editing | Writes derivative |
| `apply_fill` | Fill fields with provided values | Writes derivative |
| `apply_style` | Apply style patches to fields | Writes derivative |
| `validate_public_form` | Validate the derivative against public-form rules | No |
| `render` | Render local evidence (e.g. PNG) of a derivative | Reads, emits evidence |
| `save` | Persist/export the derivative | Writes export |

Read and validation operations never require approval; operations that write a
derivative artifact require approval (enforced in
`src/ummaya/tools/documents/permissions.py` —
`write_derivative_artifact` ⇒ `requires_approval=True`).

## Supported formats

Format handlers live under `src/ummaya/tools/documents/formats/`:

- **HWP / HWPX** — Korean word processor formats (`hwp.py`, `hwpx.py`). Legacy
  binary HWP conversion is bounded by ADR-011.
- **PDF** — AcroForm fill + render (`pdf.py`); PDF/A conformance probes.
- **OOXML** — DOCX/XLSX/PPTX (`ooxml.py`).
- **ODF** — OpenDocument (`odf.py`); LibreOffice derivative bridge bounded by ADR-012.
- **Archive / data / code / text-web / passive** — container and auxiliary handlers
  (`archive.py`, `data_file.py`, `code_file.py`, `text_web.py`, `passive.py`).

Format-engine choices are scorecard-gated (`scorecard.py`) before any dependency
is adopted — `python-hwpx`, `python-docx`, `openpyxl`, `pypdf`, `python-pptx` are
the candidate engines; HWP MCP / pyhwp / hwp.js remain comparative references.

## Permission gate + Evidence

`document` is a **heavy** permission gate (`HEAVY_GATE_PRIMITIVES = {send, document}`
in `src/ummaya/primitives/__init__.py`). Authoring stops for an explicit in-session
approval before any write/fill/render is committed; the TUI surfaces an approval
review (v0.2.5: "surface document approval review" + "preserve issued document
approval tokens"). This reuses CC's canonical `<PermissionRequest>` pipeline — no
UMMAYA-invented permission class.

Authoring is also gated on **Evidence Fabric v2** coverage. Every generated
derivative emits a joinable `DocumentEvidenceRecord`
(`src/ummaya/evidence/document_harness.py`), and the harness scenario lives at
`evidence/scenarios/document_harness_v1.yaml`. See
[`design/verification-fabric-v2.md`](./verification-fabric-v2.md) for how these
records join by `correlation_id` / `frame_hash`.

## Artifact store

Derivatives never touch web/public roots. The artifact store
(`src/ummaya/tools/documents/artifact_store.py`,
`DEFAULT_ARTIFACT_ROOT = ~/.ummaya/document_artifacts/<session_id>/`) is path-escape
guarded (`ArtifactStoreSecurityError`) and partitions work into `sources/`,
`working/`, `renders/`, `reports/`, and `exports/`. Source documents the citizen
brings in are kept separate from the fillable derivative the agent produces.

## Where it sits in the harness

- **L1-B Tool System** — registered into `ToolRegistry` at boot like any adapter,
  but backed by the documents subsystem rather than a single REST endpoint.
- **L1-C Main-Verb Abstraction** — the fifth active primitive family
  (`find`, `locate`, `send`, `check`, `document`).
- **Routing** — the modernized route-selection layer
  (`src/ummaya/tools/routing/`) decides when a citizen utterance is a document
  task versus a public-data read.

See [`docs/api/README.md`](../api/README.md) for the catalog entry and
[`AGENTS.md` § L1 pillars](../../AGENTS.md) for the canonical statement.
