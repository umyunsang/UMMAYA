# G7 — Slash Autocomplete Matcher + bootGuard Primitive Count Deep Research

> Wave-2 Lead Opus G7 — single fix-set closing 4 findings (P-B + P-H patterns).
> Two clusters: (G7a) the slash-command dropdown matcher's prefix filter and
> selectedIndex highlight glyph, and (G7b) the `bootGuard.ts` Korean diagnostic
> string contradicting the actual primitive count it enforces.

## Targets (4 findings)

| Finding | Cluster | Surface | Symptom | Severity |
|---|---|---|---|---|
| F-alpha-03 | G7a matcher | UI-B `/he` autocomplete | dropdown shows `/branch /fork /export …` (none start with `/he`) | P1 |
| F-alpha-14 | G7a matcher | UI-B `/fork` Enter | command `/branch` executed, not `/fork` (alias collision) | P1 |
| F-delta-08 | G7a matcher | UI-B `/p` autocomplete | dropdown shows `/export /help /config /branch /resume`, no `/plugins` highlight glyph | P1 |
| F-alpha-16 | G7b bootGuard | L1-C tool registry | boot probe says `(4 primitives)` but Korean diagnostic claims `5-primitive` | P2 |

## Authoritative breadcrumbs

- `docs/requirements/kosmos-migration-tree.md § UI-B.6` — *"Slash command
  autocomplete: CC 방식 (드롭다운 + highlighted match + 인라인)"*. The CC
  reference (`.references/claude-code-sourcemap/restored-src/src/utils/suggestions/commandSuggestions.ts`)
  uses Fuse.js with `threshold: 0.3` for a developer-shell experience. KOSMOS
  catalog SSOT (`tui/src/commands/catalog.ts:155`) ships its own
  `matchPrefix()` helper that already does **strict prefix-only** matching.
- `tui/src/components/PromptInput/SlashCommandSuggestions.tsx` — the
  catalog-driven dropdown originally authored under Spec 1635 P4 (FR-014).
  Removed from REPL (`tui/src/screens/REPL.tsx:347, 5777`) under "P0-2
  single-stack" but never deleted — its `matchPrefix(inputText)` call is the
  contract the audit's expected-behaviour clause cites.
- `tui/src/utils/suggestions/commandSuggestions.ts:317` —
  `generateCommandSuggestions(input, commands)` is the matcher actually wired
  into the production dropdown. CC-byte-identical Fuse code with a single
  KOSMOS shim (`filterToKosmosCommands`) atop. Fuse fuzzy-matches name +
  description + alias keys with score thresholds; this is what surfaces
  unrelated commands when typing 1-2 letters.
- `tui/src/services/toolRegistry/bootGuard.ts:25-87` — declares
  `PRIMITIVE_NAMES = ['lookup', 'submit', 'verify', 'subscribe']` (4 names),
  emits `(4 primitives)` on success, but the failure-diagnostic Korean
  string at line 82 hardcodes the literal `예약된 5-primitive 중 일부가`.
- `specs/2294-5-primitive-align/contracts/registry-boot-guard.md:35` —
  canonical contract. *"On success: return `{ ok: true, entries: 22,
  primitives: 4, adapters: 18, durationMs: <observed> }`."* TUI side's
  registered primitive count is **4** by spec.
- AGENTS.md § L1-C says *"Five reserved primitives (`lookup ·
  resolve_location · submit · verify · subscribe`) with shared
  `PrimitiveInput/Output` envelope. System prompt exposes primitive
  signatures only."* This refers to the **backend Python primitive surface
  exposed to the LLM via system prompt**; `resolve_location` is a backend-only
  primitive (no TUI Tool wrapper exists, see grep below). The TUI ToolRegistry
  the bootGuard walks contains 4 wrappers; the 5th lives in
  `src/kosmos/primitives/resolve_location/` and ships only via the system
  prompt + IPC (Spec 1634).

```bash
$ grep -rn "ResolveLocationPrimitive" tui/src --include="*.ts" --include="*.tsx"
# → 0 matches: TUI side has no Tool wrapper for resolve_location.
$ grep -n "primitives" prompts/system_v1.md | head -3
# → 5 entries listed (resolve_location/lookup/verify/submit/subscribe).
```

## G7a — Matcher root cause

### Repro (Layer 1b — `bun:test`)

`tui/src/components/PromptInput/__tests__/repro-autocomplete-prefix.test.ts`
seeds the Fuse-driven matcher with a production-shaped citizen-only command
array (mirrors `KOSMOS_CITIZEN_COMMAND_NAMES` allow-list and the `branch`
command's `aliases: ['fork']`):

```text
/he results: [ "/help", "/consent list", "/continue", "/fork", "/branch",
               "/plugins", "/migrate-sessions" ]
/p  results: [ "/plugins", "/export", "/help", "/consent revoke",
               "/consent list", "/resume", "/history", "/config",
               "/onboarding", "/migrate-sessions" ]
/fork results: [ "/fork", "/branch (fork)", "/consent list",
                 "/migrate-sessions" ]
```

The Fuse default `threshold: 0.3` admits fuzzy matches against:
1. `partKey` — split on `[:_-]` separators, weight 2.
2. `aliasKey` — `['fork']` on the branch command, weight 2.
3. `descriptionKey` — every word of the long-form description, weight 0.5.

`matchPrefix()` from `commands/catalog.ts:155-159` is the strict
contract:

```ts
export function matchPrefix(prefix: string): SlashCommandCatalogEntryT[] {
  const p = prefix.trim().toLowerCase()
  if (p === '' || p === '/') return [...UI_L2_SLASH_COMMANDS]
    .filter((e) => !e.hidden)
  return UI_L2_SLASH_COMMANDS.filter((e) =>
    !e.hidden && e.name.toLowerCase().startsWith(p))
}
```

Sanity test confirms `matchPrefix('/he') === ['/help']`,
`matchPrefix('/p') === ['/plugins']`, `matchPrefix('/fork')[0] === '/fork'`.

### F-alpha-14 alias collision

The `branch` Command (`tui/src/commands/branch/index.ts:17`) carries
`aliases: ['fork']` as belt-and-suspenders. With Fuse fuzzy matching, typing
`/fork` returns BOTH `/fork` (exact name) AND `/branch` (exact alias). The
sort routine puts `/fork` first (priority 1: exact name), but if the user
arrows-down once OR if a re-render shifts `selectedSuggestion`, Enter
executes `/branch`. Switching to strict-prefix on the catalog name eliminates
`/branch` from the `/fork` candidate list entirely (since `branch` does not
start with `fork`).

### F-delta-08 missing highlight glyph

`PromptInputFooterSuggestions.tsx:130` uses only `color="suggestion"` (theme
token) + `dimColor` to indicate the selected row. Citizens reported (snap
`delta8/snap-009`) that no row appears selected — the theme color difference
is too subtle on dark terminals. UI-B.6 promises *"highlighted match"* — a
`▶` left-arrow glyph on the selected row matches the dropdown spec literally
and is universally legible. CC's restored-src does not ship a glyph either,
but UI-B.6 explicitly calls one out.

## G7b — bootGuard primitive count

### Repro (manual, plus `registry-boot.test.ts`)

```bash
$ bun run src/entrypoints/cli.tsx --continue
tool_registry: 14 entries verified (4 primitives) in 0ms     # ← log line, line 1196
    ▛███▜      KOSMOS v0.1.0-alpha+1978
   ...
```

The success path emits `(4 primitives)` (correct, matches
`specs/2294-5-primitive-align/contracts/registry-boot-guard.md`). However the
failure path's Korean diagnostic at `bootGuard.ts:82` reads:

```text
[KOSMOS][bootGuard] 예약된 5-primitive 중 일부가 ToolRegistry에 등록되지 않았습니다.
누락: ${missingNames.join(', ')}.
KOSMOS는 4개 primitive(lookup/submit/verify/subscribe) 모두 등록되어야 부팅을 허용합니다.
```

The same paragraph asserts both *"5-primitive"* and *"4개 primitive"*.
`PRIMITIVE_NAMES.length === 4` is the actual gate. The Spec 2294 contract
fixes the TUI count at **4** (TUI-side ToolRegistry) versus **5** (backend
LLM-visible surface). The fix is to pin the diagnostic to the TUI count,
remove the contradiction, and let the AGENTS.md L1-C "5 primitive" framing
remain correct in its own (backend / system-prompt) layer.

## CC reference comparison

```bash
$ diff .references/claude-code-sourcemap/restored-src/src/utils/suggestions/commandSuggestions.ts \
       tui/src/utils/suggestions/commandSuggestions.ts | head -10
```

KOSMOS's only delta vs CC is the `KOSMOS_CITIZEN_COMMAND_NAMES` allow-list
filter; the Fuse matching algorithm is byte-identical. Replacing Fuse with
`matchPrefix()` for KOSMOS catalog commands is intentional KOSMOS divergence
(spec UI-B.6's "CC 방식" description was applied loosely; the visible-
behaviour contract is the audit triage's prefix-filter requirement).

## Fix shape (Phase 3)

### G7a — Strict prefix matcher + `▶` glyph

1. `tui/src/utils/suggestions/commandSuggestions.ts` — at the top of
   `generateCommandSuggestions(input, commands)` (after the `query === ''`
   bare-`/` branch), short-circuit to a strict prefix filter that walks the
   already-filtered `citizenCommands` array. No Fuse.search() call is made
   for KOSMOS catalog queries. CC dev-command branch is reachable only via
   `query === ''` (bare `/`) and remains unchanged.
2. `tui/src/components/PromptInput/PromptInputFooterSuggestions.tsx` — prefix
   the selected row's rendered string with `▶ ` (with a trailing space) and
   non-selected rows with `  ` (two spaces) to keep alignment. This is a
   purely visual change; the underlying `lineContent` remains a CC-shape
   string.

### G7b — bootGuard string fix

`tui/src/services/toolRegistry/bootGuard.ts:82` — replace `예약된 5-primitive`
with `예약된 4-primitive`. Update the test in `registry-boot.test.ts` if it
asserts the exact Korean substring.

## Verification chain

| Layer | Artefact |
|---|---|
| 1b | `tui/src/components/PromptInput/__tests__/repro-autocomplete-prefix.test.ts` (added) — repro before fix; assertions flip to PASS after. |
| 1b | `tui/src/components/PromptInput/__tests__/single-stack-slash.test.ts` (existing) — still passes; the single-stack invariant is preserved. |
| 1b | `tui/src/tools/__tests__/registry-boot.test.ts` — verifies bootGuard diagnostic still references the right token. |
| 4-5 | Manual `bun run tui` → type `/he`, `/p`, `/fork`, `/co` → screenshot dropdown to confirm prefix-only + `▶` glyph on selected row. Capture under `specs/realuse-audit-2026-05-05/scenarios/g7-autocomplete-after.txt` (already deferred to Wave 3 re-smoke per the dispatch tree). |

## Constraints check

- Zero new runtime dependencies (✓ — pure logic + 1-char render shift).
- CC parity preserved — the CC `query === ''` branch + Fuse infrastructure
  remain unchanged for the bare-`/` initial render and for non-catalog
  KOSMOS @ / file / agent suggestion paths. Only the KOSMOS-specific
  catalog-prefix path is rewired.
- `feedback_no_hardcoding.md` — the prefix matcher delegates to
  `matchPrefix()` from `catalog.ts`, which is itself the SSOT that the
  catalog walks (no inline keyword lists).
