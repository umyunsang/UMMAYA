# Wave-3 α Re-smoke — P0 Verification Report

> Auditor: Wave-3 re-smoke α agent · Date: 2026-05-05  
> HEAD: `995b88bb` (PR #2771 merged — Wave-2 G1/G2/G5/G6/G7 fixes integrated)  
> Method: tmux capture-pane + wait_for_pane (no hardcoded Sleep)  
> Scope: F-alpha-02, F-alpha-08, F-alpha-09, F-alpha-13, F-alpha-15  

## P0 Verdict Table

| Finding | G-fix | Wave-3 verdict | Notes |
|---|---|---|---|
| F-alpha-15 | G1 | CLOSED | PIPA gate freezes at step 3/5 without KOSMOS_PIPA_CONSENT |
| F-alpha-08 | G5 | CLOSED | sanitizeThinking redacts available_adapters/tool_id/adapter IDs |
| F-alpha-13 | G6 | CLOSED | Unit 14/14 PASS; write + read side both implemented |
| F-alpha-02 | G2 | NOT_CLOSED | Enter still no-op at preflight step 1/5 in tmux |
| F-alpha-09 | G5 | PARTIAL | G5 explicitly deferred Patch C (Messages.tsx grouping) |

## F-alpha-15 — PIPA fail-closed (G1) — CLOSED

Wave-1: AUTO_COMPLETE=1 advanced all 5 steps including pipa-consent.
Wave-3 snap-001 (no PIPA_CONSENT):
  PIPA 동의 / ● ● ◉ ○ ○  3 / 5
  [Y/Enter] 동의하고 계속 · [N/Esc] 동의하지 않고 종료
  After 5s (snap-002): IDENTICAL — no auto-advance, no REPL prompt.
Wave-3 positive (with-pipa-consent/snap-002): REPL reached (❯ visible).
Capture: wave3/alpha/captures/f-alpha-15/

## F-alpha-08 — Ctrl-O sanitizer (G5) — CLOSED

Wave-1: available_adapters / tool_id / kma_* ids visible in thinking.
Wave-3 snap-004-after-ctrl-o:
  <⟨내부⟩>를 보면 현재 날씨 관련 도구는 두 가지가 있습니다:
  1. ⟨adapter⟩ - 현재 날씨 기온 강수 습도 풍속
  Korean prose preserved verbatim. Ctrl-O toggle works (expand/collapse).
Capture: wave3/alpha/captures/f-alpha-08/

## F-alpha-09 — Thinking order partial fix (G5) — PARTIAL

G5 fixes/g5-render.md: Patch C (Messages.tsx grouping) explicitly DEFERRED.
Wave-3: Thinking-before-tool ordering correct in snap-005 (∴ before ⏺).
Trailing thinking after multi-turn completion not tested (session in-flight).
No regression introduced by G5.

## F-alpha-13 — --continue cwd-scoped (G6) — CLOSED

Wave-3: bun test src/utils/__tests__/continueResolver.shell-context.test.ts
  14 pass / 0 fail / 17 expect() calls
Write: sessionStorage.ts:1092 stamps originalShellId: getShellContextId()
Read:  conversationRecovery.ts:521-522 filters by pickByShellContextId
Test 9 directly reproduces F-alpha-13 cross-shell ordering scenario.
Capture: wave3/alpha/captures/f-alpha-13/

## F-alpha-02 — Onboarding preflight Enter (G2) — NOT_CLOSED

Wave-1: Enter no-op at step 1/5.
G2 fix: showDialog → showSetupDialog (AppStateProvider + KeybindingSetup).
Wave-3 run-f02-v2.sh: 3 Enter presses over 6s, all frames identical:
  ◉ ○ ○ ○ ○  1 / 5 / 다음 (Enter) · 이전 (Esc)
PreflightStep.useInput(key.return → onAdvance()) does not fire.
Suspected cause: Chat context binding (enter: chat:submit) in
defaultBindings.ts is active and ChordInterceptor dispatches to chat:submit
before PreflightStep raw useInput sees the event, OR AppStateProvider
mount path still has a provider gap not covered by showSetupDialog.
Capture: wave3/alpha/captures/f-alpha-02/v2/

## Side-finding (not P0): state.json datetime format

~/.kosmos/memdir/user/onboarding/state.json timestamps use +00:00 +
microseconds (Python format) rejected by Zod z.string().datetime() (Z +
milliseconds only). OnboardingState.safeParse() always falls back to
freshOnboardingState() — onboarding shows on every boot on this machine.
Recommend: z.string().datetime({ offset: true }) + microsecond normalization.
