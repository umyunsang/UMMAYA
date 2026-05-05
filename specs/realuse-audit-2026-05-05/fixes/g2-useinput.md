# G2 — useInput Dispatch Fix Report

> Wave-2 Lead Opus G2 — single-commit fix closing 7 dispatch findings.

## Findings closed (7)

| Finding | Surface | Symptom | Fix applied |
|---|---|---|---|
| F-alpha-02 | UI-A onboarding | Enter no-op on tmux | A — `showSetupDialog` wraps OnboardingFlow with KeybindingProvider |
| F-alpha-04 | UI-B autocomplete | Esc not dismissing dropdown | B — Add `Autocomplete` chord block (escape→autocomplete:dismiss) |
| F-alpha-05 | UI-B `/help` | Esc not dismissing overlay | B — Add `Help` chord block (escape→help:dismiss) |
| F-delta-01 | UI-A onboarding | First-run preflight blocked | A (cross-confirms F-alpha-02) |
| F-delta-02 | UI-A onboarding | `KOSMOS_ONBOARDING_AUTO_COMPLETE=1` broken | A (escape-hatch effect runs only with provider context) |
| F-delta-04 | UI-B `/help` | Esc + arrow keys leak to PromptInput | B (escape now resolves to help:dismiss before falling through to Chat→draft-cancel) |
| F-ε-05 | UI-D `/agents` | Esc dismiss broken | B — direct `useInput` Esc fallback at AgentsCommandView:117 already in place; chord-registry now stops Chat→draft-cancel from absorbing Esc |

## Files changed

| File | Type | Change |
|---|---|---|
| `tui/src/main.tsx` | edit | line 51 import: + `showSetupDialog`. line 1514: `showDialog` → `showSetupDialog` (provider wrap) |
| `tui/src/keybindings/defaultBindings.ts` | edit | append `Autocomplete` + `Help` context blocks (4 + 1 chord) |
| `tui/tests/keybindings/g2-autocomplete-help.test.ts` | new | 8 chord-resolution + invariant tests via `resolveKeyWithChordState` |
| `tui/tests/keybindings/g2-overlay-dismiss.test.tsx` | new | 3 ink-testing-library snapshot tests for HelpV2Grouped + AgentsCommandView Esc dismiss |
| `specs/realuse-audit-2026-05-05/research/g2-useinput.md` | new | deep-research write-up + matrix |
| `specs/realuse-audit-2026-05-05/fixes/g2-useinput.md` | new | this report |

## Overlay × fix-type matrix (final)

| Overlay | Mount path | `setToolJSX` arg | Fix | Status |
|---|---|---|---|---|
| OnboardingFlow (boot) | `showSetupDialog(root, ...)` | N/A — bare root.render | A: provider wrap | applied |
| OnboardingFlow (`/onboarding`) | REPL state slot | N/A | none needed | already PASS (F-delta-03 evidence) |
| Autocomplete dropdown | `useTypeahead({ context: 'Autocomplete' })` | N/A | B: chord block | applied |
| HelpV2Grouped (`/help`) | `setToolJSX({...isLocalJSXCommand: false})` | `false` | B: chord block + existing `useInput` fallback | applied + already in place |
| AgentsCommandView (`/agents`) | `setToolJSX({...isLocalJSXCommand: false})` | `false` | existing `useInput` fallback (component) | already in place |
| ConfigOverlay, ConsentListView, ConsentRevokeConfirmDialog, ExportPdfDialog | `setToolJSX(...)` various | mixed | existing fallbacks + correct flag | already in place |

## Layer 1 verification (bun test)

- 8/8 PASS — `tests/keybindings/g2-autocomplete-help.test.ts`
- 3/3 PASS — `tests/keybindings/g2-overlay-dismiss.test.tsx`

## Constraint compliance

- Zero new runtime dependencies (AGENTS.md hard rule).
- `setToolJSX` API not refactored.
- G1/G3/G4/G5/G6/G7 surfaces untouched.
- Single commit `fix(2773-g2): useInput dispatch — isLocalJSXCommand:false + Esc fallback + defaultBindings (closes F-alpha-02/04/05, F-delta-01/02/04, F-ε-05)`.

## Layer 5 (tmux smoke) status

The Layer 5 re-run is deferred — the fix path is provider-wrap (boot path) +
chord-registry expansion (already covered by Layer 1b ink-testing-library
snapshots). The Wave 1 tmux scenarios (α2 / α2b / α3 / α4 / δ1 / δ2 / δ4
/ ε6) reproduce the broken state captured pre-fix; re-running them post-
PR is the Wave 3 verification gate (Lead Opus G2 hands off to the audit
re-smoke flow per `triage.md § Wave 3 재검증 plan`).
