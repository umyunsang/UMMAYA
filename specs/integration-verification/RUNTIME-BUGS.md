# Integration Verification Runtime Bugs — Layer 5 발견

> 2026-05-03 Initiative #2636 (CC migration audit) 5 Epic 머지 후 사용자 요청 통합 검증.
> Layer 1 baseline (pytest + bun test + typecheck) 모두 PASS 였으나 Layer 5 interactive
> tmux 시나리오에서 6 runtime bug 발견. 본 문서는 발견 내용 + fix 박제.

## 검증 환경
- main HEAD: 46a8fcfc (Epic G #2643 머지 직후)
- 디버깅 인프라: `scripts/tui-tmux-capture.sh` (Spec debug-infra-rebuild RFC § P2)
- frame 박제: `specs/integration-verification/frames/01..07-*/`

## 발견 버그 + Fix 매트릭스

| # | 위치 | 증상 | Severity | Fix |
|---|---|---|---|---|
| 1 | `tui/src/components/onboarding/PreflightStep.tsx:78,83` | env var 이름 mismatch (`FRIENDLI_API_KEY` / `KOSMOS_DATA_GO_KR_KEY` only — 실제 .env 는 `KOSMOS_FRIENDLI_TOKEN` / `KOSMOS_DATA_GO_KR_API_KEY`) | UX (onboarding 항상 ✗) | canonical+alias 둘 다 체크 (envGuard.ts / useApiKeyVerification.ts 와 동일) |
| 2 | `tui/src/cli/print.ts:141` | 존재하지 않는 `src/services/policyLimits/index.js` import (Spec 1633 P1+P2 에서 service 제거됨) | **Critical · boot crash** | inline stub `const isPolicyAllowed = (_) => true` + SWAP 박제 |
| 3 | `tui/src/main.tsx:1511` | `require('./components/onboarding/OnboardingFlow.js')` — Bun 이 async module 의 sync require 거부 (`TypeError: require() async module ... unsupported`) | **Critical · Onboarding mount 실패** | `await import()` 으로 변환 |
| 4 | `tui/src/i18n/uiL2.ts` | `langChanged` toast 가 bundle 에 없음 → REPL.tsx 가 hardcoded 한국어 toast 사용 | UX (lang en 후에도 한국어 toast) | UiL2Bundle 에 `langChanged: (locale) => string` 추가 + KO/EN 구현 |
| 5 | `tui/src/screens/REPL.tsx:3641` | `/lang` toast text 가 hardcoded 한국어 | UX | `getUiL2I18n(langResult.locale).langChanged(...)` 으로 i18n 적용 |
| 6 | `scripts/tui-tmux-capture.sh:94` | `send_text_pane` 가 `tmux send-keys` 에 `-l` literal flag 안 줌 → `"/lang en"` 의 space 가 "Space" key 로 해석됨 | Test infra | `-l` 플래그 추가 (literal byte 전송) |

## Layer 1 PASS / Layer 5 FAIL 모순
Layer 1 (`pytest` + `bun test` + `bun typecheck`) 모두 PASS 인데 Layer 5 boot 가 즉시 crash (#2, #3) — Test coverage gap. AGENTS.md memory `feedback_pr_pre_merge_interactive_test` 위반의 산 증거. 5 Epic 머지 직전 CI 가 interactive boot 검증을 한 번도 안 함.

## 잔존 (별도 issue 추적)
- **#4-deferred — Onboarding `showDialog` Enter routing**: PreflightStep 의 `useInput` 가 tmux 자동화에서 Enter key 받지 못하는 듯 (또는 `useKoreanIME.isComposing` 영구 true). 우회: `~/.kosmos/memdir/user/onboarding/state.json` 의 `current_step_index: 5` 로 수동 마킹 시 정상 동작. 근본 원인은 React state architecture (Ink useInput + showDialog wrapper) 정밀 진단 필요.
- **#5-deferred — `/lang ko` 후 mounted HelpV2 re-render 안 됨**: process.env mutation 만으로 React component 가 useUiL2I18n() 재평가 안 함. 신규 mount 만 ko 적용. 근본 fix 는 lang command 가 React state 변경 트리거 (e.g., context provider 또는 forceUpdate key prop).
- **#7-deferred — `/consent list` panel 뷰 미구현**: footer toast "P5에서 패널 뷰 추가 예정" 표시. 요구사항 spec 차후.

## Verification
- `bun typecheck` PASS exit 0
- `bun test` 983 pass / 11 skip / 3 todo / 0 fail
- Layer 5 boot post-fix: KOSMOS branding + UFO mascot + REPL prompt 정상 렌더 (frames/04-onboarding-complete/ 박제)
