# Parallel Evaluation Plan: Public AX Document Harness

Date: 2026-06-01

## Parallelization Decision

The current implementation state supports parallel work only when write sets are disjoint. The document harness is intentionally engine-backed: UMMAYA owns tool contracts, immutable artifact lineage, patch ordering, validation, evidence, and promotion gates; promoted engines own file-format parsing and mutation.

## Dispatch Tree

```text
Lead local lane:
  - Fix package exports, formatting, static checks, and integration review.
  - Own shared package surface and final loop evaluation.

Worker US3 validation lane:
  - Own baselines.py, validate.py, public-form validator tests, and baseline fixtures.
  - Do not touch ToolRegistry or render/evidence integration.

Worker US6 candidate-evaluation lane:
  - Own evaluation.py, candidate fixtures, dependency/license gate tests, and candidate notes.
  - Avoid capability.py/scorecard.py unless a blocker requires it.

Research sidecar lane:
  - Produce source-to-criterion mapping from current primary/upstream sources.
  - No file edits.

Deferred until US3 stabilizes:
  - US4 render/re-read/evidence, because it depends on validate.py readiness state.
  - US5 ToolRegistry integration, because it depends on US1-US4 service contracts.
```

## Evaluation Criteria

| ID | Criterion | Gate Type | Source Mapping | Harness Impact |
|----|-----------|-----------|----------------|----------------|
| C1 | Standards-valid output | Hard gate | KS X 6101/OWPML for HWPX; ECMA-376/OOXML; PDF 2.0/AcroForm semantics | Produced files must validate against the relevant format/container baseline before promotion. |
| C2 | Non-destructive round trip | Hard gate for edit engines; weighted for read-only | Format standards plus fixture round trips | Open -> inspect/edit -> save must preserve unknown parts, relationships, styles, metadata, embedded objects, and unsupported features unless explicitly rejected. |
| C3 | Structured extraction | Weighted | python-docx, openpyxl, python-pptx, pypdf, and HWPX engine surfaces | Engines should expose stable, machine-addressable objects with provenance: sections, paragraphs, runs, tables, cells, sheets, slides, fields, annotations, and metadata. |
| C4 | Controlled mutation | Hard gate | HWPX engine patterns plus UMMAYA patch model | Edits must be schema-aware, diffable, atomic, and fail closed on ambiguous selectors or unsupported constructs. |
| C5 | LLM tool contract | Hard gate | MCP tool `outputSchema`, structured content, and resource-link concepts | Every model-visible operation must have narrow input schema, structured output, validation errors, and replayable evidence. |
| C6 | File-ingest safety | Hard gate | OWASP File Upload Cheat Sheet; parser security notes | Allowlisted extensions, MIME/signature checks, generated filenames, size/decompression limits, XML/ZIP bomb protection, and isolated storage are mandatory. |
| C7 | Unsupported/unsafe feature policy | Hard gate | OWASP guidance, pypdf security/robustness docs, format-specific safety constraints | Encrypted files, macros, external links, JavaScript, dynamic forms, malformed packages, and partial parser support must be detected and typed as blocked. |
| C8 | Format-specific form/data fidelity | Weighted; hard for workflows depending on the feature | KS X 6101, ECMA-376, PDF AcroForm, upstream engine docs | HWPX controls, OOXML content controls/forms, formulas, charts, comments, notes, media, and AcroForm fields are either fixture-proven or explicitly unsupported. |
| C9 | Scale and resource behavior | Weighted; hard for public upload paths | openpyxl optimized modes, pypdf safety limits, UMMAYA performance budget | Large files must have predictable memory/time behavior and configurable parser limits. |
| C10 | Headless/cross-platform operation | Hard gate | Upstream engine runtime docs and UMMAYA CI requirements | Runtime cannot require proprietary GUI automation and must work headlessly on macOS/Linux-style CI paths under pinned versions. |
| C11 | Supply-chain and maintenance posture | Weighted; hard if license or security blocks use | Upstream repositories, licenses, release posture, security policies | Licenses must be compatible, upstream must be maintainable, and runtime dependencies need pinning/provenance strategy. |
| C12 | Public corpus utility boundary | Weighted only | data.go.kr government document AI learning-data service | The corpus can support semantic/structural metrics, but cannot be sole proof of official submission-form layout conformance. |

## Loop Evaluation Rule

Each capability promotion must run this loop until the decision is stable:

```text
1. Source authority check:
   Reject unsupported format claims that cannot map to KS X 6101, ECMA-376, PDF form semantics, or checked-in UMMAYA baselines.

2. Harness contract check:
   Reject operations that cannot be represented as strict typed tool input, strict typed output, and a typed blocked result.

3. Security check:
   Reject files or engines that require unsafe execution, live network fetches, public-root storage, macro execution, or source mutation.

4. Fixture round-trip:
   Run inspect -> copy -> patch -> render/re-read -> validate -> save on local fixtures only.

5. Scorecard:
   Apply C1-C12 and the 100-point scorecard. Write promotion requires >= 85 plus all hard gates. Read-only promotion requires >= 75 plus security hard gates.

6. Self-evaluation:
   Compare expected values, protected structure, style anchors, render evidence, blocked reasons, and evidence linkage. If any hard gate fails, downgrade to blocked or read-only.

7. Decision persistence:
   Record promoted, rejected, and deferred candidates with source URLs, fixture evidence, and issue references.
```

## Parallel Safety Score

| Work Unit | Parallel Score | Reason |
|-----------|----------------|--------|
| US3 validation | High | New validation/baseline files; no ToolRegistry dependency. |
| US6 candidate evaluation | High | New evaluation runner and fixtures; can avoid shared model edits initially. |
| US4 render/re-read/evidence | Medium | Can start with tests, but implementation likely touches validate.py and diff.py after US3. |
| US5 ToolRegistry | Low | Depends on stable service contracts from US1-US4 and touches model-facing registry boot path. |
| Polish CI/privacy/performance tests | Medium | Test files are independent, but full assertions depend on final service names. |

## Reference URLs

- KS X 6101 OWPML/HWPX standard listing: https://www.kssn.net/search/stddetail.do?itemNo=K001010149626
- ECMA-376 Office Open XML: https://ecma-international.org/publications-and-standards/standards/ecma-376/
- MCP tools structured output: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- data.go.kr government document AI learning-data service: https://www.data.go.kr/data/15125451/openapi.do
- python-hwpx: https://github.com/airmang/python-hwpx
- python-hwpx PyPI provenance: https://pypi.org/project/python-hwpx/
- hwpx-mcp: https://github.com/Dayoooun/hwpx-mcp
- HwpForge MCP reference: https://github.com/ai-screams/HwpForge
- python-docx styles: https://python-docx.readthedocs.io/en/stable/user/styles-using.html
- openpyxl styles: https://openpyxl.readthedocs.io/en/3.0/styles.html
- openpyxl print settings: https://openpyxl.pages.heptapod.net/openpyxl/print_settings.html
- openpyxl optimized modes: https://openpyxl.readthedocs.io/en/stable/optimized.html
- pypdf forms: https://pypdf.readthedocs.io/en/5.4.0/user/forms.html
- pypdf security: https://pypdf.readthedocs.io/en/stable/user/security.html
- pypdf robustness: https://pypdf.readthedocs.io/en/stable/user/robustness.html
- python-pptx text: https://python-pptx.readthedocs.io/en/stable/user/text.html
