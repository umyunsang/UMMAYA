# Handoff prompt — KOSMOS K-EXAONE tool wiring (CC reference migration)

> **이 파일을 다음 세션에 그대로 붙여넣어 시작하세요.** 전 세션 컨텍스트 없이 cold start로 동작하도록 self-contained로 작성됐습니다.
>
> 모델 권장: Opus (planning + reference 분석 무거움). Auto mode 사용 가능. 큰 단위 마이그레이션이라 `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` 의 정공 spec-driven cycle 권장. 시간 압박이 있으면 직접 implement도 가능하지만 스코프가 7개 영역에 걸침을 기억할 것.

---

## 1. 작업 목적 (한 문단)

K-EXAONE이 `<tool_call>{"name":"Read",...}</tool_call>` 같은 **CC 학습 데이터 도구를 hallucinate하는 문제**를 해결한다. 진짜 원인은 **TUI가 `ChatRequestFrame.tools`를 비워 보내고 backend도 fallback inject가 없어서** K-EXAONE이 `tools=None`으로 호출되는 것. 그 결과 모델은 KOSMOS의 active primitives(`lookup`, `resolve_location`, `submit`, `verify`)를 모르고 자기 학습 데이터에 있는 CC tool들(Read, Glob, Bash 등)을 응답에 박는다. 본 epic은 CC 소스맵의 tool wiring + agentic loop 패턴을 KOSMOS로 마이그레이션해서 K-EXAONE이 KOSMOS-등록 도구만 호출하고, 호출 결과가 `tool_use` content block으로 transcript에 paint되고, follow-up turn까지 진행되도록 만든다.

## 2. 시작 전에 반드시 읽을 문서

순서대로:

1. `AGENTS.md` — KOSMOS 룰 (Conventional Commits, English source, no Co-Authored-By 등)
2. `docs/vision.md` — 6-layer 아키텍처
3. `docs/requirements/kosmos-migration-tree.md § L1-A.A3 + § P3` — Tool protocol = K-EXAONE native function calling, P3 phase 정의
4. `docs/spec-streaming-ui-projection/epic-plan.md` — 직전 epic, paint chain root cause + 디버깅 패턴
5. `src/kosmos/llm/_cc_reference/claude.ts:1900-2304` — 직전 commit `33478d4`로 cp 된 CC streaming/agentic baseline
6. **메모리 파일들** (`/Users/um-yunsang/.claude/projects/-Users-um-yunsang-KOSMOS/memory/`):
   - `feedback_cc_source_migration_pattern.md` — "task-level implementation은 CC 소스맵 복사 → 마이그레이션. 새로 작성 X"
   - `feedback_check_references_first.md` — 코딩 전에 reference 인용 후 정합 확인
   - `feedback_runtime_verification.md` — PTY로 TUI 직접 띄워 사용자 시점 검증까지

## 3. 환경 사전 점검

```bash
cd ~/KOSMOS
git log -3 --oneline
# 33478d4 feat(llm): KOSMOS-1633 P3 — wire K-EXAONE thinking via CC reference
# a7fc8f6 fix(tui): KOSMOS-1633 P3 — assistant message paint chain unblocked
# f459bfb feat(tui): KOSMOS-1633 P3 — stream-event projection for incremental paint
git status                  # clean (또는 docs/* dirty만 OK)
ls .env                     # KOSMOS_FRIENDLI_TOKEN 필수

cd tui && bun run typecheck && bun test tests/adr-precheck.test.ts tests/entrypoints tests/hooks tests/i18n tests/ink tests/ipc tests/memdir tests/permissions tests/primitive tests/store tests/theme tests/unit
# 286 pass / 0 fail

cd .. && uv run pytest tests/llm tests/ipc
# 426 pass / 0 fail
```

## 4. 핵심 진단 결과 (이전 세션에서 line-cited 확정)

### 4.1 Backend 누락 (`src/kosmos/ipc/stdio.py`)

| 영역 | 현재 상태 | 필요 변경 |
|---|---|---|
| `frame.tools` unpack (line 1099-1101) | `LLMToolDefinition.model_validate(t.model_dump())` 정상 | OK — 그대로 유지 |
| **frame.tools 빈 경우 fallback** | **없음** — `llm_tools=[]`로 LLM 호출 | `ToolRegistry().export_core_tools_openai()` 또는 active primitive 자동 inject |
| **system prompt 도구 list 주입** | **없음** — `prompts/system_v1.md` 8 lines 순수 산문 | system prompt 끝에 `## Available tools` 섹션을 active primitive signature로 자동 append |
| Registry 인스턴스화 (line 916) | `_dispatch_primitive()` 안에서만 매번 new — wasteful | session 시작 시 1회 instantiate, `_handle_chat_request` 진입 전 ready |
| Whitelist (line 1278-1284) | 하드코딩된 primitive list | primitives 카탈로그(`src/kosmos/primitives/__init__.py` 또는 `manifest.yaml`)에서 single source of truth로 끌어오기 |
| Tool result follow-up (line 1412-1419) | `LLMChatMessage(role="tool", content=payload, name=fname, tool_call_id=cid)` | OK — 그대로 유지 |

### 4.2 TUI 누락 (`tui/src/query/deps.ts`)

| 영역 | 현재 상태 | 필요 변경 |
|---|---|---|
| ChatRequestFrame 빌드 (deps.ts:73-81) | `tools` 필드 omit | `getAllBaseTools()` → active primitives + MVP 보조 → `ToolDefinition[]`로 직렬화해 spread |
| Tool object pool (`tui/src/tools.ts:228-257`) | active primitive tools 정의 존재 | Zod inputSchema → JSON Schema 2020-12 변환 + `name`/`description` 추출하는 `toToolDefinition()` 헬퍼 추가 |
| tool_call frame 처리 (deps.ts:237-242) | `createSystemMessage("🔧 …")` — display-only progress line | CC 패턴으로 `stream_event{content_block_start, content_block:{type:'tool_use', id, name, input}}` + `content_block_stop` yield → `AssistantToolUseMessage` 가 native 렌더 |
| tool_result frame 처리 (deps.ts:245-249) | `createSystemMessage("✓ ok …")` | `tool_use_id` 매칭으로 user-message에 `tool_result` content block append (`createUserMessage` with tool_result content) |
| permission_request frame 처리 (deps.ts:250-266) | **자동 거부** + warning SystemMessage | `useSessionStore().setPendingPermission(...)` 로 dispatch → `PermissionGauntletModal`이 modal 표시 → 사용자 Y/N 후 PermissionResponseFrame send |

### 4.3 UI 컴포넌트 (모두 real, paint 위험 0 — verified)

- `AssistantToolUseMessage.tsx` (367 LOC, real) — ToolUseBlockParam input
- `GroupedToolUseContent.tsx` (57 LOC, real) — multi-tool aggregation
- `ErrorEnvelope.tsx` (113 LOC, real) — 3 error styles (llm/parser/tool)
- `AssistantThinkingMessage.tsx` (85 LOC, real) — Spec 1633 직전 commit으로 wire 완료
- `MarkdownTable.tsx` (321 LOC, real)
- `permissions/PermissionGauntletModal.tsx` (100+ LOC, real, REPL.tsx:5249-5259에 mount 됨)

P0 stub shadow `.ts` 추가 발견 0건 (직전 세션에서 6개 청소 완료).

## 5. CC reference cp 매핑 (이번 epic baseline)

이전 세션에서 cp 완료(`src/kosmos/llm/_cc_reference/`):
- `claude.ts` (3419 lines)
- `client.ts` (389 lines)
- `errors.ts` (1207 lines)
- `emptyUsage.ts` (22 lines)

**추가 cp 필요** (cp 위치는 _cc_reference/ 하위에 동일 이름 유지 권장 — TS 그대로, Python migration은 별도 모듈):

| CC 파일 | Lines | 본 epic에 필요한 이유 | cp 위치 |
|---|---|---|---|
| `src/utils/api.ts` | 718 | `toolToAPISchema()` (line 119-266) — Tool → BetaTool 변환. K-EXAONE OpenAI-compat 매핑 baseline | `src/kosmos/llm/_cc_reference/api.ts` |
| `src/tools.ts` | 389 | `getAllBaseTools()` / `getTools()` / `assembleToolPool()` — tool catalog orchestration | `src/kosmos/llm/_cc_reference/tools.ts` |
| `src/constants/prompts.ts` | 914 | system prompt 동적 composition — tool name/capability 섹션 baseline | `src/kosmos/llm/_cc_reference/prompts.ts` |
| `src/query.ts` | 1729 | LLM ↔ tool_use ↔ tool_result 멀티턴 closure 본체 | `src/kosmos/llm/_cc_reference/query.ts` |
| `src/services/tools/toolOrchestration.ts` | 188 | `runTools()` async generator — concurrent read / serial write 분기 | `src/kosmos/llm/_cc_reference/toolOrchestration.ts` |
| `src/services/tools/toolExecution.ts` | 1745 | `runToolUse()` — input 검증, 실행, 에러 wrap, ToolResultBlockParam 직렬화 | `src/kosmos/llm/_cc_reference/toolExecution.ts` |
| `src/utils/messages.ts` | 5512 | `normalizeContentFromAPI()` + `ensureToolResultPairing()` — Anthropic API content blocks → 내부 MessageType. tool_use ↔ tool_result 페어링 검증 | `src/kosmos/llm/_cc_reference/messages.ts` |
| `src/utils/permissions/permissions.ts` | 1486 | permission gauntlet 본체 (Spec 033와 매핑) | `src/kosmos/llm/_cc_reference/permissions.ts` |
| `src/utils/toolResultStorage.ts` | (검색 필요) | tool result token budgeting + `processToolResultBlock()` | `src/kosmos/llm/_cc_reference/toolResultStorage.ts` |

cp 명령 (한 번에):
```bash
REF=.references/claude-code-sourcemap/restored-src/src
DEST=src/kosmos/llm/_cc_reference
cp $REF/utils/api.ts $DEST/api.ts
cp $REF/tools.ts $DEST/tools.ts
cp $REF/constants/prompts.ts $DEST/prompts.ts
cp $REF/query.ts $DEST/query.ts
cp $REF/services/tools/toolOrchestration.ts $DEST/toolOrchestration.ts
cp $REF/services/tools/toolExecution.ts $DEST/toolExecution.ts
cp $REF/utils/messages.ts $DEST/messages.ts
cp $REF/utils/permissions/permissions.ts $DEST/permissions.ts
cp $REF/utils/toolResultStorage.ts $DEST/toolResultStorage.ts 2>/dev/null || echo "toolResultStorage.ts 위치 다를 수 있음 — find로 확인"
```

## 6. 마이그레이션 스코프 (Step별 분해)

**원칙**: CC reference cp 후 Python으로 marshal. 한 번에 한 layer씩, 각 layer마다 unit test → PTY E2E → VHS 시각 검증.

### Step 1 — CC reference cp + 인덱스 (작업량 30분)

위 § 5의 9개 파일 cp. `src/kosmos/llm/_cc_reference/README.md` 작성: 파일별 1-line description + KOSMOS 매핑.

### Step 2 — TUI Tool → ToolDefinition 직렬화 (작업량 2-3h)

CC reference: `_cc_reference/api.ts:toolToAPISchema()` (line 119-266).

`tui/src/query/toolSerialization.ts` (신규):
- `toolToFunctionSchema(tool: Tool): FunctionSchema` — Zod inputSchema → JSON Schema Draft 2020-12 변환 (zod-to-json-schema 또는 수동 walker), `name` (Tool.name), `description` (Tool.userFacingName + Tool.prompt 첫 200자) 추출
- `getToolDefinitionsForFrame(): ToolDefinition[]` — `getAllBaseTools()` 호출, active primitives + MVP 보조만 필터, `toolToFunctionSchema` 적용

`tui/src/query/deps.ts:73-81` 의 ChatRequestFrame 빌드에 `tools: getToolDefinitionsForFrame()` 추가.

검증:
- bun test (toolSerialization spec) — active primitives 각각 JSON Schema valid
- PTY trace로 backend 도착한 frame.tools 길이 ≥ 5 확인

### Step 3 — Backend system prompt 도구 list 자동 inject (작업량 1-2h)

CC reference: `_cc_reference/api.ts:appendSystemContext()` + `_cc_reference/prompts.ts` 의 dynamic composition.

`src/kosmos/llm/system_prompt_builder.py` (신규):
- `build_system_prompt_with_tools(base: str, tools: list[LLMToolDefinition]) -> str` — base 끝에 `\n\n## Available tools\n` 섹션 + 각 tool에 대해 `### {name}\n{description}\n\n**Parameters**: {parameters JSON, indent=2}\n` append

`src/kosmos/ipc/stdio.py:_handle_chat_request` 진입 시:
- `system_text = await _ensure_system_prompt()`
- `if llm_tools: system_text = build_system_prompt_with_tools(system_text, llm_tools)`
- `frame.system or system_text` 로 LLM 첫 메시지 설정

검증: backend log에서 system prompt에 active primitive description 포함 확인. K-EXAONE 응답에서 `<tool_call>{"name":"Read"}` 가 사라지고 `<tool_call>{"name":"lookup"}` 또는 KOSMOS primitive 이름만 등장.

### Step 4 — Backend registry fallback (작업량 1-2h)

CC reference: `_cc_reference/tools.ts:assembleToolPool()` (line 345-367).

`src/kosmos/ipc/stdio.py`:
- session 시작(또는 첫 chat_request) 시 `ToolRegistry()` 1회 instantiate, module-level cache
- `_handle_chat_request`에서 `if not frame.tools: llm_tools = registry.export_core_tools_openai()` fallback
- `registry.export_core_tools_openai()` 가 active primitives + MVP 보조를 OpenAI function shape로 반환 (현재 정의는 `src/kosmos/tools/registry.py:373-378`, KOSMOS-1978 T053b의 `_dispatch_primitive` 가 사용 가능한지 확인)

검증: TUI `frame.tools=[]` 로 보내도 backend가 fallback inject해서 K-EXAONE이 도구 사용. 이중 안전망.

### Step 5 — TUI tool_call frame → tool_use content block paint (작업량 2-3h)

CC reference: `_cc_reference/messages.ts:normalizeContentFromAPI()` + `_cc_reference/claude.ts:1995-2052` (content_block_start tool_use case).

`tui/src/query/deps.ts:237-242` 변경:
- 현재 `createSystemMessage("🔧 …")` 단일 yield
- 신규 패턴 (CC mirror):
  ```typescript
  yield { type: 'stream_event', event: { type: 'content_block_start', index: ++blockIndex, content_block: { type: 'tool_use', id: fa.call_id, name: fa.name, input: fa.arguments } } }
  yield { type: 'stream_event', event: { type: 'content_block_stop', index: blockIndex } }
  ```
- 그러면 `handleMessageFromStream` (utils/messages.ts:3024-3037) 가 `streamingToolUses` array에 push해서 `AssistantToolUseMessage` 가 native 렌더

`message_start` 시점에 `content` 배열에 tool_use block 누적되도록 final `createAssistantMessage`도 함께 수정. CC는 한 turn에 text block + N개 tool_use block 다 yield.

검증: VHS GIF에 `🔧 lookup({...})` 진행라인 대신 CC-style tool_use 박스 paint 확인.

### Step 6 — TUI tool_result frame → tool_result user-message (작업량 2-3h)

CC reference: `_cc_reference/messages.ts:ensureToolResultPairing()` (line 1150-1250).

`tui/src/query/deps.ts:245-249`:
- 현재 `createSystemMessage("✓ ok …")` 만
- 신규: `createUserMessage` with `[{type: 'tool_result', tool_use_id: fa.call_id, content: <envelope>}]` 로 transcript에 user-role 메시지 append → 이게 다음 turn LLM context로 자동 들어감 (CC 패턴)

검증: agentic loop multi-turn 시 두 번째 turn LLM 호출 시 `messages` 에 `{role:'tool'}` 또는 `{role:'user', content:[{type:'tool_result',...}]}` 정상 진입.

### Step 7 — PermissionGauntletModal 실 연결 (작업량 2-3h)

CC reference: `_cc_reference/permissions.ts` (1486 lines, KOSMOS Spec 033와 매핑 검토 필요).

`tui/src/query/deps.ts:250-266`:
- 현재 `createSystemMessage(... auto-deny)` + `permission_response` decision='denied' 즉시 send
- 신규:
  - `useSessionStore.getState().setPendingPermission({request_id, primitive_kind, description_ko, description_en, risk_level})` 로 dispatch
  - `await waitForPermissionDecision(request_id)` (Promise — modal이 Y/N 후 resolve)
  - decision 결과로 `permission_response` send
- `PermissionGauntletModal` (이미 REPL.tsx:5249에 mount) 에서 Y/N 처리 후 session-store cleared + Promise resolve

검증: PTY로 submit primitive 호출하면 modal 떠서 사용자 입력 대기. VHS tape에서 modal frame capture.

## 7. 검증 방법 (사용자 시점)

매 step마다:

```bash
# Static
cd tui && bun run typecheck && bun test tests/...
cd .. && uv run pytest tests/llm tests/ipc
```

**PTY E2E** (사용자 prompt 시뮬레이션 — `feedback_runtime_verification` 메모리 기준):

`/tmp/run_pty_tool_e2e.py` (Step 별 시나리오):
- Step 2 검증: prompt "강남구 응급실" → frame.tools 길이 trace로 5+ 확인
- Step 3 검증: prompt 동일 → backend log에서 system prompt 끝에 "lookup" 등장 확인 + K-EXAONE 응답에 `<tool_call>{"name":"Read"}` 0회
- Step 5/6 검증: prompt 동일 → tool_call frame 1+ 도착 + tool_result frame 1+ 도착 + final response paint
- Step 7 검증: prompt "출생신고 서류 제출" (submit primitive trigger) → PermissionGauntletModal frame 캡처

**VHS GIF** (frame-by-frame, screenshot):

```
# /tmp/probe-tool-loop.tape
Output "/tmp/probe-tool-loop.gif"
Set Shell "bash"; Set FontSize 14; Set Width 1100; Set Height 700; Set Padding 16
Hide
Type "cd ~/KOSMOS/tui"; Enter; Sleep 200ms
Type "set -a; source ../.env; set +a"; Enter; Sleep 200ms
Type "export KOSMOS_FORCE_INTERACTIVE=1 OTEL_SDK_DISABLED=true"; Enter; Sleep 200ms
Type "clear"; Enter; Sleep 200ms
Show
Type "bun run tui"; Enter; Sleep 12s
Type "강남구 근처 24시간 응급실을 알려주세요."
Sleep 1s; Enter
Sleep 60s
Screenshot "/tmp/probe-tool-loop-final.png"
Sleep 500ms
```

GIF frame 추출 (10fps): `ffmpeg -i /tmp/probe-tool-loop.gif -vf "fps=10" /tmp/frames/frame_%03d.png`

기대 시각 시퀀스:
1. user prompt 입력 직후
2. spinner "Querying…" 또는 thinking 채널이 paint (직전 epic 결과)
3. tool_use 박스 (CC-style: `🔧 lookup` + JSON args)
4. tool_result 박스 (envelope summary)
5. 최종 자연어 응답 ("강남구 24시간 응급실은 …")

## 8. 한계 + 후속 epic (out of scope)

이 epic이 다루지 **않는** 것:

- `lookup` mode 분리 (search vs fetch BM25 라우팅) — Spec 022 영역
- Adapter-level permission gate (Spec 033) — 이번 epic은 PermissionGauntletModal **modal 자체** 만 wire
- Plugin-tier tools (Spec 1636) — active primitives + MVP only
- App/push notification runtime — required before any future `subscribe` primitive returns
- Spec 1635 P4 UI L2의 onboarding/help/etc — paint chain만 사용

후속 epic 제안:
- Spec 022 follow-up: `lookup(search/fetch)` BM25 + dense 하이브리드 검증
- Permission v2 (Spec 033) 의 layer 2/3 receipt 발급 + audit ledger 영구화
- KMA / KOROAD live API 실연 (paint + tool dispatch가 가능해야 trigger 가능)

## 9. Spec-driven workflow 권장 흐름

```
/speckit-specify "K-EXAONE tool wiring: TUI sends ChatRequestFrame.tools, backend injects system-prompt tool list, agentic loop closes with tool_use/tool_result content blocks paint"
  ↓
human review spec.md
  ↓
/speckit-plan
  ↓ Phase 0 read .specify/memory/constitution.md + docs/vision.md § Reference materials
  ↓ Map each design decision to _cc_reference/{api.ts, query.ts, toolExecution.ts, messages.ts}
human review plan.md
  ↓
/speckit-tasks → 약 15-20 tasks 예상 (7 step × 2-3 sub-tasks)
  ↓
/speckit-analyze → constitution compliance
  ↓
/speckit-taskstoissues → Sub-Issues API 로 Epic 아래 등록
  ↓
/speckit-implement → Agent Teams 병렬 (Sonnet workers, Opus Lead/review)
  ↓
PR with `Closes #EPIC` only → CI watch → Copilot review gate → merge
```

이 epic의 Constitution 핵심:
- AGENTS.md hard rules: 모든 source English, no `--no-verify`, no `requirements.txt`, no Go/Rust
- AGENTS.md "no new runtime dep" — `zod-to-json-schema` 추가는 신중히 검토. 가능하면 stdlib walker로 변환
- L1-A.A3 = K-EXAONE native function calling
- L1-B.B6 = composite tool 제거 — 합쳐지지 않은 primitive list만 노출
- C7 = `plugin.<id>.<verb>` namespace 예약 — primitive 4종 root reserved

## 10. 시작 명령

세션 진입 시 첫 명령:

```bash
cd ~/KOSMOS
git log -3 --oneline
ls src/kosmos/llm/_cc_reference/
gh issue create --title "Epic: K-EXAONE tool wiring (CC reference migration)" --body "$(cat docs/spec-kexaone-tool-wiring/handoff-prompt.md | head -80)" --label epic,agent-ready,size/L
```

이 prompt 를 가지고 `/speckit-specify` 시작.

## 부록 A — 참조 commit history

```
33478d4 feat(llm): KOSMOS-1633 P3 — wire K-EXAONE thinking via CC reference
a7fc8f6 fix(tui): KOSMOS-1633 P3 — assistant message paint chain unblocked
f459bfb feat(tui): KOSMOS-1633 P3 — stream-event projection for incremental paint
148b0d1 docs(epic): KOSMOS streaming UI projection — plan + handoff prompt
34304f6 feat(backend): KOSMOS-1633 P3 — parse K-EXAONE inline <tool_call> XML
```

## 부록 B — 잠재 risk + mitigation

| Risk | 가능성 | Mitigation |
|---|---|---|
| Zod → JSON Schema 변환이 nested discriminated union에서 깨짐 | 중 | active primitive schemas are simple enough for zod 자체 `.toJSONSchema()` 또는 `zod-to-json-schema` lib 검토 |
| K-EXAONE이 system prompt에 도구 list 있어도 여전히 `Read` hallucinate | 저-중 | system prompt에 `Only the following tools are available` 강한 명령 + `<tool_call>` 응답 후 unknown_tool error frame을 LLM에게 turn으로 feedback해 학습 | 
| FriendliAI Tier 1 RPM 한계 (60 RPM) — multi-turn loop가 한 prompt당 2-5 회 호출 | 중 | 직전 epic의 `RetryPolicy` 그대로 동작, 단 burst시 sleep |
| AssistantToolUseMessage가 Tool registry lookup 실패하면 빈 paint | 저 | TUI의 `getAllBaseTools()` 와 paint 시 `findToolByName()` 동일 source 보장 |
| Permission modal이 long-running tool 동안 사용자 응답 없으면 timeout | 중 | Spec 033의 5-min timeout + `Esc` interrupt 검증 |

## 부록 C — 진단 도구 인계

`/tmp/run_pty.py` (이전 세션) — 단순 PTY harness, 한 prompt 입력 후 buffer dump.

`/tmp/run_pty_tool.py` (이전 세션) — winsize 200×80, deadline 240s, 도구 호출 시나리오 prompt.

`/tmp/probe-streaming.tape` (이전 세션 VHS) — 900×600 viewport, "한 문장으로 답해주세요…" prompt.

backend stderr 가 PTY로 forward 안 되는 issue 있음 — backend 디버깅 필요시 `open("/tmp/kosmos-be.log", "a")` 패턴으로 file에 직접 write (이전 세션에서 검증된 우회).

---

작업 시작 전 `git log` 로 head 확인. `33478d4` 보다 head가 진행됐다면 그 변경 사항을 먼저 검토 후 진행.

---

## 변경 파일 예상 list (커밋 대상)

```
src/kosmos/llm/_cc_reference/
  + api.ts (cp from CC)
  + tools.ts (cp from CC)
  + prompts.ts (cp from CC)
  + query.ts (cp from CC)
  + toolOrchestration.ts (cp from CC)
  + toolExecution.ts (cp from CC)
  + messages.ts (cp from CC)
  + permissions.ts (cp from CC)
  + toolResultStorage.ts (cp from CC)
  + README.md (인덱스)

src/kosmos/llm/
  + system_prompt_builder.py (신규)

src/kosmos/ipc/
  M stdio.py (registry fallback + system prompt 도구 inject + whitelist source-of-truth)

tui/src/query/
  + toolSerialization.ts (신규)
  M deps.ts (frame.tools 채움 + tool_call/tool_result/permission_request CC-style projection)

tui/src/store/ 또는 utils/
  M sessionStore (pending_permission setter + waitForDecision Promise)

tests/llm/
  + test_system_prompt_builder.py
tests/ipc/
  M test_stdio.py (registry fallback 분기)
tui/tests/
  + tools/serialization.test.ts
  M ipc/handlers.test.ts (deps.ts 신규 분기)

docs/spec-kexaone-tool-wiring/
  + spec.md (/speckit-specify output)
  + plan.md (/speckit-plan output)
  + tasks.md (/speckit-tasks output)
  M handoff-prompt.md (이 파일 — 작업 결과 반영)
```
