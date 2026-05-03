# Implementation Plan: Tool System Residue Cleanup (Audit-Driven CORE THESIS Realignment)

**Branch**: `feat/2638-s2-tool-system-residue` | **Date**: 2026-05-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/2638-tool-system-residue/spec.md`

**Note**: This plan is filled in by `/speckit-plan`. Source-of-truth for the workflow remains `.specify/templates/plan-template.md`.

## Summary

Initiative #2636 의 S2 Tool System slice (`specs/cc-migration-audit/scope-S2-tool-system.md`) 가 식별한 잔존 잔재 3건 (R2 REPLTool 분기 / R3 14 dev tool dead-import / R4 AgentTool 18파일 SHA-256 분류) 를 CORE THESIS (KOSMOS = CC + 2 swap, byte-identical default) 기준으로 재판단·박제·분류한다.

**핵심 통찰 (specify 단계 측정 결과)**:
- **R2** — KOSMOS `tools.ts:274,311` 의 `isReplModeEnabled() && REPLTool` 분기는 CC `tools.ts:277,314` 와 byte-identical. Spec 1633 으로 `REPLTool=null` 처리되어 dead 하지만 분기 자체 제거 = KOSMOS-only divergence = CORE THESIS 위반. **결론: 분기 보존 + SWAP-2 박제 주석 추가**.
- **R3** — 30개 의심 dev tool import 모두 outside-callers ≥ 1 (ConfigTool 1 ~ BashTool 196). FR-013 ("permissions/sandbox/attachments references constants") confirmed. **결론: 14 import 보존 + SWAP-2 박제 헤더 추가**.
- **R4** — `tui/src/tools/AgentTool/` 18파일 SHA-256 비교: BYTE-IDENTICAL 9 / DIFFERS 9 (변경 라인 2 ~ 104). **결론: classification 문서로 9 differ 정밀 분류 (SDK shim spillover / telemetry stub spillover / Spec 027 mailbox 종속 / Korean prompt / 회귀 의심) + 회귀 의심 발견 시 결정 박제**.

본 Epic 의 산출물은 (a) 신규 markdown 1 파일 (`agent-tool-classification.md`), (b) 기존 4 TS 파일에 박제 주석 추가 (`tui/src/tools.ts` + `tui/src/constants/prompts.ts` + `tui/src/memdir/memdir.ts`). 코드 동작 변경 0, 신규 dependency 0.

## Technical Context

**Language/Version**: TypeScript 5.6+ on Bun v1.2.x (TUI, 변경 없음). Python 3.12+ (백엔드, 본 Epic은 미수정).
**Primary Dependencies**: 모두 기존 — `ink`, `react`, `@inkjs/ui`, `string-width`, `zod`, `@modelcontextprotocol/sdk` (TS); `pydantic >= 2.13`, `pydantic-settings >= 2.0`, `httpx >= 0.27`, `opentelemetry-sdk`, `pytest`, `pytest-asyncio` (Python). **신규 runtime dependency 0** (AGENTS.md hard rule).
**Storage**: N/A. 본 Epic 은 코드/문서 변경만이며 runtime state 0.
**Testing**: `bun typecheck` (KOSMOS narrows to `src/stubs/**`), `bun test` (parity vs main), `pytest` (parity vs main). 박제 주석 + markdown 만이라 회귀 0 기대.
**Target Platform**: 모든 KOSMOS 지원 플랫폼 (macOS / Linux 터미널). 본 Epic 은 platform-agnostic.
**Project Type**: hygiene / documentation-only spec on top of existing TUI + backend mono-repo.
**Performance Goals**: N/A. 본 Epic 은 perf 영향 0.
**Constraints**: (a) Spec 2522 (Epic #2579, KOSMOS-w-2522) 가 같은 `tools.ts` 영역 작업 중 → 본 Epic 은 Spec 2522 머지 후 rebase. (b) `bun typecheck` / `bun test` / `pytest` parity 필수 (SC-002~004). (c) net 코드 LOC 변경 0 (SC-007 — 주석/markdown 만).
**Scale/Scope**: 1 신규 markdown (~150 LOC) + 4 TS 파일 박제 주석 추가 (각 1-3 라인) = 총 ~10 LOC 코드 주석 + ~150 LOC markdown.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

본 Epic 의 헌법 컴플라이언스 평가 (`.specify/memory/constitution.md` v1.1.1 기준):

| Principle | Status | 근거 |
|---|---|---|
| **I. Reference-Driven Development** | ✅ PASS | 모든 설계 결정이 CC restored-src (`.references/claude-code-sourcemap/restored-src/src/{tools.ts,Tool.ts,tools/AgentTool/,constants/prompts.ts,memdir/memdir.ts}`) 와 Initiative #2636 audit 산출물 (`specs/cc-migration-audit/scope-S2-tool-system.md`) 에 직접 trace. 본 Epic 은 reference-driven 의 모범 사례 — Audit 권고를 그대로 수용하지 않고 CC byte-identical baseline 으로 재검증해 R2/R3 false positive 감지. |
| **II. Fail-Closed Security (NON-NEGOTIABLE)** | ✅ PASS (N/A) | 본 Epic 은 permission policy 0 변경. 박제 주석 + classification 문서만이라 권한 표면 0 영향. KOSMOS-invented permission classifications (5-mode / pipa_class / auth_level / etc.) 모두 Spec 1979 으로 이미 제거됨. 본 Epic 은 그것들을 재도입하지 않음. |
| **III. Pydantic v2 Strict Typing (NON-NEGOTIABLE)** | ✅ PASS (N/A) | 본 Epic 은 tool I/O schema 0 변경. AgentTool / dev tool / REPL 의 기존 Pydantic 모델 (있다면) 0 수정. 신규 모델 0. |
| **IV. Government API Compliance** | ✅ PASS (N/A) | 본 Epic 은 외부 API 호출 0. data.go.kr 미접촉. 신규 어댑터 0. |
| **V. Policy Alignment** | ✅ PASS (N/A) | 본 Epic 은 PIPA flow 0 변경. 시민 데이터 흐름 0 영향. |
| **VI. Deferred Work Accountability** | ⚠ PASS (조건부) | spec.md 의 "Scope Boundaries & Deferred Items" 에 5 deferred 항목 박제 (audit 자동화 / R4 회귀 의심 즉시 회귀 / Spec 2522 통합 / dev tool test caller 정리 / KOSMOS-only AgentTool 분류 정책). 모두 `NEEDS TRACKING` 마커 — `/speckit-taskstoissues` 단계에서 issue 생성. |

**Gate result**: PASS. Complexity Tracking 불필요.

## Project Structure

### Documentation (this feature)

```text
specs/2638-tool-system-residue/
├── plan.md                           # 본 파일 (/speckit-plan 산출물)
├── research.md                       # Phase 0 산출물 (/speckit-plan)
├── tasks.md                          # Phase 2 산출물 (/speckit-tasks 단계)
├── spec.md                           # /speckit-specify 산출물 (이미 작성)
├── agent-tool-classification.md      # US1 (P1) 의 핵심 산출물 — 18파일 분류표
├── checklists/requirements.md        # /speckit-specify 산출물 (이미 작성)
├── data-model.md                     # N/A — 본 Epic 은 데이터 모델 0
├── quickstart.md                     # N/A — 본 Epic 은 사용자 향 기능 0
└── contracts/                        # N/A — 본 Epic 은 외부 contract 0
```

**N/A 명시 근거** (Phase 1 의 의무 산출물 중 본 Epic 에서 생성하지 않는 것):
- `data-model.md`: 본 Epic 은 markdown 분류 표 + TS 파일 박제 주석만 추가. 새 데이터 entity / 필드 / 관계 0. spec.md 의 "Key Entities" 섹션이 ~3개 항목 (classification document, SWAP-2 박제 주석 마커, audit re-scan 산출물) 을 나열하지만 모두 documentation entity 이지 코드 layer entity 가 아님.
- `contracts/`: 본 Epic 은 외부 인터페이스 0. CLI / API / RPC / event schema 0 변경. Tool.ts 인터페이스도 무수정 (Out of Scope 명시).
- `quickstart.md`: 본 Epic 은 사용자 (개발자 또는 시민) 가 직접 실행할 신규 기능 0. 산출물은 미래 audit re-scan 자동 통과 / Codex 리뷰어 즉시 이해 같은 indirect benefit 만 — quickstart 가 적용될 시나리오 없음.

### Source Code (repository root) — 변경 영향 표면

```text
tui/src/
├── tools.ts                          # 박제 주석 추가 (R2 분기 2곳 + R3 dev tool import 헤더 1곳)
├── constants/prompts.ts              # 박제 주석 추가 (R2 isReplModeEnabled 호출 직상)
├── memdir/memdir.ts                  # 박제 주석 추가 (R2 isReplModeEnabled 호출 직상)
└── tools/AgentTool/                  # 18파일 — 코드 0 수정. classification 문서가 별도 markdown 으로 분류만.

specs/2638-tool-system-residue/agent-tool-classification.md    # 신규 markdown
```

**비변경 표면**:
- `tui/src/Tool.ts` — byte-identical PASS (audit). Out of Scope.
- `tui/src/tools/AgentTool/*` — 18파일 코드 0 수정. classification 문서로 메타정보만 박제.
- `tui/src/tools/REPLTool/*` — Spec 1633 으로 이미 `REPLTool = null` chain 처리 완료. Out of Scope.
- 신규 디렉토리 0.
- 신규 파일 0 (markdown 1개 제외).
- Python 백엔드 (`src/kosmos/**`) 0 수정.

**Structure Decision**: 본 Epic 은 KOSMOS 의 **Layer 2 (Tool System)** hygiene cleanup. Migration tree (`docs/requirements/kosmos-migration-tree.md § L1-B`) 의 B1 (CC `Tool` 인터페이스 byte-identical 사용) 결정에 정합. 새 디렉토리 / 모듈 / 패키지 추가 0. 기존 4 TS 파일에 박제 주석 + 1 신규 markdown 으로 끝.

## Phase 0 — Research

산출물: [`research.md`](./research.md). 본 Epic 의 research 는 (a) Audit 권고 vs CORE THESIS 충돌 해결, (b) AgentTool 9 differ 파일의 변경 카테고리 사전 조사, (c) 박제 주석 텍스트 컨벤션 결정 셋이 핵심. 모든 NEEDS CLARIFICATION 0건 (specify 단계에서 이미 모든 결정을 reasonable defaults 로 박제).

## Phase 1 — Design & Contracts

본 Epic 은 hygiene-only 이므로 Phase 1 의 의무 산출물 중 다음은 N/A:
- `data-model.md` — entity/필드 0
- `contracts/` — 외부 인터페이스 0
- `quickstart.md` — 사용자 시나리오 0

대신 Phase 1 산출물은:
- **`agent-tool-classification.md` 의 헤더 + 9 byte-identical 행만 박제** (US1 의 시작점). 9 differ 행 정밀 분류는 implementation 단계 (`/speckit-implement`).
- **Agent context update**: `.specify/scripts/bash/update-agent-context.sh claude` 실행으로 CLAUDE.md "Active Technologies" + "Recent Changes" 박제.

## Complexity Tracking

위 Constitution Check 가 모든 gate PASS — 본 섹션은 N/A. 본 Epic 은 단순 documentation hygiene 이라 헌법 위반 0.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (없음) | (없음) | (없음) |

## Risk Mitigation Plan

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **R-A**: AgentTool 9 differ 파일 중 회귀 의심 1+건 발견 | 중 | 중 | `/speckit-implement` 단계에서 회귀 의심 발견 시 spec FR-003 의 결정 경로 ((a) 즉시 CC 회귀 OR (b) swap-2 정당화 헤더) 따라 즉시 박제. 즉시 회귀 옵션 선택 시 코드 동작 변경 발생 가능 — 그 경우 SC-007 (net LOC 0) 위반이지만 SC-001 (회귀 의심 0건) 우선. follow-up issue 자동 생성. |
| **R-B**: Spec 2522 (#2579) 머지 충돌 | 중 | 낮 | 박제 주석은 단순 텍스트 추가라 conflict 발생 시 trivial resolution. Assumptions 박제됨. PR 머지 순서: Spec 2522 → 본 Epic. 본 Epic 머지 전 main 으로 rebase. |
| **R-C**: 박제 주석 마커 텍스트가 audit 도구 파싱과 미스매칭 | 낮 | 중 | 본 Epic 은 audit 자동 스크립트 미존재 상태에서 진행. 마커 컨벤션을 미리 합의 (`// SWAP-2 박제 ...` 또는 `/* SWAP-2 RETAINED-IMPORT ... */`) 하고 research.md 에 박제. audit 자동화는 별도 Epic (Deferred). |
| **R-D**: classification 문서가 분류 도중에 18 파일 수가 변동 | 낮 | 중 | spec Assumptions 에 박제됨 — `/speckit-implement` 시작 시 `find tui/src/tools/AgentTool -type f \| wc -l` 로 18 재확인. 변동 시 spec / plan 재고. |
| **R-E**: `bun test` parity 깨짐 (의도 외 회귀) | 낮 | 높 | 본 Epic 의 모든 코드 변경은 주석 추가만 → 컴파일러/runtime 영향 0. `bun typecheck` + `bun test` 를 Phase 6 (Polish) 의무 통과 게이트로 박제. 회귀 발생 시 즉시 회귀 분석 + revert. |

## Reference Mapping (per Constitution Principle I)

본 Epic 의 모든 설계 결정 → reference 매핑:

| Decision | Primary reference | 인용 위치 |
|---|---|---|
| R2 박제 주석 (REPL 분기 보존) | `.references/claude-code-sourcemap/restored-src/src/tools.ts:277,314` (CC 본체 분기) | spec FR-005, plan Summary |
| R3 박제 헤더 (14 dev tool import 보존) | `.references/claude-code-sourcemap/restored-src/src/tools.ts` (CC 본체 import 표) + KOSMOS `tools.ts:192-217` (FR-013 docstring) | spec FR-004, plan Summary |
| R4 AgentTool 9 byte-identical 보존 | `.references/claude-code-sourcemap/restored-src/src/tools/AgentTool/{agentColorManager.ts, agentDisplay.ts, agentMemory.ts, agentMemorySnapshot.ts, built-in/generalPurposeAgent.ts, built-in/statuslineSetup.ts, constants.ts, loadAgentsDir.ts, resumeAgent.ts}` | spec US1, plan Summary |
| R4 9 differ 분류 알고리즘 | Audit `scope-S2-tool-system.md § MIGRATE-FOR-SWAP table # 6` (AgentTool R4 권고) + `docs/vision.md § Layer 2 — Tool System § Tool definition shape` | research.md |
| 박제 주석 마커 컨벤션 (`// SWAP-2 ...`) | KOSMOS 기존 컨벤션 (`tools.ts:34-35,50-51,70-71,102-103,137-139` 의 `// KOSMOS Spec 1633 / Epic #2293 ...` 주석 패턴) | research.md |
| Spec 2522 머지 우선 | `docs/requirements/kosmos-migration-tree.md § L1-B B1` (Tool 등록 메커니즘 byte-identical) + 워크트리 `KOSMOS-w-2522` 활성 | spec Assumptions, plan Risk R-B |
| Constitution Principle VI deferred tracking | `.specify/memory/constitution.md § VI` | spec "Scope Boundaries & Deferred Items" + tasks 단계 NEEDS TRACKING resolution |

## Acceptance Hand-off to `/speckit-tasks`

`/speckit-tasks` 가 본 plan 으로부터 생성해야 할 task category:

1. **Phase 1 (Setup)**: 워크트리 검증, audit measurement command 박제 (research.md 와 일치) — 이미 거의 done.
2. **Phase 2 (Foundational)**: `agent-tool-classification.md` skeleton + 9 byte-identical 행 박제.
3. **Phase 3 (US1 P1)**: 9 differ 파일 정밀 `diff -u CC KOSMOS` + 카테고리 분류 + 회귀 의심 결정 박제 — 9 task ([P] mark 가능: 파일별 독립).
4. **Phase 4 (US2 P2)**: `tools.ts` dev tool import 박제 헤더 추가 — 1 task.
5. **Phase 5 (US3 P3)**: `tools.ts:274` + `tools.ts:311` + `prompts.ts:269` + `memdir.ts:385` 4 callsite 박제 주석 추가 — 4 task ([P] mark 가능: 파일별 독립).
6. **Phase 6 (Polish)**: `bun typecheck`, `bun test`, `pytest` parity 검증 + 가능 시 audit 재실행 검증 — 2 task.

총 예상 task 수 ~17개. Sonnet teammate 병렬 dispatch 후보 = Phase 3 (9 differ 파일별 9 task) + Phase 5 (4 callsite 4 task). Phase 4 는 Phase 3 의 결과 무관하게 진행 가능.
