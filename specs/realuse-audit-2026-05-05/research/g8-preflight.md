# G8 — Onboarding Preflight Enter Dispatch (research)

> Wave-4 Lead Opus G8 — F-alpha-02 + F-delta-01 + F-W3-alpha-side root-cause excavation.

## Symptom

Step 1/5 (PreflightStep) Enter is a no-op in tmux/Bun-PTY. Two prior fix attempts (Wave-2 G2 — `showSetupDialog` provider wrap; Wave-3 re-smoke verification) confirmed the dispatch path was still dead. Wave-3 hypothesis: ChordInterceptor routing `enter → chat:submit` was eating the keystroke before PreflightStep's `useInput((_, key) => key.return && onAdvance())` could fire.

## Hypothesis space (entering Wave-4)

1. (a) PreflightStep needs `setToolJSX({isLocalJSXCommand: true})`.
2. (b) Lower priority of `Chat` chord during onboarding context.
3. (c) Register `onboarding:advance` action in `defaultBindings.ts` + use `useKeybinding` properly.
4. (d) The **F-W3-alpha-side** Zod-rejection theory — `safeParse()` falls back to `freshOnboardingState()` every boot, so onboarding never advances *because the state never persists*.

None of (a)/(b)/(c) is correct. (d) is real but is NOT the root cause of the Enter no-op (it would only loop step 1 between sessions, not freeze step 1 within a session). The actual root cause was unobservable at the Wave-2/Wave-3 level: **the `useInput` hook in PreflightStep registers on the wrong EventEmitter.**

## Phase 1 — instrument keystroke flow

Approach: tee write `/tmp/g8-*.log` from each candidate stage:

| Stage | Log | Outcome |
|---|---|---|
| `tui/src/keybindings/KeybindingProviderSetup.tsx::ChordInterceptor` | `/tmp/g8-chord.log` | **3 entries on 3 Enter presses, all `result={"type":"none"}` ctx=`["Global"]`. NO `stopImmediatePropagation()` called.** |
| `tui/src/components/onboarding/PreflightStep.tsx::useInput` callback | `/tmp/g8-preflight.log` | **0 entries. Handler never fires.** Mount log fired (`useEffect` → `[PREFLIGHT mounted/effect]`). |
| `tui/src/ink/hooks/use-input.ts::useEffect` listener register | `/tmp/g8-uselisteners.log` | 46 listeners accumulated by step 1/5; previous dialog trees never unmounted their useInput hooks (NPM-ink ↔ repo-ink emitter mismatch keeps refs alive). |

**Smoking gun**: ChordInterceptor sees Enter (so the keystroke reaches at least one repo-ink listener), but PreflightStep's listener — even though registered as a regular `useInput` — never fires.

## Phase 2 — diff KOSMOS vs CC restored-src

`docs/adr/ADR-005-korean-ime-strategy.md` swaps the `'ink'` package import to `npm:@jrichman/ink@6.6.9` (Hangul IME composition fix). At the same time, KOSMOS preserves a CC-source-mapped Ink reimplementation at `tui/src/ink/` that is **only** loadable through the explicit shim `tui/src/ink.ts` (`import { useInput } from '../../ink.js'`).

Components inside the app split along this fault line:

| Importer pattern | Resolves to | StdinContext |
|---|---|---|
| `import { useInput } from '../../ink.js'` | repo Ink (`tui/src/ink/hooks/use-input.ts`) | repo `tui/src/ink/components/StdinContext.tsx` |
| `import { useInput } from 'ink'` | npm `@jrichman/ink@6.6.9` (`tui/node_modules/ink/build/hooks/use-input.js`) | npm `tui/node_modules/ink/build/components/StdinContext.js` |

These are **two different React contexts** with two different default values. The `tui/src/ink.ts::createRoot` (used by `interactiveHelpers.showSetupDialog`) renders the App component **from the repo Ink only** — npm-ink's App is never instantiated, so npm-ink's `StdinContext` falls through to its module-level default (a fresh `EventEmitter` that nobody emits to: `tui/node_modules/ink/build/components/StdinContext.js:7`).

## Root cause

`tui/src/components/onboarding/PreflightStep.tsx:13` (and four sibling step files) imports `useInput` from `'ink'` (npm). Each `useInput` call subscribes a listener to npm-ink's default-empty `internal_eventEmitter`. **No stdin event ever reaches that emitter at runtime**, so the `key.return` branch never fires — the citizen presses Enter, the keystroke is delivered into repo-ink's `App.processInput` → repo-ink's emitter → repo-ink-side `useInput` hooks (ChordInterceptor) only.

PreflightStep's npm-ink `useInput` is a **silent dead handler**.

## Why HelpV2 dismiss "works" (cross-validation)

`tui/src/components/help/HelpV2Grouped.tsx:132` registers BOTH paths:

```tsx
useKeybinding('help:dismiss', () => onDismiss?.(), { context: 'Help' });
useInput((_input, key) => { if (key.escape) onDismiss?.() });  // npm-ink, defense-in-depth
```

In tmux, the npm-ink `useInput` is silently dead, but `useKeybinding` (which lives in `tui/src/keybindings/useKeybinding.ts`, `import { useInput } from '../ink.js'` — repo-ink) DOES fire on the live emitter and resolves `Esc` → `help:dismiss` via the chord registry. That's why F-delta-04 closed in Wave-3.

In `ink-testing-library` tests the App is rendered by npm-ink (the test harness's `render()` mounts npm-ink's App with a custom stdin), so npm-ink's StdinContext is wired and the `useInput` fallback DOES fire. That's why the G2 overlay-dismiss tests (`tui/tests/keybindings/g2-overlay-dismiss.test.tsx:32+`) pass.

PreflightStep had **only** the npm-ink `useInput` — no repo-ink path — so it worked in tests but was dead at runtime.

## context7 query: `zod datetime offset microsecond`

Local repro:

```
> bun -e 'const z = require("zod"); const s = z.string().datetime({offset: true}); console.log(s.safeParse("2026-05-03T22:06:41.838+00:00").success)'
true
> ... s.safeParse("2026-05-03T22:06:41.838123+00:00").success
true
> ... s.safeParse("2026-05-03T22:06:41.838Z").success
true
```

`{offset: true}` accepts BOTH `Z` and `±HH:MM` offsets, AND any precision up to 9 fractional digits. No `precision` opt needed.

## AGENTS.md infra-insight #3 — `isLocalJSXCommand` deeper trace

PromptInput.tsx:244 sets `isModalOverlayActive = useIsModalOverlayActive() || isLocalJSXCommandActive`. **PromptInput is not mounted during boot-time onboarding** (the OnboardingFlow tree is the only top-level component), so `isLocalJSXCommandActive` is irrelevant here. Hypothesis (a) was a red herring.

`showSetupDialog` mounts the OnboardingFlow inside `<AppStateProvider><KeybindingSetup>` at `tui/src/interactiveHelpers.tsx:89`. The Wave-2 G2 fix correctly wired the chord registry — that's why ChordInterceptor sees Enter. The bug was *one layer down*, in the npm-ink/repo-ink import split.

## Fix taxonomy

Three minimal changes (≤ 200 LoC budget):

1. **Repo-ink dual-path in onboarding step components** — keep the existing `'ink'` (npm) `useInput` as the test-side path AND add a `'../../ink.js'` (repo) `useInput` as the runtime-side path. Mirrors HelpV2Grouped's defense-in-depth pattern. Five files: PreflightStep, ThemeStep, PIPAConsentStep, MinistryScopeStep, TerminalSetupStep.
2. **OnboardingFlow `useApp` switched to repo Ink** — same fault line: `useApp().exit()` from npm-ink is a no-op (`tui/node_modules/ink/build/components/AppContext.js:5`). Repo-ink shim (`tui/src/ink.ts:74`) routes to the live App.
3. **Zod schema `{offset: true}`** — `tui/src/schemas/ui-l2/onboarding.ts` widens both `started_at` and `completed_at` to accept any ISO-8601 offset + any sub-second precision. Eliminates the F-W3-alpha-side onboarding-loop.

## Phase 4 — TDD verification

- Layer 1b — `tui/tests/components/onboarding/PreflightStep.test.tsx` (7 pass). The dual-path keeps the npm-ink listener, so `ink-testing-library`'s `stdin.write('\r')` still fires `onAdvance` in-test.
- Layer 5 — `bash specs/realuse-audit-2026-05-05/wave3/alpha/scenarios/run-f02-v2.sh /tmp/post-fix-final/` cycles preflight → theme → ministry-scope (3 Enter presses, 3 distinct frames). Pre-fix snap diff was empty; post-fix snap-001 (552B) ≠ snap-003 (652B) ≠ snap-005 (660B).
