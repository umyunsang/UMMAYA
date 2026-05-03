# Feature Specification: Tool System Residue Cleanup (Audit-Driven CORE THESIS Realignment)

**Feature Branch**: `feat/2638-s2-tool-system-residue`
**Created**: 2026-05-03
**Status**: Draft
**Input**: Initiative #2636 / Epic #2638 — S2 Tool System slice의 R2/R3/R4 잔존 잔재를 CORE THESIS (KOSMOS = CC + 2 swap, byte-identical default) 기준으로 재판단·박제·분류한다. 산출물은 audit 재실행 시 R2/R3/R4 가 자동으로 "INTENTIONAL_PRESERVE" 또는 "CLASSIFIED" 마크로 통과하는 코드 주석 + 분류 문서.

## User Scenarios & Testing *(mandatory)*

> **Stakeholder**: 본 spec의 "사용자"는 (a) Initiative #2636 회귀 감사를 재실행하는 미래 Lead Opus, (b) Epic 머지 후 새 PR을 검토하는 Codex 리뷰어, (c) `tui/src/tools.ts` 를 수정하려는 다음 Sonnet teammate. 셋 모두 "왜 KOSMOS 가 CC와 다르게 보이지만 실은 byte-identical 인가" 또는 "왜 18개 파일 중 9개만 byte-identical 인가" 를 즉시 알 수 있어야 한다.

### User Story 1 — AgentTool 18파일 정밀 분류 + 박제 (Priority: P1)

미래 Lead Opus가 AgentTool 디렉토리에 `git diff` 또는 SHA-256 비교를 돌려 "9 byte-identical / 9 differ" 결과를 본 순간, **각 differ 파일이 어느 버킷 (PRESERVE-IDENTICAL-WITH-SHIM / MIGRATE-FOR-SWAP / 회귀 의심) 에 속하는지** 와 **그 분류의 근거 (어떤 swap-2 종속성, 어떤 Spec, 어떤 라인 변경)** 를 단일 문서에서 확인할 수 있다. 분류 결과가 박제되지 않으면 매 audit 재실행마다 같은 SHA-256 비교를 처음부터 다시 해야 하고, 회귀 판단은 매번 새로 수행되어 일관성을 잃는다.

**Why this priority**: R4 는 본 Epic 의 작업량 대부분 (9개 파일 정밀 분석) 을 차지하고, 유일하게 새 산출물 (classification 문서) 을 생성한다. R2/R3 가 박제 주석 추가로 끝나는 반면 R4 는 swap-2 종속성 입증이라는 본질적 판단이 필요. 이 분류 문서가 없으면 audit 재실행 시 R4 항목이 다시 "needs human review" 로 떨어진다.

**Independent Test**: `grep -c "^| " specs/2638-tool-system-residue/agent-tool-classification.md` 가 9 differ 파일 9 행 + byte-identical 9 파일 9 행 = 최소 18 분류 행 emit. 각 행에 (파일경로, 변경라인수, 버킷, 근거 Spec/라인) 4개 필드 모두 채워짐.

**Acceptance Scenarios**:

1. **Given** `tui/src/tools/AgentTool/` 의 18 파일이 존재, **When** classification 문서를 열람, **Then** 18 파일 모두 분류표에 포함되며 9개는 BYTE-IDENTICAL 행, 9개는 분류 + 근거 행으로 emit
2. **Given** 9 differ 파일 중 회귀 의심 후보가 감지됨, **When** classification 문서를 검토, **Then** 회귀 의심 항목은 (a) 즉시 CC 회귀 가능 / (b) swap-2 정당화 헤더 추가 둘 중 하나로 결정 박제
3. **Given** 분류표가 박제됨, **When** 동일 audit 재실행, **Then** 9 differ 파일 각각이 "CLASSIFIED" 마크로 통과 (needs human review 0 건)

---

### User Story 2 — `tools.ts` dev tool import 14건 SWAP-2 박제 헤더 (Priority: P2)

새 PR 에서 `tools.ts` 를 보는 리뷰어 (Codex 또는 사람) 가 14개 dev tool import (TodoWriteTool, TaskCreateTool, ConfigTool 등) 와 mock-only WebFetchTool/WebSearchTool 등 KOSMOS 13-tool surface 외 import 를 발견했을 때, **"왜 import 되지만 등록 안 되는가" 의 답이 같은 파일 위쪽 박제 주석에서 즉시 보인다**. 현재는 docstring (line 192-217) 이 일부 설명을 포함하지만 14개 import 블록 자체에는 주석이 없어 "dead import 같다 → 제거하자" 라는 회귀 충동이 발생한다.

**Why this priority**: P2. 박제 헤더 추가는 실제 코드 동작을 바꾸지 않고 문서 명확성만 높임. 기능적으로는 재배선 없이도 시스템이 작동하지만, 다음 audit 사이클에서 R3 가 다시 "dead-import 의심" 으로 잡히는 것을 막아 회귀 감사 비용을 줄임.

**Independent Test**: `tui/src/tools.ts` 의 dev tool import 블록 (대략 line 19-96) 위에 `// SWAP-2 박제` 또는 `// SWAP-2 RETAINED-IMPORT` 식의 마커 주석 존재 + 14개 도구 각각의 outside-caller count 인용 + FR-013 명시 + CC byte-identical 보존 의도 명시.

**Acceptance Scenarios**:

1. **Given** 리뷰어가 `tools.ts` 를 신규로 열람, **When** import 섹션을 스캔, **Then** dev tool import 블록 위에 SWAP-2 박제 헤더가 즉시 발견됨
2. **Given** 박제 헤더가 14개 import 의 outside-caller 근거를 인용, **When** Codex 또는 audit re-scan 이 이 블록을 검토, **Then** "PRESERVE-IDENTICAL-WITH-CC + FR-013 sandbox/permissions reference" 로 즉시 통과 (회귀 의심 마크 0)
3. **Given** 헤더가 박제됨, **When** 후속 PR 이 dev tool import 추가/수정, **Then** PR 작성자가 헤더 박제 컨벤션을 따라 새 entry 추가 (회귀 감사 자기-방어)

---

### User Story 3 — `tools.ts` `isReplModeEnabled() && REPLTool` 분기 SWAP-2 박제 주석 (Priority: P3)

`tools.ts:274` 와 `tools.ts:311` 의 `isReplModeEnabled()` 분기를 보는 사람이 **"이 분기는 dead by Spec 1633 (REPLTool=null chain) 이지만 CC byte-identical 보존을 위해 유지된다"** 를 분기 바로 위 1-2 줄 주석에서 확인할 수 있다. 동일한 박제 주석이 `constants/prompts.ts:269` + `memdir/memdir.ts:385` 의 `isReplModeEnabled()` callsite 에도 박제됨.

**Why this priority**: P3. 박제 주석 4곳 추가로 끝나는 가장 작은 작업 단위. 기능 변경 0. 박제가 없어도 audit 재실행 시 R2 가 다시 "분기 dead" 로 잡히지만 영향은 회귀 감사 비용 약간 증가 정도.

**Independent Test**: `grep -B2 "isReplModeEnabled" tui/src/tools.ts tui/src/constants/prompts.ts tui/src/memdir/memdir.ts` 에서 4 callsite 각각 위에 SWAP-2 박제 주석이 존재 (Spec 1633 / Epic #2293 chain 인용 + CC byte-identical 인용).

**Acceptance Scenarios**:

1. **Given** `tools.ts:274` 에서 `if (isReplModeEnabled() && REPLTool)` 분기를 발견, **When** 위 라인을 확인, **Then** "// SWAP-2: dead-by-design (Spec 1633 REPLTool=null chain), CC byte-identical preserved" 식 박제 주석 발견
2. **Given** `prompts.ts:269` + `memdir.ts:385` 에서 `isReplModeEnabled()` 호출, **When** 동일하게 위 라인 확인, **Then** 동일 패턴 박제 주석 발견
3. **Given** 4 callsite 박제 완료, **When** audit re-scan 실행, **Then** R2 항목이 "INTENTIONAL_PRESERVE" 마크로 통과

---

### Edge Cases

- **EC-1**: AgentTool 9 differ 파일 중 어느 하나가 어떤 분류 버킷에도 들어가지 않으면? → "회귀 의심" 으로 분류하고 (a) 즉시 CC 회귀 (b) follow-up issue 생성 둘 중 하나를 spec 안에서 결정
- **EC-2**: 박제 헤더 추가가 `bun typecheck` / `bun test` 를 깨뜨리면? → 주석은 컴파일 영향 0 이라야 함. 코드 변경이 동반되면 본 spec 의 SC-2/SC-3 위반
- **EC-3**: Spec 2522 (Tool surface v4, Epic #2579) 가 같은 `tools.ts` 영역에서 작업 중. 머지 충돌 발생 시 어느 spec 이 우선? → AGENTS.md 컨플릭트 규칙 + 머지 순서: **Spec 2522 가 본 Epic 보다 우선** (공식 4-primitive 표면 정비). 본 Epic 은 Spec 2522 머지 후 rebase 하여 박제 주석을 새 라인 위치에 재적용
- **EC-4**: KOSMOS-only 파일 (`built-in/exploreAgent.ts` 같은 것) 이 BYTE-IDENTICAL 로 잡혔다 → KOSMOS-only 면 SHA-256 비교 자체가 N/A. 본 측정에서 KOSMOS-only 파일 0 (모두 CC 에 동일 경로 존재) 이라 EC 무효
- **EC-5**: 9 byte-identical 파일에 미래 누군가가 1 byte 라도 수정 → audit 재실행 시 그 파일이 differ 로 떨어지고 분류 다시 필요. classification 문서에 "BYTE-IDENTICAL 9 파일 변경 시 재분류 필수" 경고 박제

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템 (KOSMOS 코드베이스) 은 `specs/2638-tool-system-residue/agent-tool-classification.md` 문서를 보유해야 하며, 이 문서는 `tui/src/tools/AgentTool/` 의 모든 파일 (현재 18 개) 을 BYTE-IDENTICAL / PRESERVE-IDENTICAL-WITH-SHIM / MIGRATE-FOR-SWAP / 회귀 의심 4 버킷 중 정확히 한 곳에 매핑해야 한다.
- **FR-002**: classification 문서의 각 differ 파일 항목은 (a) CC 대비 변경 라인 수, (b) 변경의 본질 (SDK shim / telemetry stub / swap-2 mailbox wiring / Task primitive backing 등), (c) swap-2 정당화 근거 (Spec 번호, FR 번호, AGENTS.md 섹션 인용) 를 명시해야 한다.
- **FR-003**: classification 문서는 "회귀 의심" 으로 분류된 파일 각각에 대해 (a) 즉시 CC 회귀 또는 (b) swap-2 정당화 헤더 추가 후 PRESERVE-IDENTICAL-WITH-SHIM/MIGRATE-FOR-SWAP 으로 재분류 둘 중 하나를 결정·박제해야 한다.
- **FR-004**: `tui/src/tools.ts` 는 dev tool import 블록 (TodoWriteTool, TaskCreateTool, ConfigTool, EnterPlanModeTool, EnterWorktreeTool, ExitWorktreeTool, ExitPlanModeV2Tool, AskUserQuestionTool, SkillTool, ScheduleCronTool, TaskOutputTool, TaskGetTool, TaskListTool, TaskUpdateTool, TaskStopTool, TestingPermissionTool, LSPTool, BashTool, FileEditTool, FileReadTool, FileWriteTool, GlobTool, GrepTool, NotebookEditTool, ListMcpResourcesTool, ReadMcpResourceTool, ToolSearchTool 중 R3 의 14개) 위에 SWAP-2 박제 헤더 주석을 보유해야 한다. 헤더는 (a) FR-013 ("permissions/sandbox/attachments references the constants") 인용, (b) outside-caller 가 0 이 아님을 명시 (요약 통계 또는 examples), (c) CC byte-identical 보존 의도 명시를 포함해야 한다.
- **FR-005**: `tui/src/tools.ts` 의 `isReplModeEnabled()` 분기 2곳 (line 303 — `&& REPLTool` 가드 포함, line 341 — env 단독) 직상에 SWAP-2 박제 주석을 추가해야 한다. 주석은 (a) CC `tools.ts:277` / `tools.ts:314` 와 byte-identical 사실 인용, (b) `isReplModeEnabled()` 가 env-gated (`CLAUDE_REPL_MODE` 또는 `USER_TYPE=ant` + `CLAUDE_CODE_ENTRYPOINT=cli`) 라는 사실 명시, (c) line 303 은 `&& REPLTool` 가드로 인해 REPLTool=null (Spec 1633 / Epic #2293) 시 dead, line 341 은 REPLTool 비-종속 (replEnabled 평가 결과로 자연 no-op) 임을 정확히 분류, (d) CC parity 보존 의도 (CORE THESIS) 를 포함해야 한다.
- **FR-006**: `tui/src/constants/prompts.ts:269` 와 `tui/src/memdir/memdir.ts:385` 의 `isReplModeEnabled()` 호출 직상에도 SWAP-2 박제 주석을 추가해야 한다. 주석은 (a) CC 동일 라인 byte-identical 인용, (b) env-gated 사실 명시, (c) REPLTool=null 와 무관한 본인의 동작 (prompts.ts: REPL-aware prompt section 반환 / memdir.ts: embedded search 모드 토글) 정확 명시, (d) CC parity 보존 의도를 포함해야 한다. 두 callsite 모두 "dead-by-design" 으로 분류하면 안 되며 (env 로 활성 가능), 단순 CC parity 보존이라는 보다 정확한 정당성을 제시해야 한다.
- **FR-007**: 본 Epic 의 모든 변경은 신규 runtime dependency 0 (Python `pyproject.toml` 추가 0, TS `tui/package.json` 추가 0) 을 만족해야 한다 (AGENTS.md hard rule).
- **FR-008**: 본 Epic 의 모든 변경은 코드 동작 변경 0 을 만족해야 한다 — 추가되는 것은 주석 + 신규 markdown 문서 1개. `bun typecheck` / `bun test` / `pytest` 결과는 main 대비 회귀 0.
- **FR-009**: classification 문서와 박제 주석은 한국어 primary, 기술 용어 (SDK / shim / telemetry / FR-XXX / SWAP-2 / Spec NNNN) 는 영어 표기 보존. 인용된 CC 라인 번호 + 파일 경로는 절대 경로가 아닌 `.references/claude-code-sourcemap/restored-src/src/...` 형식 상대 경로.
- **FR-010**: classification 문서의 각 분류 결정은 SHA-256 또는 `diff -u` 출력을 단일 근거로 인용해야 하며, 추측 (`likely`, `probably`) 만으로 분류해서는 안 된다.
- **FR-011**: 본 Epic 머지 후 audit 재실행 (`scripts/audit-cc-migration.sh` 또는 동등) 에서 R2/R3/R4 항목이 자동으로 PASS 마크로 통과 (회귀 의심 0 건). audit 스크립트가 박제 주석 마커 (`SWAP-2 박제` 같은 것) 를 인식해야 한다.

### Key Entities

- **Classification Document** (`specs/2638-tool-system-residue/agent-tool-classification.md`):
  - 18 행 분류표 (파일 경로 / SHA-256 비교 결과 / 변경 라인 수 / 분류 버킷 / 근거 Spec·FR·CC 라인 / 결정 사유) + (선택적) 회귀 의심 처리 결과 박제 섹션
- **SWAP-2 박제 주석 마커**: `tui/src/tools.ts` (dev tool import 블록 + REPL 분기 2곳) + `tui/src/constants/prompts.ts` + `tui/src/memdir/memdir.ts` 에 추가되는 짧은 주석 텍스트 (각 1-3 라인)
- **Audit re-scan 산출물** (변경 없음 — 본 Epic 의 검증 도구일 뿐): 박제 주석 + classification 문서가 audit 재실행 시 PASS 마크로 통과함을 입증하는 로그

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: classification 문서가 18 분류 행을 모두 포함하고, 9 differ 파일 중 "회귀 의심" 으로 남은 파일이 0 (모두 PRESERVE-IDENTICAL-WITH-SHIM / MIGRATE-FOR-SWAP / CC 회귀 결정 셋 중 하나로 박제됨).
- **SC-002**: `bun typecheck` 가 본 worktree 에서 main 과 동일하게 통과 (KOSMOS narrows to `src/stubs/**`). 박제 주석 + 신규 markdown 으로 인한 회귀 0.
- **SC-003**: `bun test` parity — main 대비 통과/실패 카운트 변동 0.
- **SC-004**: `pytest` parity — main 대비 통과/실패 카운트 변동 0.
- **SC-005**: 미래 사람이 `tui/src/tools.ts` 를 처음 열어 dev tool import 14건의 박제 헤더를 읽는데 평균 30 초 이내에 "왜 import 되지만 등록 안 되는가" 답을 찾을 수 있음 (헤더 위치 + 인용 명시성으로 측정).
- **SC-006**: 박제 주석 4곳 (REPL 분기 2 + prompts/memdir 2) 이 모두 박제 후, 같은 4 callsite 가 CC restored-src 의 동일 라인 번호와 정확히 매칭됨을 `diff` 로 검증 (코드 라인은 변경 0, 주석만 추가).
- **SC-007**: 본 Epic PR 의 net 코드 변경 (주석 + markdown 제외) = 0 LOC. 모든 변경은 (a) 신규 markdown 1 파일, (b) 기존 4 파일에 주석 추가만으로 구성.
- **SC-008**: 신규 runtime dependency 0 (pyproject.toml + tui/package.json diff 0).

## Assumptions

- **Spec 2522 머지 우선**: 같은 `tui/src/tools.ts` 를 수정하는 Epic #2579 (KOSMOS-w-2522) 가 본 Epic 보다 먼저 머지되며, 본 Epic 은 그 위에 rebase 한다. 박제 주석 라인 번호는 rebase 후 결정.
- **CC restored-src 는 read-only**: `.references/claude-code-sourcemap/restored-src/` 는 본 Epic 에서 수정 0. 비교 base 로만 사용.
- **18 파일 enumerate 안정**: AgentTool 디렉토리 파일 수 (현재 18) 가 본 Epic 진행 중 변동 없음 (US1 분류 도중에 누가 새 파일을 추가하지 않음). 변동 시 spec 재고.
- **outside-caller count 신뢰**: 30 의심 import 모두 outside-callers ≥ 1 이라는 측정 (R3 검증) 이 본 Epic 진행 중 유효. 새 PR 이 import 의 caller 를 0 으로 만들면 박제 헤더의 인용 카운트 갱신 필요.
- **audit 재실행 도구 존재**: Initiative #2636 의 audit 재실행 스크립트가 존재하거나, 같은 grep/SHA-256 방식 수동 재실행이 가능.
- **K-EXAONE / FriendliAI 무관**: 본 Epic 은 LLM 호출 0, 외부 API 호출 0, 네트워크 0. 순수 코드/문서 변경.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **REPLTool / dev tool 등록 표 변경 금지**: KOSMOS 13-tool surface (Spec 1634 P3 contracts/primitive-envelope.md § 1) 는 본 Epic 에서 수정 0. `getAllBaseTools()` 등록 도구 목록 변경은 swap-2 표면 결정이라 별도 Epic.
- **Tool.ts 인터페이스 수정 금지**: `Tool.ts` 는 byte-identical PASS (audit 결과). 본 Epic 에서 수정 0. 인터페이스 시그니처 변경은 swap-2 표면 광범위 영향이라 별도 Epic + ADR 필수.
- **CC restored-src 수정 금지**: source-of-truth read-only. 박제 주석은 KOSMOS 측에만 추가.
- **dev tool 등록 표에 새 도구 추가 금지**: Spec 2522 영역. 본 Epic 머지 후에도 dev tool 14개는 dead import 상태 유지 (FR-013 강조).
- **AgentTool 자체 인터페이스 수정 금지**: AgentTool 의 sub-agent 시그니처는 swap-2 의 Task primitive backing (FR-017) 종속이라 본 Epic 에서 수정 0. 인터페이스 변경 필요 시 별도 Epic.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Audit 재실행 자동 스크립트 (`scripts/audit-cc-migration.sh`) | 본 Epic 은 박제 주석 + classification 문서 산출물에 집중. audit 자동 실행은 R2/R3/R4 PASS 검증의 마지막 1마일이지만 별도 도구 작업 (CI 통합 포함) 이라 분리. | Initiative #2636 follow-up Epic (audit-tooling) | #2674 |
| AgentTool 9 differ 파일 중 회귀 의심 발견 시 즉시 CC 회귀 | 본 Epic 에서는 분류 + 결정 박제까지만. 실제 CC 회귀 코드 변경 (가령 `agentToolUtils.ts` 104 라인 발산을 CC 본체로 되돌리기) 은 swap-2 인터페이스 영향이 클 가능성 있어 별도 Epic 으로 분리. classification 문서가 회귀 의심을 지목하면 follow-up issue 생성. | TBD (회귀 의심 발견 시 결정) | #2675 (조건부) |
| `tools.ts` getAllBaseTools 표 자체의 Spec 2522 통합 | Spec 2522 (Epic #2579) 가 4 primitive surface v4 정비 진행 중. 본 Epic 머지 후 rebase 시 박제 주석 라인 번호 재조정만 필요. | Epic #2579 (Spec 2522) | #2579 |
| dev tool 14 import 의 unit-test 측 caller 정리 | outside-caller count 가 196 (BashTool) 처럼 큰 도구는 다수 unit/integration test 가 import 하는 경우. 테스트 정리는 별도 Epic. 본 Epic 은 박제 헤더만. | TBD (test-cleanup epic) | #2676 |
| KOSMOS-only AgentTool 파일 (현재 0건이지만 future) 분류 정책 | 현재 AgentTool 18 파일 모두 CC 에 동일 경로 존재. 미래 KOSMOS-original AgentTool 확장 (가령 `built-in/koreanGovAgent.ts`) 추가 시 분류 정책 (PRESERVE-AS-SWAP-IMPL) 적용 방법은 별도 Epic. | TBD (when needed) | #2677 |
