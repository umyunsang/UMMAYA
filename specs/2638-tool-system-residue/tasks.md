---
description: "Task list for Epic B (#2638) — Tool System Residue Cleanup"
---

# Tasks: Tool System Residue Cleanup (Audit-Driven CORE THESIS Realignment)

**Input**: Design documents from `/specs/2638-tool-system-residue/`
**Prerequisites**: spec.md ✓ / plan.md ✓ / research.md ✓ (data-model.md / contracts/ / quickstart.md = N/A per plan)

**Tests**: 본 Epic 은 hygiene-only (코드 동작 변경 0). 신규 unit test 0. 검증은 기존 `bun test` / `pytest` parity 로 수행. Phase 6 의 verification task 가 검증 게이트.

**Organization**: Tasks are grouped by user story (US1 = R4 분류 / US2 = R3 박제 헤더 / US3 = R2 박제 주석). MVP = US1 단독.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 건드리며 의존성 0 → 병렬 dispatch 가능
- **[Story]**: US1 / US2 / US3 (Setup / Foundational / Polish 는 미부여)
- 모든 파일 경로는 worktree (`/Users/um-yunsang/KOSMOS-w-2638`) 기준 상대 경로

## Path Conventions (본 Epic)

- 산출물 markdown: `specs/2638-tool-system-residue/agent-tool-classification.md`
- 박제 주석 추가 대상: `tui/src/{tools.ts, constants/prompts.ts, memdir/memdir.ts}`
- Reference baseline: `.references/claude-code-sourcemap/restored-src/src/{tools.ts, tools/AgentTool/, constants/prompts.ts, memdir/memdir.ts}`
- 환경: `SPECIFY_FEATURE=2638-tool-system-residue` env 필수 (branch 가 `feat/...` prefix 라 setup 스크립트 우회)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: worktree state 검증 + audit measurement 재현 가능성 확보

- [X] T001 worktree state + audit measurement 재현 검증 — `cd /Users/um-yunsang/KOSMOS-w-2638 && pwd && git branch --show-current` 가 `feat/2638-s2-tool-system-residue` 출력 확인 + `find tui/src/tools/AgentTool -type f | wc -l` 가 18 출력 확인 + research § R-3 의 9 BYTE-IDENTICAL + 9 DIFFERS 분류가 현재 코드 상태와 일치 (재 SHA-256 비교) — 결과 로그를 `specs/2638-tool-system-residue/research.md` 의 R-3 섹션에 변동 시 patch 적용. 변동 없으면 task 통과.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: classification 문서 skeleton + 9 BYTE-IDENTICAL 행 박제. US1 본체 (9 differ 분류) 가 시작하기 전 prerequisite.

**⚠️ CRITICAL**: T002 이전 어떤 user story task 도 시작 X.

- [X] T002 `specs/2638-tool-system-residue/agent-tool-classification.md` skeleton 생성 — frontmatter (date, spec link, plan link, research link) + 헤더 ("AgentTool 18-File Classification") + 4-bucket 분류 정의 섹션 (BYTE-IDENTICAL / PRESERVE-IDENTICAL-WITH-SHIM / MIGRATE-FOR-SWAP / 회귀 의심) + Markdown 분류표 헤더 (`| # | 파일 | SHA-256 | 변경 라인 | 분류 | swap 카테고리 | 근거 (Spec/FR/CC 라인) | 결정 사유 |`) + BYTE-IDENTICAL 9 행 박제 (`agentColorManager.ts`, `agentDisplay.ts`, `agentMemory.ts`, `agentMemorySnapshot.ts`, `built-in/generalPurposeAgent.ts`, `built-in/statuslineSetup.ts`, `constants.ts`, `loadAgentsDir.ts`, `resumeAgent.ts` — 각 행 SHA-256 측정값 명시 + "BYTE-IDENTICAL" 분류 + "CC 본체와 byte-copy" 근거).

**Checkpoint**: classification.md 가 9 BYTE-IDENTICAL 행으로 시작. US1 / US2 / US3 병렬 시작 가능.

---

## Phase 3: User Story 1 — R4 AgentTool 9 differ 정밀 분류 + 박제 (Priority: P1) 🎯 MVP

**Goal**: `tui/src/tools/AgentTool/` 의 9 differ 파일 각각에 대해 (a) `diff -u CC KOSMOS` 실측, (b) PRESERVE-IDENTICAL-WITH-SHIM / MIGRATE-FOR-SWAP / 회귀 의심 4-bucket 분류, (c) swap-1/swap-2/swap-5 카테고리 + 근거 Spec·FR·CC 라인 박제, (d) 회귀 의심 0건 또는 결정 박제. 산출물 = `agent-tool-classification.md` 의 differ 9 행 + 회귀 의심 처리 섹션.

**Independent Test**: `wc -l specs/2638-tool-system-residue/agent-tool-classification.md` ≥ 30 라인 + `grep -c "^| " agent-tool-classification.md` 가 최소 19 행 (헤더 1 + BYTE-IDENTICAL 9 + DIFFERS 9) emit + 9 differ 행 각각에 4 필드 (분류 / swap 카테고리 / 근거 / 결정) 모두 채워짐. 회귀 의심 0건이면 "회귀 의심 0건 — 9 differ 모두 swap-1/swap-2/swap-5 정합" 명시 박제.

### Implementation for User Story 1

- [X] T003 [US1] PRESERVE-IDENTICAL-WITH-SHIM 5 file 분류 행 박제 in `specs/2638-tool-system-residue/agent-tool-classification.md` — 5 파일 (`AgentTool.tsx`, `agentToolUtils.ts`, `forkSubagent.ts`, `runAgent.ts`, `UI.tsx`) 각각 (i) `diff -u .references/claude-code-sourcemap/restored-src/src/tools/AgentTool/<파일> tui/src/tools/AgentTool/<파일>` 실행, (ii) 변경 내용 카테고리 확인 (swap-1 SDK alias 또는 swap-5 telemetry stub spillover), (iii) research § R-3 preview 분류 검증 — 일치 시 행 박제, 불일치 시 회귀 의심 처리 (T005 로 이관). 박제 행 형식: `| N | <파일경로> | <SHA-256 8자리> | <라인수> | PRESERVE-IDENTICAL-WITH-SHIM | swap-1 또는 swap-5 | <근거 인용: Spec NNNN / FR-XXX / CC 라인> | <결정 사유 1-2 문장> |`.

- [X] T004 [US1] MIGRATE-FOR-SWAP 4 file 분류 행 박제 in `specs/2638-tool-system-residue/agent-tool-classification.md` — 4 파일 (`built-in/exploreAgent.ts`, `built-in/planAgent.ts`, `builtInAgents.ts`, `prompt.ts`) 각각 (i) `diff -u CC KOSMOS` 실행, (ii) swap-2 정당성 검증 (Tool surface 결정 / Korean prompt / Task primitive backing FR-017 / citizen agent surface), (iii) research § R-3 preview 분류 검증 — 일치 시 행 박제, 불일치 시 회귀 의심 처리 (T005). 박제 행 형식 동일 (T003), `swap-2` 카테고리. 특히 `prompt.ts` 4-line diff 의 KOSMOS-only 추가 주석 + system prompt 추가는 FR-017 인용 필수.

- [X] T005 [US1] 회귀 의심 verification + 결정 박제 in `specs/2638-tool-system-residue/agent-tool-classification.md` — T003/T004 후 회귀 의심으로 분류된 행이 있다면, 각각 (i) Option A (즉시 CC 회귀) 또는 Option B (swap-2 정당화 헤더 추가 후 PRESERVE/MIGRATE 재분류) 결정, (ii) Option B 선택 시 해당 파일에 박제 주석 추가 (선택). 회귀 의심 0건이면 markdown 의 "## 회귀 의심 처리 결과" 섹션에 "회귀 의심 0건 — preview 분류 (research § R-3) 가 implement 단계에서 모두 검증됨. 9 differ 모두 swap-1/swap-2/swap-5 정합." 박제. 회귀 의심 1+ 건이면 spec Deferred Items 표의 "AgentTool 9 differ 회귀 의심" 행에 후속 처리 issue 번호 박제 (또는 NEEDS TRACKING 유지).

**Checkpoint**: At this point, US1 (R4 분류) 완료 — `agent-tool-classification.md` 가 18 분류 행 + 회귀 의심 처리 결과 모두 박제. SC-001 / SC-005 (US1 부분) / SC-007 (markdown은 코드 LOC 0) 만족.

---

## Phase 4: User Story 2 — R3 14 dev tool import SWAP-2 박제 헤더 (Priority: P2)

**Goal**: `tui/src/tools.ts` 의 14개 dev tool import 블록 (line 19-96 영역) 위에 SWAP-2-RETAINED-IMPORT-BLOCK 박제 헤더 추가. 헤더는 (a) FR-013 인용, (b) 14 도구 + outside-caller count 요약, (c) CC byte-identical 보존 의도 명시.

**Independent Test**: `grep -B1 "SWAP-2-RETAINED-IMPORT-BLOCK" tui/src/tools.ts` 출력에 14 도구 enumerate + outside-caller count 요약 + FR-013 인용이 모두 포함됨. `git diff tui/src/tools.ts | grep "^+" | grep -v "^+++" | wc -l` 가 ~10-20 라인 (주석 추가만, 코드 0 변경).

### Implementation for User Story 2

- [X] T006 [US2] `tui/src/tools.ts` dev tool import 블록 위에 SWAP-2-RETAINED-IMPORT-BLOCK 박제 헤더 추가 — `tui/src/tools.ts` 의 dev tool import 영역 (대략 line 19-27 = `BashTool, FileEditTool, FileReadTool, FileWriteTool, GlobTool, NotebookEditTool, WebFetchTool, TaskStopTool, BriefTool` + line 64-69 = `TaskOutputTool, WebSearchTool, TodoWriteTool, ExitPlanModeV2Tool, TestingPermissionTool, GrepTool` + line 84-96 = `AskUserQuestionTool, LSPTool, ListMcpResourcesTool, ReadMcpResourceTool, ToolSearchTool, EnterPlanModeTool, EnterWorktreeTool, ExitWorktreeTool, ConfigTool, TaskCreateTool, TaskGetTool, TaskUpdateTool, TaskListTool`) 직상에 다중 라인 주석 헤더 추가. 헤더 형식: `// SWAP-2-RETAINED-IMPORT-BLOCK (FR-013):` 로 시작 + (a) "14 dev tool 이 KOSMOS getAllBaseTools() 에 미등록이지만 import 보존 — permissions/sandbox/attachments 인프라가 tool name constants 참조 (FR-013)", (b) "outside-caller count 요약 (BashTool 196, FileReadTool 91, ToolSearchTool 31, ...)", (c) "CC `.references/claude-code-sourcemap/restored-src/src/tools.ts` 의 동일 import 와 byte-identical 보존 (CORE THESIS)", (d) 본 Epic / Spec 인용 (`Spec 2638 / Initiative #2636`). 변경은 주석 추가만 — 코드 동작 0 영향. **주의**: 기존 docstring (line 192-217) 은 그대로 유지, 신규 헤더는 import 블록 직상에 별도 박제.

**Checkpoint**: US2 완료 — tools.ts dev tool import 블록 위에 박제 헤더. SC-005 (US2 부분 — 30초 이내 답 발견) / SC-007 (코드 0 변경, 주석만) 만족.

---

## Phase 5: User Story 3 — R2 isReplModeEnabled 분기 SWAP-2 박제 주석 (Priority: P3)

**Goal**: `isReplModeEnabled()` 호출 4 callsite (`tools.ts:274`, `tools.ts:311`, `prompts.ts:269`, `memdir.ts:385`) 직상에 SWAP-2-PRESERVE 박제 주석 추가. 주석은 (a) Spec 1633 / Epic #2293 의 REPLTool=null chain 인용, (b) CC 동일 라인 byte-identical 인용, (c) "dead-by-design" 마크.

**Independent Test**: `grep -B1 "isReplModeEnabled" tui/src/tools.ts tui/src/constants/prompts.ts tui/src/memdir/memdir.ts | grep -c SWAP-2-PRESERVE` ≥ 4. 박제 주석 형식 일관 (모두 `SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293)` prefix).

### Implementation for User Story 3

- [X] T007 [US3] `tui/src/tools.ts:274` 와 `tui/src/tools.ts:311` 의 `isReplModeEnabled()` 분기 직상에 SWAP-2-PRESERVE 박제 주석 추가 — line 274 위에 `// SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293) — branch byte-identical with CC tools.ts:277, dead-by-design.` + line 311 위에 `// SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293) — branch byte-identical with CC tools.ts:314, dead-by-design.` 추가. **주의**: T006 (US2 헤더) 와 동일 파일이라 [P] 불가 — T006 머지 후 진행. 주석은 `if (isReplModeEnabled() ...)` 직상 빈 라인 또는 새 라인 삽입. 코드 동작 0 영향.

- [X] T008 [P] [US3] `tui/src/constants/prompts.ts:269` 의 `isReplModeEnabled()` 호출 직상에 SWAP-2-PRESERVE 박제 주석 추가 — `// SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293) — call byte-identical with CC constants/prompts.ts:277, dead-by-design.` 추가. T007/T009 와 다른 파일이라 병렬 가능.

- [X] T009 [P] [US3] `tui/src/memdir/memdir.ts:385` 의 `isReplModeEnabled()` 호출 직상에 SWAP-2-PRESERVE 박제 주석 추가 — `// SWAP-2-PRESERVE: REPLTool=null chain (Spec 1633 / Epic #2293) — call byte-identical with CC memdir/memdir.ts:385, dead-by-design.` 추가. T007/T008 와 다른 파일이라 병렬 가능.

**Checkpoint**: US3 완료 — 4 callsite 모두 박제 주석 보유. SC-006 (4 callsite CC 매칭 + 코드 0 변경) 만족.

---

## Phase 6: Polish & Verification (Cross-Cutting)

**Purpose**: 신규 dependency 0 / 코드 동작 0 / typecheck + test parity / 박제 마커 정합성 검증 (audit re-scan 자동 PASS 가능 검증).

- [X] T010 `bun typecheck` parity 검증 — `cd tui && bun run typecheck 2>&1 | tee /tmp/typecheck-2638.log` 실행 후 main 브랜치 동일 명령 결과와 비교. 회귀 0 (실패 카운트 변동 0) 확인. SC-002 만족 검증. 회귀 발견 시 즉시 분석 + revert.

- [X] T011 `bun test` parity 검증 — `cd tui && bun test 2>&1 | tee /tmp/buntest-2638.log` 실행 후 main 브랜치 동일 명령 결과와 비교. 통과/실패/스킵 카운트 변동 0 확인. SC-003 만족 검증. 회귀 발견 시 즉시 분석 + revert.

- [X] T012 `pytest` parity 검증 — `uv run pytest 2>&1 | tee /tmp/pytest-2638.log` 실행 후 main 브랜치 동일 명령 결과와 비교. 통과/실패/스킵 카운트 변동 0 확인. SC-004 만족 검증. (본 Epic 은 Python 미수정이라 회귀 가능성 매우 낮음 — 단 sanity check.)

- [X] T013 박제 마커 정합성 + 신규 dependency 0 검증 — (a) `grep -c "SWAP-2-PRESERVE\|SWAP-2-RETAINED-IMPORT-BLOCK\|SWAP-2-MIGRATE" tui/src/tools.ts tui/src/constants/prompts.ts tui/src/memdir/memdir.ts specs/2638-tool-system-residue/agent-tool-classification.md` 결과가 (T002 의 9 BYTE-IDENTICAL + T003 의 5 SHIM + T004 의 4 SWAP-2 + T006 의 1 헤더 + T007 의 2 + T008 의 1 + T009 의 1) 합산값 ≥ 23 출력 확인. (b) `git diff main -- tui/package.json pyproject.toml` 결과 0 라인 (신규 dependency 0 — SC-008 만족). (c) `git diff --shortstat tui/src/tools.ts tui/src/constants/prompts.ts tui/src/memdir/memdir.ts | awk '{print $4, $6}'` 가 deletion 0 + insertion 만 출력 (코드 0 변경, 주석만 — SC-007 만족).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 즉시 시작 가능
- **Foundational (Phase 2)**: T001 후 시작. T002 가 모든 US 의 prerequisite (classification.md skeleton 존재 필요)
- **User Stories (Phase 3+5)**: T002 후 모두 병렬 시작 가능 (서로 의존 0)
- **Polish (Phase 6)**: 모든 US 완료 후 시작

### User Story Dependencies

- **US1 (P1, R4 분류)**: T002 후 시작 — US2/US3 와 독립, 병렬 가능
- **US2 (P2, R3 박제 헤더)**: T002 후 시작 — US1/US3 와 독립, 병렬 가능
- **US3 (P3, R2 박제 주석)**: T002 후 시작 — US1/US2 와 독립, 단 T007 (tools.ts) 는 T006 (tools.ts) 와 동일 파일이라 sequence 필수

### Within Each User Story

**US1**:
- T003 + T004 모두 `agent-tool-classification.md` 같은 파일 → sequence (T003 → T004) 또는 cohesive 1 task 로 처리 가능. 본 분할은 PRESERVE vs MIGRATE 카테고리 분리로 검증 명확성 우선.
- T005 는 T003 + T004 후 시작 (회귀 의심 결과 종합).

**US2**: T006 단일 task — 의존 없음.

**US3**:
- T007 (tools.ts) 와 T008 (prompts.ts), T009 (memdir.ts) — T008/T009 는 [P] 병렬, T007 은 T006 (tools.ts) 후 sequence.
- T008 + T009 는 다른 파일 → 병렬 가능.

### Parallel Opportunities

- **T002 완료 후**: US1 (Lead 또는 Sonnet teammate sonnet-us1) + US2 (sonnet-us2) + US3 부분 (sonnet-us3) 동시 dispatch 가능
- **US1 내부**: T003/T004 sequential (같은 파일), T005 후행
- **US3 내부**: T007 (T006 후), T008 + T009 [P]
- **Polish**: T010/T011/T012/T013 모두 sequential (서로의 결과 참조)

---

## Sonnet Teammate Dispatch Tree (per AGENTS.md § Agent Teams)

```text
Phase 1 Setup (T001):                   Lead solo
Phase 2 Foundational (T002):            Lead solo
Phase 3 US1 (T003-T005):                sonnet-us1                    ┐
Phase 4 US2 (T006):                     sonnet-us2 — start in parallel ├─ T002 후 병렬
Phase 5 US3 partial (T008, T009):       sonnet-us3                    ┘
Phase 5 US3 finish (T007):              Lead — after T006 완료
Phase 6 Polish (T010-T013):             Lead solo (sequential verification)
```

**Sonnet teammate prompt 가이드** (≤ 30 lines per AGENTS.md):
- sonnet-us1: spec.md US1 + research § R-3 + tasks T003-T005 + classification.md skeleton (T002 산출). 작업: 9 differ 분류 행 박제 + 회귀 의심 결정.
- sonnet-us2: spec.md US2 + research § R-2 + tasks T006 + tools.ts dev tool import 영역 (line 19-96). 작업: SWAP-2-RETAINED-IMPORT-BLOCK 헤더 추가.
- sonnet-us3: spec.md US3 + research § R-1, R-4 + tasks T008/T009 + prompts.ts:269 / memdir.ts:385. 작업: 2 callsite SWAP-2-PRESERVE 박제 주석 추가.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 (Setup) → T002 (Foundational) → T003-T005 (US1)
2. **STOP and VALIDATE**: `agent-tool-classification.md` 18 분류 행 + 회귀 의심 처리 박제 검증
3. MVP 머지 후 US2 / US3 incremental delivery 가능 (별 PR 또는 같은 PR 의 추가 commit)

### Incremental Delivery (single PR 권장 — feedback `feedback_integrated_pr_only`)

본 Epic 은 hygiene-only 라 단일 PR 통합이 적합:
1. T001 + T002 → Foundation
2. T003-T005 (US1) + T006 (US2) + T007-T009 (US3) → 모두 같은 브랜치 commit
3. T010-T013 (Polish) → 통합 verification
4. PR 단일 push → Codex 리뷰 → 머지

### Parallel Team Strategy

T002 완료 후 sonnet-us1 + sonnet-us2 + sonnet-us3 동시 dispatch (3 Sonnet teammate 병렬). Lead 가 마지막 T007 + Phase 6 처리. AGENTS.md 의 "1 Lead Opus + Sonnet team" 패턴 정합.

---

## Notes

- **Task budget**: 13 task / 90 cap (15% utilization). 충분 여유.
- **Code 변경 LOC budget**: ~10 LOC (모두 주석 추가). markdown 새 파일 1개 (~150 LOC).
- **신규 runtime/dev dependency**: 0 (AGENTS.md hard rule).
- **신규 환경 변수**: 0.
- **TUI 동작 변경**: 0 — Layer 5 (tmux capture-pane) smoke 불필요. PR description 에 `TUI behavior no-change` 명시.
- **`SPECIFY_FEATURE` env**: 모든 spec-kit 스크립트 호출 시 `SPECIFY_FEATURE=2638-tool-system-residue` 필수 (branch 가 `feat/...` prefix 라 setup 우회용).
- **Spec 2522 (Epic #2579) rebase**: Spec 2522 머지 후 본 Epic 의 박제 주석 라인 번호 재조정 필요 — trivial conflict.
- **회귀 의심 발견 시**: T005 가 follow-up issue 자동 생성 (NEEDS TRACKING — `/speckit-taskstoissues` 단계에서 Deferred 표 resolution).
- **Codex review 응답**: 모든 push 후 Codex 인라인 코멘트 P1 응답 필수 (CLAUDE.md `## Copilot Review Gate`).
- **PR 머지**: `Closes #2638` only (Task sub-issue 는 PR body 에 미포함, 머지 후 GraphQL 로 close).

