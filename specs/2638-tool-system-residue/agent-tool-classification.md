# AgentTool 18-File Classification

**Spec**: [spec.md](./spec.md) (Epic #2638) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)
**Date**: 2026-05-03 | **Audit baseline**: [`specs/cc-migration-audit/scope-S2-tool-system.md`](../cc-migration-audit/scope-S2-tool-system.md)
**CC source-of-truth**: `.references/claude-code-sourcemap/restored-src/src/tools/AgentTool/` (Claude Code 2.1.88)

본 문서는 `tui/src/tools/AgentTool/` 18 파일에 대한 4-bucket 분류표. Initiative #2636 audit 의 R4 ("AgentTool 11파일 정밀 byte 비교") 권고를 Lead Opus 가 18파일로 확장하여 정밀 측정 + 분류한 결과.

## 4-Bucket 분류 정의

- **BYTE-IDENTICAL**: KOSMOS 파일이 CC `.references/claude-code-sourcemap/restored-src/src/tools/AgentTool/<파일>` 와 SHA-256 완전 일치. 추가 검증 불필요.
- **PRESERVE-IDENTICAL-WITH-SHIM**: KOSMOS 파일이 CC 와 다르지만 변경의 본질이 swap-1 (Anthropic SDK alias) 또는 swap-5 (telemetry stub) spillover. 본질 로직 byte-identical, 외피만 KOSMOS shim. CORE THESIS 정합.
- **MIGRATE-FOR-SWAP**: KOSMOS 파일이 swap-2 (Tool surface 결정 / Korean 시민 컨텍스트 / FR-017 Task primitive backing) 본체 종속으로 변경됨. swap-2 정당성 명시 인용 필수.
- **회귀 의심**: 위 3 카테고리 어디에도 안 들어가는 발산. 즉시 결정 필요 (Option A: CC 회귀 / Option B: swap-2 정당화 헤더 추가).

**카테고리 합산**: BYTE-IDENTICAL 9 + PRESERVE-IDENTICAL-WITH-SHIM 5 (preview) + MIGRATE-FOR-SWAP 4 (preview) + 회귀 의심 0 (preview) = 18 ✓

---

## 분류표 — BYTE-IDENTICAL 9 (T002 산출)

CC 와 SHA-256 완전 일치 확인 (2026-05-03 측정). 추가 박제 불필요 — KOSMOS 가 CC 본체를 byte-copy 한 상태 유지.

| # | 파일 | SHA-256 (8자리) | 변경 라인 | 분류 | swap 카테고리 | 근거 (Spec/FR/CC 라인) | 결정 사유 |
|---|---|---|---:|---|---|---|---|
| 1 | `tools/AgentTool/agentColorManager.ts` | `b5a65b50` | 0 | BYTE-IDENTICAL | N/A | CC `.references/claude-code-sourcemap/restored-src/src/tools/AgentTool/agentColorManager.ts` SHA-256 일치 | CC 본체 byte-copy. CORE THESIS preserved. |
| 2 | `tools/AgentTool/agentDisplay.ts` | `8d89463e` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. |
| 3 | `tools/AgentTool/agentMemory.ts` | `f5d4ce3b` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. |
| 4 | `tools/AgentTool/agentMemorySnapshot.ts` | `f89b7d04` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. |
| 5 | `tools/AgentTool/built-in/generalPurposeAgent.ts` | `79ec39e7` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. KOSMOS 의 시민용 default agent 도 동일. |
| 6 | `tools/AgentTool/built-in/statuslineSetup.ts` | `d364fd00` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. statusline 기능 KOSMOS 비활성이지만 import 보존 (CORE THESIS). |
| 7 | `tools/AgentTool/constants.ts` | `d2da1c4a` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. AGENT_TOOL_NAME 등 상수. |
| 8 | `tools/AgentTool/loadAgentsDir.ts` | `06cb0d5a` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. agents.md loader. |
| 9 | `tools/AgentTool/resumeAgent.ts` | `3bb835c4` | 0 | BYTE-IDENTICAL | N/A | CC SHA-256 일치 | CC 본체 byte-copy. agent resume 기능. |

---

## 분류표 — DIFFERS 9 (T003/T004 산출 — placeholder)

본 섹션은 **T003 (PRESERVE-IDENTICAL-WITH-SHIM 5 file) + T004 (MIGRATE-FOR-SWAP 4 file)** 에서 각 파일별 정밀 `diff -u CC KOSMOS` 측정 후 박제됨. preview 분류는 [research.md § R-3](./research.md) 참고.

### T003 — PRESERVE-IDENTICAL-WITH-SHIM 5 file

| # | 파일 | SHA-256 (8자리) | 변경 라인 | 분류 | swap 카테고리 | 근거 (Spec/FR/CC 라인) | 결정 사유 |
|---|---|---|---:|---|---|---|---|
| 10 | `tools/AgentTool/AgentTool.tsx` | `669a0af8` | 9 | PRESERVE-IDENTICAL-WITH-SHIM | swap-1 + swap-5 | research § R-3 # 1 — (a) `teleportToRemote` CC import → inline no-op async stub (swap-1: Anthropic `claude.ai cloud teleport` 제거, Spec 1633 / Epic #2293); (b) `proactiveModule` CC growthbook require → `isProactiveActive` import from `utils/proactiveModule.js` (swap-5: Anthropic growthbook 텔레메트리 제거) | 변경 본질은 swap-1 SDK alias + swap-5 telemetry stub 2개 뿐. 본질 로직 (shouldRunAsync 조건, agent lifecycle) byte-identical. CORE THESIS 정합. |
| 11 | `tools/AgentTool/agentToolUtils.ts` | `301e215d` | 104 | PRESERVE-IDENTICAL-WITH-SHIM | swap-5 | research § R-3 # 2 — `ToolPermissionContext` import 제거 + `isInProtectedNamespace` 사용처 삭제 + `yoloClassifier` block 전체 삭제 (~90줄). yoloClassifier = Anthropic growthbook auto-mode TRANSCRIPT_CLASSIFIER. Spec 1633 / Epic #2293 삭제 spillover (swap-5 telemetry) | `classifyHandoffIfNeeded` 본체 및 호출 경로 전부 yoloClassifier 종속 → 삭제 정당. 나머지 `agentToolUtils` 로직 (getMaxThinkingTokens, token counting, 등) byte-identical. CORE THESIS 정합. |
| 12 | `tools/AgentTool/forkSubagent.ts` | `cc31dd56` | 2 | PRESERVE-IDENTICAL-WITH-SHIM | swap-1 | research § R-3 # 6 — `@anthropic-ai/sdk/resources/beta/messages/messages.mjs` → `src/sdk-compat.js` import path 1줄 교체 (swap-1 SDK alias spillover) | 변경은 import path 1줄만. 함수 본체 byte-identical. CORE THESIS 정합. |
| 13 | `tools/AgentTool/runAgent.ts` | `2c537faa` | 12 | PRESERVE-IDENTICAL-WITH-SHIM | swap-5 | research § R-3 # 8 — `services/api/promptCacheBreakDetection` import → no-op `cleanupAgentTracking` stub; `utils/telemetry/perfettoTracing.js` 3 함수 → no-op stubs. 두 모듈 모두 Spec 1633 P1 에서 삭제된 Anthropic 텔레메트리 (swap-5 telemetry spillover) | 텔레메트리 stub 교체 3개. 에이전트 실행 로직 (runAgentWithTokenTracker, session lifecycle) byte-identical. CORE THESIS 정합. |
| 14 | `tools/AgentTool/UI.tsx` | `9b691cc6` | 2 | PRESERVE-IDENTICAL-WITH-SHIM | swap-1 | research § R-3 # 9 — `@anthropic-ai/sdk/resources/index.mjs` → `src/sdk-compat.js` import path 1줄 교체 (swap-1 SDK alias spillover) | 변경은 import path 1줄만. 컴포넌트 본체 byte-identical. CORE THESIS 정합. |

### T004 — MIGRATE-FOR-SWAP 4 file

| # | 파일 | SHA-256 (8자리) | 변경 라인 | 분류 | swap 카테고리 | 근거 (Spec/FR/CC 라인) | 결정 사유 |
|---|---|---|---:|---|---|---|---|
| 15 | `tools/AgentTool/built-in/exploreAgent.ts` | `aceb2043` | 91 | MIGRATE-FOR-SWAP | swap-2 | research § R-3 # 3 — CC `exploreAgent.ts` (~91줄) 전체가 Bash/FileEdit/Glob/Grep/NotebookEdit dev tool 이름 + 동작 참조 포함 read-only codebase exploration prompt. KOSMOS 13-tool 시민용 surface 에서 dev tool 미등록 → CC prompt 무의미. KOSMOS는 `EXPLORE_AGENT = { agentType: 'explore', description: ... }` 최소 stub으로 교체 (ESM link 유지). Audit `scope-S2-tool-system.md § MIGRATE-FOR-SWAP` 와 동일 패턴 | Dev tool 미등록 시민용 Tool surface 결정 (swap-2) 이 CC explore prompt 전체를 무의미하게 만듦. Stub은 `builtInAgents.ts` ESM import chain 을 끊지 않기 위한 최소 존재. CORE THESIS 정합 (swap-2 정당화 명시). |
| 16 | `tools/AgentTool/built-in/planAgent.ts` | `7edfe358` | 98 | MIGRATE-FOR-SWAP | swap-2 | research § R-3 # 4 — CC `planAgent.ts` (~98줄) 전체가 Bash/FileEdit/Glob/Grep dev tool 종속 plan composition agent prompt. KOSMOS dev tool 미등록 → CC prompt 무의미. `PLAN_AGENT = { agentType: 'plan', description: ... }` 최소 stub 교체. exploreAgent 와 동일 패턴. | exploreAgent 와 동일 swap-2 정당성 — dev tool 의존 CC plan prompt 전체가 KOSMOS citizen surface 에서 무의미. Stub 존재로 ESM import 유지. CORE THESIS 정합. |
| 17 | `tools/AgentTool/builtInAgents.ts` | `4b4f6793` | 44 | MIGRATE-FOR-SWAP | swap-2 | research § R-3 # 5 — CC 4 import 제거 (`claudeCodeGuideAgent` / `EXPLORE_AGENT` CC버전 / `PLAN_AGENT` CC버전 / `verificationAgent`) + `getFeatureValue_CACHED_MAY_BE_STALE` from growthbook 제거 + `areExplorePlanAgentsEnabled()` 함수 → `return false` stub. KOSMOS는 `GENERAL_PURPOSE_AGENT` + `STATUSLINE_SETUP_AGENT` 2개만 등록. 시민용 agent surface 결정 = swap-2. | CC dev-centric built-in agent 4종 (explore/plan/claudeCodeGuide/verification) 은 KOSMOS citizen surface 와 무관 (swap-2). `areExplorePlanAgentsEnabled()` 는 caller 호환 유지 위해 `false` stub 보존. CORE THESIS 정합. |
| 18 | `tools/AgentTool/prompt.ts` | `a9a69b37` | 4 | MIGRATE-FOR-SWAP | swap-2 | research § R-3 # 7 — 2-line comment 추가 ("Task primitive backing (KOSMOS L1-C C6): AgentTool backs the reserved 'Task' primitive verb for Korean public-service agent orchestration.") + `shared` 상수 첫 문장 뒤에 1줄 추가 ("This tool backs the Task primitive for orchestrating Korean public-service agents."). FR-017 (AgentTool repurposed as Task primitive backing) 직접 인용. | KOSMOS L1-C C6 Task primitive backing 을 LLM 가시 prompt 에 박제 (swap-2: Korean 시민 컨텍스트 + Task primitive backing). 나머지 prompt 본문 byte-identical. FR-017 인용. |

---

## 회귀 의심 처리 결과 (T005 산출 — placeholder)

**회귀 의심 0건** — preview 분류 (research § R-3) 가 implement 단계에서 모두 검증됨. 9 differ 모두 swap-1/swap-2/swap-5 정합. 박제 완료 (T005).

---

## 변경 시 재분류 (Edge Case EC-5)

본 분류표의 BYTE-IDENTICAL 9 파일 또는 DIFFERS 9 파일에 누군가 1 byte 라도 수정 시 audit 재실행에서 SHA-256 변동 감지 → 본 분류표 재검증 필요. Initiative #2636 의 audit 자동 스크립트 (#2674) 가 최종 게이트.

## Reference

- spec.md FR-001/FR-002/FR-003 — classification 문서 요구사항
- research.md § R-3 — preview 분류 (T003/T004 의 baseline)
- AGENTS.md § CORE THESIS — KOSMOS = CC + 2 swap, byte-identical default
- Initiative #2636 — CC Migration Audit-Driven Realignment
