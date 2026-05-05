# G5 — Render commit / JSON truncation / Ctrl-O sanitizer (fix report)

> Wave-2 Lead Opus G5. Branch `fix/2773-g5-render-ctrlo`. Single commit.
> Closes F-beta-05 + F-beta-06 + F-alpha-08 (full); partial F-alpha-09; F-alpha-10 documented.

## Summary

Three minimal patches address P-E (universal JSON 절단) and P-F (raw 내부
필드 + Ctrl-O 누출) cross-domain patterns:

| Patch | Files | Findings closed |
|---|---|---|
| A. JSON-aware ellipsis (`truncateJson`) | `tui/src/tools/_shared/jsonTruncate.ts` (new) · `tui/src/tools/LookupPrimitive/LookupPrimitive.ts` | F-beta-05 (universal), unblocks F-beta-09 |
| B. Ctrl-O thinking sanitizer | `tui/src/components/messages/sanitizeThinking.ts` (new) · `tui/src/components/messages/AssistantThinkingMessage.tsx` | F-alpha-08 |
| D. System prompt enum mappings + adapter Field descriptions | `prompts/system_v1.md` · `prompts/manifest.yaml` · `src/kosmos/tools/kma/kma_current_observation.py` | F-beta-06 |

Patch C (F-alpha-09 trailing-thinking re-order in transcript) is **deferred** —
the load-bearing change is in `Messages.tsx` grouping logic which has higher
regression surface; out of scope for the "single commit" constraint and
explicitly not in G5/G6/G7 surface boundary.

F-alpha-10 is **documented as not-a-regression**: KOSMOS' Ctrl-O default-
collapsed → Ctrl-O #1 expand → Ctrl-O #2 collapse semantics is byte-identical
with `.references/claude-code-sourcemap/restored-src/src/components/messages/
AssistantThinkingMessage.tsx`. The audit's stated expected ("default = full,
Ctrl-O = collapse") was a misread of CC convention. No code change needed;
adding only a clarifying comment in research doc.

## Patch B — Ctrl-O sanitizer allow / deny list

The sanitizer (`sanitizeThinking`) operates ONLY on the citizen-facing
display surface. The raw ``thinking`` channel that the agentic loop sends
back to the LLM in subsequent turns is NOT modified — agentic context is
preserved.

**Deny (redacted)**:

| Pattern | Replacement | Rationale |
|---|---|---|
| `\bavailable_adapters\b` | `⟨내부⟩` | F-alpha-08 — internal block name (suffix injection) |
| `\btool_id\b` | `⟨내부⟩` | F-alpha-08 — internal field name |
| `\bhira_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — HIRA registry id leak |
| `\bkma_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — KMA registry id leak |
| `\bkoroad_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — KOROAD registry id leak |
| `\bnmc_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — NMC registry id leak |
| `\bnfa119_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — NFA119 registry id leak |
| `\bmohw_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — MOHW registry id leak |
| `\bmock_(?:verify\|lookup\|submit\|subscribe)_[a-z0-9_]+\b` | `⟨adapter⟩` | F-alpha-08 — mock-namespace registry id leak |

**Allow (preserved verbatim)**:

| Pattern | Rationale |
|---|---|
| `lookup` / `resolve_location` / `submit` / `verify` / `subscribe` | These 5 primitive names are also citizen-facing — they appear in the `⏺ lookup(...)` gutter glyph row that the citizen sees in normal mode. Redacting in transcript would create a cognitive mismatch. |
| Korean prose ("사용자가", "도구를", "결과로는…" etc.) | Citizen NEEDS to see the model's reasoning. The sanitizer is regex-token-based; arbitrary Korean text passes through unchanged. |
| English prose that does not match a deny pattern | Same rationale. |

**Idempotent guarantee**: applying `sanitizeThinking(sanitizeThinking(x))` yields the same string as a single application — the placeholders contain non-word characters (`⟨`, `⟩`) and never match the deny patterns.

**Test coverage**: `tui/tests/components/messages/sanitizeThinking.test.ts` (9 cases including a verbatim reproduction of the F-alpha-08 leak surface from `snap/alpha5b/snap-003-after-ctrl-o-collapse.txt:13-19, 41-54`).

## Patch A — JSON-aware truncation

`truncateJson(s, max)` returns `s` unchanged when `s.length <= max`,
otherwise `s.slice(0, max - 1) + '…'`. The U+2026 ellipsis is a single
column-cell so the visible width is preserved.

Replaces three `.slice(0, N)` calls in
`tui/src/tools/LookupPrimitive/LookupPrimitive.ts:387-405` (collection /
timeseries / record render paths).

Other primitives (Submit / Verify / Subscribe) do not have this issue —
verified by grep `JSON.stringify` + `.slice(` across all four primitives.

**Test coverage**: `tui/tests/primitive/jsonTruncate.test.ts` (6 cases
including a verbatim reproduction of F-beta-05 β1 snap-005 surface).

## Patch D — System prompt enum mappings

Added a CRITICAL directive block to `<output_style>` of
`prompts/system_v1.md` covering:

- **PTY** (강수형태) — all 7 codes (0/1/2/3/5/6/7) with Korean labels.
- **SKY** (하늘상태) — codes 1/3/4 with Korean labels.
- **VEC** (풍향) — 16 compass directions with degree boundaries; vec=271
  worked example pinning the F-known criterion #4 mismatch.

Manifest hash `prompts/manifest.yaml:13` updated to `c67d2b0b…`.

Defense-in-depth: `src/kosmos/tools/kma/kma_current_observation.py` —
`KmaCurrentObservationOutput.pty` and `.vec` fields converted from bare
docstring annotation to `Field(default=…, description=…)` so the
mapping surfaces via Pydantic JSON schema for any future suffix
exposure.

**Test coverage**: `tests/llm/test_prompt_enum_mappings.py` (4 invariants
across PTY / SKY / VEC / CRITICAL directive presence).

## Verification (Layer 1b + Layer 1a)

- `bun test tui/tests/components/messages/sanitizeThinking.test.ts` — 9/9 PASS expected
- `bun test tui/tests/primitive/jsonTruncate.test.ts` — 6/6 PASS expected
- `pytest tests/llm/test_prompt_enum_mappings.py -v` — 4/4 PASS expected
- `pytest tests/llm/test_prompt_loader_xml_tags.py` — should remain GREEN
  (no `<output_enum_mappings>` tag was added — rules live inside `<output_style>`).

Layer 5 re-run of α5/α5b + β1-β5 is recommended after merge — see
`research/g5-render.md § Phase 4` for the per-frame check list.

## Out of scope (deferred to Wave-3)

- F-alpha-09 — trailing thinking re-order in transcript group (touches
  `Messages.tsx` grouping logic).
- F-alpha-10 — documented as CC-byte-identical, no fix needed.
- F-beta-09 — auto-checks after F-beta-05 truncation lifts.

## Constraint compliance

- **Single commit**: `fix(2773-g5): Message renderer JSON ellipsis + Ctrl-O sanitizer + system prompt enum mappings (closes F-beta-05/06, F-alpha-08, partial F-alpha-09/10)` — one commit on branch `fix/2773-g5-render-ctrlo`.
- **Don't touch G1/G2/G3/G4/G6/G7 surfaces**: ✓ — only `tui/src/tools/LookupPrimitive/`, `tui/src/components/messages/`, `prompts/`, `src/kosmos/tools/kma/kma_current_observation.py` modified.
- **Zero new runtime deps**: ✓ — `truncateJson` and `sanitizeThinking` are stdlib-only TS; the system prompt change is text-only; the Pydantic Field migration uses already-imported `Field`.
