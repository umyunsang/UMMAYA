# G10 — Deep Research: Agents Chord Block + Ctrl-O Thinking Grouping

> Wave-4 G10 · Date: 2026-05-05 · HEAD: `e63050e4`

---

## G10a — CC `defaultBindings.ts` Agents context binding

### CC reference pattern

CC's `defaultBindings.ts` (restored-src) uses the same `KeybindingBlock[]` pattern
for overlay-specific contexts. The `Help` and `Autocomplete` blocks added by G2
mirror CC's structure exactly. CC does not have an explicit `Agents` panel context
because CC's `/agents` command has different UX, but the pattern is clear:

- Any overlay that needs Esc dismiss must have a context block in `DEFAULT_BINDING_BLOCKS`
  so `ChordInterceptor` can resolve Esc → `<overlay>:dismiss` BEFORE the Chat context's
  `draft-cancel` / `chat:cancel` can claim it.

### Root cause of F-ε-05 (NOT_CLOSED after G2)

`AgentsCommandView` mounts via `setToolJSX({ isLocalJSXCommand: false })`. This keeps
`isLocalJSXCommandActive = false` in PromptInput, so the Chat context's useInput hooks
stay active. The Chat chord bindings (including `escape: 'chat:cancel'` in
`DEFAULT_BINDING_BLOCKS`) are always in scope.

`ChordInterceptor` calls `resolveKeyWithChordState` with all active contexts. The contexts
at the time of Esc include `['Chat', 'Global']` (no `'Agents'`). `DEFAULT_BINDING_BLOCKS`
iteration is last-match-wins, so Esc resolves to `chat:cancel`. ChordInterceptor fires
`chat:cancel` and calls `event.stopImmediatePropagation()`, preventing the raw `useInput`
fallback in `AgentsCommandView` from ever seeing the event.

The G2 fix report noted `F-ε-05` as "existing `useInput` fallback (component) — already in place"
but wave-3 re-smoke showed NOT_CLOSED. The fallback cannot fire when ChordInterceptor
pre-empts it with a Chat-context match.

### Fix

Two-layer fix mirroring HelpV2Grouped exactly:
1. Add `Agents` chord block to `DEFAULT_BINDING_BLOCKS` with `escape: 'agents:dismiss'`
2. Add `useKeybinding('agents:dismiss', onExit, { context: 'Agents' })` in `AgentsCommandView`

When `useKeybinding` runs, it calls `keybindingContext.registerHandler({ action: 'agents:dismiss', context: 'Agents', handler })`. The `handlerContexts` set now contains `'Agents'`. ChordInterceptor builds `contexts = [...handlerContexts, ...activeContexts, 'Global']` = `['Agents', 'Chat', 'Global']`. With `'Agents'` in the list, `DEFAULT_BINDING_BLOCKS` last-match-wins gives `agents:dismiss` (Agents block declared after Help, which is after Chat). Handler fires. `onExit()` called. Raw `useInput` fallback remains as defense-in-depth for Bun-PTY raw `\x1b` delivery.

---

## G10b — CC Messages.tsx grouping — thinking BEFORE tool_use

### CC's approach

In CC's agentic loop (`.references/claude-code-sourcemap/restored-src/`), the LLM
(Claude) delivers a single assistant message with `content: [thinking_block, tool_use_block]`
in that order. `normalizeMessages` splits this into two `NormalizedAssistantMessage` items:
index 0 = `{content: [thinking_block]}`, index 1 = `{content: [tool_use_block]}`.
`reorderMessagesInUI` then places `tool_result` after `tool_use`. Thinking stays at its
array position (before tool_use). Order: `thinking → tool_use → tool_result`. Correct.

### KOSMOS regression path

K-EXAONE on FriendliAI delivers `reasoning_content` as `thinking_delta` events that may
complete with a different `content_block_stop` sequence than the `tool_use` block. In
multi-turn sessions or when the streaming state is rebuilt from a persisted JSONL session,
the content array may arrive as `[tool_use_block, thinking_block]` instead of the canonical
order. After `normalizeMessages` splits it, thinking appears at index 1 (after tool_use).
After `reorderMessagesInUI` groups `{tool_use → tool_result}`, thinking is "orphaned" after
the tool_result row in Ctrl-O transcript view.

### Fix

In `normalizeMessages`, before splitting a multi-block assistant message, apply a stable
partition sort: thinking/redacted_thinking blocks first, all others (text, tool_use) second.
This is idempotent on CC-canonical messages (already ordered correctly) and fixes KOSMOS's
FriendliAI-specific ordering.

```typescript
const isThinkingBlock = (b) => b.type === 'thinking' || b.type === 'redacted_thinking'
const orderedContent = content.length > 1
  ? [...content.filter(isThinkingBlock), ...content.filter(b => !isThinkingBlock(b))]
  : content
```

12 lines total. Only affects multi-block messages. Wave-3 finding was PARTIAL because the
issue only manifests in session replay or multi-turn scenarios — not visible in single-turn
live smoke.

---

## G10c — F-W3-beta-A: Fabricated derived value (거리 288m)

### Evidence

`wave3/beta/beta5/beta5-post-settle-scrollback.txt` — K-EXAONE responded to β5 (서울 응급실)
with "약 288m" as a distance estimate computed from HIRA `xPos`/`yPos` coordinates,
even though the `distance` field IS present in `hira_hospital_search` output. The issue is
the LLM computing distances from coord differences rather than citing the payload field,
AND the system prompt had no explicit prohibition on derived-value computation.

### Fix

Add `[CRITICAL — payload 에 없는 derived value 추측 금지]` block to `<output_style>` in
`prompts/system_v1.md`. Enumerate: 거리 / 이동시간 / ETA / 순위 / 평점 / 진료 가능 여부.
Specifically: "HIRA payload에 `distance` 필드가 있으면 그 값만 인용; xPos/yPos 좌표 차로 직접 계산 금지."

---

## G10d — F-W3-beta-B: HIRA `dgsbjt` field not used on first call

### Evidence

β5 first HIRA call had no `dgsbjt` parameter → ~900 mixed results returned → LLM had to
infer specialty from names → fallible and verbose. The `HiraHospitalSearchInput` schema
has `dgsbjt` as an optional field with excellent `Field(description=...)` documentation.
The BM25 suffix picks up the `llm_description` which already says "WHEN TO USE: citizen
mentions a specific 진료과 ('근처 내과 알려줘' → dgsbjt='내과')". But the system prompt's
`<tool_usage>` section has no HIRA-specific guidance.

### Fix options

Option A: Add to `prompts/system_v1.md` `<output_style>` — pro: always visible to LLM; con: grows system prompt.
Option B: Add to `llm_description` in `hospital_search.py` `self_contained_decl` — already has dgsbjt mention; BM25 suffix picks it up at query time.

**Decision**: Option A (system prompt) — the `_build_available_adapters_suffix` injects `llm_description` only when `hira_hospital_search` is a BM25 candidate. If the citizen's first query doesn't include hospital keywords, the suffix doesn't appear and the LLM has no guidance. System-prompt directive is always-on.

Add to `<output_style>`: `[CRITICAL — HIRA 병원 검색 시 dgsbjt 필드 사용 의무]` — cite natural-language examples + note that the validator maps Korean names to codes automatically.

---

## SHA-256 update

Both G10c + G10d modify `prompts/system_v1.md`. `prompts/manifest.yaml` sha256 must be updated after all edits.

Command: `shasum -a 256 prompts/system_v1.md | awk '{print $1}'`
