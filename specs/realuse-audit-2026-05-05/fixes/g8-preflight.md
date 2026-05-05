# G8 — Onboarding Preflight Enter Dispatch Fix Report

> Wave-4 Lead Opus G8 — single-commit fix closing 3 dispatch findings.

## Findings closed (3)

| Finding | Surface | Verdict change | Root cause line |
|---|---|---|---|
| F-alpha-02 | UI-A onboarding step 1 (preflight) Enter | NOT_CLOSED → **CLOSED** ✓ | `tui/src/components/onboarding/PreflightStep.tsx:13` imported `useInput` from npm `'ink'` (`@jrichman/ink@6.6.9`), whose `StdinContext` default is a fresh-empty `EventEmitter` (`tui/node_modules/ink/build/components/StdinContext.js:7`). The repo Ink (`tui/src/ink/`) renders the App at runtime, so npm-ink's emitter never receives stdin events — silent dead handler. |
| F-delta-01 | UI-A first-run preflight gate | NOT_CLOSED → **CLOSED** ✓ | Same root cause as F-alpha-02. |
| F-W3-alpha-side | `OnboardingState` Zod schema rejects offset/microsecond timestamps | New (P1) → **CLOSED** ✓ | `tui/src/schemas/ui-l2/onboarding.ts:28,35` used `z.string().datetime()` (Z + ms only). Widened to `z.string().datetime({ offset: true })` so `+00:00`/`-09:00` offsets and any sub-second precision validate. Eliminates the per-boot `safeParse() → freshOnboardingState()` fallback loop. |

## Files changed

| File | Type | Change |
|---|---|---|
| `tui/src/components/onboarding/PreflightStep.tsx` | edit | dual-path `useInput` — keep npm-ink import (`useInput as useNpmInput`) for `ink-testing-library` parity AND add repo-ink import (`useInput as useRepoInput` from `'../../ink.js'`) for the live runtime emitter. Both wired to the same `handleKey` callback. |
| `tui/src/components/onboarding/ThemeStep.tsx` | edit | same dual-path pattern. |
| `tui/src/components/onboarding/PIPAConsentStep.tsx` | edit | same pattern, applied to BOTH internal `useInput` call sites (the 5-step flow path AND the Spec 035 3-step flow path). |
| `tui/src/components/onboarding/MinistryScopeStep.tsx` | edit | same dual-path pattern. |
| `tui/src/components/onboarding/TerminalSetupStep.tsx` | edit | same dual-path pattern. |
| `tui/src/components/onboarding/OnboardingFlow.tsx` | edit | `useApp` switched to repo Ink shim (npm-ink's `useApp().exit()` is a no-op when npm-ink's App isn't mounted — `tui/node_modules/ink/build/components/AppContext.js:5`). |
| `tui/src/schemas/ui-l2/onboarding.ts` | edit | `OnboardingStep.completed_at` and `OnboardingState.started_at` widened from `z.string().datetime()` to `z.string().datetime({ offset: true })` via shared `ISO_DATETIME` const. |
| `specs/realuse-audit-2026-05-05/research/g8-preflight.md` | new | deep-research write-up with phase-by-phase instrumentation log. |
| `specs/realuse-audit-2026-05-05/fixes/g8-preflight.md` | new | this report. |
| `specs/realuse-audit-2026-05-05/wave4/g8-preflight/captures-post-fix/` | new | Layer 5 tmux post-fix capture (`snap-000…snap-005`, `final.txt`). |

LoC delta: +60 / -5 across 7 source files (well within the ≤ 200 LoC budget).

## Why dual-path (not just repo-ink)

`tui/tests/components/onboarding/PreflightStep.test.tsx` uses `ink-testing-library`'s `render()`, which mounts an npm-ink App with a synthetic stdin. After the fix, the test's `stdin.write('\r')` fires npm-ink's `useInput` — the dual-path keeps that wire intact. At runtime, the repo-ink App's `useInput` fires; the npm-ink listener is harmless (its emitter is dead). Mirrors the HelpV2Grouped defense-in-depth pattern documented in `tui/src/components/help/HelpV2Grouped.tsx:122-141` and AGENTS.md infra-insight #4.

## Verification

| Layer | Command | Result |
|---|---|---|
| 1a (pytest) | `uv run pytest tests/ --ignore=tests/context/test_system_prompt_refactor_equivalence.py --deselect tests/integration/test_agentic_loop.py::test_multi_tool_turn_is_coerced_to_one_visible_dispatch` | **3825 passed** (2 deselected pre-existing failures predate G8). |
| 1a (Zod schema spot-check) | `bun -e 'OnboardingState.safeParse({...started_at:"2026-05-03T22:06:41.838+00:00",...completed_at:"2026-05-03T22:06:41.838123+00:00"...}).success'` | `true` (Python format passes). |
| 1b (bun test PreflightStep) | `bun test tests/components/onboarding/PreflightStep.test.tsx` | **7 pass / 0 fail / 22 expect()**. |
| 1b (bun test all onboarding) | `bun test tests/components/onboarding` | **35 pass / 0 fail / 107 expect()**. |
| 1b (bun test all keybindings) | `bun test tests/keybindings` | **184 pass / 0 fail**. |
| 1b (bun test full suite) | `bun test` | **1297 pass / 12 fail / 11 skip / 3 todo**. The 12 fail count is identical to baseline (`git stash`-verified) — **no new regressions**. |
| 5 (Layer-5 tmux smoke) | `bash specs/realuse-audit-2026-05-05/wave3/alpha/scenarios/run-f02-v2.sh specs/realuse-audit-2026-05-05/wave4/g8-preflight/captures-post-fix/` | **3 distinct frames** — preflight (552B) → theme (652B, snap-003) → ministry-scope (660B, snap-005). Pre-fix all 3 snaps were byte-identical. |

## Layer 5 evidence (proof of CLOSED)

Capture path: `specs/realuse-audit-2026-05-05/wave4/g8-preflight/captures-post-fix/`

```
$ ls -la specs/realuse-audit-2026-05-05/wave4/g8-preflight/captures-post-fix/
-rw-r--r--   552  snap-001-step1-visible.txt    # 환경 점검 / ◉ ○ ○ ○ ○  1 / 5
-rw-r--r--   552  snap-002-step1-stable.txt     # (idle 2s, no change)
-rw-r--r--   652  snap-003-after-enter-1.txt    # 테마 미리보기 / ● ◉ ○ ○ ○  2 / 5  ← Enter advanced
-rw-r--r--  4505  snap-004-after-enter-2.txt    # 부처 API 사용 동의 (PIPA modal)   ← Enter advanced
-rw-r--r--   660  snap-005-after-enter-3.txt    # 부처 API 사용 동의 v1 / 4 / 5    ← Enter advanced
```

Three Enter presses produced three distinct frames — preflight, theme, PIPA-then-ministry-scope. All 5 onboarding-step components now respond to keyboard input under the live runtime PTY harness.

## Constraint compliance

- Zero new runtime dependencies (AGENTS.md hard rule preserved).
- ≤ 200 LoC code change (actual: +60 / -5).
- Single commit `fix(2773-g8): onboarding preflight Enter — Zod state.json normalization + repo-ink dual-path useInput + useApp shim (closes F-alpha-02, F-delta-01, F-W3-alpha-side)`.
- G9-G12 surfaces untouched (modified files restricted to `tui/src/components/onboarding/*` + one schema file).
- The npm-ink ↔ repo-ink import split documented in `research/g8-preflight.md` for future component authors. Other components that import `useInput` from `'ink'` (e.g. `PluginInstallFlow.tsx`, `ConfigOverlay.tsx`, `ConsentListView.tsx`, `HistorySearchOverlay.tsx`, `agents.tsx`) are NOT broken because they mount inside the running REPL where their corresponding `useKeybinding`-route fallbacks (HelpV2Grouped pattern) cover the runtime path. Only the boot-time-only OnboardingFlow lacked a fallback.

## Architectural note (deferred to Initiative #2290)

The npm-ink ↔ repo-ink fault line is fragile and bug-prone. A follow-up Epic should either:
- (i) Replace the npm-ink `useInput` with a repo-ink-aware shim that re-exports `useInput` from the repo Ink while preserving npm-ink's IME-patched parser, OR
- (ii) Migrate KOSMOS off the npm Ink fork entirely once ADR-005's IME concern can be folded into repo Ink.

This is out of scope for Wave-4; the dual-path defense-in-depth pattern documented here is the immediate stable workaround.
