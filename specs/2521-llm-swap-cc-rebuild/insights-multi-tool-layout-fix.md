# 멀티 툴 레이아웃 회귀 — 사후 분석 + 디버깅 인사이트

> **작성**: 2026-05-02 (Codex GPT-5.5 가 해결한 후 분석)
> **이슈**: K-EXAONE on FriendliAI 가 turn 당 multiple `lookup` tool_call 을 emit → TUI 레이아웃 깨짐
> **해결 커밋**: working tree (브랜치 `feat/2521-procedure-a-and-audit`)
> **선행 핸드오프**: `multi-tool-layout-handoff.md` (Lead Opus 가 다른 LLM 에 토스용으로 작성)

---

## 1. 증상

### 회귀 #1 — 멀티 툴 레이아웃 (Codex 가 해결)

```
❯ 부산 사하구 날씨 지금 날씨 알려줘

● lookup(kma_current_observation)
                                   ← 빈 줄 1개
● lookup(kma_short_term_forecast)
                                   ← 빈 줄 1개
● lookup(kma_current_observation)
                                   ← 빈 줄 1개
● lookup(kma_forecast_fetch)
                                   ← 빈 줄 1개
● lookup(kma_current_observation)
                                   ← 빈 줄 1개
∴ Thinking — 사용자가 부산 사하구의 ...

✽ Bunning…
```

문제 3가지:

| # | 증상 | 사용자 표현 |
|---|---|---|
| A | 5개 도구 호출 사이 1-line 빈 줄 | "uiux 측면에서 계속 이상한 흐름으로 배치" |
| B | `∴ Thinking` 이 도구 *아래* 위치 | "왜 도구호출부터 하는거지?" |
| C | 결과 (`⎿ ...`) 가 어떤 도구에도 안 보임 | (스트리밍 중 정상이지만 시각적으로 답답) |

### 회귀 #2 — Adapter param schema invisibility (parallel_tool_calls=False 후 재발견)

L1 fix (`parallel_tool_calls=False`) 적용 후 K-EXAONE 가 turn 당 1 tool 만 emit 하지만, *그 1 tool 도 invalid_params* 로 모두 거부되는 새 회귀 노출:

```
● lookup(kma_forecast_fetch)
  ⎿  검색 오류: Invalid parameters for tool.
● lookup(kma_current_observation)
  ⎿  검색 오류: Invalid parameters for tool.
● lookup(kma_short_term_forecast)
  ⎿  검색 오류: Invalid parameters for tool.
```

원인: `_build_available_adapters_suffix` 가 의도적으로 schema 정보를 token budget 핑계로 안 줬음 (`stdio.py:797` 주석에 명시 — "the LLM can still infer params from search_hint"). K-EXAONE 가 `search_hint` (bilingual keyword 리스트) 만 보고 schema 추측 못 해서 `{"location": "부산", "date": "2026-05-01"}` 같은 직관 호출 → 모든 어댑터 pydantic validation 실패.

해결: `AdapterCandidate.input_schema_json` (Spec 2297 path B 가 이미 추가했던 full Pydantic JSON Schema) 의 properties 를 한 줄씩 dump:

```
- kma_forecast_fetch [2.81] — 단기예보 날씨 ...
    · lat (number, 필수) — WGS-84 latitude of the target location, ...
    · lon (number, 필수) — WGS-84 longitude of the target location, ...
    · base_date (string, 필수 pattern='^\d{8}$') — Forecast base date in YYYYMMDD format, ...
    · base_time (string, 필수) — Forecast base time in HHMM format. Must be one of: 0200, 0500, ...
```

Suffix 길이가 ~400 → ~2200 chars 로 늘지만 N 번 invalid_params retry 비용보다 훨씬 저렴.

## 2. Lead Opus 가 시도한 fix (실패)

### Fix #1 — `Message.tsx` index-aware addMargin

```tsx
addMargin={addMargin && index_0 === 0}
```

**가정**: 한 assistant message 가 5 content blocks 를 가지고 있음. 두 번째 이상 block 의 marginTop=0 으로 만들면 갭 사라짐.

**결과**: 회귀 그대로. 사용자 재시도 후 동일.

### Fix #2 — `llmClient.ts` content reorder

```typescript
reorderedContent.push(..._thinking, ..._text, ..._tools, ..._other)
```

**가정**: K-EXAONE 의 reasoning_content 가 tool_calls 보다 늦게 도착해도 final content array 는 thinking → tool_use 순서.

**결과**: chat 모드에선 thinking 이 `Message.tsx:548-550` 에서 null 로 hidden 이라 effect 없음. transcript 모드에서만 작동.

## 3. Codex GPT-5.5 의 정답 — 3-tier defense in depth

### L1: LLM API parameter — 가장 근본

`src/kosmos/llm/client.py`:

```python
if tool_payloads:
    # KOSMOS citizen flows require one observed tool result before
    # the model may request the next tool. FriendliAI's
    # OpenAI-compatible default permits parallel tool calls.
    payload["parallel_tool_calls"] = False
```

**핵심**: `parallel_tool_calls: false` 는 OpenAI Chat Completions API 가 정식 공개한 옵션 (2024). FriendliAI 가 OpenAI-compat 채널이라 그대로 forward → K-EXAONE 가 한 turn 에 단 1개 tool 만 emit 하도록 LLM 자체 강제.

**왜 결정타인가**: 다른 모든 fix 의 토대. 이 한 줄이 "K-EXAONE 가 multi-tool 시도조차 안 함" 보장.

### L2: Backend dispatcher safety net

`src/kosmos/ipc/stdio.py:1661`:

```python
tool_call_indices = sorted(tool_call_buf.keys())
if len(tool_call_indices) > 1:
    selected_idx = tool_call_indices[0]
    dropped = tool_call_indices[1:]
    logger.warning(
        "_handle_chat_request: received %d tool calls in one LLM turn; "
        "dispatching index %s only and dropping indices %s to enforce "
        "one observed tool result per turn",
        len(tool_call_indices),
        selected_idx,
        dropped,
    )
    tool_call_indices = [selected_idx]
```

**핵심**: L1 이 무시되거나 stream 중간 상태에 multi-tool 노출돼도 첫 번째만 dispatch + warning 로그.

**Defense pattern**: invariant 위반 시 silent drop 이 아니라 `logger.warning` 으로 가시성 확보.

### L3: Frontend layout visual fallback

`tui/src/utils/multiToolLayout.ts` (NEW, 90 lines):

```typescript
export function isSameAssistantToolStack(
  prev: LayoutMessageLike | undefined,
  current: LayoutMessageLike,
  streamingToolUseIDs: ReadonlySet<string>,
): boolean {
  const prevTool = getAssistantToolUseBlock(prev)
  const currentTool = getAssistantToolUseBlock(current)
  if (!prevTool || !currentTool || prev?.type !== 'assistant' || current.type !== 'assistant') return false
  // Same message_id → siblings of one assistant turn
  if (prev.message?.id && prev.message.id === current.message?.id) return true
  // Both still streaming → in-flight siblings
  return streamingToolUseIDs.has(prevTool.id) && streamingToolUseIDs.has(currentTool.id)
}

export function getStreamingThinkingInsertIndex(messages: readonly LayoutMessageLike[]): number {
  let lastUserIndex = -1
  for (let i = messages.length - 1; i >= 0; i--) {
    if (isUserTurnMessage(messages[i])) { lastUserIndex = i; break }
  }
  // Splice 위치: last user 직후 + 첫 tool_use-like 직전
  for (let i = lastUserIndex + 1; i < messages.length; i++) {
    if (isToolUseLikeMessage(messages[i])) return i
  }
  return messages.length
}

// Synthetic system/thinking message — sentinel UUID 로 type-safe 검출
export const STREAMING_THINKING_LAYOUT_UUID = 'streaming-thinking'
export function createStreamingThinkingLayoutMessage(thinking: string)
```

`tui/src/components/MessageRow.tsx`:

```typescript
// 새 prop
suppressTopMargin?: boolean

// 적용
const t6 = !hasMetadata && !suppressTopMargin
```

`tui/src/components/Messages.tsx`:

```typescript
// 1) Synthetic streaming thinking message 를 messages list 에 splice
const layoutMessages = useMemo(() => {
  if (!streamingThinkingLayoutMessage) return renderableMessages
  const next = renderableMessages.slice()
  next.splice(streamingThinkingInsertIndex, 0, streamingThinkingLayoutMessage)
  return next
}, [...])

// 2) renderMessageRow 에서 prev 와 current 비교 → siblings 판정
const prevMsg = index > 0 ? layoutMessages[index - 1] : undefined
const suppressTopMargin = isSameAssistantToolStack(prevMsg, msg_8, streamingToolUseIDs)

// 3) 화면 하단의 별도 streamingThinking 박스 제거
- {isStreamingThinkingVisible && streamingThinking && !isBriefOnly && <Box marginTop={1}>...</Box>}
```

### L4: 부수 정리

- **`tui/src/utils/messageReorder.ts`** (NEW, 220 lines) — `reorderMessagesInUI` + `isToolUseRequestMessage` + `isToolUseResultMessage` 를 `messages.ts` 에서 추출 (-207 lines)
- **`tui/src/query/deps.ts`** — `outbound_traces` 를 LLM-facing content 에서 strip + UI-side `toolUseResult` 별도 필드 + `sourceToolAssistantUUID` 링크
- **`tui/src/query.ts`** — `getResolvedToolUseIDs` 로 race-safe dispatch (이미 result 도착한 tool_use 는 다음 dispatch loop 에서 제외)
- **`tui/tests/components/multiToolStacking.test.ts`** (NEW, 7 tests) — `isSameAssistantToolStack` / `getStreamingThinkingInsertIndex` / `createStreamingThinkingLayoutMessage` / `reorderMessagesInUI` 의 결정적 unit tests

## 4. 왜 Lead Opus 의 fix 는 실패했나

### 잘못된 가정의 root cause

| 측면 | Lead Opus 가정 | 실제 (Codex 가 정답) |
|---|---|---|
| 5개 `● lookup()` 의 message 구조 | **한** assistant message 안 5 content blocks | **5개 별도** assistant messages, 각각 1 content block |
| 빈 줄의 출처 | 한 message 내 두 번째 이상 block 의 `marginTop=1` | 각 별도 message 의 `MessageRow` 가 모두 `addMargin=true` (CC default) |
| Fix 위치 | `Message.tsx` 의 `index_0` 기반 분기 | `MessageRow.tsx` 의 `suppressTopMargin` + 같은 turn 의 sibling 검출 |
| Thinking 위치 | content array reorder (`llmClient.ts`) | renderable list 에 synthetic thinking 메시지 splice (`Messages.tsx`) |
| 근본 우회 | 없음 (UI-only 처리) | **`parallel_tool_calls=False`** — LLM 자체가 1 tool 만 emit |

### 가설 검증을 미룬 것이 결정적 실수

핸드오프 문서 § 4 에서 가설 3 ("5 tool_use 가 5 별도 assistant message") 을 적었지만 "검증 필요" 로 표시하고 다른 가설을 우선 시도. Codex 는 그 가설을 정답으로 채택하고 진행 → 즉시 정답 도착.

**교훈**: 가설 N 개 중 어느 게 정답인지 모르면, *가장 검증 비용이 큰 가설부터* 검증해야 함. UI fix 한 번 시도가 backend code reading 한 번보다 빠른 것 같지만, 잘못된 UI fix 는 fix 마다 새로운 가짜 시그널을 만들어 root cause 찾기 더 어렵게 만듦.

## 5. 디버깅 휴리스틱 — 차후 적용

### H1. LLM swap 후 이상 동작은 LLM API 공식 옵션부터 의심

새 LLM 으로 swap 한 후 이상 동작이 보이면 OpenAI Chat Completions API 표준 옵션 (`parallel_tool_calls`, `response_format`, `seed`, `logit_bias`, `tool_choice`) 이 default 로 어떻게 설정되는지 매뉴얼부터 확인.

- 같은 모델이라도 provider (Anthropic / OpenAI / FriendliAI / vLLM) 별 default 다름
- 이 한 옵션이 해결책일 가능성 30%+ — 시도 비용 0
- 시스템 프롬프트 룰 (`<turn_order>` 등) 은 LLM 이 무시할 수 있는 soft 제약. API 옵션은 hard 제약

### H2. 여러 가설이 있으면 가장 비싼 가설부터 검증

"검증 비용 = 의심 깊이". 코드 5 layer 깊은 곳을 의심하면 그것부터 reading 해서 fact 확정. UI fix 가 빠르다고 그쪽부터 시도하면, 잘못된 UI fix 가 가짜 시그널 만들어 root cause 찾기 더 어려워짐.

### H3. Defense in depth 3-tier

UI/UX 회귀 fix 는 최소 3 layer:

```
L1: Source of truth — invariant 를 가장 깊은 곳에 박기 (LLM API parameter)
L2: Boundary safety net — invariant 위반 시 첫 dispatcher 가 잡기
L3: Visual fallback — 그래도 노출되면 시각적으로 graceful degrade
```

L1 만 하면 LLM 이 옵션 무시하면 깨짐. L3 만 하면 backend race / future swap 으로 깨짐. 3 layer 모두 적용해야 미래 회귀에 견고.

### H4. Synthetic message sentinel 패턴

React/Ink 처럼 message list 가 source of truth 인 구조에서, 별도 floating box 추가 대신 *가짜 message 를 type-tagged 로 list 에 splice* 하는 게 우아.

```typescript
const STREAMING_THINKING_LAYOUT_UUID = 'streaming-thinking'

// 위치 계산 → splice
const idx = getStreamingThinkingInsertIndex(messages)
messages.splice(idx, 0, createStreamingThinkingLayoutMessage(thinking))

// type-safe 검출
function isStreamingThinkingLayoutMessage(msg): msg is StreamingThinking {
  return msg.uuid === STREAMING_THINKING_LAYOUT_UUID
}
```

장점:
- Cursor / scroll / select 가 message list 기반이라 자동으로 맞물림
- 기존 `renderMessageRow` switch 에 한 분기만 추가하면 끝
- React key 가 sentinel UUID 라 reconcile 안정적

### H5. Debug 가설 검증 우선순위 매트릭스

| 의심 layer | 검증 방법 | 비용 | Confidence boost |
|---|---|---|---|
| LLM API param | 공식 docs + provider 매트릭스 | 5분 | 매우 높음 (1 옵션이 해결할 수 있음) |
| Backend dispatch | 로그 + JSONL session inspect | 15분 | 높음 (code path 명확) |
| Message structure | TUI session JSONL 의 message 분리 패턴 | 10분 | 매우 높음 (정답 가설 빠름) |
| Frontend render | Layer 5 PTY frame capture + grep | 30분+ | 낮음 (symptom 만 보임) |
| React Compiler cache | dev tools + console.log | 1시간+ | 매우 낮음 (정답일 확률 작음) |

### H6. 같은 turn 의 sibling 검출 패턴

다른 LLM 들도 비슷한 multi-tool 케이스 가질 수 있음. KOSMOS 의 `isSameAssistantToolStack` 패턴 재사용:

```typescript
// 두 가지 신호
// (a) message.id 같음 → 같은 commit
// (b) 둘 다 streamingToolUseIDs 안에 있음 → in-flight 시 임시 처리

function isSameAssistantToolStack(prev, current, streamingToolUseIDs) {
  if (...) return false
  if (prev.message?.id === current.message?.id) return true
  return streamingToolUseIDs.has(prevTool.id) && streamingToolUseIDs.has(currentTool.id)
}
```

이 같은 두 신호 패턴은 다른 sibling-detection 케이스 (e.g. parallel verify, batch submit) 에도 적용 가능.

### H7. Token budget 우선 최적화는 LLM accuracy 를 망가뜨릴 수 있음

회귀 #2 의 root cause: `_build_available_adapters_suffix` 가 input_schema 를 *prompt-cache friendly 하게 만들기 위해* 일부러 안 노출 → "the LLM can still infer params from search_hint" 라고 주석 박아둠 → 모든 도구가 invalid_params.

**경험칙**: LLM 이 *정확한 호출* 을 하는 데 필요한 정보는 token budget 보다 우선. 한 번의 invalid retry 가 schema dump (수백 token) 보다 훨씬 비싸다 — N retries × full system prompt + multi-turn assistant context = 수천 token 낭비 + 사용자 대기시간 증가.

**적용 룰**:

1. **Schema / 시그니처 / contract 정보는 압축하지 말고 정확히 노출**. 80자 description 은 노이즈가 아니라 LLM 이 schema 를 이해하는 데 필요한 신호. 80자 cap 은 합리적; 0자 (description 안 보임) 는 retry loop 보장.

2. **"LLM 이 search_hint 로 추측 가능" 같은 가정은 fragile**. 같은 모델이라도 provider / temperature / context 길이 / 최근 학습 데이터에 따라 추측 정확도 다름. K-EXAONE on FriendliAI 가 `location: "부산"` 으로 추측한 것처럼 — Anthropic Claude 라면 정답이었을 수 있는 케이스도 fail.

3. **Token budget worry 의 진짜 답은 prompt cache + dynamic suffix**. KOSMOS 가 이미 `prompts/system_v1.md` 의 static prefix 를 cache 하고 dynamic suffix 만 매 turn 새로 생성 — suffix 길이 늘어도 재계산 비용은 BM25 lookup + render 만. cache 효과는 prefix 가 보존되므로 그대로.

4. **회귀 발견 시점**: invalid_params 가 *모든* 도구에서 일관되게 나오면 schema 정보가 LLM 에 안 도달한 것. 도구 1개에서만 fail 이면 그 도구의 schema 버그. 일관된 fail 패턴이 진단 신호.

5. **반대 케이스 — 진짜 token bloat 위험**: response body / 큰 enum (>20) / nested object 의 모든 필드 dump 는 LLM 이 안 보고 token 만 먹음. Top-level required + optional 만 + 80자 description 이 sweet spot. KOSMOS 의 fix 가 정확히 이 균형.

**비유**: schema 노출은 docs/manual 같음. 짧게 만들려고 함수 시그니처 빼버리면 사용자 (LLM) 가 함수 호출 못함. token 아끼려다 retry × N 번에 결국 더 비싸짐.

## 6. KOSMOS 프로젝트 특이사항

### LLM provider swap 의 hidden cost

CC 의 byte-identical port + 2 swap 모델 (`AGENTS.md § CORE THESIS`) 이 명시한 swap 영역:
- LLM 채널 (Anthropic → FriendliAI K-EXAONE)
- 도구 표면 (개발자 → 시민 행정 서비스)

**숨은 swap 부담**: 같은 OpenAI-compat API 를 따라도 *default 옵션* 이 provider 마다 다름.

| 옵션 | Anthropic Messages | OpenAI Chat | FriendliAI Serverless |
|---|---|---|---|
| parallel tool calls | (concept 다름) | default true | default true (OpenAI 따름) |
| reasoning channel | thinking content_block | reasoning_content delta | reasoning_content delta |
| stream chunk granularity | token | paragraph | paragraph |
| stop sequences | array of strings | array of strings | array of strings |

K-EXAONE 의 reasoning_content + parallel_tool_calls 가 둘 다 visible 됐을 때 layout 이 깨진 케이스. CC 는 Anthropic 전용 가정을 byte-identical 로 갖고 있어서 — 새 provider 로 swap 하면 이런 *기본 가정 차이* 가 회귀로 노출됨.

**checklist for future LLM swaps**:
1. 모든 `chat.completions.create` 옵션 default 비교 (Anthropic ↔ provider X)
2. Streaming chunk granularity 차이 (token vs paragraph vs none)
3. Reasoning / thinking 채널의 위치 (content block vs delta vs separate field)
4. Tool call structure (id 형식, function name encoding, arguments schema)
5. Token budget 계산 차이 (cache_read_input_tokens 등)

### KOSMOS 의 ReAct flow invariant

`prompts/system_v1.md` `<turn_order>` 섹션:
> **One tool per turn** — 한 turn 안에서 도구는 정확히 한 개만 호출.

이건 문서 룰. **실제 enforcement 는 `parallel_tool_calls=False` API 옵션** 으로 보장. 시스템 프롬프트 룰 + API 옵션 + backend dispatch guard 3중 boundary.

## 7. 회귀 방지 체크리스트

미래 PR 가 같은 회귀 일으키지 않도록:

**Layout (회귀 #1)**:
- [ ] `bun test tests/components/multiToolStacking.test.ts` 통과 (Codex 가 추가)
- [ ] `src/kosmos/llm/client.py` 의 `parallel_tool_calls = False` 보존 (LLM swap 시 재확인)
- [ ] `src/kosmos/ipc/stdio.py` 의 multi-tool drop guard 보존
- [ ] `tui/src/utils/multiToolLayout.ts` 의 `isSameAssistantToolStack` 보존
- [ ] Layer 5 PTY 캡처에서 multi-tool 시나리오 (`부산 사하구 날씨`) 5 줄 stack 빈 줄 0
- [ ] Streaming 중에도 `∴ Thinking` preview 가 last user 와 first tool_use 사이에 위치

**Schema visibility (회귀 #2)**:
- [ ] `src/kosmos/ipc/stdio.py:_build_available_adapters_suffix` 가 input_schema_json 의 properties 를 per-field signature 로 dump (`· name (type, 필수|선택 pattern=... enum=...) — desc`)
- [ ] Live 검증: `uv run python -c "..."` 로 BM25 후보 top-3 의 schema signature 가 `lat`/`lon`/`base_date pattern='^\d{8}$'` 등 정확한 필드 노출 확인
- [ ] LLM swap 시 dynamic suffix 길이 증가가 prompt cache 깨지 않는지 확인 (static prefix 분리 보존)
- [ ] 어떤 LLM provider 에서도 모든 도구가 invalid_params 를 일관되게 emit 하지 않는지 모니터링 — 그렇다면 schema 정보가 LLM 에 안 도달한 것

## 8. 참조

- 핸드오프 문서: `multi-tool-layout-handoff.md` (해결 전 작성)
- 변경 파일들 (working tree, 미커밋):
  - `src/kosmos/llm/client.py:989` — parallel_tool_calls=False
  - `src/kosmos/ipc/stdio.py:1661` — multi-tool drop guard
  - `tui/src/utils/multiToolLayout.ts` (NEW)
  - `tui/src/utils/messageReorder.ts` (NEW, extracted)
  - `tui/src/components/MessageRow.tsx` — suppressTopMargin prop
  - `tui/src/components/Messages.tsx` — synthetic thinking splice
  - `tui/src/query.ts` + `tui/src/query/deps.ts` — outbound_traces 정리
  - `tui/tests/components/multiToolStacking.test.ts` (NEW, 7 tests)
- OpenAI API docs: https://platform.openai.com/docs/api-reference/chat/create#chat-create-parallel_tool_calls

---

**최종 인사이트 한 줄**:
> 새 LLM provider 로 swap 한 후 이상 동작은 *LLM API 공식 옵션* 부터 의심. Soft 제약(시스템 프롬프트) 은 LLM 이 무시할 수 있지만, *hard 제약(API parameter)* 은 무시 못 함. 그리고 가설이 N 개 있으면 *가장 검증 비용이 큰 가설부터* 검증.
