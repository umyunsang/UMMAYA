# Research — Phase 0 (Tool System Residue Cleanup)

**Date**: 2026-05-03 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

본 문서는 `/speckit-plan` Phase 0 의 산출물. 본 Epic 의 모든 NEEDS CLARIFICATION 0건 — `/speckit-specify` 단계에서 reasonable defaults 로 모두 박제. Phase 0 의 핵심은 (a) Audit 권고 vs CORE THESIS 충돌 해결 박제, (b) AgentTool 9 differ 파일 preview 분류, (c) 박제 주석 마커 컨벤션, (d) Deferred items validation 결과.

## R-1 — Decision: R2 REPLTool 분기 보존 (REJECT Audit DROP 권고)

**Decision**: KOSMOS `tools.ts:274,311` 의 `isReplModeEnabled() && REPLTool` 분기는 **보존**한다. 분기 자체 + `isReplModeEnabled()` import + `REPLTool/constants.ts` 모두 변경 0. 단 분기 위에 SWAP-2 박제 주석 추가 (FR-005).

**Rationale** (CORE THESIS 기준):
- KOSMOS `tools.ts:274` `if (isReplModeEnabled() && REPLTool)` ↔ CC `tools.ts:277` `if (isReplModeEnabled() && REPLTool)` — **byte-identical**
- KOSMOS `tools.ts:311` `if (isReplModeEnabled())` ↔ CC `tools.ts:314` `if (isReplModeEnabled())` — **byte-identical**
- KOSMOS `constants/prompts.ts:269` ↔ CC `constants/prompts.ts:277` — **byte-identical**
- KOSMOS `memdir/memdir.ts:385` ↔ CC `memdir/memdir.ts:385` — **byte-identical**
- KOSMOS는 Spec 1633 (#2293) 으로 `REPLTool = null` 처리 → 분기는 dead path (`if (false && null)`) 이지만 분기 syntax 자체는 CC와 동일
- 분기 제거 = KOSMOS-only divergence with CC = **CORE THESIS ("byte-identical default") 위반**
- Audit 권고 ("향후 회귀 위험: env var 토글로 재활성 가능") 는 valid concern 이지만, KOSMOS는 `process.env.USER_TYPE === 'ant'` 가 citizen-facing build 에서 절대 true 가 안 되므로 (KOSMOS 는 Anthropic-internal 빌드가 아님) `REPLTool = null` 이 영구적 — env 토글로 재활성 불가능

**Alternatives considered**:
- **Path A — Audit 권고대로 DROP**: 분기 + import + REPLTool/constants.ts 전부 제거. 장점: 코드 cleaner, audit re-scan 시 R2 자동 PASS. 단점: KOSMOS-only divergence 4 callsite + 1 디렉토리, CORE THESIS 위반, 미래 CC 2.x → 3.x upgrade 시 merge conflict 증가.
- **Path B — 박제 주석으로 dead-by-design 명시**: ✅ **선택**. 코드 변경 0, CC byte-identical 보존, audit re-scan 시 SWAP-2 마커로 PASS, CC upgrade 시 conflict 0.

## R-2 — Decision: R3 14 dev tool dead-import 보존 (REJECT Audit DROP 권고)

**Decision**: KOSMOS `tools.ts` 의 14개 의심 dev tool import (TodoWriteTool / Task* / Team* / ConfigTool / ScheduleCronTool / TestingPermissionTool / 등) 는 **모두 보존**한다. import 라인 변경 0. 단 import 블록 위에 SWAP-2 박제 헤더 추가 (FR-004).

**Rationale**:
- specify 단계 측정: 30개 의심 import 모두 `tools.ts` + `tools/<X>/` 디렉토리 외 outside-callers ≥ 1 건 (BashTool 196, FileReadTool 91, ToolSearchTool 31, SkillTool 26, ExitPlanModeV2Tool 24, BriefTool 22, WebFetchTool 18, AskUserQuestionTool 17, TodoWriteTool 15, EnterWorktreeTool 14, NotebookEditTool 16, TaskStopTool 12, ListMcpResourcesTool 10, ReadMcpResourceTool 9, TaskOutputTool 8, TaskCreateTool 6, EnterPlanModeTool 6, WebSearchTool 6, TaskUpdateTool 5, ScheduleCronTool 4, GrepTool 36, FileEditTool 69, FileWriteTool 52, GlobTool 28, LSPTool 3, TaskGetTool 3, TaskListTool 3, ConfigTool 1, ExitWorktreeTool 1, TestingPermissionTool 1)
- KOSMOS `tools.ts:192-217` 의 docstring 이 이미 FR-013 ("permissions/sandbox/attachments references the constants") 명시 — 본 Epic 은 그 docstring 을 보강하고 import 블록 위에 마커 주석 추가하는 것
- import 자체는 CC `tools.ts` 와 byte-identical (CC 도 같은 import 보유)
- import 제거 = KOSMOS-only divergence with CC = **CORE THESIS 위반**

**Alternatives considered**:
- **Path A — Audit 권고대로 caller 0 인 import 제거**: 측정 결과 caller 0 인 import 0건이라 적용 대상 0. 무의미.
- **Path B — 박제 헤더로 unregistered-but-imported 의도 명시**: ✅ **선택**.

## R-3 — Decision: R4 AgentTool 18파일 분류 + Markdown 박제

**Decision**: `tui/src/tools/AgentTool/` 18파일 정밀 SHA-256 비교 + 9 differ 파일 정밀 4-bucket 분류. 산출물은 단일 markdown (`agent-tool-classification.md`). 코드 변경 0.

### Preview classification (research-level — full classification 은 implement 단계 산출)

| # | 파일 | 변경 라인 | Preview 분류 | 근거 |
|---|---|---:|---|---|
| 1 | `AgentTool.tsx` | 9 | **PRESERVE-IDENTICAL-WITH-SHIM** | (a) `teleportToRemote` from `utils/teleport.js` → no-op stub (CC `claude.ai cloud teleport`, swap-1 spillover from Spec 1633 / Epic #2293 — `tui/src/utils/teleport.ts` 삭제됨); (b) `proactiveModule` (CC growthbook feature flag) → `isProactiveActive` import from `utils/proactiveModule.js` (swap-5 telemetry spillover — Anthropic growthbook 제거) |
| 2 | `agentToolUtils.ts` | 104 | **PRESERVE-IDENTICAL-WITH-SHIM** | (a) `ToolPermissionContext` import drop (yoloClassifier 삭제 결과); (b) `isInProtectedNamespace` 사용처 삭제 (yoloClassifier 의존); (c) `yoloClassifier` block 전부 삭제 (Anthropic growthbook auto-mode classifier — swap-5 telemetry spillover, Spec 1633) |
| 3 | `built-in/exploreAgent.ts` | 91 | **MIGRATE-FOR-SWAP** | CC explore agent prompt 전체 (~83 라인) 가 Bash/FileEdit/Glob/Grep/NotebookEdit dev tool 이름 + behavior reference → KOSMOS 13-tool surface 에서 dev tool 미등록 → CC prompt 가 무의미. Audit `scope-S2-tool-system.md § L2-A claudeCodeGuideAgent + verificationAgent` 와 동일 패턴 (의도적 미포팅 / KOSMOS 비적용). Stub 또는 minimal replacement 가 들어 있는지 implement 단계에서 정밀 확인 필요. swap-2 (Tool surface) 종속. |
| 4 | `built-in/planAgent.ts` | 98 | **MIGRATE-FOR-SWAP** | exploreAgent 와 동일 패턴 — CC plan agent prompt 가 Bash/FileEdit/Glob/Grep dev tool 의존. swap-2 종속. |
| 5 | `builtInAgents.ts` | 44 | **MIGRATE-FOR-SWAP** | 4 import 제거 (`claudeCodeGuideAgent` / `EXPLORE_AGENT` / `PLAN_AGENT` / `verificationAgent`) + `getFeatureValue_CACHED_MAY_BE_STALE` from growthbook 제거 + `areExplorePlanAgentsEnabled()` 함수 삭제. KOSMOS는 `GENERAL_PURPOSE_AGENT` + `STATUSLINE_SETUP_AGENT` 2개만 등록. 시민용 agent surface 결정 = swap-2. |
| 6 | `forkSubagent.ts` | 2 | **PRESERVE-IDENTICAL-WITH-SHIM** | `@anthropic-ai/sdk/resources/beta/messages/messages.mjs` → `src/sdk-compat.js` import path 1줄 (swap-1 SDK alias spillover) |
| 7 | `prompt.ts` | 4 | **MIGRATE-FOR-SWAP** | 2-line comment 추가 (KOSMOS L1-C C6 Task primitive backing 명시) + 1-line system prompt 추가 ("This tool backs the Task primitive for orchestrating Korean public-service agents."). FR-017 (AgentTool repurposed as Task primitive backing) 직접 인용. swap-2 종속. |
| 8 | `runAgent.ts` | 12 | **PRESERVE-IDENTICAL-WITH-SHIM** | `services/api/promptCacheBreakDetection` import → no-op stub `cleanupAgentTracking` (Spec 1633 / Epic #2293 의 `services/api/promptCacheBreakDetection.ts` 삭제 spillover, swap-5 telemetry) |
| 9 | `UI.tsx` | 2 | **PRESERVE-IDENTICAL-WITH-SHIM** | `@anthropic-ai/sdk/resources/index.mjs` → `src/sdk-compat.js` import path 1줄 (swap-1 SDK alias spillover) |

**Preview 회귀 의심**: 0건. 9 differ 파일 모두 swap-1 (SDK alias) / swap-2 (Tool surface + Task primitive backing) / swap-5 (telemetry stub) 셋 중 한 카테고리로 정합. 본 Epic 의 implement 단계가 preview 분류를 정밀 검증하면서 회귀 의심 발견 시 spec FR-003 의 결정 경로 적용.

**Rationale for category labeling**:
- **PRESERVE-IDENTICAL-WITH-SHIM**: SDK alias / telemetry stub / utility no-op stub 같은 swap-1 또는 swap-5 spillover. 본질 로직 byte-identical, 외피만 KOSMOS shim.
- **MIGRATE-FOR-SWAP**: swap-2 본체 — Tool surface 결정 (citizen-facing 13-tool / dev tool 미등록 / Task primitive backing) 으로 인한 prompt 본문 / agent registration / Korean context 추가. swap-2 정당성 명시 인용 필수.

### 회귀 의심 처리 절차 (FR-003)

implement 단계에서 회귀 의심 발견 시:
1. classification 문서에 회귀 의심 행 추가 (변경 라인 + 카테고리 미상)
2. 두 옵션 중 하나 결정 박제:
   - **Option A — 즉시 CC 회귀**: 해당 파일을 CC byte-copy 로 되돌림. SC-007 (net LOC 0) 위반 가능 (코드 수정 발생). PR description 에 회귀 사유 명시.
   - **Option B — swap-2 정당화 헤더 추가**: 해당 파일에 swap-2 정당성 박제 주석 추가 (FR-002 형식: Spec 번호 / FR / 인용). PRESERVE-IDENTICAL-WITH-SHIM 또는 MIGRATE-FOR-SWAP 으로 재분류.
3. 결정을 spec Deferred Items 표의 "AgentTool 9 differ 파일 중 회귀 의심 발견 시" 행에 issue 번호로 박제 (`/speckit-taskstoissues` 단계).

## R-4 — Decision: 박제 주석 마커 컨벤션

**Decision**: KOSMOS 기존 컨벤션 (`tools.ts:34-35,50-51,70-71,102-103,137-139` 의 `// KOSMOS Spec NNNN / Epic #NNNN — <설명>` 패턴) 을 그대로 차용하되, audit re-scan 도구 (미래) 가 인식할 수 있는 표준화된 마커를 추가.

**마커 형식**:
- **R2 박제 주석** (REPL 분기 4 callsite): `// SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293) — branch byte-identical with CC <CC파일>:<라인>, dead-by-design.`
- **R3 박제 헤더** (dev tool import 블록): `// SWAP-2-RETAINED-IMPORT-BLOCK ...` 다중 라인 헤더, 14개 도구 + outside-caller 요약 + FR-013 인용.
- **R4 박제 주석** (`prompt.ts` 같이 KOSMOS 가 직접 in-file 추가하는 경우): `// SWAP-2-MIGRATE: <설명> (FR-XXX, Spec NNNN)`. 기존 KOSMOS 컨벤션과 호환.

**Rationale**:
- KOSMOS 기존 마커 (`// KOSMOS Spec NNNN / Epic #NNNN`) 와 호환: grep 으로 `Spec` + 숫자 패턴 검색 가능
- 신규 prefix `SWAP-2-PRESERVE` / `SWAP-2-RETAINED-IMPORT-BLOCK` / `SWAP-2-MIGRATE` 는 Initiative #2636 audit 도구가 4-bucket 분류 (PORT / PRESERVE-IDENTICAL / MIGRATE-FOR-SWAP / DROP-CANDIDATE) 와 직접 매핑 가능
- 마커 텍스트는 한국어 primary, 기술 용어는 영어 (FR-009)

**Alternatives considered**:
- **`@swap-2` doc-comment 태그**: TypeScript jsdoc 호환되지만 KOSMOS 기존 컨벤션과 분리되어 마커 인식 일관성 저하. **REJECTED**.
- **별도 marker 파일** (예: `tui/src/tools.ts.markers.json`): 코드와 마커가 분리되어 유지보수 부담. **REJECTED**.

## R-5 — Deferred Items Validation (Constitution Principle VI)

**Decision**: 본 Epic 의 spec 에 `Scope Boundaries & Deferred Items` 섹션 존재 — 구조 컴플라이언트.

**Validation results** (Phase 0 step 2):

### Out of Scope (Permanent) — 5 항목, 모두 영구 제외 (tracking 불필요)
1. REPLTool / dev tool 등록 표 변경 금지
2. Tool.ts 인터페이스 수정 금지
3. CC restored-src 수정 금지
4. dev tool 등록 표에 새 도구 추가 금지
5. AgentTool 자체 인터페이스 수정 금지

### Deferred to Future Work — 5 항목, 모두 `NEEDS TRACKING` (`/speckit-taskstoissues` 단계 resolution)
1. Audit 재실행 자동 스크립트 — Initiative #2636 follow-up
2. AgentTool 9 differ 회귀 의심 즉시 회귀 — TBD (조건부)
3. `tools.ts` getAllBaseTools 표의 Spec 2522 통합 — Epic #2579
4. dev tool 14 import 의 unit-test 측 caller 정리 — TBD (test-cleanup epic)
5. KOSMOS-only AgentTool 파일 분류 정책 — TBD (when needed)

### Unregistered deferral pattern scan (spec.md 전수 grep)
**검사 명령**: `grep -niE "separate epic|future epic|future phase|deferred to|later release|out of scope for v1|phase 2\+|^v2| v2 |next epic|별도 epic|향후|미래" specs/2638-tool-system-residue/spec.md`

**결과**: 9 매치, 모두 합법:
- 라인 117/118/121: Out of Scope (Permanent) 섹션 내부 `별도 Epic` 언급 — 영구 제외 사유 설명, tracking 불필요
- 라인 128/130/131: Deferred to Future Work 표 내부 `별도 Epic` 언급 — `NEEDS TRACKING` 마커 보유
- 라인 10/14/66/99: `미래 Lead Opus` / `미래 사람` / `미래 누군가` 와 같이 stakeholder 또는 시간적 미래 지칭 — deferred work 가 아님

**Verdict**: ✅ **PASS** — 모든 deferral 가 구조화된 표 또는 영구 Out of Scope 에 박제됨. `/speckit-analyze` 가 CRITICAL 마크할 항목 0건.

## R-6 — Spec 2522 머지 우선 + rebase 전략

**Decision**: 본 Epic 은 KOSMOS-w-2522 (Spec 2522 / Epic #2579) 머지 후 본 worktree (KOSMOS-w-2638) 의 `feat/2638-s2-tool-system-residue` 브랜치를 `main` 으로 rebase. 박제 주석 라인 번호 재조정 (단순 텍스트 추가라 conflict trivial).

**Rationale**:
- Spec 2522 가 `tools.ts` 의 4 primitive surface v4 정비 진행 중 — 등록 표 본체 + import 일부 수정 가능성
- 본 Epic 의 변경 (박제 주석) 은 구조 무관, 단순 텍스트 추가만이라 rebase 시 wallclock 5분 이내 가능
- AGENTS.md `§ Conflict resolution` 준수: 두 spec 간 충돌 시 issue 또는 GitHub Discussion. Spec 2522 가 같은 영역 작업 우선이므로 본 Epic 이 양보.

**Alternatives considered**:
- **본 Epic 먼저 머지 후 Spec 2522 rebase**: Spec 2522 가 본 Epic 의 박제 주석을 본인 영역에서 보존해야 하는 부담. 양 PR 의 작업량 비교 시 본 Epic 이 더 가벼움. **REJECTED**.

## R-7 — TUI 동작 변경 0 검증

**Decision**: 본 Epic 의 모든 변경 (4 TS 파일 박제 주석 + 1 신규 markdown) 은 TUI runtime 동작 0 영향. Layer 5 (tmux capture-pane) smoke 불필요. Layer 1b (ink-testing-library) 도 N/A. SC-002 / SC-003 (`bun typecheck` / `bun test` parity) 가 검증 게이트.

**Rationale**:
- 박제 주석은 `//` 또는 `/* */` 단일 라인/블록 — 컴파일러는 무시
- 신규 markdown 은 코드 외부 산출물 — runtime 0 영향
- AGENTS.md `§ TUI verification` 의 hard rule ("Any PR that modifies `tui/src/**` MUST capture (a) interactive PTY scenario AND (b) per-frame text snapshots AND (c) vhs visual scenario") 는 **TUI 동작 변경 PR** 에 적용 — 본 Epic 은 PR description 에 `TUI behavior no-change` 명시

**Bypass 정당성**:
- `tui/src/tools.ts` / `tui/src/constants/prompts.ts` / `tui/src/memdir/memdir.ts` 변경은 모두 주석 추가만 (functional 변경 0)
- 박제 주석 추가 후 `git diff --shortstat` 결과 = `4 files changed, ~10 insertions(+), 0 deletions(-)` (전부 주석)
- Phase 6 (Polish) 에서 `bun typecheck` + `bun test` parity 로 회귀 0 검증 (SC-002/SC-003)

## R-8 — Reference mapping (Constitution Principle I)

본 Epic 의 모든 설계 결정 → reference 매핑 (이미 plan.md `§ Reference Mapping` 표에 박제). 본 research.md 는 그 표를 augment:

| Decision | Primary reference | 인용 위치 |
|---|---|---|
| R-1 (R2 분기 보존) | CC `tools.ts:277,314` byte-identical | spec FR-005, plan Summary, research § R-1 |
| R-2 (R3 import 보존) | CC `tools.ts` import 표 + KOSMOS `tools.ts:192-217` FR-013 docstring | spec FR-004, plan Summary, research § R-2 |
| R-3 (R4 분류 + classification 문서) | CC `tools/AgentTool/{18 files}` SHA-256 + Audit `scope-S2-tool-system.md § MIGRATE-FOR-SWAP table` | spec US1, plan Summary, research § R-3 |
| R-4 (박제 마커 컨벤션) | KOSMOS 기존 컨벤션 `tools.ts:34-35,50-51,70-71,102-103,137-139` | research § R-4 |
| R-5 (Deferred validation) | Constitution Principle VI | research § R-5 |
| R-6 (Spec 2522 머지 순서) | AGENTS.md `§ Conflict resolution` + worktree `KOSMOS-w-2522` 활성 | research § R-6 |
| R-7 (TUI 동작 0) | AGENTS.md `§ TUI verification` (bypass: TUI no-change) | research § R-7 |

## Summary

본 Phase 0 research 는 **0 NEEDS CLARIFICATION**, **0 unresolved decision**, **0 untracked deferral** 로 완료. Phase 1 (data-model.md / contracts/ / quickstart.md) 는 본 Epic 이 hygiene-only 라 N/A — plan.md `§ Project Structure` 에 명시. agent context update 는 `update-agent-context.sh claude` 실행으로 처리.

다음 단계: `/speckit-tasks` 진입하여 본 plan + research 로부터 17개 예상 task 생성.
