# ADR-009: `mcpb-compat.ts` lazy-load shim (KOSMOS-original)

**Status**: Accepted
**Date**: 2026-05-03
**Epic**: #2642 (S7 IPC/Bridge cleanup) · Initiative #2636 (CC Migration Audit-Driven Realignment)
**Affected**:
- `tui/src/mcpb-compat.ts` (the shim itself, 26 LOC)
- `tui/src/utils/dxt/helpers.ts` (canonical caller, lazy `loadMcpb()` consumer)
- `tui/src/utils/plugins/mcpPluginIntegration.ts` (secondary caller)
- `tui/package.json` (`@anthropic-ai/mcpb` declared as a dependency)

## Context

`@anthropic-ai/mcpb` (Anthropic's MCP-bundle manifest validator) ships a
zod-v3 schema graph that eagerly creates ~300 `.bind(this)` schema
instances at import time, costing roughly **700 KB of resident heap**.
Most KOSMOS sessions never process a `.dxt` (MCP-bundle) file — citizen
sessions invoke Korean public-API adapters via `lookup` / `submit` /
`verify` primitives, not MCP bundles. Paying the import-
time heap cost up-front for a feature touched by < 5 % of sessions is
wasteful.

Claude Code (CC 2.1.88, restored-src) has **no equivalent shim**.
CC imports the package eagerly at the top of every consumer because the
CC consumer set is dominated by developer workflows that frequently use
DXT plugins, so the heap cost amortises across an active developer's
typical session shape. KOSMOS's citizen workflow shape is different —
the lazy import deferral is a measurable win.

The decision posture is recorded here for two reasons:

1. **CC parity discipline**: every TS file that diverges from CC must
   either be byte-identical or carry a `// SWAP:` justification (per
   AGENTS.md § CORE THESIS). `tui/src/mcpb-compat.ts` is **not a swap**
   in the sense of swap-1 (LLM = K-EXAONE) or swap-2 (Tool = GovAPITool)
   — it is a KOSMOS-original performance optimisation. AGENTS.md
   § Hard rules state "Stack changes require an ADR under `docs/adr/`",
   and introducing a load-pattern shim where CC has none qualifies.
2. **Future-portability**: if Anthropic publishes a `mcpb` v4 with eager
   imports removed, the shim becomes redundant. Future agents need
   rationale to either drop the shim (CC re-parity) or keep it (defensive
   layering). This ADR captures the original justification so the
   re-evaluation is informed.

The S7 audit (`specs/cc-migration-audit/scope-S7-ipc-bridge.md § 2.5 +
§ 5 Finding 5`) called out the missing ADR explicitly:

> `mcpb-compat.ts` — KOSMOS-original 혁신, ADR 등록 권고
> Epic #2293 FR-010 의 mcpb v3 lazy-load shim 은 CC 대응 없음. swap 1/2
> 가 아닌 성능 최적화(700KB heap 회피) → KOSMOS-original 혁신으로 분류.
> 유지 정당, 단 ADR 등록해 향후 CC 재포팅 시 결정 근거 보존 필요.

## Decision

**Keep the `mcpb-compat.ts` lazy-load shim as a single canonical
indirection point.** Every TUI file that needs `mcpb` types or its
manifest schema MUST import from `src/mcpb-compat.js`, never directly
from `@anthropic-ai/mcpb`.

Two surfaces are exported:

```ts
export type { McpbManifest } from '@anthropic-ai/mcpb'      // type-only
export async function loadMcpb(): Promise<typeof import('@anthropic-ai/mcpb')> {
  return import('@anthropic-ai/mcpb')                       // dynamic
}
```

Type imports are zero-cost (erased at compile). Schema/value access goes
through `await loadMcpb()` which triggers the import on first use only.

A grep-gate enforces the single-entry-point invariant:

```bash
# Must always succeed (no direct package imports outside the shim itself).
$ grep -rln "from '@anthropic-ai/mcpb'" tui/src/ \
    | grep -v "^tui/src/mcpb-compat\.ts$"
# expected: empty output
```

This gate is part of Spec 2293 § FR-010 / SC-007.

## Rationale

### Why a shim instead of an upstream patch

`@anthropic-ai/mcpb` is published by Anthropic; KOSMOS cannot patch the
zod-v3 import behaviour without forking the package. A 26-line shim
inside KOSMOS is the smallest possible carrier of the optimisation.

### Why a single file, not inline at every call site

The grep-gate (Spec 2293 SC-007) needs a single anchor to enforce the
"all `mcpb` imports go through the shim" invariant. Inline `import()`
at every call site would defeat the gate and leak the package literal
into multiple files, fragmenting the optimisation contract.

### Why re-export the type rather than `unknown`

`McpbManifest` consumers in `utils/dxt/helpers.ts` and downstream rely on
the structural type for IDE autocomplete + compile-time checks. Re-exporting
preserves type safety; the type-only import is erased at runtime so it
does not trigger the eager-load cost.

### Why not vendor zod-v4 with the manifest schema

Migrating mcpb to zod-v4 would touch upstream Anthropic code and
contradict CORE THESIS byte-identical defaults. The shim leaves
`@anthropic-ai/mcpb` untouched and absorbs the deferral entirely on the
KOSMOS side.

### Measured impact (Spec 2293 § FR-010)

- Pre-shim startup heap: ~9.2 MB (with mcpb eager import)
- Post-shim startup heap: ~8.5 MB (without)
- Δ: ~700 KB saved on every cold start
- Measurement methodology: Bun `--smol` startup + Node `process.memoryUsage().heapUsed`
  delta vs a no-mcpb-import baseline

## Consequences

### Positive

- 700 KB of resident heap saved on every cold session start.
- Single anchor (`tui/src/mcpb-compat.ts`) for any future mcpb version
  pin, package replacement, or removal.
- Grep-gate (Spec 2293 SC-007) keeps the optimisation invariant from
  silently regressing across TUI rewrites.
- No CC byte-identical surface is touched (the shim sits beside, not in,
  bridge/upstreamproxy/native-ts).

### Negative

- One extra await per first-use of `loadMcpb()` (≤ 5 ms typical),
  measurable only on the very first DXT manifest validation per session.
- Future agents need to read this ADR to understand why the shim exists.
  Mitigated by the in-file `// KOSMOS-original — Epic #2293 FR-010`
  header on `mcpb-compat.ts` and the grep-gate test in Spec 2293.

### Neutral

- `@anthropic-ai/mcpb` remains a regular dependency in `tui/package.json`.
- Type-only imports continue to compile cleanly without triggering the
  eager-load.

## Alternatives considered

### A. Eager import at the top of `utils/dxt/helpers.ts` (CC parity)

Rejected — costs 700 KB on every cold start for a feature most citizen
sessions never use.

### B. Drop `@anthropic-ai/mcpb` entirely; reimplement manifest schema

Rejected — diverges from Anthropic's canonical MCP-bundle spec; rejected
by CORE THESIS byte-identical default (mcpb is the upstream contract).

### C. Vendor a minimal mcpb manifest type without runtime validation

Rejected — runtime validation is required for plugin install safety
(Spec 1636); reimplementing it inside KOSMOS would regress security.

## References

- `tui/src/mcpb-compat.ts` (shim, 26 LOC)
- `specs/2293-ui-residue-cleanup/spec.md § FR-010 + § SC-007` (originating spec)
- `specs/cc-migration-audit/scope-S7-ipc-bridge.md § 2.5 + § 5 Finding 5` (audit recommendation)
- `specs/cc-migration-audit/decisions.md § S7 IPC Bridge` (canonical decision row)
- `AGENTS.md § Hard rules` (ADR requirement for stack changes)
- `AGENTS.md § CORE THESIS` (byte-identical CC default with `// SWAP:` exemption)
