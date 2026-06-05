# HWP Promotion Deep Research

Date: 2026-06-03

## Local Anchors

- `docs/vision.md`: UMMAYA is a Claude Code-style harness with public-service
  tools below the tool-loop boundary.
- `docs/requirements/ummaya-migration-tree.md`: public-document harness belongs
  to L1-B tool system and L1-C primitive abstraction.
- `.references/claude-code-sourcemap/restored-src/`: reference for tool-loop
  rendering and fail-closed behavior, not for Korean document engines.
- `src/ummaya/tools/documents/formats/hwp.py`: the static HWP adapter remains
  known-only, while `UnhwpReadOnlyInspectionEngine` is the promoted runtime
  read engine.
- `src/ummaya/tools/documents/engines.py`: default promoted engines register
  HWPX, HWP read-only, DOCX, XLSX, PPTX, and PDF.
- `src/ummaya/tools/documents/registry.py`: `inspect/extract` can work with a
  promoted inspection adapter; `fill/style/save` require a mutation-capable
  engine and working derivative.
- `src/ummaya/tools/documents/models.py`: `FormatCapabilityProfile` currently
  rejects `DocumentFormat.hwp` with `supports_write=True`.
- `.evidence/document-fixtures/public-ax-samples/`: copied public AX HWP/HWPX
  fixtures used as local, offline promotion evidence.

## 2026 External Evidence

| Source | Current Signal | HWP Promotion Impact |
| --- | --- | --- |
| OpenHWP, <https://github.com/openhwp/openhwp> | Rust workspace with `hwp` for HWP 5.0 binary read, `hwpx` for HWPX read/write, IR for HWP/HWPX conversion, MIT license. README support table lists HWP 5.0 read only and HWPX read/write. | Best permissive architecture source for HWP read and HWP-to-IR/HWPX conversion. Not evidence for direct HWP binary write. Local fixture metadata currently says Apache-2.0 and must be corrected to MIT before implementation. |
| HwpForge, <https://github.com/ai-screams/HwpForge> | Rust HWPX programmatic control with Markdown/HWPX, JSON round-trip, MCP tooling, dual MIT/Apache licensing. HWP5 path is read/audit/re-emission/convert-oriented. | Strongest AI-agent-shaped reference for HWPX derivative authoring and MCP-style structured tooling. HWP5 is useful as HWP-to-HWPX audit/convert path, not as direct HWP write proof. |
| rhwp, <https://github.com/edwardkim/rhwp> | Rust/WASM HWP/HWPX viewer/editor, MIT, with parser -> document model -> edit operations -> render pipeline -> SVG/Canvas architecture. `@rhwp/core` 0.7.13 is already in UMMAYA dependencies for HWPX SVG evidence. | Strong render/model reference. Already adopted narrowly for HWPX render evidence. For HWP promotion, use as comparative render evidence before adopting as an HWP mutation engine. |
| unhwp, <https://github.com/iyulab/unhwp> | Rust MIT extractor for HWP 5.0 and HWPX into Markdown, plain text, JSON, with metadata, assets, streaming API, and FFI bindings. | Good read/extract candidate. It does not solve form-safe HWP authoring; it can improve LLM-readable extraction and table/image evidence. |
| pyhwp, <https://github.com/mete0r/pyhwp> and <https://pyhwp.readthedocs.io/en/latest/hwp5.html> | Python HWP v5 parser/processor with internal stream extraction and experimental ODT/plain-text conversion; AGPL-3.0 found. Docs model HWP5 as OLE2 structured storage. | Keep as comparative local parser evidence only. AGPL makes it unsuitable for an Apache-2.0 runtime dependency without a separate legal/ADR decision. Local public AX fixtures already show pyhwp text extraction fails or degrades on several table-heavy HWP samples. |
| 2026 public-sector HWPX transition reporting | The National AI Strategy Committee/MOIS/MCST transition direction restricts HWP attachment in public systems and pushes HWPX because HWP is closed and AI-unfriendly; local reports also note ChatGPT-level HWP/HWPX read support as a user expectation. | UMMAYA should support reading `.hwp` because users still have legacy files, but authoring should converge on HWPX derivatives unless direct binary HWP gates become strong. |

## Candidate Scorecard

Scoring weights: extraction fidelity 20, write fidelity 20, style/layout control
15, deterministic round-trip 15, public-form validation 15, security/privacy 10,
license/maintenance/usability 5.

| Candidate | Score | Decision | Rationale |
| --- | ---: | --- | --- |
| Keep HWP as known-only blocked format | 71 | Supersede | Honest but insufficient for user expectation; blocks even read/extract workflows. |
| Promote `pyhwp` read runtime | 48 | Reject | AGPL gate fails and real table-heavy public fixtures degrade. Useful only as comparative evidence. |
| Promote `OpenHWP-read-only` as HWP inspection engine | 86 | Defer runtime, retain as Stage 2/IR candidate | Permissive, native HWP5 parser, explicit read support, IR direction. Runtime bridge packaging still needs proof. |
| Promote `unhwp-read-only` extraction | 87 | Adopt for Stage 1 read runtime | Strong text/Markdown/JSON extraction, MIT license, PyPI Python binding, and successful extraction from all copied local public AX HWP fixtures. It does not solve form-safe HWP authoring. |
| Promote `HwpForge HWP5 -> HWPX` derivative path | 88 | Adopt for Stage 2 after Stage 1 read gate | Most aligned with LLM harness and HWPX authoring. HWP5 public surface must pass fixture evidence before model-visible use. |
| Promote `rhwp` HWP render/edit directly | 78 | Defer | Strong ecosystem signal, but UMMAYA currently uses only `@rhwp/core` render evidence for HWPX. HWP mutation requires separate dependency, API, and fixture gates. |
| Hand-roll HWP binary mutation | 24 | Reject | High corruption risk, no public-form fidelity proof, and violates root-cause/fallback rules. |

## Final Verdict

HWP can be promoted, but not as direct binary write.

The correct promotion is staged:

1. Stage 1: `DocumentFormat.hwp` promoted for `inspect/extract` only through a
   local `unhwp`-backed read engine.
2. Stage 2: `.hwp` authoring requests create an explicit HWPX working derivative
   using OpenHWP/HwpForge-style HWP-to-IR/HWPX conversion, then reuse the
   existing HWPX fill/render/reread path. The output format is `.hwpx`; the
   original `.hwp` remains immutable.
3. Stage 3: direct `.hwp` binary write remains blocked until a permissive OSS
   engine passes read/write/render/reread/public-form gates on real Korean public
   fixtures. No current source justifies enabling this now.

This matches the 2026 public-sector direction: legacy `.hwp` must be readable for
continuity, while AI-friendly authoring should converge on `.hwpx`.

## Proposed Runtime Contract

```python
class HwpReadOnlyInspectionEngine:
    document_format = DocumentFormat.hwp
    engine_id = "unhwp-read-only"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        ...


class HwpToHwpxDerivativeEngine:
    source_format = DocumentFormat.hwp
    output_format = DocumentFormat.hwpx
    engine_id = "hwpforge-or-openhwp-hwp5-to-hwpx"

    def convert_for_edit(self, source: DocumentArtifact) -> DocumentArtifact:
        ...
```

Model-visible behavior:

- `document(operation="inspect", *.hwp)` -> OK if the read engine passes gates.
- `document(operation="fill", *.hwp)` -> creates a HWPX working derivative only
  when conversion evidence passes. The result must say that the editable output is
  a converted HWPX derivative.
- `document(operation="save", *.hwp as hwp)` -> blocked until direct HWP write
  gates pass.
- `document_apply_fill` must never mutate original HWP bytes.

## Promotion Gates

Hard gates:

1. License gate: permissive license verified in the current upstream repository.
2. Local-only gate: no external document upload, no government live call, no
   browser auto-open, no CI live network.
3. Read correctness gate: real public AX HWP fixtures produce non-empty
   paragraphs and table/cell anchors where table-heavy source exists.
4. Corrupt/encrypted gate: corrupt HWP, encrypted HWP without password, and
   malformed OLE containers fail closed with typed blocked reasons.
5. Schema gate: extraction maps into `DocumentExtraction` without `Any` or
   untyped metadata-only fallback.
6. Conversion lineage gate: HWP-to-HWPX derivatives record source artifact id,
   source SHA-256, conversion engine id, output SHA-256, and format lineage.
7. Render/reread gate: converted HWPX derivative renders through the existing
   `rhwp-node-wasm` SVG path and rereads into comparable fields/tables.
8. TUI gate: user sees CC-style progress, tool call, changed fields, and final
   response; HWP conversion metadata is not presented as the main visual diff.

Promotion thresholds:

- Read-only HWP promotion: score >= 75 and all hard gates pass.
- HWP-to-HWPX editable derivative: score >= 85 and render/reread gates pass.
- Direct HWP binary write: score >= 95, direct mutation round-trip on real public
  fixtures, and an ADR explicitly changes the current write boundary.

## Implementation Checkpoints

1. Correct stale candidate metadata:
   - Update `OpenHWP-read-only` license from Apache-2.0 to MIT in the fixture.
   - Add `unhwp-read-only` and `HwpForge-hwp5-to-hwpx` candidate profiles.
2. Add tests first:
   - HWP inspection is blocked before engine injection.
   - Injected HWP read engine promotes `inspect/extract` only.
   - HWP fill remains blocked without conversion.
   - HWP fill with conversion produces HWPX derivative and never writes HWP.
3. Add `HwpReadOnlyInspectionEngine` behind a narrow CLI/Rust bridge:
   - Use `unhwp` as the default local read-only Python binding after fixture
     extraction evidence.
   - Keep OpenHWP as the preferred future IR/conversion reference.
   - Keep pyhwp only as oracle evidence.
4. Add `DocumentConversionEngine` registry:
   - `source_format -> output_format`, separate from mutation engines.
   - `copy_for_edit` can route HWP source to HWPX derivative only when conversion
     profile is promoted.
5. Extend artifact lineage:
   - `source_hwp -> converted_hwpx_working -> derivative_hwpx`.
6. Extend TUI document card:
   - Show the same inline changed-field diff after the HWPX derivative mutation.
   - Show one concise line: `Converted HWP to editable HWPX derivative`.
7. Evidence matrix:
   - Public AX four `.hwp` samples.
   - At least one clean small HWP fixture.
   - Corrupt CFB fixture.
   - Encrypted HWP fixture if available.
   - Converted HWPX render/reread artifact.

## Development Decision

Start with Stage 1 and Stage 2. Do not enable Stage 3.

The next development loop should be:

1. Add/repair candidate profiles and tests.
2. Build the conversion registry skeleton without a real converter.
3. Inject a fake promoted HWP conversion engine in tests to validate lineage and
   primitive behavior.
4. Add the real OpenHWP/HwpForge bridge only after the interface is fail-closed.
5. Run local public AX HWP alpha tests and Evidence Fabric gates.

## Development Loop 1 - Candidate and Conversion Skeleton

Status: implemented as a fail-closed skeleton.

Reference bootstrap:

- UMMAYA thesis/docs: `docs/vision.md` public-document harness reference
  materials and `docs/requirements/ummaya-migration-tree.md` L1-B/L1-C.
- CC restored source: no Korean HWP engine analog is present. CC remains the
  fail-closed tool-loop/result-ordering reference only.
- UMMAYA target files: `capability.py`, `conversion.py`,
  `candidate_profiles.yaml`, and focused document tests.
- External primary sources used in this loop:
  - OpenHWP upstream: HWP 5.0 read, HWPX read/write, IR conversion, MIT license.
  - HwpForge upstream and npm registry: MCP-shaped HWPX tooling, JSON/patch
    operations, `@hwpforge/mcp` 0.5.2 as a tiny dual-license package candidate.
  - `unhwp` upstream: MIT HWP/HWPX extractor to Markdown/Text/JSON with table
    and asset preservation.
  - `pyhwp` upstream: AGPL parser/processor retained only as comparative
    evidence.
  - 2026 agent/tool-use research signal: MCP-Bench/MCP-Atlas-style benchmarks
    support explicit tool/operation contracts and execution-grounded evaluation;
    document-delegation corruption reports reinforce deterministic conversion,
    reread, and render gates instead of raw LLM byte editing.

Implemented:

- Added `convert` as a first-class candidate promotion operation.
- Kept direct HWP `write` globally blocked.
- Added `DocumentConversionRegistry` and `DocumentConversionEngine` protocol
  mirroring the existing engine-registry registration/duplicate/require pattern.
- Corrected `OpenHWP-read-only` license metadata to MIT.
- Added `unhwp-read-only` as comparative HWP read/extract oracle.
- Added `HwpForge-hwp5-to-hwpx` as HWP-to-HWPX derivative conversion candidate.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py::test_hwp_read_only_candidate_promotes_read_and_blocks_write -q`
    failed because the HwpForge conversion candidate did not exist.
  - `uv run pytest tests/tools/documents/test_conversion_registry.py -q`
    failed because `ummaya.tools.documents.conversion` did not exist.
- GREEN:
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py::test_hwp_read_only_candidate_promotes_read_and_blocks_write -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_conversion_registry.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_conversion_registry.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_capability_profiles.py -q`
    -> pass.

Remaining gates:

- No real OpenHWP/HwpForge runtime dependency has been added.
- No `.hwp` user-facing write path is enabled.
- Next loop should wire fake conversion into `DocumentToolRuntime.copy_for_edit`
  tests first, then add a real local bridge only after an ADR/dependency gate.

## Development Loop 2 - Runtime Copy Boundary

Status: implemented with fake-engine TDD and fail-closed runtime wiring.

Reference bootstrap:

- UMMAYA thesis/docs: same as loop 1; document work remains deterministic tool
  execution, not raw LLM byte authoring.
- CC restored source: no Korean HWP conversion analog is present. The adopted
  CC constraint is result-loop fail-closed behavior: tool success is not emitted
  when the required execution boundary is absent.
- UMMAYA target files: `registry.py` runtime/session-pool injection and
  `test_builtin_hwp_adapter.py` HWP copy tests.
- 2026-current sources refreshed in this loop:
  - HwpForge MCP package docs (`hwpforge-bindings-mcp` 0.6.0) show the relevant
    shape as explicit tool operations, not hidden UI/browser fallbacks.
  - OpenHWP upstream keeps HWP/HWPX/IR conversion as separate modules, matching
    a narrow conversion boundary instead of direct HWP mutation.
  - MCP-Atlas and ComplexMCP 2026 benchmark papers reinforce that agents must be
    evaluated on natural prompts, concrete tool execution, multi-step state, and
    deterministic tool outputs; this supports a tested `copy_for_edit`
    conversion gate before mutation.

Implemented:

- Added `conversion_registry` injection to `DocumentToolRuntime`,
  `_SessionDocumentRuntimePool`, and `register_document_tools`.
- Changed `copy_for_edit` for HWP sources:
  - without a promoted HWP-to-HWPX conversion engine, returns blocked
    `unsupported_operation`;
  - with a promoted conversion engine, writes a `working_copy` HWPX derivative
    with `application/owpml` MIME and records the HWP source as parent;
  - source HWP bytes remain unchanged.
- Preserved generic same-format `copy_for_edit` for non-HWP formats.
- Preserved default HWP direct-write block because no default HWP read/conversion
  engine is registered.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py::test_hwp_copy_for_edit_without_conversion_engine_is_blocked tests/tools/documents/test_builtin_hwp_adapter.py::test_hwp_copy_for_edit_uses_promoted_conversion_to_hwpx_derivative -q`
    failed because HWP was raw-copied and `DocumentToolRuntime` did not accept
    `conversion_registry`.
- GREEN:
  - same focused two-test command -> pass.
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_candidate_evaluation.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_document_tool_flow.py -q` -> pass.

Remaining gates:

- No real HWP-to-HWPX converter dependency has been added.
- Converted HWPX render/reread is validated only through a fake conversion
  payload; real HwpForge/OpenHWP bridge requires ADR, dependency-size/license
  check, local-only execution proof, and fixture evidence.
- Next loop should add the dependency/ADR gate and, if approved by the gate,
  implement the real bridge behind `DocumentConversionEngine`.

## Development Loop 3 - ADR-Backed Runtime Bridge Gate

Status: implemented as a stricter candidate/dependency gate. No real HWP bridge
dependency was added.

Reference bootstrap:

- UMMAYA thesis/docs: `docs/vision.md` keeps document work as deterministic tool
  execution under the national-infrastructure harness. `spec.md` FR-005 and
  FR-006 keep direct HWP binary authoring blocked.
- CC restored source: no HWP bridge analog exists. The relevant CC parity rule is
  that tool execution cannot claim success when permission or execution
  prerequisites are absent.
- UMMAYA target files: `evaluation.py`, `candidate_profiles.yaml`,
  `ADR-011-hwp-conversion-bridge.md`, and focused candidate/dependency tests.
- 2026-current sources refreshed:
  - HwpForge documents HWPX read/write, Markdown bridge, JSON round-trip, MCP
    tooling, and HWP5 CLI audit/convert helpers under a dual MIT OR Apache-2.0
    license.
  - OpenHWP documents HWP 5.0 read, HWPX read/write, and HWP-to-HWPX IR
    conversion under MIT.
  - unhwp remains a strong HWP/HWPX extraction oracle but not an editable
    derivative runtime.
  - MCP-Atlas and ComplexMCP 2026 reinforce real tool execution, multi-step
    state, deterministic scoring, and non-mock validation before model-visible
    promotion.

Scorecard decision:

| Candidate | Score signal | Runtime gate | Decision |
| --- | ---: | --- | --- |
| OpenHWP-read-only | 75, read threshold met | defer | Keep best read bridge candidate, but no runtime promotion until ADR-011 gates pass. |
| HwpForge-hwp5-to-hwpx | 92, conversion threshold met | defer | Keep best HWP-to-HWPX derivative candidate, but no runtime promotion until ADR-011 gates pass. |
| unhwp-read-only | 75, read threshold met | pass, read-only | Promoted in Loop 5 as the default local HWP inspection runtime; still not a mutation or conversion engine. |
| pyhwp-read-only | 75, read threshold met | license fail | Reject as runtime dependency; AGPL/comparative only. |

Implemented:

- Added ADR-gated dependency metadata to candidate profiles:
  - `requires_adr`
  - `adr_ref`
  - `permission_boundary`
  - `local_only_execution`
  - `package_ref`
- Added validation that ADR-required document bridges must:
  - cite `docs/adr/ADR-*.md`;
  - use `document_primitive_only` permission boundary;
  - remain local-only when dependency gate is `pass`;
  - declare an exact package reference.
- Split dependency reasons so `defer` is no longer reported as generic failure:
  - `dependency_gate_failed`
  - `dependency_gate_deferred`
  - `license_gate_failed`
  - `license_gate_deferred`
- Changed OpenHWP and HwpForge HWP bridge profiles from runtime-promoted to
  deferred. They still show threshold success reasons, but final
  `promoted=False` until ADR-011 bridge evidence is complete.
- Added `docs/adr/ADR-011-hwp-conversion-bridge.md` to define the real bridge
  promotion boundary.

Verification:

- RED:
  - focused candidate/dependency tests failed because OpenHWP/HwpForge were still
    promoted and dependency metadata rejected ADR/permission/local-only fields.
- GREEN:
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py::test_hwp_candidates_score_but_defer_runtime_bridge_until_adr_gate_passes tests/tools/documents/test_dependency_gate.py::test_hwp_bridge_candidates_require_adr_and_document_permission_boundary tests/tools/documents/test_dependency_gate.py::test_candidate_profile_requires_adr_for_passed_runtime_bridge_gate tests/tools/documents/test_dependency_gate.py::test_candidate_profile_rejects_remote_runtime_bridge_dependency -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.

Remaining gates:

- No real package or bridge is installed.
- Next loop can implement a dry-run bridge contract test that shells out to a
  pinned local CLI only when the dependency fixture is present; otherwise it must
  stay skipped or blocked, never fallback-success.
- Real promotion still requires package lock review, public AX HWP fixture
  conversion, HWPX detection, HWPX inspect/render/reread, source SHA immutability,
  and typed corrupt/encrypted failure evidence.

## Development Loop 4 - Fail-Closed Local CLI Bridge Contract

Status: implemented. No real HWP converter dependency was installed or promoted.

Reference bootstrap:

- UMMAYA thesis/docs: the bridge remains a local document primitive execution
  boundary, not a general shell/tool escape hatch.
- CC restored source: the migrated shape follows CC's visible tool execution
  rule: if an execution precondition is missing or output validation fails, the
  tool result must be blocked/failed instead of silently falling back.
- 2026-current sources refreshed:
  - HwpForge is still the best conversion-shaped candidate because it exposes
    HWP/HWPX CLI/MCP surfaces and HWPX write-oriented flows under permissive
    licensing.
  - OpenHWP remains the strongest Rust read/IR candidate for future deterministic
    HWP parsing, but runtime adoption still needs adapter evidence before
    write-path promotion.
  - MCP-Atlas and ComplexMCP reinforce execution-level scoring: the bridge must
    validate tool parameters, run state, output artifacts, and failure modes
    rather than judging only final text.

Scorecard decision:

| Candidate shape | Fit | Decision |
| --- | ---: | --- |
| Built-in fake converter | Low | Retain only as a narrow unit double; not enough for runtime promotion evidence. |
| Pinned local CLI bridge | High | Implement now. It creates a reusable dry-run contract for HwpForge/OpenHWP-style converters without adding the package yet. |
| Bundled default converter | Deferred | Do not add until ADR-011 lock/license/size/local-only gates pass. |

Implemented:

- Added `LocalCliDocumentConversionEngine`:
  - requires an absolute, existing, executable local path;
  - requires argv placeholders for `{source}` and `{output}`;
  - executes with `shell=False`, stdin closed, bounded timeout, and isolated
    temporary output directory;
  - rejects non-zero exit, timeout, missing output, empty output, and source-file
    mutation;
  - validates HWPX output as a package with `mimetype=application/owpml`,
    `Contents/header.xml`, and at least one `Contents/section*.xml`.
- Added `DocumentConversionEngineError` so runtime conversion validation failures
  remain fail-closed through `BlockedReason.validation_failed`.
- Added runtime evidence test that:
  - inspects a source HWP;
  - converts it through the local CLI bridge into an HWPX working derivative;
  - rereads the derivative through the real `HwpXPackageTextEngine`;
  - confirms the source HWP bytes are unchanged.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_conversion_registry.py -q`
    failed on missing `DocumentConversionEngineError` and
    `LocalCliDocumentConversionEngine`.
- GREEN:
  - `uv run pytest tests/tools/documents/test_conversion_registry.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents -q` -> pass.
  - `uv run pytest tests/evidence tests/ci -q` -> pass.
  - `uv run ruff check src/ummaya/tools/documents/conversion.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py`
    -> pass.
  - `uv run mypy src/ummaya/tools/documents/conversion.py` -> pass.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass.
  - `git diff --check` -> pass.

Remaining gates:

- Real HWP package adoption is still deferred.
- Next loop should wire a disabled-by-default bridge profile that can be
  activated only by an explicit local executable path/env/config entry, then run
  copied public-AX HWP fixtures through convert -> HWPX inspect -> render/reread
  evidence.

## Development Loop 5 - Read-Only HWP Runtime Promotion

Status: implemented for inspection/extraction only. HWP direct write and real
HWP-to-HWPX authoring remain blocked.

Reference bootstrap:

- UMMAYA thesis/docs: HWP work remains one `document` primitive below the public
  AX tool loop; source document bytes are immutable.
- ADR-011: read-only HWP inspection may pass a smaller gate set than conversion,
  but conversion/write still require the full HWPX derivative evidence contract.
- Current upstream evidence:
  - `unhwp` provides HWP 5.0/HWPX extraction to Markdown, text, JSON, metadata,
    and assets through Rust plus Python bindings.
  - OpenHWP remains the stronger future IR/conversion reference because it
    separates HWP read, HWPX read/write, and HWP-to-HWPX IR.
  - HwpForge remains the more LLM/MCP-shaped HWPX derivative authoring reference.

Empirical gate:

- `uv run --with unhwp==0.5.0 python ...` extracted text from all copied local
  public AX HWP fixtures in `.evidence/document-fixtures/public-ax-samples/`.
- The extracted samples included:
  - `2. [서식1~서식5] 2026년 경기도 공공데이터·AI 활용 창업경진대회 제출 서류.hwp`
  - `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_개인정보 수집·이용 동의서.hwp`
  - `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_아이디어 기획서 양식.hwp`
  - `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_참가서약서.hwp`

Implemented:

- Added `unhwp>=0.5.0,<0.6` as a core runtime dependency with an inline spec
  justification in `pyproject.toml`.
- Added `UnhwpReadOnlyInspectionEngine`:
  - exposes `DocumentFormat.hwp` and `engine_id="unhwp-read-only"`;
  - parses HWP through the local `unhwp` Python binding;
  - maps extracted lines into `ParagraphBlock` anchors;
  - records `section_count`, `paragraph_count`, `image_count`, text hash,
    markdown hash, and `unhwp` package version;
  - emits a warning that HWP inspection is read-only and authoring requires a
    promoted HWPX derivative bridge.
- Registered the engine in `build_default_document_engine_registry()`.
- Kept the static HWP adapter known-only so classification and runtime promotion
  remain separate boundaries.
- Added an early runtime mutation guard: direct `document(fill/style/save)` on
  `.hwp` returns a typed `unsupported_operation` and creates no working or
  derivative artifacts.
- Updated candidate metadata so `unhwp-read-only` is an ADR-cited, local-only,
  document-primitive-scoped runtime dependency.

Verification:

- RED:
  - `test_default_runtime_inspects_public_ax_hwp_with_unhwp_read_engine` first
    failed because the extracted paragraph collection was shaped as a tuple and
    the broad parse guard masked the schema error as an `unhwp` parse error.
- GREEN:
  - Narrowed the parse guard and mapped paragraphs as a list.
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run pytest tests/agents/test_no_new_deps.py tests/permissions/test_zero_new_dependencies.py tests/ipc/test_no_new_runtime_deps.py -q`
    -> pass.
  - `uv run pytest tests/tools/documents -q`
    -> pass.
  - `uv run pytest tests/evidence tests/ci -q`
    -> pass.
  - `uv run ruff check src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/engines.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/agents/test_no_new_deps.py tests/permissions/test_zero_new_dependencies.py tests/ipc/test_no_new_runtime_deps.py`
    -> pass.
  - `uv run ruff format --check src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/engines.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py tests/agents/test_no_new_deps.py tests/permissions/test_zero_new_dependencies.py tests/ipc/test_no_new_runtime_deps.py`
    -> pass.
  - `uv run mypy src/ummaya/tools/documents/formats/hwp.py src/ummaya/tools/documents/engines.py src/ummaya/tools/documents/registry.py`
    -> pass.
  - `git diff --check`
    -> pass.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass; run id `ev-21f5f069-00b4-4af5-919d-0765f549eb09`.

Remaining gates:

- `unhwp-read-only` does not expose table/cell semantic anchors at the level
  needed for autonomous fill planning.
- Real HWP-to-HWPX conversion is still not promoted.
- Direct HWP binary write remains blocked.

## Development Loop 6 - HWP Rich Read IR

Status: implemented for read-only HWP table and field-candidate extraction.
Mutation remains blocked.

Reference bootstrap:

- UMMAYA thesis/docs: HWP remains a document-engine adapter below the single
  `document` primitive. It may improve inspect/extract quality without changing
  the write boundary.
- CC restored source: no HWP/HWPX format engine analog exists. CC remains the
  fail-closed tool-result reference only.
- Current upstream evidence:
  - `unhwp` states that it preserves headings, lists, tables, inline formatting,
    images, and structured Markdown/JSON outputs for HWP/HWPX.
  - OpenHWP remains the preferred future HWP-to-IR/HWPX conversion architecture
    reference.
  - HwpForge remains the strongest LLM/MCP-shaped HWPX authoring reference, not
    a direct HWP mutation proof.

Empirical gate:

- Real copied public AX HWP fixtures showed `unhwp.markdown` contains Markdown
  pipe tables.
- The contest proposal template fixture exposes clear table rows such as
  `팀명 -> UMMAYA` and
  `아이디어명 -> 공공데이터와 AX 기술을 활용한 UMMAYA 국가 인프라 에이전트`.

Implemented:

- Added Markdown pipe-table extraction inside `UnhwpReadOnlyInspectionEngine`.
- Mapped tables into `TableBlock`/`TableCell` with stable
  `/hwp/unhwp/table[n]/row[r]/cell[c]` anchors.
- Inferred low-confidence read-only `FormField` candidates from label/value rows.
- Added `table_count` and `field_candidate_count` metadata.
- Kept direct `.hwp` `fill/style/save` blocked.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py::test_unhwp_read_engine_promotes_markdown_tables_and_field_candidates -q`
    failed because HWP extraction returned no tables.
- GREEN:
  - The same test passed after mapping `unhwp.markdown` tables to
    `TableBlock`/`FormField`.
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run ruff check src/ummaya/tools/documents/formats/hwp.py tests/tools/documents/test_builtin_hwp_adapter.py`
    -> pass.
  - `uv run mypy src/ummaya/tools/documents/formats/hwp.py`
    -> pass.
  - `uv run pytest tests/tools/documents -q`
    -> pass.
  - `uv run pytest tests/evidence tests/ci -q`
    -> pass.
  - `git diff --check`
    -> pass.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass; run id `ev-91d2ecec-19a6-4380-ae2c-f062e73ede8a`.

Remaining gates:

- `unhwp` Markdown tables are extraction evidence, not layout-accurate render
  evidence.
- Table/field candidates are read-only and may support autonomous planning, but
  cannot be used as mutation targets until a HWP-to-HWPX derivative bridge passes
  ADR-011.

## Development Loop 7 - Explicit Local HWP Conversion Bridge Wiring

Status: implemented as an opt-in local executable boundary. No converter package
is bundled or silently selected.

Reference bootstrap:

- UMMAYA thesis/docs: document conversion remains under the `document` primitive
  and artifact store, not `workspace_bash`.
- ADR-011: conversion engines must be local-only, explicit, source-immutable,
  HWPX-validating, and fail-closed.
- Current upstream evidence:
  - OpenHWP and HwpForge remain viable bridge candidates, but UMMAYA has not
    pinned either as the default converter.
  - The safest runtime shape is therefore an explicit local executable bridge
    that can host a vetted OpenHWP/HwpForge adapter later without changing the
    `DocumentConversionEngine` contract.

Implemented:

- Added `build_default_document_conversion_registry()`.
- The default registry remains empty unless `UMMAYA_HWP_TO_HWPX_CONVERTER` is
  set.
- When the converter path is set, `UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON` is
  mandatory and must contain explicit `{source}` and `{output}` placeholders.
- Optional configuration:
  - `UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID`
  - `UMMAYA_HWP_TO_HWPX_CONVERTER_TIMEOUT_SECONDS`
- `DocumentToolRuntime` now uses this default builder only when no
  `conversion_registry` is injected.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_explicit_local_hwp_bridge -q`
    failed because the default builder did not exist.
- GREEN:
  - `uv run pytest tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py -q`
    -> pass.
  - `uv run ruff check src/ummaya/tools/documents/conversion.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py`
    -> pass.
  - `uv run ruff format --check src/ummaya/tools/documents/conversion.py src/ummaya/tools/documents/registry.py tests/tools/documents/test_conversion_registry.py tests/tools/documents/test_builtin_hwp_adapter.py`
    -> pass.
  - `uv run mypy src/ummaya/tools/documents/conversion.py src/ummaya/tools/documents/registry.py`
    -> pass.
  - `uv run pytest tests/tools/documents -q`
    -> pass.
  - `uv run pytest tests/evidence tests/ci -q`
    -> pass.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    -> pass; run id `ev-5b389205-1ab0-4301-b0a7-12cf113f6b36`.
  - `git diff --check`
    -> pass.

Remaining gates:

- No actual OpenHWP/HwpForge converter binary is bundled.
- A real converter must still pass public AX HWP fixture conversion,
  source-SHA immutability, HWPX inspect, render, reread, and typed failure gates
  before HWP authoring can be claimed complete.

## Development Loop 8 - Single Primitive HWP Derivative Authoring

Status: implemented for the runtime boundary with an injected promoted
conversion engine. This is not a real-converter promotion.

Reference bootstrap:

- UMMAYA thesis/docs: HWP/HWPX document work remains under the single `document`
  primitive and CC-style tool-loop result boundary.
- CC restored source: no Korean HWP conversion analog is present. The relevant
  parity point is one model-facing tool operation with internal validation,
  mutation, render, and structured result evidence.
- ADR-011: HWP source bytes stay immutable; editing legacy HWP requires a local
  HWP-to-HWPX derivative bridge and HWPX reread/render gates.
- 2026-current sources:
  - OpenHWP documents HWP 5.0 read, HWPX read/write, and an IR direction for
    HWP to HWPX conversion under MIT.
  - HwpForge documents a local CLI/MCP-shaped HWPX authoring stack and an
    HWP5 decode/projection helper crate; it remains the best conversion-shaped
    runtime candidate but is not yet bundled.
  - `unhwp` remains the strongest read-only extractor for HWP/HWPX text,
    Markdown, JSON, tables, and assets; it is not a mutation engine.
  - MCP tool-result guidance and 2026 MCP workflow papers reinforce explicit
    action boundaries, structured failure modes, and deterministic workflow
    execution instead of letting the model manually call inspect/copy/render.

Candidate scorecard:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep top-level `document(fill, *.hwp)` blocked even when a conversion bridge exists | 69 | Supersede | Safe, but prevents the approved single-primitive workflow from using the verified bridge. |
| Let the model call `document_copy_for_edit` manually for HWP | 61 | Reject | Reintroduces primitive/tool confusion and diverges from CC's one edit-operation surface. |
| Convert HWP to HWPX inside `document` before autonomous planning, then mutate/render the HWPX derivative | 94 | Adopt | Preserves source immutability, keeps conversion fail-closed, and lets natural authoring requests use the same one-tool workflow. |
| Directly mutate HWP binary after read extraction | 24 | Reject | No current permissive OSS evidence proves safe direct HWP write fidelity. |

Implemented:

- Removed the unconditional early `DocumentFormat.hwp` block inside
  `DocumentToolRuntime.document`.
- For HWP mutation operations, `document` now calls `copy_for_edit` first.
  - Without a promoted HWP-to-HWPX conversion engine, the result remains blocked
    with the existing typed unsupported-operation boundary.
  - With a promoted conversion engine, the working artifact is a HWPX
    derivative and autonomous fill planning/patch normalization run against the
    HWPX extraction, not the read-only HWP extraction.
- Preserved original HWP source immutability and explicit conversion lineage.
- Broadened the no-converter blocked message to keep the user-facing direct-HWP
  write warning visible at both `document` and `document_copy_for_edit` levels.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py::test_document_primitive_fills_converted_hwp_derivative_through_single_operation -q`
    failed because `document(fill, *.hwp)` returned blocked before using the
    injected conversion registry.
- GREEN:
  - The same test now passes and proves `document` performs conversion,
    autonomous 12->13 week planning, HWPX mutation, render evidence, reread, and
    original HWP byte immutability through one operation.
  - `uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_conversion_registry.py -q`
    passed with 22 HWP/conversion tests.

Remaining gates:

- The conversion engine in the new single-primitive test is still a promoted
  test double. A real OpenHWP/HwpForge/local CLI bridge must still pass public
  AX HWP fixture conversion, HWPX inspect/render/reread, source-SHA immutability,
  and typed failure gates before HWP derivative authoring is complete.

## HwpForge MCP Probe - Not Yet a HWP Converter

Status: evaluated and rejected as an automatic HWP-to-HWPX bridge.

Current package evidence:

- `npm view @hwpforge/mcp version license bin dist.unpackedSize repository.url --json`
  returned version `0.5.2`, license `MIT OR Apache-2.0`, bin
  `hwpforge-mcp`, unpacked size `4375`, repository
  `git+https://github.com/ai-screams/HwpForge.git`.
- `npm search hwpforge --json` showed platform binary packages for macOS
  arm64/x64, Linux arm64/x64, and Windows x64, all at `0.5.2`.
- `cargo search hwpforge` and `cargo search openhwp` could not run in this
  local environment because `cargo` is not installed.

Runtime probe:

```bash
printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ummaya-probe","version":"0.0.0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | npx -y @hwpforge/mcp
```

Observed tool surface:

- `hwpforge_convert`: Markdown -> HWPX.
- `hwpforge_from_json`: JSON -> HWPX.
- `hwpforge_inspect`, `hwpforge_to_json`, `hwpforge_patch`,
  `hwpforge_restyle`, `hwpforge_templates`, `hwpforge_to_md`,
  `hwpforge_validate`: HWPX-centered inspection/edit/validation operations.

Decision:

- Do not auto-register `@hwpforge/mcp` as
  `UMMAYA_HWP_TO_HWPX_CONVERTER`.
- It is useful as a future HWPX authoring/editing backend candidate.
- It does not currently satisfy the real HWP-to-HWPX derivative bridge gate
  because the exposed MCP tools do not accept `.hwp` as a source and do not
  provide a HWP5-to-HWPX conversion operation.
- The next real-converter loop must target either OpenHWP IR/HWPX crates through
  a pinned local binary, or HwpForge's native CLI/crate surface if it exposes a
  HWP5 conversion command outside the MCP tool list.

## Development Loop 9 - HwpForge CLI Conversion Probe Evidence

Status: implemented as a diagnostic Evidence Fabric gate. HWP authoring remains
unpromoted in this local environment because no `hwpforge` CLI binary is
installed or pinned.

Reference bootstrap:

- UMMAYA thesis/docs: the `document` primitive owns HWP mutation and derivative
  creation; `workspace_bash` or an external MCP server must not silently mutate
  documents.
- CC restored source: no Korean HWP conversion analog exists. The parity point
  remains explicit tool-result evidence and no hidden fallback success.
- ADR-011: HWP-to-HWPX conversion needs an explicit local executable, source SHA
  immutability, HWPX derivative validation, render/reread evidence, public AX
  fixture evidence, and typed failures.
- 2026-current sources:
  - HwpForge upstream README and source now expose `convert-hwp5`, `audit-hwp5`,
    and `census-hwp5` in the CLI crate. The command contract is
    `hwpforge --json convert-hwp5 <source.hwp> --output <output.hwpx>`.
  - GitHub latest release is `v0.6.0` with no binary assets, and the CLI crate
    is `publish = false`, so a reproducible local binary requires Git/Cargo
    pinning or a future published binary package.
  - npm still exposes only `@hwpforge/mcp@0.5.2`; the MCP tool list remains
    HWPX-centered and does not provide HWP5-to-HWPX conversion.

Candidate scorecard update:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Auto-register `@hwpforge/mcp` as the converter | 31 | Reject | MCP package is HWPX-centered and cannot satisfy HWP source input. |
| Auto-discover `hwpforge` on PATH and silently register it | 58 | Reject | Would create environment-dependent success and hide missing package/fixture gates. |
| Add explicit `hwpforge` CLI probe evidence without auto-registration | 91 | Adopt | Makes the real bridge state visible in Evidence Fabric while preserving ADR-011 fail-closed behavior. |
| Bundle/build HwpForge CLI immediately from Git | 72 | Defer | Strong candidate, but requires Rust toolchain, lockfile review, artifact-size review, and fixture conversion gates. |

Implemented:

- Added `src/ummaya/tools/documents/hwp_conversion_probe.py`.
  - Reports `configured`, `available`, `missing`, or `misconfigured`.
  - Recommends the exact ADR-compatible env contract:
    `UMMAYA_HWP_TO_HWPX_CONVERTER`,
    `UMMAYA_HWP_TO_HWPX_CONVERTER_ARGS_JSON`,
    `UMMAYA_HWP_TO_HWPX_CONVERTER_ENGINE_ID`, and
    `UMMAYA_HWP_TO_HWPX_CONVERTER_TIMEOUT_SECONDS`.
  - Does not register any converter automatically.
- Added `document_bridge_probe_records` to the Evidence Fabric JSON payload.
  The record carries only candidate/status/reasons/recommended env/evidence
  refs, not document bytes or converted output.
- Updated `tests/fixtures/documents/candidate_profiles.yaml` so
  `HwpForge-hwp5-to-hwpx` points at
  `git:https://github.com/ai-screams/HwpForge.git#v0.6.0:crates/hwpforge-bindings-cli`
  instead of incorrectly using `npm:@hwpforge/mcp@0.5.2` as the conversion
  package reference.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py -q`
    failed because `ummaya.tools.documents.hwp_conversion_probe` did not exist.
  - `uv run pytest tests/tools/documents/test_dependency_gate.py::test_hwp_bridge_candidates_require_adr_and_document_permission_boundary -q`
    failed because the candidate fixture still pointed to `npm:@hwpforge/mcp@0.5.2`.
  - `uv run pytest tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records -q`
    failed because `build_evidence_output_payload()` did not yet expose
    `hwp_bridge_probe_env`.
- GREEN:
  - `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py
    tests/tools/documents/test_candidate_evaluation.py::test_hwp_candidates_score_but_defer_runtime_bridge_until_adr_gate_passes
    tests/tools/documents/test_dependency_gate.py::test_hwp_bridge_candidates_require_adr_and_document_permission_boundary -q`
    passed with 6 tests.
  - `uv run pytest tests/evidence/test_document_harness_evidence.py::test_evidence_cli_payload_includes_document_harness_records
    tests/tools/documents/test_hwp_conversion_probe.py -q` passed with 5 tests.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    produced run id `ev-55186f02-a814-4e83-a6ef-a1f9bda768b8`. Its
    `document_bridge_probe_records[0]` reports
    `status=missing`, `reasons=["hwpforge_cli_not_found"]`, and the recommended
    `hwpforge --json convert-hwp5 {source} --output {output}` env contract.

Remaining gates:

- Install or build a pinned local HwpForge CLI binary, or another permissive
  local converter, before HWP-to-HWPX conversion can be promoted.
- Run the real public AX HWP fixtures through convert -> HWPX inspect ->
  render/reread -> audit -> save evidence.
- Keep direct HWP binary writing blocked.

## Development Loop 10 - hwpxjs HWP-to-HWPX Bridge and Render Gate Failure

Status: partially implemented as a local conversion bridge candidate. HWP
authoring remains unpromoted because the converted public AX HWPX derivative
fails the existing RHWP visual render gate.

Reference bootstrap:

- UMMAYA thesis/docs: HWP source bytes remain immutable; editable work must move
  into a derivative owned by the `document` primitive.
- CC restored source: no HWP engine analog exists. The relevant parity rule is
  that native tool failures stay visible as tool results, not hidden fallback
  success.
- ADR-011: HWP-to-HWPX conversion requires source SHA immutability, valid HWPX
  derivative, render/re-read evidence, public AX fixture evidence, and typed
  failure behavior.
- 2026-current sources:
  - `ssabro/hwpxjs` and `@ssabrojs/hwpxjs@0.4.0` expose a local TypeScript
    parser/converter for HWP 5.0 and HWPX, MIT license, Node.js/browser ESM
    runtime, and CLI command `hwpxjs convert:hwp <file.hwp> <out.hwpx>`.
  - The upstream README reports HWP -> HWPX conversion with tables, images,
    fonts, paragraph/style definitions, and HWPX package writing.
  - OpenHWP/HwpForge remain the stronger long-term Rust IR/HWPX references, but
    `hwpxjs` is the currently installable local CLI candidate that passed real
    conversion probes in this environment.

Candidate scorecard update:

| Candidate | Score | Decision | Reason |
|---|---:|---|---|
| Keep only explicit env bridge | 78 | Supersede for local dev default | Safe but forces every developer to hand-wire a proven installed CLI. |
| Auto-register discovered `hwpxjs` CLI on PATH | 89 | Adopt as candidate bridge | MIT, exact npm pin, local-only CLI, validates HWPX output, and converted all copied public AX HWP fixtures to valid HWPX packages. |
| Claim HWP authoring complete after conversion succeeds | 41 | Reject | Converted HWPX must still render/re-read/save; real fixture render currently fails in RHWP border rendering. |
| Switch to direct HWP write | 19 | Reject | No current source passes direct binary write gates. |

Implemented:

- Added exact npm dependency `@ssabrojs/hwpxjs@0.4.0`.
- Updated `DocumentConversionRegistry` default construction so an executable
  `hwpxjs` on PATH registers `hwpxjs-cli-convert-hwp` with args
  `("convert:hwp", "{source}", "{output}")` and a 120-second timeout.
- Updated HWP bridge probe diagnostics so discovered `hwpxjs` is reported as
  `hwpxjs_cli_found_for_default_registration`, while the probe itself still
  does not mutate registry state.
- Added regression coverage for default registry discovery and probe reporting.
- Added render-gate fail-closed handling: native render bridge exceptions now
  return `status=blocked`, `blocked_reason=validation_failed`,
  `render_passed=False`, and no render artifact records instead of crashing the
  document tool call.

Empirical evidence:

- `npx -y @ssabrojs/hwpxjs@0.4.0 convert:hwp` converted all four copied
  public AX `.hwp` fixtures under
  `.evidence/document-fixtures/public-ax-samples/` into HWPX packages with
  `mimetype=application/owpml` and `Contents/section0.xml`.
- Real top-level `document(operation="save")` alpha on
  `2026년도 AX 아이디어 경진대회_데이터 활용_아이디어 기획 부문_아이디어 기획서 양식.hwp`
  with an explicit `/hwpx/text[1]` patch:
  - converted HWP -> HWPX derivative;
  - applied the structured patch and produced a diff;
  - failed the RHWP render gate with
    `src/renderer/layout/border_rendering.rs:153:23 index out of bounds`;
  - returned `blocked(validation_failed)`;
  - skipped save.
- Natural autonomous fill on the same real HWP fixture still returned
  `needs_input`: the current autonomous planner did not infer a safe fill plan
  from the converted HWP content.

Verification:

- RED:
  - `uv run pytest tests/tools/documents/test_render_and_reread.py::test_render_engine_exception_returns_blocked_result_without_artifacts -q`
    failed because renderer exceptions bubbled out of
    `render_document_evidence()`.
  - `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py::test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry -q`
    failed after the expected reason was tightened from
    `hwpxjs_cli_found_but_not_registered`.
- GREEN:
  - `uv run pytest tests/tools/documents/test_render_and_reread.py::test_render_engine_exception_returns_blocked_result_without_artifacts -q`
    passed.
  - `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py::test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry -q`
    passed.
  - `uv run pytest tests/tools/documents/test_hwp_conversion_probe.py::test_probe_detects_hwpxjs_cli_on_path_without_mutating_registry tests/tools/documents/test_conversion_registry.py::test_default_conversion_registry_registers_discovered_hwpxjs_bridge -q`
    passed.
  - `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`
    produced run id `ev-58ac5dac-d2ea-4329-a13f-b4b52425e05c` with
    `document_bridge_probe_records[0]` reporting
    `candidate_id=hwpxjs-cli-convert-hwp`, `status=available`, and
    `hwpxjs_cli_found_for_default_registration`.

Remaining gates:

- HWP-to-HWPX derivative authoring cannot be counted complete until converted
  public AX HWPX derivatives render through a promoted renderer, re-read
  correctly, validate, and save.
- RHWP render panic must be root-caused against the converted HWPX package:
  either sanitize/repair unsupported BorderFill structures before render with a
  deterministic package transform, upgrade/swap the renderer behind the same
  gate, or keep the specific conversion output blocked.
- Autonomous HWP fill planning must infer safe field targets from converted HWPX
  or HWP read-only IR before user prompts like `문서내용을 파악하고 알아서 작성해`
  can be treated as real-use authoring.
