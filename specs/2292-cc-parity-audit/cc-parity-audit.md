# CC Parity Audit — Epic α deliverable (Initiative #2290)

**Date**: 2026-04-29
**Status**: Read-only audit complete
**Authority**:
- `AGENTS.md § CORE THESIS` — KOSMOS = AX-infrastructure callable-channel client
- `specs/1979-plugin-dx-tui-integration/cc-source-scope-audit.md § 1.1, § 1.2, § 3 (Phase α)` — 1,531 / 73 / 212 / 274 / 68 baseline
- `specs/1979-plugin-dx-tui-integration/delegation-flow-design.md § 12` — final canonical architecture
- `.references/claude-code-sourcemap/restored-src/` — CC 2.1.88 byte-identical source-of-truth (research-only)
- `specs/2292-cc-parity-audit/spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Spec mapping**: This deliverable satisfies spec.md FR-001 ~ FR-010 and SC-001 ~ SC-007.

---

## 0. Executive summary

| Metric | Actual | Baseline (cc-source-scope-audit) | Delta |
|---|---|---|---|
| keep-byte-identical | 1531 | 1531 | +0 |
| import-candidate    | 67 | 73 | -6 |
| modified (strictly) | 218 | 212 | +6 |
| kosmos-only         | 274 | 274 | +0 |
| cc-only             | 68 | 68 | +0 |
| **differing union** | 285 | 285 | +0 |

**Verdict**: Total file membership matches baseline exactly. Only an internal -6/+6 boundary shift between import-candidate and strictly-modified. spec.md FR-001 audit table will use actual count 218 (was 212); cc-parity-audit.md narrative documents the drift.

Modified file classification result:

| Classification | Count | % of 218 |
|---|---|---|
| Legitimate     | 188 | 86% |
| Cleanup-needed | 30 | 13% |
| Suspicious     | 0 | 0% |

Parity spot-check: **50/50 byte-identical match** (seed=2292). Wilson 95% lower bound ≈ 92.9% parity confidence over the 1,531-file population.

Import-only diff verification: **67/67 confirmed import-only**, 0 reclassified to modified.


## 1. Drift notes

이 audit 시점 (2026-04-29) 의 baseline 대비 카테고리 boundary 가 일부 이동했다:

- **import-candidate**: actual 67 (baseline 73, delta -6). 6 files reclassified from import-only → strictly-modified since baseline (likely body content drift in services/ during Spec 1633 in-progress).
- **modified**: actual 218 (baseline 212, delta +6). +6 corresponds 1:1 to import-candidate -6. Internal boundary shift only — total differing union (modified + import-candidate) = 285, identical to baseline (212+73).

총 differing union 은 baseline 과 정확히 동일 (285건). 본 audit 는 actual 숫자를 권위 numeric 으로 채택한다 (FR-010).


## 2. Modified Files (T009 · spec.md FR-001 / FR-004 / SC-001)

전체 218 행. 자동 분류 + Lead 수동 검토 (T007) 완료. 분류별 행은 GFM markdown 표로 박제. 변경 사유와 reference citation 모든 행 채움.

<details>
<summary>전체 표 펼치기 (218 rows)</summary>

| # | kosmos_path | classification | change_summary | reference |
|---|---|---|---|---|
| 1 | tui/src/QueryEngine.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 2 | tui/src/Tool.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 3 | tui/src/assistant/sessionHistory.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 1978 |
| 4 | tui/src/bridge/bridgeConfig.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 5 | tui/src/bridge/bridgeMain.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 6 | tui/src/bridge/createSession.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 7 | tui/src/bridge/inboundMessages.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 8 | tui/src/bridge/initReplBridge.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 9 | tui/src/bridge/trustedDevice.ts | Legitimate | KOSMOS 인프라 디렉토리 (tui/src/bridge/) — 정당 변경 | Spec 287 (TUI Ink+React+Bun) 또는 Spec 032 (IPC std… |
| 10 | tui/src/cli/handlers/auth.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 11 | tui/src/cli/print.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: @anthropic-ai/, queryHaiku | Spec 1633 closure pending |
| 12 | tui/src/commands.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 1979, 2112 |
| 13 | tui/src/commands/bridge/bridge.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 14 | tui/src/commands/cost/cost.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 15 | tui/src/commands/fast/fast.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 16 | tui/src/commands/feedback/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 17 | tui/src/commands/insights.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryWithModel | Spec 1633 closure pending |
| 18 | tui/src/commands/privacy-settings/privacy-settings.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 19 | tui/src/commands/rate-limit-options/rate-limit-options.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 20 | tui/src/commands/remote-env/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 21 | tui/src/commands/remote-setup/api.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 1978 |
| 22 | tui/src/commands/remote-setup/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 23 | tui/src/commands/rename/generateSessionName.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 24 | tui/src/commands/review/reviewRemote.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |
| 25 | tui/src/commands/ultraplan.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 26 | tui/src/components/Feedback.tsx | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 27 | tui/src/components/FeedbackSurvey/useFeedbackSurvey.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 28 | tui/src/components/FeedbackSurvey/useMemorySurvey.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 29 | tui/src/components/FeedbackSurvey/usePostCompactSurvey.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 30 | tui/src/components/HelpV2/HelpV2.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 31 | tui/src/components/IdeOnboardingDialog.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 32 | tui/src/components/LogoV2/AnimatedClawd.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632 |
| 33 | tui/src/components/LogoV2/Clawd.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632 |
| 34 | tui/src/components/LogoV2/CondensedLogo.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 35 | tui/src/components/LogoV2/LogoV2.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 36 | tui/src/components/LogoV2/Opus1mMergeNotice.tsx | Legitimate | KOSMOS-only 토큰 (EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 37 | tui/src/components/LogoV2/WelcomeV2.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 38 | tui/src/components/Markdown.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632 |
| 39 | tui/src/components/Messages.tsx | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 40 | tui/src/components/PromptInput/Notifications.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 41 | tui/src/components/PromptInput/PromptInput.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 42 | tui/src/components/PromptInput/PromptInputFooterLeftSide.tsx | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 43 | tui/src/components/PromptInput/usePromptInputPlaceholder.ts | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 44 | tui/src/components/RemoteEnvironmentDialog.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 45 | tui/src/components/ResumeTask.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 46 | tui/src/components/StatusLine.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 47 | tui/src/components/TeleportProgress.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 48 | tui/src/components/agents/generateAgent.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 49 | tui/src/components/mcp/MCPRemoteServerMenu.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 50 | tui/src/components/messages/AssistantTextMessage.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 51 | tui/src/components/messages/RateLimitMessage.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 52 | tui/src/components/tasks/BackgroundTasksDialog.tsx | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 53 | tui/src/components/tasks/RemoteSessionDetailDialog.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 54 | tui/src/constants/figures.ts | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 55 | tui/src/constants/messages.ts | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 56 | tui/src/constants/prompts.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, friendli) 식별 — 정당 변경 | Spec ids in git log: 1632, 1634, 1637, 2077 |
| 57 | tui/src/constants/xml.ts | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 58 | tui/src/cost-tracker.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 59 | tui/src/entrypoints/cli.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 1978 |
| 60 | tui/src/entrypoints/init.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2077 |
| 61 | tui/src/entrypoints/sdk/coreSchemas.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 62 | tui/src/hooks/notifs/useMcpConnectivityStatus.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 63 | tui/src/hooks/notifs/useNpmDeprecationNotification.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 2077 |
| 64 | tui/src/hooks/notifs/useRateLimitWarningNotification.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 65 | tui/src/hooks/toolPermission/permissionLogging.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 66 | tui/src/hooks/useApiKeyVerification.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 67 | tui/src/hooks/useAssistantHistory.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 68 | tui/src/hooks/useCanUseTool.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 69 | tui/src/hooks/useDirectConnect.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 70 | tui/src/hooks/useRemoteSession.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 71 | tui/src/hooks/useSSHSession.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 72 | tui/src/hooks/useTerminalSize.ts | Legitimate | Spec id 인용 (1632, 1637) — git 기록 기반 정당 변경 | Specs: #1632, #1637 |
| 73 | tui/src/hooks/useVirtualScroll.ts | Legitimate | Spec id 인용 (1632, 1637, 287) — git 기록 기반 정당 변경 | Specs: #1632, #1637, #287 |
| 74 | tui/src/interactiveHelpers.tsx | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 75 | tui/src/keybindings/KeybindingProviderSetup.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 288 |
| 76 | tui/src/keybindings/defaultBindings.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1635, 1637, 288 |
| 77 | tui/src/keybindings/loadUserBindings.ts | Legitimate | Spec id 인용 (1632, 1637, 288) — git 기록 기반 정당 변경 | Specs: #1632, #1637, #288 |
| 78 | tui/src/keybindings/match.ts | Legitimate | Spec id 인용 (1632, 1637, 288) — git 기록 기반 정당 변경 | Specs: #1632, #1637, #288 |
| 79 | tui/src/keybindings/parser.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 288 |
| 80 | tui/src/keybindings/resolver.ts | Legitimate | KOSMOS-only 토큰 (kosmos) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 288 |
| 81 | tui/src/keybindings/template.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 288 |
| 82 | tui/src/keybindings/useKeybinding.ts | Legitimate | Spec id 인용 (1632, 1637, 288) — git 기록 기반 정당 변경 | Specs: #1632, #1637, #288 |
| 83 | tui/src/keybindings/validate.ts | Legitimate | Spec id 인용 (1632, 1637, 288) — git 기록 기반 정당 변경 | Specs: #1632, #1637, #288 |
| 84 | tui/src/main.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos) 식별 — 정당 변경 | Spec ids in git log: 1635, 1637, 1978, 2077, 2152 |
| 85 | tui/src/query.ts | Legitimate | Spec id 인용 (1632, 1633, 2152) — git 기록 기반 정당 변경 | Specs: #1632, #1633, #2152 |
| 86 | tui/src/query/deps.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2077 |
| 87 | tui/src/replLauncher.tsx | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 88 | tui/src/screens/REPL.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1978, 1979, 2077, 2152 |
| 89 | tui/src/server/directConnectManager.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 90 | tui/src/services/PromptSuggestion/promptSuggestion.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 91 | tui/src/services/analytics/config.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 92 | tui/src/services/analytics/firstPartyEventLogger.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2077 |
| 93 | tui/src/services/analytics/growthbook.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 94 | tui/src/services/analytics/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |
| 95 | tui/src/services/analytics/metadata.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 96 | tui/src/services/api/adminRequests.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 97 | tui/src/services/api/claude.ts | Resolved by Spec 2521 byte-copy | Anthropic / Spec 033 잔재 토큰 감지: verifyApiKey, queryHaiku, qu… — byte-copy(2521) commit 3175862 replaces 1101 LOC with CC 3419 LOC original; swap commits 4d6b9a1 / 3139e4c / 07d23f8 layered on top. Old residues eliminated. | Spec 2521 commit: 3175862 · Closure date: 2026-05-01 |
| 98 | tui/src/services/api/client.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: verifyApiKey | Spec 1633 closure pending |
| 99 | tui/src/services/api/errorUtils.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 100 | tui/src/services/api/errors.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 101 | tui/src/services/api/filesApi.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 102 | tui/src/services/api/firstTokenDate.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 103 | tui/src/services/api/grove.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 104 | tui/src/services/api/logging.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 105 | tui/src/services/api/overageCreditGrant.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 106 | tui/src/services/api/promptCacheBreakDetection.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 107 | tui/src/services/api/referral.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 108 | tui/src/services/api/sessionIngress.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 109 | tui/src/services/api/ultrareviewQuota.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 110 | tui/src/services/api/usage.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 111 | tui/src/services/api/withRetry.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/services/api/ | Spec 1633 closure pending |
| 112 | tui/src/services/awaySummary.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 2077 |
| 113 | tui/src/services/claudeAiLimits.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2077 |
| 114 | tui/src/services/compact/autoCompact.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 115 | tui/src/services/compact/compact.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 116 | tui/src/services/compact/postCompactCleanup.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 117 | tui/src/services/compact/prompt.ts | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 118 | tui/src/services/mcp/auth.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 119 | tui/src/services/mcp/claudeai.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2077 |
| 120 | tui/src/services/mcp/client.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 121 | tui/src/services/mcp/config.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 122 | tui/src/services/mcp/xaaIdpLogin.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 123 | tui/src/services/oauth/client.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 124 | tui/src/services/oauth/getOauthProfile.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 125 | tui/src/services/oauth/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 126 | tui/src/services/plugins/pluginCliCommands.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 127 | tui/src/services/settingsSync/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 128 | tui/src/services/teamMemorySync/index.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 129 | tui/src/services/tokenEstimation.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: anthropic-sdk | Spec 1633 closure pending |
| 130 | tui/src/services/toolUseSummary/toolUseSummaryGenerator.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 131 | tui/src/services/tools/toolExecution.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 132 | tui/src/services/vcr.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 133 | tui/src/services/voiceStreamSTT.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 134 | tui/src/setup.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 135 | tui/src/skills/bundled/debug.ts | Legitimate | KOSMOS-only 토큰 (kosmos) 식별 — 정당 변경 | Spec ids in git log: 1632, 1634 |
| 136 | tui/src/skills/bundled/scheduleRemoteAgents.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 1978 |
| 137 | tui/src/state/AppState.tsx | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 138 | tui/src/tasks/RemoteAgentTask/RemoteAgentTask.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 139 | tui/src/tools.ts | Legitimate | Spec id 인용 (1632, 1634) — git 기록 기반 정당 변경 | Specs: #1632, #1634 |
| 140 | tui/src/tools/AgentTool/AgentTool.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2077 |
| 141 | tui/src/tools/AgentTool/builtInAgents.ts | Legitimate | Spec id 인용 (1632, 1634) — git 기록 기반 정당 변경 | Specs: #1632, #1634 |
| 142 | tui/src/tools/AgentTool/prompt.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1634 |
| 143 | tui/src/tools/AgentTool/runAgent.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 144 | tui/src/tools/BashTool/utils.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 145 | tui/src/tools/BriefTool/upload.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 146 | tui/src/tools/RemoteTriggerTool/RemoteTriggerTool.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 147 | tui/src/tools/SkillTool/SkillTool.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 148 | tui/src/tools/WebFetchTool/utils.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 149 | tui/src/tools/WebSearchTool/WebSearchTool.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 150 | tui/src/types/generated/events_mono/claude_code/v1/claude_code_internal_event.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |
| 151 | tui/src/types/generated/events_mono/growthbook/v1/growthbook_experiment_event.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |
| 152 | tui/src/types/logs.ts | Legitimate | Spec id 인용 (1632) — git 기록 기반 정당 변경 | Specs: #1632 |
| 153 | tui/src/utils/advisor.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 154 | tui/src/utils/api.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2112 |
| 155 | tui/src/utils/apiPreconnect.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 156 | tui/src/utils/attachments.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 157 | tui/src/utils/auth.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 2077 |
| 158 | tui/src/utils/authPortable.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 159 | tui/src/utils/background/remote/preconditions.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 160 | tui/src/utils/background/remote/remoteSession.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633 |
| 161 | tui/src/utils/claudeInChrome/mcpServer.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 162 | tui/src/utils/computerUse/mcpServer.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 163 | tui/src/utils/context.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 164 | tui/src/utils/contextAnalysis.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 165 | tui/src/utils/env.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 166 | tui/src/utils/fastMode.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 167 | tui/src/utils/filePersistence/outputsScanner.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 168 | tui/src/utils/forkedAgent.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 169 | tui/src/utils/gracefulShutdown.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 170 | tui/src/utils/hooks.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 171 | tui/src/utils/hooks/apiQueryHookHelper.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 172 | tui/src/utils/hooks/execPromptHook.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 173 | tui/src/utils/hooks/skillImprovement.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 174 | tui/src/utils/http.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 175 | tui/src/utils/imageResizer.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 176 | tui/src/utils/managedEnv.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 177 | tui/src/utils/mcp/dateTimeParser.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 178 | tui/src/utils/mcpValidation.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 179 | tui/src/utils/messages.ts | Legitimate | Spec id 인용 (1632, 1633, 1634) — git 기록 기반 정당 변경 | Specs: #1632, #1633, #1634 |
| 180 | tui/src/utils/messages/mappers.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |
| 181 | tui/src/utils/model/agent.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 182 | tui/src/utils/model/aliases.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 183 | tui/src/utils/model/bedrock.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 184 | tui/src/utils/model/check1mAccess.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1978 |
| 185 | tui/src/utils/model/configs.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 186 | tui/src/utils/model/deprecation.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 187 | tui/src/utils/model/model.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637, 2112 |
| 188 | tui/src/utils/model/modelAllowlist.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 189 | tui/src/utils/model/modelCapabilities.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 190 | tui/src/utils/model/modelOptions.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, kosmos, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 191 | tui/src/utils/model/modelStrings.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 192 | tui/src/utils/model/modelSupportOverrides.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 193 | tui/src/utils/model/providers.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI, friendli) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 194 | tui/src/utils/model/validateModel.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 2112 |
| 195 | tui/src/utils/modifiers.ts | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 196 | tui/src/utils/notebook.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 197 | tui/src/utils/permissions/permissionSetup.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/utils/permissions/ | Spec 1633 closure pending |
| 198 | tui/src/utils/permissions/permissions.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/utils/permissions/ | Spec 1633 closure pending |
| 199 | tui/src/utils/permissions/yoloClassifier.ts | Cleanup-needed | Spec 1633 cleanup 디렉토리: tui/src/utils/permissions/ | Spec 1633 closure pending |
| 200 | tui/src/utils/plugins/mcpbHandler.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: @anthropic-ai/ | Spec 1633 closure pending |
| 201 | tui/src/utils/plugins/pluginInstallationHelpers.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 202 | tui/src/utils/plugins/pluginOptionsStorage.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 203 | tui/src/utils/preflightChecks.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 204 | tui/src/utils/processUserInput/processSlashCommand.tsx | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 205 | tui/src/utils/processUserInput/processTextPrompt.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 206 | tui/src/utils/processUserInput/processUserInput.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 207 | tui/src/utils/sessionTitle.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 208 | tui/src/utils/settings/settings.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 209 | tui/src/utils/settings/validation.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632 |
| 210 | tui/src/utils/shell/prefix.ts | Cleanup-needed | Anthropic / Spec 033 잔재 토큰 감지: queryHaiku | Spec 1633 closure pending |
| 211 | tui/src/utils/sideQuery.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, FriendliAI) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 212 | tui/src/utils/sinks.ts | Legitimate | Spec id 인용 (1632, 1633) — git 기록 기반 정당 변경 | Specs: #1632, #1633 |
| 213 | tui/src/utils/swarm/inProcessRunner.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1637 |
| 214 | tui/src/utils/swarm/spawnInProcess.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637 |
| 215 | tui/src/utils/swarm/teammateModel.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS, EXAONE) 식별 — 정당 변경 | Spec ids in git log: 1632, 2112 |
| 216 | tui/src/utils/systemPrompt.ts | Legitimate | Spec id 인용 (1632, 2077) — git 기록 기반 정당 변경 | Specs: #1632, #2077 |
| 217 | tui/src/utils/toolSearch.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1637, 2112 |
| 218 | tui/src/utils/ultraplan/ccrSession.ts | Legitimate | KOSMOS-only 토큰 (KOSMOS) 식별 — 정당 변경 | Spec ids in git log: 1632, 1633, 1978 |

</details>

**Raw data**: [`data/modified-218-classification.json`](data/modified-218-classification.json) — full schema (signals + cc_source_path 등) 포함.


## 3. Suspicious Transfer List (T008 · spec.md FR-005 / SC-004)

Suspicious 분류 0 건 — audit 결과 모든 modified 파일에 명확한 KOSMOS 정당화 또는 알려진 Spec 1633 잔재. 후속 Epic 진입을 위한 transfer 는 다음과 같다:

**Suspicious transfer (Epic β/δ)**

| Destination Epic | Count |
|---|---|
| Epic β #2293 (Suspicious) | 0 |
| Epic δ #2295 (Suspicious) | 0 |
| Uncategorized | 0 |

**Cleanup-needed transfer (별도 채널 — Epic β #2293)**: 30 건. 분류 breakdown:

| Pattern | Count |
|---|---|
| tui/src/services/api/* | 15 |
| tui/src/utils/permissions/* | 3 |
| queryHaiku / verifyApiKey / queryWithModel residue (claude.ts dispatcher) | 8 |
| @anthropic-ai/ import | 2 |
| anthropic-sdk import | 1 |
| 기타 (Feedback.tsx 등) | 1 |

**Raw data**: [`data/suspicious-transfer.json`](data/suspicious-transfer.json) — paste-ready format.


## 4. Spot-Check (50) (T012 · spec.md FR-002 / FR-006 / SC-002 / SC-005)

Population: 1,531 byte-identical files. Sample: 50 files via Python `random.Random(2292).sample(...)` (Mersenne Twister, stable across Python 3.x).

**Result**: **50/50 sha256 match**. Wilson score 95% lower bound ≈ 92.9% parity confidence; 첫 mismatch 발견 시 본 표 + staging 파일이 자동으로 reclassify entry 를 생성.

<details>
<summary>전체 표 펼치기 (50 rows)</summary>

| idx | kosmos_path | match | sha256 (prefix) |
|---|---|---|---|
| 0 | tui/src/hooks/useClaudeCodeHintRecommendation.tsx | ✅ | 8b2966eb1a… |
| 1 | tui/src/utils/extraUsage.ts | ✅ | 507a8df3b3… |
| 2 | tui/src/utils/execSyncWrapper.ts | ✅ | c00dd9ec4d… |
| 3 | tui/src/utils/agentSwarmsEnabled.ts | ✅ | 239205d4a6… |
| 4 | tui/src/components/design-system/ThemedBox.tsx | ✅ | 7fe462efe3… |
| 5 | tui/src/bridge/jwtUtils.ts | ✅ | 0510d42414… |
| 6 | tui/src/types/plugin.ts | ✅ | a00ee3fda9… |
| 7 | tui/src/components/tasks/taskStatusUtils.tsx | ✅ | e81b9ff0a1… |
| 8 | tui/src/ink/termio/ansi.ts | ✅ | aaec4c4387… |
| 9 | tui/src/constants/common.ts | ✅ | 289d78777a… |
| 10 | tui/src/components/messageActions.tsx | ✅ | 5f02733eb4… |
| 11 | tui/src/components/MessageResponse.tsx | ✅ | 18eff40130… |
| 12 | tui/src/constants/cyberRiskInstruction.ts | ✅ | 0647e7362b… |
| 13 | tui/src/tools/ConfigTool/supportedSettings.ts | ✅ | ef643901d1… |
| 14 | tui/src/utils/systemTheme.ts | ✅ | 2bd14fbe8a… |
| 15 | tui/src/components/messages/UserMemoryInputMessage.tsx | ✅ | bb48117e14… |
| 16 | tui/src/utils/plugins/marketplaceManager.ts | ✅ | 1386960deb… |
| 17 | tui/src/tools/MCPTool/prompt.ts | ✅ | cf108697cf… |
| 18 | tui/src/components/agents/new-agent-creation/wizard-steps/DescriptionStep.tsx | ✅ | 85113925c5… |
| 19 | tui/src/components/ChannelDowngradeDialog.tsx | ✅ | 9d5f9e6bc8… |
| 20 | tui/src/moreright/useMoreRight.tsx | ✅ | ba5701874d… |
| 21 | tui/src/tools/ToolSearchTool/constants.ts | ✅ | bc30ccdd13… |
| 22 | tui/src/components/StructuredDiff.tsx | ✅ | c964fc8735… |
| 23 | tui/src/tools/ScheduleCronTool/UI.tsx | ✅ | 47bb0b416c… |
| 24 | tui/src/context/mailbox.tsx | ✅ | b06f325098… |
| 25 | tui/src/utils/sanitization.ts | ✅ | ddda6adcaa… |
| 26 | tui/src/commands/install-github-app/ExistingWorkflowStep.tsx | ✅ | 98c9ce6dab… |
| 27 | tui/src/tools/MCPTool/UI.tsx | ✅ | baef187622… |
| 28 | tui/src/commands/terminalSetup/terminalSetup.tsx | ✅ | 728a02ecd4… |
| 29 | tui/src/components/PromptInput/IssueFlagBanner.tsx | ✅ | 85fbe996e5… |
| 30 | tui/src/entrypoints/agentSdkTypes.ts | ✅ | 1a19463435… |
| 31 | tui/src/components/permissions/rules/WorkspaceTab.tsx | ✅ | 2c27600341… |
| 32 | tui/src/commands/keybindings/index.ts | ✅ | 0d2a4487d3… |
| 33 | tui/src/utils/privacyLevel.ts | ✅ | 45f438503d… |
| 34 | tui/src/utils/task/outputFormatting.ts | ✅ | f157457dd9… |
| 35 | tui/src/utils/nativeInstaller/download.ts | ✅ | 3ccd60a354… |
| 36 | tui/src/components/NotebookEditToolUseRejectedMessage.tsx | ✅ | 6f034cdcc8… |
| 37 | tui/src/tasks/LocalShellTask/killShellTasks.ts | ✅ | b00adaa4bc… |
| 38 | tui/src/components/messages/UserToolResultMessage/RejectedToolUseMessage.tsx | ✅ | 32e5193b1f… |
| 39 | tui/src/bridge/codeSessionApi.ts | ✅ | 58669a33cc… |
| 40 | tui/src/skills/bundled/stuck.ts | ✅ | 9083fb39d7… |
| 41 | tui/src/hooks/useFileHistorySnapshotInit.ts | ✅ | 8a4e162289… |
| 42 | tui/src/utils/execFileNoThrowPortable.ts | ✅ | 0802410bb2… |
| 43 | tui/src/commands/extra-usage/extra-usage-core.ts | ✅ | b3bb634cf8… |
| 44 | tui/src/tools/ExitWorktreeTool/UI.tsx | ✅ | c52811b796… |
| 45 | tui/src/commands/mobile/mobile.tsx | ✅ | acccea2ee9… |
| 46 | tui/src/hooks/useElapsedTime.ts | ✅ | 827d504ba4… |
| 47 | tui/src/utils/swarm/backends/teammateModeSnapshot.ts | ✅ | 5d3740beb6… |
| 48 | tui/src/hooks/useMergedTools.ts | ✅ | eae7817917… |
| 49 | tui/src/components/LogoV2/EmergencyTip.tsx | ✅ | 100ca243ed… |

</details>

**Reproducibility**: seed=2292; sample list 가 본 markdown plaintext + [`data/spot-check-results.json`](data/spot-check-results.json) 두 곳에 박제 — 시드 유실 시에도 sample 재현 보장.


## 5. Import-only Diff (67) (T015 · spec.md FR-003 / SC-003)

Candidate population: 67 files (cc-source-scope-audit baseline 73 → 67 actual; drift -6 explained in § 1).

**Result**: **67/67 confirmed import-only diff**, 0 reclassified to modified.

<details>
<summary>전체 표 펼치기 (67 rows)</summary>

| kosmos_path | verdict | first import line changed |
|---|---|---|
| tui/src/bootstrap/state.ts | import-only confirmed | -import type { BetaMessageStreamParams } from '@anthropic-a… |
| tui/src/bridge/inboundAttachments.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/commands/createMovedToPluginCommand.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/commands/review.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/commands/review/ultrareviewCommand.tsx | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/commands/statusline.tsx | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/components/FallbackToolUseErrorMessage.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/components/Message.tsx | import-only confirmed | -import type { BetaContentBlock } from '@anthropic-ai/sdk/r… |
| tui/src/components/MessageSelector.tsx | import-only confirmed | -import type { ContentBlockParam, TextBlockParam } from '@a… |
| tui/src/components/agents/new-agent-creation/wizard-steps/GenerateStep.tsx | import-only confirmed | -import { APIUserAbortError } from '@anthropic-ai/sdk'; |
| tui/src/components/messages/AssistantThinkingMessage.tsx | import-only confirmed | -import type { ThinkingBlock, ThinkingBlockParam } from '@a… |
| tui/src/components/messages/AssistantToolUseMessage.tsx | import-only confirmed | -import type { ToolUseBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/components/messages/GroupedToolUseContent.tsx | import-only confirmed | -import type { ToolResultBlockParam, ToolUseBlockParam } fr… |
| tui/src/components/messages/UserAgentNotificationMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserBashInputMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserChannelMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserCommandMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserPromptMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserResourceUpdateMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserTeammateMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserTextMessage.tsx | import-only confirmed | -import type { TextBlockParam } from '@anthropic-ai/sdk/res… |
| tui/src/components/messages/UserToolResultMessage/UserToolErrorMessage.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/components/messages/UserToolResultMessage/UserToolResultMessage.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/components/messages/UserToolResultMessage/utils.tsx | import-only confirmed | -import type { ToolUseBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/components/permissions/AskUserQuestionPermissionRequest/AskUserQuestionPermissionRequest.tsx | import-only confirmed | -import type { Base64ImageSource, ImageBlockParam } from '@… |
| tui/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx | import-only confirmed | -import type { Base64ImageSource, ImageBlockParam } from '@… |
| tui/src/components/permissions/PermissionRequest.tsx | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/hooks/toolPermission/PermissionContext.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/hooks/toolPermission/handlers/interactiveHandler.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/hooks/toolPermission/handlers/swarmWorkerHandler.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/hooks/usePromptsFromClaudeInChrome.tsx | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/services/api/dumpPrompts.ts | import-only confirmed | -import type { ClientOptions } from '@anthropic-ai/sdk' |
| tui/src/services/compact/microCompact.ts | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/services/tools/StreamingToolExecutor.ts | import-only confirmed | -import type { ToolUseBlock } from '@anthropic-ai/sdk/resou… |
| tui/src/services/tools/toolOrchestration.ts | import-only confirmed | -import type { ToolUseBlock } from '@anthropic-ai/sdk/resou… |
| tui/src/skills/bundledSkills.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/tools/AgentTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam, ToolUseBlockParam } fr… |
| tui/src/tools/AgentTool/forkSubagent.ts | import-only confirmed | -import type { BetaToolUseBlock } from '@anthropic-ai/sdk/r… |
| tui/src/tools/BashTool/BashTool.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/BashTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/BashTool/bashPermissions.ts | import-only confirmed | -import { APIUserAbortError } from '@anthropic-ai/sdk' |
| tui/src/tools/FileEditTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/FileReadTool/FileReadTool.ts | import-only confirmed | -import type { Base64ImageSource } from '@anthropic-ai/sdk/… |
| tui/src/tools/FileReadTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/FileWriteTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/GlobTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/GrepTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/LSPTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/NotebookEditTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/PowerShellTool/PowerShellTool.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/PowerShellTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/SkillTool/UI.tsx | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/tools/ToolSearchTool/ToolSearchTool.ts | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/types/command.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/types/permissions.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/types/textInputTypes.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/utils/analyzeContext.ts | import-only confirmed | -import type { Anthropic } from '@anthropic-ai/sdk' |
| tui/src/utils/errors.ts | import-only confirmed | -import { APIUserAbortError } from '@anthropic-ai/sdk' |
| tui/src/utils/groupToolUses.ts | import-only confirmed | -import type { BetaToolUseBlock } from '@anthropic-ai/sdk/r… |
| tui/src/utils/log.ts | import-only confirmed | -import type { BetaMessageStreamParams } from '@anthropic-a… |
| tui/src/utils/messageQueueManager.ts | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/utils/permissions/classifierShared.ts | import-only confirmed | -import type { BetaContentBlock } from '@anthropic-ai/sdk/r… |
| tui/src/utils/processUserInput/processBashCommand.tsx | import-only confirmed | -import type { ContentBlockParam } from '@anthropic-ai/sdk/… |
| tui/src/utils/queryHelpers.ts | import-only confirmed | -import type { ToolUseBlock } from '@anthropic-ai/sdk/resou… |
| tui/src/utils/tokens.ts | import-only confirmed | -import type { BetaUsage as Usage } from '@anthropic-ai/sdk… |
| tui/src/utils/toolResultStorage.ts | import-only confirmed | -import type { ToolResultBlockParam } from '@anthropic-ai/s… |
| tui/src/utils/toolSchemaCache.ts | import-only confirmed | -import type { BetaTool } from '@anthropic-ai/sdk/resources… |

</details>

**Raw data**: [`data/import-verify-results.json`](data/import-verify-results.json).


## 6. Manual Review Log (T007 · spec.md FR-001 / FR-008)

Reviewer: Lead (Opus, Initiative #2290 Epic α); Date: 2026-04-29

**Verdict**: PASS — 자동 분류 결과 신뢰성 확인. 30 Cleanup-needed 모두 알려진 Spec 1633 잔재와 정확히 매칭. 5 Legitimate sample 모두 KOSMOS-only 토큰 (KOSMOS / EXAONE / FriendliAI) 정당화 확인.

**Coverage**: 30 Cleanup-needed 전수 + 5 Legitimate sample + 0 Suspicious. Staging 파일 (spot-check, import-verify) 부재 — reclassification 후처리 0 건.

**Raw data**: [`data/manual-review-log.json`](data/manual-review-log.json).


## 7. Reproducibility (T018 · spec.md FR-006 / SC-005)

Re-run sequence (≈5 min total):

```bash
cd /Users/um-yunsang/KOSMOS  # or your repo root
specs/2292-cc-parity-audit/scripts/enumerate-files.sh        # R1
python3 specs/2292-cc-parity-audit/scripts/spot-check-50.py     # R2 (seed=2292)
python3 specs/2292-cc-parity-audit/scripts/verify-import-diff.py # R3
python3 specs/2292-cc-parity-audit/scripts/classify-modified.py  # R4
python3 specs/2292-cc-parity-audit/scripts/compose-audit-md.py   # R5 (regenerate this doc)
```

Manifest: [`data/repro-manifest.json`](data/repro-manifest.json) — 4-step formalisation per data-model.md § ReproducibilityProcedure.


## 8. Phase α exit criteria (T020 · spec.md FR-009 / SC-007)

| Criterion | Status |
|---|---|
| Audit doc 작성 + 사용자 검토 가능 | ✅ 본 markdown |
| Suspicious list 분리 (Epic β/δ transfer) | ✅ § 3 — 0 Suspicious + 30 Cleanup-needed |
| 표본 ≥ 50 + reproducibility | ✅ § 4 — 50/50, seed=2292, scripts 박제 |
| 212 modified 파일 100% 분류 | ✅ § 2 — 218 (drift +6) 100% 분류 |
| Read-only invariant | ✅ § 9 verification |

### Next-Epic readiness

- **Epic β #2293 (KOSMOS-original UI residue cleanup)**: 진입 가능. 30 Cleanup-needed 항목이 task 입력 — 그 중 15개는 `tui/src/services/api/*` (claude.ts dispatcher Spec 1633 closure), 8개는 `queryHaiku` callsite, 3개는 `utils/permissions/*` (Spec 033 잔재).
- **Epic γ #2294 (5-primitive align with CC Tool.ts)**: 본 audit 산출이 직접 transfer 항목 0 건 — Epic γ 는 별도 design 진입 (delegation-flow-design § 12 의존).
- **Epic δ #2295 (Backend permissions/ cleanup)**: 본 audit (TUI-only) 산출이 직접 transfer 항목 0 건 — Epic δ 는 `src/kosmos/permissions/` 백엔드 audit 별도 필요 (Out of Scope Permanent of this Epic α).
- **Epic ε #2296 (AX-infrastructure mock adapters)**: 의존성 없음, Epic γ/δ 결과 후 진입.
- **Epic ζ #2297 (E2E smoke + policy mapping)**: Epic ε 후속.
- **Epic η #2298 (System prompt rewrite)**: 선택, 마지막 진입.

### Conditional Deferred — #2319 (표본 50 → 100 확장)

Spot-check 50/50 match → 본 placeholder issue 는 **close as won't-fix** 권장. 추가 신뢰 구간이 필요하면 issue 재오픈 후 표본 100 으로 재실행.


## 9. Read-only Invariant Verification (T019 · spec.md FR-007 / SC-006)

본 Epic 의 모든 산출은 `specs/2292-cc-parity-audit/` 내부에 있다. PR 검증 시:

```bash
git status --short -- ':!specs/2292-cc-parity-audit'
# 출력이 비어있으면 invariant 충족 (FR-007 / SC-006)
```

본 markdown 도 read-only invariant 의 직접 산출 (compose-audit-md.py 가 spec 디렉토리 안에서만 작성).

---

*Generated by `specs/2292-cc-parity-audit/scripts/compose-audit-md.py`. Re-running with the same JSON appendix produces a byte-identical markdown — this document IS the deliverable.*

---

## 10. Follow-up cleanup tracking (post-Spec-2521)

**Updated**: 2026-05-01 (T038–T041 of Spec 2521)
**Scope**: Spec 2521 in-scope files = `tui/src/services/api/claude.ts`, `tui/src/ipc/llmClient.ts`, `src/kosmos/llm/client.py`, `src/kosmos/ipc/stdio.py`

### Spec 2521 closure summary

| Category | Count | Description |
|---|---|---|
| (a) Resolved by Spec 2521 byte-copy | 1 | claude.ts 1101 LOC → CC 3419 LOC byte-identical; old residues eliminated |
| (b) Resolved by Spec 2521 swap commit | 0 | No additional in-scope cleanup-needed entries resolved via explicit swap commit |
| (c) Deferred — out of Spec 2521 scope | 29 | All remaining cleanup-needed entries reference files outside the 4 Spec 2521 in-scope files |

**Total cleanup-needed processed**: 1 of 30 (in-scope). 29 deferred to follow-up epics below.

### (c) Out-of-scope deferred entries

These 29 entries are outside the 4 Spec 2521 in-scope files and require separate epic tracking.

#### Group 1 — tui/src/services/api/* (14 entries, excluding claude.ts which is resolved)

These files are Anthropic-1P cloud API modules (admin, billing, referral, quota, session ingress, etc.) that have no FriendliAI equivalent and should be either deleted or replaced with KOSMOS-equivalent stubs.

| # | File | Cleanup reason | Epic candidate |
|---|---|---|---|
| 96 | tui/src/services/api/adminRequests.ts | Anthropic admin API — no KOSMOS equivalent; dead code | Epic β #2293 (UI residue cleanup) |
| 98 | tui/src/services/api/client.ts | `verifyApiKey` residue — Anthropic key validation, not applicable to FriendliAI | Epic β #2293 |
| 99 | tui/src/services/api/errorUtils.ts | Anthropic error shape dependency; replace with FriendliAI error handling | Epic β #2293 |
| 100 | tui/src/services/api/errors.ts | Anthropic error types; replace or stub with KOSMOS equivalents | Epic β #2293 |
| 101 | tui/src/services/api/filesApi.ts | Anthropic Files API (claude.ai cloud); no FriendliAI equivalent | Epic β #2293 |
| 102 | tui/src/services/api/firstTokenDate.ts | Anthropic account-level metadata API; irrelevant to KOSMOS | Epic β #2293 |
| 103 | tui/src/services/api/grove.ts | Anthropic internal service API; no KOSMOS equivalent | Epic β #2293 |
| 104 | tui/src/services/api/logging.ts | Anthropic event logging endpoint; replace with OTEL (Spec 021) | Epic β #2293 |
| 105 | tui/src/services/api/overageCreditGrant.ts | Anthropic billing API; no KOSMOS equivalent | Epic β #2293 |
| 106 | tui/src/services/api/promptCacheBreakDetection.ts | Prompt cache break detection tied to Anthropic cache headers; review for FriendliAI compat | Epic β #2293 |
| 107 | tui/src/services/api/referral.ts | Anthropic referral program API; no KOSMOS equivalent | Epic β #2293 |
| 108 | tui/src/services/api/sessionIngress.ts | Anthropic session ingress (claude.ai cloud); no KOSMOS equivalent | Epic β #2293 |
| 109 | tui/src/services/api/ultrareviewQuota.ts | Anthropic ultra-review quota API; no KOSMOS equivalent | Epic β #2293 |
| 110 | tui/src/services/api/usage.ts | Anthropic usage tracking API; replace with KOSMOS OTEL spans | Epic β #2293 |
| 111 | tui/src/services/api/withRetry.ts | Retry logic references Anthropic-specific 429/529 patterns; review for FriendliAI compat | Epic β #2293 |

#### Group 2 — queryHaiku callsites (8 entries)

These files call `queryHaiku` (a lightweight Anthropic model query helper) for summarization or classification tasks. Each must be rewired to call K-EXAONE via the KOSMOS query engine, or the calling feature must be disabled/replaced.

| # | File | Cleanup reason | Epic candidate |
|---|---|---|---|
| 11 | tui/src/cli/print.ts | `queryHaiku` + `@anthropic-ai/` import for print formatting; rewire to K-EXAONE or remove | Epic β #2293 |
| 17 | tui/src/commands/insights.ts | `queryWithModel` for insights generation; rewire to KOSMOS query engine | Epic β #2293 |
| 23 | tui/src/commands/rename/generateSessionName.ts | `queryHaiku` for session name generation; rewire to K-EXAONE | Epic β #2293 |
| 26 | tui/src/components/Feedback.tsx | `queryHaiku` for feedback summarization; rewire or stub out | Epic β #2293 |
| 130 | tui/src/services/toolUseSummary/toolUseSummaryGenerator.ts | `queryHaiku` for tool-use summary; rewire to K-EXAONE | Epic β #2293 |
| 148 | tui/src/tools/WebFetchTool/utils.ts | `queryHaiku` for content summarization after fetch; rewire to K-EXAONE | Epic β #2293 |
| 177 | tui/src/utils/mcp/dateTimeParser.ts | `queryHaiku` for date-time parsing fallback; rewire or use stdlib | Epic β #2293 |
| 207 | tui/src/utils/sessionTitle.ts | `queryHaiku` for session title generation; rewire to K-EXAONE | Epic β #2293 |
| 210 | tui/src/utils/shell/prefix.ts | `queryHaiku` for shell prefix suggestion; rewire to K-EXAONE or remove | Epic β #2293 |

#### Group 3 — tui/src/utils/permissions/* (3 entries)

These files contain Spec 033 (CC permission gauntlet) residue mixed with Anthropic-specific permission logic. They require the KOSMOS permission V2 spectrum (Spec 033) re-application.

| # | File | Cleanup reason | Epic candidate |
|---|---|---|---|
| 197 | tui/src/utils/permissions/permissionSetup.ts | Anthropic permission setup residue (Spec 033 migration incomplete); needs KOSMOS V2 spectrum wiring | Epic β #2293 or Epic δ #2295 |
| 198 | tui/src/utils/permissions/permissions.ts | Anthropic permission model residue; needs KOSMOS V2 computed derivation (Spec 025 Path B) | Epic β #2293 or Epic δ #2295 |
| 199 | tui/src/utils/permissions/yoloClassifier.ts | Anthropic YOLO mode classifier residue; review for KOSMOS `bypassPermissions` equivalence | Epic β #2293 |

#### Group 4 — Miscellaneous (3 entries)

| # | File | Cleanup reason | Epic candidate |
|---|---|---|---|
| 129 | tui/src/services/tokenEstimation.ts | `anthropic-sdk` import for token counting; replace with tiktoken or provider-neutral counter | Epic β #2293 |
| 200 | tui/src/utils/plugins/mcpbHandler.ts | `@anthropic-ai/` import in plugin handler; verify if SDK type import or runtime call | Epic β #2293 |

### Priority recommendation

All 29 deferred entries map to **Epic β #2293 (KOSMOS-original UI residue cleanup)** as the primary destination. Entries #197 and #198 (`permissions/`) may overlap with **Epic δ #2295 (Backend permissions cleanup)** and should be assigned after Epic δ spec review confirms scope boundary. No new epic is required — existing Epic β absorbs all 29.
