# G2 — useInput Dispatch Deep Research

> Wave-2 Lead Opus G2 — single-track fix for AGENTS.md infra-insight #3 + #4
> dispatch failures across 7 findings sharing the same root cause. Two distinct
> root causes are reconciled below; one fix-set closes all 7.

## Targets (7 findings)

| Finding | Surface | Symptom | Severity |
|---|---|---|---|
| F-alpha-02 | UI-A onboarding preflight | Enter no-op on tmux | P0 |
| F-alpha-04 | UI-B autocomplete | Esc not dismissing dropdown | P1 |
| F-alpha-05 | UI-B `/help` overlay | Esc not dismissing (footer literally says "Esc · 닫기") | P1 |
| F-delta-01 | UI-A onboarding | First-run preflight blocked (cross-confirms F-alpha-02) | P0 |
| F-delta-02 | UI-A onboarding | `KOSMOS_ONBOARDING_AUTO_COMPLETE=1` escape hatch broken | P1 |
| F-delta-04 | UI-B `/help` | Esc + arrow keys leak to PromptInput history | P1 |
| F-ε-05 | UI-D `/agents` | Esc dismiss broken | P1 |

## Authoritative breadcrumbs

- AGENTS.md § "Infrastructure insights (2026-05-04 integration-verification)"
  insight **#3** — `setToolJSX({isLocalJSXCommand: true})` deactivates EVERY
  `useInput` hook in the parent prompt subtree (PromptInput.tsx:244 gate).
- AGENTS.md insight **#4** — `useKeybinding(action, handler)` only fires if
  the chord registry has a default chord for that action; brand-new actions
  (e.g. `help:dismiss` outside Tier 1) register a handler but no chord, so
  Esc never resolves to the action and the handler silently never fires.
- `tui/src/components/onboarding/OnboardingFlow.tsx:117-126` — known-but-
  unresolved comment authored by the integration-verification team:
  > "tmux/expect-driven smoke scenarios where stdin handling under
  > `showDialog` proves brittle … PreflightStep's useInput never fired on
  > Enter under the dialog wrapper — dispatch root cause TBD."
- `specs/integration-verification/RUNTIME-BUGS.md` — bugs #3 + #4-deferred.
- F-delta-03 (PASS): `/onboarding theme` re-entry works end-to-end. The
  re-entry path mounts via `kosmosOnboardingMode` state inside REPL.tsx —
  NOT via `showDialog(root, ...)` at boot. **This is the smoking-gun
  evidence that the problem is the boot-time mount path, not the
  `OnboardingFlow` component itself.**

## Two root causes (reconciled)

### Root cause A — boot-time `showDialog` lacks providers

**Code site**: `tui/src/main.tsx:1514`

```tsx
// Current (broken)
await showDialog(root, (done) => {
  return React.createElement(OnboardingFlow, {
    sessionId: getKosmosBridgeSessionId(),
    onComplete: () => done(),
    locale: getCurrentLocale(),
  });
});
```

**Reference (CC restored-src)**:
`.references/claude-code-sourcemap/restored-src/src/interactiveHelpers.tsx:120`
uses `showSetupDialog(root, ...)` which wraps in `<AppStateProvider>` +
`<KeybindingSetup>`. The KOSMOS port preserves `showSetupDialog` (line 89 of
the same file) but **never imports it from `main.tsx`**. The boot-time
KOSMOS onboarding gate at `main.tsx:1514` calls the bare `showDialog`
instead. Result: the React tree mounted under `root.render()` has NO
`KeybindingProvider` (chord registry not wired), so `useKeybinding`
handlers register a context-provider-less handler that the chord
interceptor cannot dispatch to. The bare `useInput` hook does survive
without `KeybindingSetup` (it only needs Ink's `<App>` for `StdinContext`),
which is why `/onboarding theme` works (it mounts under REPL.tsx where
`KeybindingSetup` is in the parent tree).

The CC pattern at `interactiveHelpers.tsx:120` is the canonical evidence
this is the design intent — the wrapping is mandatory.

### Root cause B — `DEFAULT_BINDING_BLOCKS` missing 14 contexts

**Code site**: `tui/src/keybindings/defaultBindings.ts:117-209`

KOSMOS ships only **5 keybinding context blocks**:
`Global / Chat / HistorySearch / Confirmation / Select`.

CC restored-src ships **17 context blocks**, including:
- `Autocomplete` — `escape: 'autocomplete:dismiss'`, `tab: 'autocomplete:accept'`,
  `up/down: previous/next`
- `Help` — `escape: 'help:dismiss'`
- `Settings`, `Tabs`, `Transcript`, `Task`, `ThemePicker`, `Scroll`,
  `Attachments`, `Footer`, `MessageSelector`, `MessageActions`,
  `DiffDialog`, `ModelPicker`, `Plugin`

Per AGENTS.md insight **#4**: every KOSMOS overlay component that calls
`useKeybinding('autocomplete:dismiss' / 'help:dismiss' / etc.)` registers
its handler with `KeybindingProvider`, but the chord interceptor never
matches the keystroke to the action because **the chord registry has no
binding for that action**. Esc just falls through to whichever ancestor
hook captures it (PromptInput's main `useInput` at line 1932, which on
Esc with non-empty messages calls `doublePressEscFromEmpty()`).

Existing defense-in-depth fixes (HelpV2Grouped:135, AgentsCommandView:117,
ConsentListView, ConsentRevokeConfirmDialog, ExportPdfDialog) already pair
the `useKeybinding` with a direct `useInput((_, k) => k.escape && handler())`
fallback — but Esc is ALSO captured by the parent `useTypeahead` (line 1374:
`useInput((_input, _key, event) => handleKeyDown(...))`) which wraps Esc
into `KeyboardEvent` and dispatches via `handleKeyDown`. When suggestions
exist, `useKeybindings(autocompleteHandlers, ...)` SHOULD fire on `escape:
autocomplete:dismiss`, but the chord block is missing from defaults.

The autocomplete-specific failure (F-alpha-04) is the cleanest illustration:
useTypeahead's `useKeybindings` registers handlers but the chord registry
never resolves Esc → `autocomplete:dismiss`. Esc then falls through to
PromptInput which silently does nothing for the autocomplete (it has no
"clear suggestions" branch on Esc).

## Overlay × fix-type matrix

| Overlay | Mount path | `setToolJSX` arg | Already fixed? | Remaining gap |
|---|---|---|---|---|
| OnboardingFlow (boot) | `showDialog(root, ...)` at main.tsx:1514 | N/A — bare root.render | NO | Switch to `showSetupDialog` (root cause A) |
| OnboardingFlow (`/onboarding`) | `kosmosOnboardingMode` state in REPL.tsx:5802 | N/A — direct child of REPL | YES (works per F-delta-03) | none |
| AutocompleteDropdown (useTypeahead) | inline render via `useTypeahead({ context: 'Autocomplete' })` | N/A | NO | Add `Autocomplete` chord block (root cause B) |
| HelpV2Grouped (`/help`) | `setToolJSX({jsx: HelpV2Grouped, isLocalJSXCommand: false})` REPL.tsx:3469 | `false` ✓ | partial — has `useInput` Esc fallback | Add `Help` chord block so `useKeybinding('help:dismiss')` actually fires (defense-in-depth alignment with CC) |
| AgentsCommandView (`/agents`) | `setToolJSX(...)` REPL.tsx:3877 | `false` ✓ | partial — has direct `useInput` Esc fallback | none in this fix track (already wired) |
| ConfigOverlay (`/config`) | `setToolJSX({...isLocalJSXCommand: true})` REPL.tsx:3499 | `true` ✗ | — | Out of scope (G7); flagged for future |
| ConsentListView | `isLocalJSXCommand: false` ✓ | already correct |  | |
| ConsentRevokeConfirmDialog | `false` ✓ | already correct |  | |

The autocomplete + help + agents trio (F-alpha-04, F-alpha-05, F-delta-04,
F-ε-05) is closed by **adding Autocomplete + Help context blocks to
DEFAULT_BINDING_BLOCKS** (root cause B). The agents view already has the
defense-in-depth `useInput` fallback — it dismisses correctly once the
parent chord registry stops swallowing Esc on its own (because no other
context binds escape outside of Chat→draft-cancel and Select→cancel).

The onboarding trio (F-alpha-02, F-delta-01, F-delta-02) is closed by
**switching `main.tsx:1514` from `showDialog` to `showSetupDialog`** (root
cause A). The provider wrapping enables chord dispatch + restores the
React-context tree the `useApp().exit` and `emitSurfaceActivation` hooks
expect.

## Phase 1 — Instrumentation observations (already in repo)

- Parent `useInput` order (insertion-time): root.render order determines
  EventEmitter listener order; child `useInput` registered LATER fires
  AFTER parent unless `event.stopImmediatePropagation()` is called.
- PromptInput's main `useInput` at line 1932: `key.escape` branches do NOT
  call `event.stopImmediatePropagation()` — so the event SHOULD propagate.
  The actual gap is the chord registry, not propagation.
- AgentsCommandView already has direct `useInput` Esc fallback (line 117).
  It registers AFTER PromptInput because /agents mounts after REPL boots,
  so its handler fires SECOND in the listener list — Ink's listener-order
  semantics (last-registered fires last) means parent fires first, child
  fires second. With `isLocalJSXCommand: false` parent's `isModalOverlayActive`
  is `false` → parent does NOT call `event.stopImmediatePropagation()` →
  child Esc fires. So `/agents` SHOULD work. Wave 1 evidence claims it
  doesn't — needs Layer-5 verification post-fix.

## Phase 2 — Diff CC vs KOSMOS

```text
.references/claude-code-sourcemap/restored-src/src/keybindings/defaultBindings.ts
  17 context blocks total
  Includes: Global / Chat / HistorySearch / Confirmation / Select
            Autocomplete / Help / Settings / Tabs / Transcript / Task
            ThemePicker / Scroll / Attachments / Footer / MessageSelector
            MessageActions / DiffDialog / ModelPicker / Plugin

tui/src/keybindings/defaultBindings.ts (current)
  5 context blocks total
  Missing: Autocomplete / Help / Settings / Tabs / Transcript / Task /
           ThemePicker / Scroll / Attachments / Footer / MessageSelector /
           DiffDialog / ModelPicker / Plugin
```

Adding Autocomplete + Help is the minimum to close G2. Adding the rest is
out-of-scope for this fix track; flagged for follow-up (the action enums
already exist in `tui/src/keybindings/schema.ts` so adding the chord
blocks is bookkeeping-only).

```text
.references/claude-code-sourcemap/restored-src/src/interactiveHelpers.tsx
  Onboarding dialog uses showSetupDialog (with AppStateProvider + KeybindingSetup)

tui/src/main.tsx:1514
  KOSMOS onboarding gate uses showDialog (no providers).
```

## Phase 3 — Minimal fix scope

1. `tui/src/main.tsx:1514` — replace `showDialog` with `showSetupDialog`.
   Import added: `showSetupDialog` from `./interactiveHelpers.js`.
2. `tui/src/keybindings/defaultBindings.ts` — append two context blocks
   (`Autocomplete` + `Help`) to `DEFAULT_BINDING_BLOCKS`. No type changes;
   the actions are already in `KEYBINDING_ACTIONS` and contexts in
   `KEYBINDING_CONTEXTS`.

Zero new dependencies. No `setToolJSX` API changes. No refactor of
overlay components — existing defense-in-depth `useInput` Esc fallbacks
remain (they served as the only working dismissal path before this fix).

## Phase 4 — TDD

Snapshot tests (Layer 1b — `bun test` + `ink-testing-library`) per overlay:
- `HelpV2Grouped` Esc → calls `onDismiss` (with KeybindingProvider mounted).
- `AgentsCommandView` Esc → calls `onExit`.
- `OnboardingFlow` boot path with `showSetupDialog` wrapper renders
  PreflightStep and Enter advances to ThemeStep.

Layer 5 (tmux) re-runs of the original Wave 1 scenarios:
- α2 / α2b — onboarding preflight Enter advances within 5 s
- α3 — `/help` Esc dismisses, REPL prompt back within 2 s
- α4 — autocomplete Esc clears suggestions
- δ1 — first-run boot reaches REPL after 5-step onboarding
- δ2 — `KOSMOS_ONBOARDING_AUTO_COMPLETE=1` reaches REPL within 2 s
- δ4 — `/help` Esc dismiss + arrow keys not leaking
- ε6 — `/agents` Esc dismiss
