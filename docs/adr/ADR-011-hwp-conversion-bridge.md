# ADR-011: HWP Conversion Bridge Promotion Boundary

**Status**: Accepted
**Date**: 2026-06-03
**Initiative**: #2290
**Affected**:
- `src/ummaya/tools/documents/conversion.py`
- `src/ummaya/tools/documents/registry.py`
- `src/ummaya/tools/documents/evaluation.py`
- `tests/fixtures/documents/candidate_profiles.yaml`
- `specs/2803-document-production-hardening/spec.md`

## Context

UMMAYA's public-document harness must support files that Korean public
infrastructure users actually exchange. Legacy `.hwp` remains common, but binary
HWP direct mutation is not a safe foundation for a citizen-facing AX harness.

The document harness already owns a deterministic boundary:

1. user documents are copied into immutable artifact storage;
2. write operations require a working derivative;
3. document mutation happens through the `document` primitive;
4. render, reread, diff, validation, and save evidence are attached before a
   result can be treated as successful.

Loop 2 added a separate `DocumentConversionEngine` boundary so `.hwp` sources can
be converted into `.hwpx` working derivatives without mutating the original HWP
bytes. Loop 3 separately promoted a read-only `unhwp` inspection engine after it
extracted real local public AX HWP fixtures into `DocumentExtraction` without
creating a working derivative. This ADR defines the shared promotion boundary for
both read-only HWP inspection and future conversion bridges.

## Current Sources

- `docs/vision.md`: UMMAYA is the Claude Code harness migrated to Korean public
  infrastructure; document operations are tool execution, not raw LLM byte
  generation.
- `specs/2803-document-production-hardening/spec.md`: direct HWP authoring is
  a target capability only after a candidate engine proves read, edit, save,
  re-read, style preservation, and render comparison on real fixtures.
- `docs/adr/ADR-010-workspace-bash-permission-boundary.md`: shell or workspace
  operations must not mutate document binaries; document mutation stays under
  the `document` primitive.
- HwpForge: Rust HWPX library and MCP/CLI surface for AI-oriented HWPX
  generation, JSON round-trip editing, Markdown bridge, and HWP5 CLI audit or
  conversion helpers. It is dual MIT OR Apache-2.0.
  <https://github.com/ai-screams/HwpForge>
- OpenHWP: Rust workspace with `hwp` for HWP 5.0 read, `hwpx` for HWPX
  read/write, and `ir` for HWP to HWPX conversion. Its published support table
  lists HWP write as unsupported and HWPX write as supported.
  <https://github.com/openhwp/openhwp>
- unhwp: Rust extractor for HWP/HWPX to Markdown, text, JSON, metadata, and
  assets. UMMAYA uses it only as the local read-only `.hwp` inspection runtime;
  it is not a write converter.
  <https://github.com/iyulab/unhwp>
- hwpxjs: MIT TypeScript library and CLI for HWP 5.0/HWPX parsing, HWP-to-HWPX
  conversion, HWPX writing, Markdown/HTML bridges, and local Node/browser ESM
  execution. UMMAYA may register the pinned local CLI
  `@ssabrojs/hwpxjs@0.4.0` as a HWP-to-HWPX conversion candidate when `hwpxjs`
  is available on PATH, but conversion success alone is not HWP authoring
  promotion.
  <https://github.com/ssabro/hwpxjs>
- MCP-Atlas and ComplexMCP 2026: current tool-use benchmarks emphasize
  concrete tool execution, multi-step state, authentic servers or sandboxes, and
  deterministic scoring. This supports a real fixture/render/reread gate before
  exposing HWP conversion to the model.
  <https://arxiv.org/abs/2602.00933>
  <https://arxiv.org/abs/2605.10787>

## Decision

Do not promote a real HWP runtime bridge merely because the scorecard is high.

An HWP read or HWP-to-HWPX conversion candidate may be scored as technically
promising, but it remains `dependency.gate: defer` until the relevant gates pass.
For read-only HWP inspection, gates 1-5, 9, and 10 are required. For HWP-to-HWPX
conversion, all gates are required:

1. ADR reference: candidate profile includes this ADR as `adr_ref`.
2. License: SPDX license is permissive for UMMAYA's Apache-2.0 project.
3. Package pin: exact package or crate reference is recorded and lockfile impact
   is reviewed.
4. Local-only execution: converter reads and writes only local artifact-store
   paths; no remote document upload or external conversion service is allowed.
5. Permission boundary: every mutation or derivative creation goes through the
   `document` primitive, never `workspace_bash`, raw shell, or a direct adapter
   bypass.
6. HWP source immutability: original HWP artifact SHA-256 is unchanged after
   conversion.
7. HWPX derivative validity: output is detected as HWPX and can be inspected by
   the promoted HWPX engine.
8. Render/reread evidence: converted derivative can be rendered and reread; diff
   evidence remains attached to the derivative, not to the original HWP.
9. Public AX fixture evidence: all local public AX HWP fixtures either convert
   successfully with comparable structure or fail closed with typed reasons.
10. Failure typing: encrypted, corrupt, unsupported-version, and malformed HWP
    inputs return typed blocked or failed results without fallback success.

Until the required gates pass, candidate profiles may record high scores but
`evaluate_candidate_profiles()` must return `promoted=False` with
`dependency_gate_deferred`. The currently promoted `.hwp` runtime is
`unhwp-read-only`, and only for inspection/extraction. A locally discovered
`hwpxjs` converter may create HWPX working derivatives, but the resulting
document operation remains blocked if render/re-read/save gates fail.

## Rationale

The selected boundary preserves the public-document harness contract: HWP is a
source artifact, HWPX is the editable derivative, and direct HWP binary write is
not part of the runtime.

This also keeps UMMAYA aligned with the Claude Code-style tool loop. A tool result
must not claim success when a required engine, permission boundary, or
deterministic evidence path is missing. The model can ask for document work, but
runtime success is earned through the adapter gate.

## Alternatives Considered

- **Promote HwpForge immediately via MCP**: rejected for now. The MCP surface is
  promising, but UMMAYA owns its own `document` primitive and artifact lineage;
  an external MCP server cannot bypass that contract.
- **Promote OpenHWP read immediately**: deferred. The architecture is the best
  permissive source for HWP read and IR conversion, but runtime bridge packaging
  and fixture gates still need proof.
- **Use unhwp as read-only runtime**: accepted for Stage 1 inspection after local
  public AX HWP fixtures extracted successfully. It remains rejected as a primary
  write/conversion path because it does not provide the HWPX editable derivative
  contract.
- **Use pyhwp**: rejected as runtime dependency because of AGPL and degraded
  results on local table-heavy public AX fixtures.
- **Call a remote converter**: rejected. User document bytes must remain local
  unless a separate policy-cited public channel explicitly authorizes transfer.

## Consequences

Positive:

- Prevents accidental model-visible HWP conversion before deterministic evidence.
- Keeps public-document mutation under one primitive and one permission surface.
- Lets legacy HWP content become LLM-readable through a promoted local read-only
  engine without implying HWP authoring support.
- Lets OpenHWP/HwpForge remain the leading bridge candidates without committing
  runtime dependency debt too early.

Risks:

- HWP authoring still remains unavailable until the bridge gates pass.
- Implementing the real bridge may require Rust or Node packaging work and
  lockfile updates.

Mitigations:

- Candidate profiles explicitly encode `requires_adr`, `adr_ref`,
  `permission_boundary`, `local_only_execution`, and `package_ref`.
- Tests assert that HWP conversion bridge candidates are deferred and that the
  promoted HWP read engine remains local-only and document-primitive-scoped.
- `DocumentToolRuntime.copy_for_edit` remains fail-closed when no converter is
  registered.
- Native render bridge exceptions from converted HWPX derivatives are returned
  as typed `blocked(validation_failed)` document results with no render records,
  so a conversion-only success cannot be mistaken for completed HWP authoring.

## Verification

Required gates before a real bridge can be promoted:

```bash
uv run pytest tests/tools/documents/test_candidate_evaluation.py tests/tools/documents/test_dependency_gate.py -q
uv run pytest tests/tools/documents/test_builtin_hwp_adapter.py tests/tools/documents/test_conversion_registry.py -q
uv run pytest tests/tools/documents tests/evidence tests/ci -q
uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json
```

The Stage 1 read-only promotion adds `unhwp>=0.5.0,<0.6` as a local runtime
dependency. The Stage 2 bridge may use pinned local converter packages such as
`@ssabrojs/hwpxjs@0.4.0` only behind the conversion registry and only after the
render/re-read failure state remains visible to the caller. No direct HWP
binary-write dependency is added by this ADR.
