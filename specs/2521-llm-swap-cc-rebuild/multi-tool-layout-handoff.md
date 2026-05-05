# 멀티 툴 레이아웃 회귀 — 핸드오프 문서

> **상태 (2026-05-02)**: 두 fix 시도했으나 사용자 환경에서 동일 회귀 재현. 다른 LLM 모델로 cross-debug 필요.
> **브랜치**: `feat/2521-procedure-a-and-audit`
> **현재 HEAD**: `8e16b1d` (`fix(2521): tighten multi-tool layout + canonicalize content-block order`)

---

## 1. 증상 (재현 가능)

**입력**: `bun run tui` → `부산 사하구 날씨 지금 날씨 알려줘` 또는 `부산 날씨 어때 지금?`

**관측되는 화면**:

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
∴ Thinking — 사용자가 부산 사하구의 현재 날씨를 알려달라고 요청했습니다. 시스템
프롬프트에서 <available_adapters query="부산 사하... (ctrl+o to expand)

✽ Bunning…
```

**기대 화면 (CC original 패턴)**:

```
❯ 부산 사하구 날씨 지금 날씨 알려줘

∴ Thinking — 사용자가 부산 사하구의 현재 날씨를 …
● lookup(kma_current_observation)
  ⎿ (결과 또는 spinner)
● lookup(kma_short_term_forecast)
  ⎿ (결과 또는 spinner)
...
```

## 2. 문제 분해

| # | 증상 | 원인 가설 | 검증 상태 |
|---|---|---|---|
| **A** | 5개 `● lookup()` 사이마다 1-line 빈 줄 | 모든 content block 이 `marginTop=1` 받음 | fix #1 시도, **여전히 회귀** |
| **B** | `∴ Thinking` 이 도구 *아래*에 위치 | K-EXAONE 의 `delta.reasoning_content` 가 `delta.tool_calls` 와 독립 채널, 순서 보장 없음 | fix #2 시도, transcript 모드에서만 해결될 수 있음 (chat 모드의 `streamingThinking` 박스는 별도 위치) |
| **C** | 결과 (`⎿ ...`) 가 어떤 도구에도 안 보임 | 도구가 모두 in-progress (LLM 이 5개를 한 turn 에 emit, backend dispatching 중) | by-design 가능성. CC 도 multi-tool turn 에선 같은 동작 |
| **D** | 도구 옆에 spinner (`◴ ◔ ◑`) 가 안 보임 | `ToolUseLoader` 가 `BLACK_CIRCLE` ↔ ` ` blink → 정적 스크린샷에선 안 보임 | by-design (animation 필요) |

**핵심 회귀**: A. 사용자가 같은 fix 적용 후에도 빈 줄 그대로.

## 3. 시도된 fix

### Fix #1 — `tui/src/components/Message.tsx:112` (커밋 `8e16b1d`)

```tsx
// before
t4 = (_, index_0) => <AssistantMessageBlock key={index_0} param={_} addMargin={addMargin} ... />

// after
t4 = (_, index_0) => <AssistantMessageBlock key={index_0} param={_} addMargin={addMargin && index_0 === 0} ... />
```

**의도**: 같은 assistant message 안의 두 번째 이상 content block 은 marginTop=0.

**검증**: `bun typecheck` clean, `bun test` 929 pass. 사용자 인터렉티브 검증 → **여전히 회귀**.

### Fix #2 — `tui/src/ipc/llmClient.ts:625` (커밋 `8e16b1d`)

```typescript
// 메시지 commit 시점에 contentBlocks 를 [thinking, text, tool_use, other] 순으로 정렬
const reorderedContent: typeof acc.contentBlocks = []
const _thinking = [], _text = [], _tools = [], _other = []
for (const block of acc.contentBlocks) {
  if (!block) continue
  if (block.type === 'thinking' || block.type === 'redacted_thinking') _thinking.push(block)
  else if (block.type === 'text') _text.push(block)
  else if (block.type === 'tool_use') _tools.push(block)
  else _other.push(block)
}
reorderedContent.push(..._thinking, ..._text, ..._tools, ..._other)
```

**의도**: K-EXAONE 가 tool_calls 를 reasoning_content 보다 먼저 stream 해도 최종 commit 된 message 의 content array 는 thinking → text → tool_use 순서 보장.

**검증**: chat 모드에선 thinking content_block 이 Message.tsx:548-550 에서 null 반환 → 보이지 않음. **`streamingThinking` 박스 (Messages.tsx:720) 의 위치는 그대로 messages list 아래** — 이게 사용자가 보는 `∴ Thinking — preview` 의 출처.

## 4. 의심되는 root cause 후보

### 가설 1: 빌드 캐시 (가장 가능성 높음)

사용자가 `bun run tui` 를 재시작하지 않았거나, bun 의 transpile 캐시가 stale. 

**검증법**:
```bash
cd /Users/um-yunsang/KOSMOS/tui
rm -rf node_modules/.cache
pkill -f "bun run tui"  # 기존 프로세스 정리
bun run tui  # 새로 시작
```

### 가설 2: marginTop 가 다른 곳에서 옴

`Message.tsx` 의 outer wrapper 가 자체 marginTop 을 가지거나 `MessageRow` 가 row gap 을 추가할 수 있음.

**검증 위치**:
- `tui/src/components/MessageRow.tsx:233` — `<Message addMargin={t6} ...>` 의 `t6 = !hasMetadata`
- `tui/src/components/messages/AssistantToolUseMessage.tsx:285` — `<Box marginTop={t5} ...>` (`t5 = addMargin ? 1 : 0`)
- `tui/src/components/Messages.tsx:701` — `renderableMessages.flatMap(renderMessageRow)` (gap 없음 확인)

### 가설 3: 5개 tool_use 가 5개의 *별도* assistant message

각 tool 이 별도 assistant message 라면 fix #1 (같은 message 내부 index) 이 작동 안 함. 각 message 의 첫 content block 은 항상 addMargin=true 받음.

**검증법**: backend 로그에서 `tool_call_buf` 한 turn 에 몇 개 entry 있는지 확인. 또는 TUI session JSONL `~/.kosmos/sessions/<id>.jsonl` 에서 assistant 엔트리 개수 확인.

### 가설 4: React Compiler 캐시 ($ memoCache)

`Message.tsx` 의 컴파일된 `_c(45)` 캐시가 lambda `t4` 를 stale 하게 hold. 하지만 lambda 내부는 closure 로 addMargin 참조 → 새 render 마다 재실행되어야 함.

**검증법**: t4 lambda 가 매 render 새로 만들어지는지 확인. `$[37] = t4` 의 cache hit 빈도.

## 5. 디버깅 권장 절차 (다음 LLM 용)

1. **빌드 캐시 우선 정리**:
   ```bash
   pkill -f "bun run tui"
   rm -rf /Users/um-yunsang/KOSMOS/tui/node_modules/.cache
   cd /Users/um-yunsang/KOSMOS/tui && bun run tui
   ```
   부산 날씨 재시도 후 회귀 여부 확인. 사라지면 **가설 1** 확정.

2. **Layer 5 frame capture** (캐시 정리 후):
   ```bash
   cd /Users/um-yunsang/KOSMOS
   KOSMOS_DEBUG_COLS=180 KOSMOS_DEBUG_ROWS=60 \
     scripts/tui-text-debug.sh /tmp/tdb-busan-clean \
     specs/2521-llm-swap-cc-rebuild/scripts/text-debug-busan-weather.expect
   grep -l "● lookup" /tmp/tdb-busan-clean/frame_*.txt | head -1 | xargs cat
   ```
   캡처된 frame 에서 `● lookup` 5줄 사이의 빈 줄 개수 카운트. 0 = fix 작동, 1 = 회귀 유지.

3. **Unit test 로 결정적 검증** (사용자 환경 무관):
   파일: `tui/tests/components/multiToolStacking.test.tsx` (initial draft committed)
   목표: 5개 tool_use block 이 같은 assistant message 안에서 1-line 빈 줄 없이 stack 됨을 ink-testing-library 로 assert. 현재 import 가 깨져있어 다음 LLM 이 fix 필요.

4. **Backend 로그 trace** (가설 3 검증):
   ```bash
   KOSMOS_LOG_LEVEL=DEBUG bun run tui 2>&1 | tee /tmp/busan-trace.log
   # 부산 날씨 입력
   grep -E "tool_call_buf|tool_call_index|message_id" /tmp/busan-trace.log
   ```
   한 `message_id` 하에 N 개 `tool_call_index` 이 emit 되는지 확인. N=5 → 한 message 에 5 tool_use.

5. **MessageRow / Message 의 outer Box marginTop 추적**:
   ```bash
   grep -rn "marginTop=\|marginY=\|paddingTop=" \
     tui/src/components/Message.tsx \
     tui/src/components/MessageRow.tsx \
     tui/src/components/messages/Assistant*.tsx
   ```

## 6. 해결 목표 (차순 LLM 작업 명세)

### Goal A — 확실한 layout fix (필수)

> 같은 assistant message 안의 N 개 tool_use block 사이에 빈 줄이 0 이어야 한다.

**Acceptance**:
1. `bun test tests/components/multiToolStacking.test.tsx` 가 5 tool_use stack 에서 인접 row 간격 = 1 line (빈 줄 0) 을 assert + 통과.
2. Layer 5 PTY 캡처에서 `● lookup` 5 줄이 빈 줄 없이 연속으로 보임.
3. 회귀 없음: 단일 tool_use turn 에선 여전히 적절한 marginTop=1 (이전 user message 와의 간격).

**가능 접근**:
- 위 가설 1-4 차례로 검증 후 진짜 root cause 에 fix 집중
- 만약 가설 3 (별도 message) 이 사실이면 fix #1 전제가 틀림 — 다른 fix (e.g., 인접 assistant tool_use message 간 marginTop=0) 가 필요
- React Compiler 캐시가 문제면 cache invalidation key 에 `index_0` 추가

### Goal B — Thinking 위치 (chat 모드)

> 시민이 보는 chat 모드에서 `∴ Thinking — preview` 가 직전 user message 와 첫 tool_use 사이에 위치해야 한다.

**Acceptance**:
1. `Messages.tsx:720` 의 `<AssistantThinkingMessage streamingThinking>` 가 `renderableMessages` flatMap 출력의 *마지막 user message 직후* 에 inject 되어야 함.
2. `streamingThinking.streamingEndedAt` 이 set 된 이후 (= 30s window) 도 같은 위치 유지.

**현재 코드 위치**: `Messages.tsx:720-725`. flatMap 결과에 인덱스 기반 splice 가 필요할 수 있음.

### Goal C — 결과 (`⎿`) paint 보장 (검증)

> 백엔드가 ToolResultFrame 을 보냈을 때, 해당 tool_use block 바로 아래에 `⎿ ...` 가 paint 되어야 한다.

**현재 동작**: CC 의 `processedMessages` 가 tool_use 직후에 user message (tool_result) 를 reorder 해서 `UserToolSuccessMessage` 가 paint. KOSMOS 도 동일 로직 작동해야 함.

**Acceptance**:
1. Layer 5 PTY 캡처에서 `● lookup(...) ⎿ ...` 가 같은 block 으로 paint.
2. 백엔드 `kosmos.tools._outbound_trace` 가 send 한 `outbound_traces` 가 verbose 모드에서 보이는지 (이건 이미 PR 에서 검증 완료).

## 7. 회귀 위험 영역

- `tui/src/ipc/llmClient.ts` 의 reorder logic 이 transcript 모드 / `--verbose` 모드에 정상 작동하는지 (chat 모드는 thinking 숨김이라 차이 안 보임).
- `tui/src/components/Message.tsx` 의 `addMargin && index_0 === 0` 가 React Compiler 의 `_c(45)` 캐시와 호환되는지 (lambda closure 가 stale addMargin 잡지 않는지).
- `feat/2521-procedure-a-and-audit` 브랜치에서 다른 부분 회귀 없는지 (`bun test` 929 pass / `pytest` 1117 pass 가 baseline).

## 8. 관련 코드 포인터

| 영역 | 파일:라인 | 역할 |
|---|---|---|
| addMargin propagation | `tui/src/components/Message.tsx:112` | content block 별 marginTop 결정 |
| AssistantToolUseMessage 외곽 | `tui/src/components/messages/AssistantToolUseMessage.tsx:285` | `marginTop={t5}` 적용 (`t5 = addMargin ? 1 : 0`) |
| ToolUseLoader spinner | `tui/src/components/ToolUseLoader.tsx` | `●` ↔ ` ` blink 애니메이션 |
| Final content reorder | `tui/src/ipc/llmClient.ts:625-657` | `[thinking, text, tool_use, other]` 정렬 |
| streamingThinking render | `tui/src/components/Messages.tsx:720` | thinking preview 위치 |
| K-EXAONE thinking gate | `src/kosmos/llm/client.py:969` | `KOSMOS_K_EXAONE_THINKING` env (default true) |
| Backend tool_call dispatch | `src/kosmos/ipc/stdio.py:1661` | `tool_call_buf` 순회 → ToolCallFrame emit |
| System prompt turn_order | `prompts/system_v1.md` `<turn_order>` 섹션 | "One tool per turn" 제약 (LLM 이 무시 중) |

## 9. 빠른 실험 아이디어

1. **다른 LLM 모델로 동일 시도**: `KOSMOS_K_EXAONE_THINKING=false` 로 강제 비활성화 → reasoning channel 안 와서 thinking 위치 문제 사라지는지 확인.
2. **하나의 어댑터로 성공한 케이스 확인**: `서울특별시 종로구 청와대로 1 좌표 알려줘` (resolve_location) 는 verbose smoke (frame_0425) 에서 정상 layout. multi-tool 만 깨지는지 확정.
3. **Backend 측 enforcement**: `stdio.py:1661` 의 `for idx in sorted(tool_call_buf.keys()):` 에서 첫 번째만 dispatch + 나머지는 LLM 에게 "turn_order 위반" 메시지로 reject.

---

## 부록: 기존 fix 의 commit 메시지 (참조)

```
fix(2521): tighten multi-tool layout + canonicalize content-block order

User-reported 2026-05-02: K-EXAONE on FriendliAI emits multiple
``● lookup(...)`` calls per turn with 1-line gaps between every block
AND ``∴ Thinking — ...`` lands BELOW the tool_use blocks instead of
above them — breaking the ReAct visual cadence the citizen expects.

Two structural fixes covering both halves of the layout glitch:

1. tui/src/components/Message.tsx — addMargin is now index-aware.
2. tui/src/ipc/llmClient.ts — final content array is reordered
   thinking → text → tool_use → other at message commit.
```

(전체 커밋: `git show 8e16b1d`)
