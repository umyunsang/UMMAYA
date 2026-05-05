# G7 — Slash Autocomplete + bootGuard Primitive Count Fixes

> Wave-2 Lead Opus G7 — single-commit fix-set for 4 audit findings.
> Research: `specs/realuse-audit-2026-05-05/research/g7-autocomplete.md`.

## Findings closed

| Finding | Severity | Surface | Fix |
|---|---|---|---|
| F-alpha-03 | P1 | UI-B `/he` autocomplete | strict prefix matcher in `generateCommandSuggestions` |
| F-alpha-14 | P1 | UI-B `/fork` Enter | strict prefix excludes alias-only matches → `/branch` no longer surfaces for typed `/fork` |
| F-delta-08 | P1 | UI-B `/p` autocomplete | strict prefix matcher + `▶ ` selected-row glyph (UI-B.6) |
| F-alpha-16 | P2 | L1-C tool registry | bootGuard Korean diagnostic now reads `예약된 4-primitive` (was `5-primitive`); JSDoc clarifies `resolve_location` is backend-only |

## Files changed (4 src + 2 tests)

| File | Lines | Type |
|---|---|---|
| `tui/src/utils/suggestions/commandSuggestions.ts` | +25 / 0 | strict-prefix branch added BEFORE the existing CC Fuse path; bare-`/` branch unchanged |
| `tui/src/components/PromptInput/PromptInputFooterSuggestions.tsx` | +9 / -1 | `▶ ` glyph on selected row, two-space placeholder on others to keep alignment |
| `tui/src/services/toolRegistry/bootGuard.ts` | +13 / -2 | JSDoc + Korean diagnostic correctness pass |
| `tui/src/tools/__tests__/registry-boot.test.ts` | +6 / -1 | assertion now expects `4-primitive` substring per Spec 2294 |
| `tui/src/components/PromptInput/__tests__/g7-autocomplete-prefix.test.ts` | new (78) | regression guard for the 3 matcher findings |

`bun test` shows the 3 G7 matcher repro tests + the bootGuard diagnostic
test were FAILING before and are PASSING after — no other test changed
state. Net change: **+3 PASS / 0 new failures**.

## Diff narratives

### `commandSuggestions.ts`

The CC Fuse path is preserved verbatim for the bare-`/` initial render and
for non-catalog completion paths (`@` agents / files / directories /
`/resume` titles). When the citizen has typed at least one character after
`/`, KOSMOS short-circuits to a strict prefix filter against the
`citizenCommands` array (which was already filtered by the
`KOSMOS_CITIZEN_COMMAND_NAMES` allow-list). Stable alphabetical ordering
makes `selectedSuggestion=0` deterministic for both human and PTY-smoke
verification. The Fuse fuzzy-matching algorithm — which scored against
`partKey` (split on `[:_-]`), `aliasKey`, and every word of
`descriptionKey` — was the root cause that pulled `/branch /fork /export`
into the `/he` candidate list and let `/branch`'s `aliases: ['fork']`
collide with a typed `/fork` name match.

### `PromptInputFooterSuggestions.tsx`

The selected-row caret `▶` is prepended to `displayText_0` with a trailing
space. Non-selected rows get `"  "` (two spaces) so all rows stay
column-aligned. The width-budget arithmetic at line 129
(`Math.min(maxColumnWidth ?? stringWidth(item.displayText) + 5, …)`)
already reserves a +5-char pad, so the 2-char prefix never pushes the row
past `maxNameWidth = floor(columns * 0.4)` — verified against the longest
catalog entry (`/migrate-sessions`, 17 chars + 2 = 19 < 32 at 80 columns).

### `bootGuard.ts`

The success-path log line `(N primitives)` was always correct
(N = `primitives.length` — 4 in the canonical TUI registry). The failure
diagnostic literal at line 82 hardcoded `예약된 5-primitive`, which
contradicted the very next line of the same string (`KOSMOS는 4개
primitive(lookup/submit/verify/subscribe) 모두 등록되어야`) and the success-log line. Fixed to
`예약된 4-primitive`. Added JSDoc clarification: `resolve_location` is the
5th primitive in the AGENTS.md L1-C surface but lives backend-side
(exposed via the system prompt + IPC, not as a TUI Tool).

## Verification chain

| Layer | Status | Evidence |
|---|---|---|
| 1a (pytest) | not exercised | TS-only fix surface |
| 1b (`bun test` matcher) | **PASS — 6/6** | `g7-autocomplete-prefix.test.ts` |
| 1b (`bun test` registry-boot) | **PASS — 9/9** | `registry-boot.test.ts` (existing 4-primitive Case 1 now agrees with the diagnostic) |
| 1b (`bun test` single-stack) | **PASS — 4/4** | `single-stack-slash.test.ts` (KOSMOS_CITIZEN allow-list invariant preserved) |
| 1b (`bun test` full) | **+3 PASS, 0 regressions** | `1239 pass, 12 fail` (pre-existing #1633 dead-code-deletion invariants + 1 stream-event test, none caused by G7) |
| 4 / 5 | deferred to Wave-3 re-smoke | per dispatch tree — α2 / α8 / δ8 scenarios re-captured under `specs/realuse-audit-2026-05-05/scenarios/g7-autocomplete-after.txt` after merge |
| Boot probe | **PASS** | `bun run src/entrypoints/cli.tsx --help` returns 0; `tool_registry: 14 entries verified (4 primitives)` log line unchanged |

## Constraints check

- Zero new runtime dependencies (`bun.lock` unchanged).
- CC parity for non-KOSMOS-catalog paths preserved (Fuse infrastructure
  intact for bare-`/` initial render + `@` / file / agent completions).
- `feedback_no_hardcoding.md` — the prefix matcher delegates to the
  `getCommandName(cmd).toLowerCase().startsWith(query)` check on the
  catalog SSOT; no inline keyword list.
- Spec 1633 single-stack invariant preserved
  (`KOSMOS_CITIZEN_COMMAND_NAMES` allow-list still gates the input).

## Commit message

```text
fix(2773-g7): slash autocomplete matcher prefix filter + bootGuard 5-primitive (closes F-alpha-03/14/16, F-delta-08)

Wave-2 G7 of the realuse-audit-2026-05-05 triage:

* Slash autocomplete matcher (P-B pattern, F-alpha-03 / F-alpha-14 /
  F-delta-08): replace Fuse fuzzy matching with strict prefix match on
  the catalog SSOT once the citizen has typed any character after `/`.
  Eliminates `/he` → /branch /fork /export collision and `/fork` Enter
  → /branch alias-collision. Bare-`/` initial render keeps the CC Fuse
  path. Adds `▶ ` selected-row glyph in PromptInputFooterSuggestions per
  UI-B.6 (highlighted match).

* bootGuard primitive count (P-H pattern, F-alpha-16): Korean
  diagnostic at `bootGuard.ts:82` now reads `예약된 4-primitive` to
  match the TUI registry's 4 primitives (Spec 2294 contract). The 5th
  primitive (`resolve_location`) is backend-only per AGENTS.md L1-C and
  is exposed via the system prompt + IPC, not as a TUI Tool.

bun test: +3 pass / 0 regressions vs baseline. Zero new runtime deps.

Refs: specs/realuse-audit-2026-05-05/research/g7-autocomplete.md
      specs/realuse-audit-2026-05-05/fixes/g7-autocomplete.md
```
