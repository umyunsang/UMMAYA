# G10 — Fix Report: Agents chord block + Ctrl-O thinking grouping + system prompt no-fabrication + HIRA dgsbjt directive

> Wave-4 G10 · Date: 2026-05-05 · HEAD: `e63050e4` (base)
> Closes F-ε-05 (P0), F-alpha-09 (P1/deferred), F-W3-beta-A (P1), F-W3-beta-B (P1)

## Findings closed

| Finding | Surface | Symptom | Fix applied |
|---|---|---|---|
| F-ε-05 | UI-D `/agents` | Esc dismiss no-op — ChordInterceptor absorbed Esc via Chat→chat:cancel before raw useInput fallback in AgentsCommandView could fire | G10a — `Agents` chord block in `defaultBindings.ts` + `useKeybinding('agents:dismiss', ..., { context: 'Agents' })` in `AgentsCommandView` |
| F-alpha-09 | Messages Ctrl-O | Thinking block appeared after tool_result in transcript view when stream-end timestamps differed (K-EXAONE FriendliAI ordering) | G10b — defensive stable sort in `normalizeMessages` (thinking blocks first within multi-block assistant messages) |
| F-W3-beta-A | system prompt | LLM computed "약 288m" distances from HIRA xPos/yPos coords instead of citing `distance` payload field | G10c — `[CRITICAL — payload 에 없는 derived value 추측 금지]` directive in `prompts/system_v1.md` `<output_style>` |
| F-W3-beta-B | system prompt | HIRA `dgsbjt` specialty filter not used on first call; LLM received ~900 unfiltered results | G10d — `[CRITICAL — HIRA 병원 검색 시 dgsbjt 필드 사용 의무]` directive in `prompts/system_v1.md` |

## Files changed

| File | Type | Change |
|---|---|---|
| `tui/src/keybindings/defaultBindings.ts` | edit | Append `Agents` context block `{ context: 'Agents', bindings: { escape: 'agents:dismiss' } }` after `Help` block |
| `tui/src/commands/agents.tsx` | edit | Add `import useKeybinding` + `useKeybinding('agents:dismiss', () => { onExit?.() }, { context: 'Agents' })` before existing `useInput` fallback |
| `tui/src/utils/messages.ts` | edit | `normalizeMessages` — stable partition sort (thinking first) for multi-block assistant messages before per-block split |
| `prompts/system_v1.md` | edit | Add two CRITICAL directives in `<output_style>`: no-fabrication derived values + HIRA dgsbjt mandatory usage |
| `prompts/manifest.yaml` | edit | Update `system_v1` sha256 to `0e6b812843420bed61fe7879e3c318262aefdb85dde5a72a993bfbe4f7bf2b23` |
| `tui/tests/keybindings/g2-autocomplete-help.test.ts` | edit | Add G10a tests: `Agents` block catalogue invariant + Esc resolves to `agents:dismiss` when Agents context active + without Agents, Esc still resolves to chat:cancel/draft-cancel |
| `tui/tests/keybindings/g2-overlay-dismiss.test.tsx` | edit | Add G10a test: AgentsCommandView Esc with `activeContexts: ['Agents', 'Chat', 'Global']` via chord path |
| `tests/llm/test_prompt_enum_mappings.py` | edit | Add G10c test (no-fabrication directive present) + G10d test (hira dgsbjt directive present) |

## G10a — Agents chord block + useKeybinding

**Root cause**: `AgentsCommandView` used only `useInput` for Esc dismiss. `ChordInterceptor` (mounted first) resolved Esc to `chat:cancel` via Chat context block in `DEFAULT_BINDING_BLOCKS` and called `event.stopImmediatePropagation()`, preventing the fallback `useInput` from firing.

**Fix**: Two-layer pattern identical to `HelpV2Grouped`:
1. `DEFAULT_BINDING_BLOCKS` Agents block → `resolveKeyWithChordState` returns `agents:dismiss` when `'Agents'` in context list
2. `useKeybinding('agents:dismiss', ..., { context: 'Agents' })` → registers `'Agents'` in `handlerContexts` → ChordInterceptor includes it → `agents:dismiss` wins over `chat:cancel` (last-match-wins, Agents block declared after Help/Chat)

Raw `useInput` fallback preserved for Bun-PTY raw `\x1b` delivery defense-in-depth.

## G10b — Thinking block ordering in normalizeMessages

**Root cause**: K-EXAONE on FriendliAI occasionally delivers `content: [tool_use, thinking]` ordering (later stream-end timestamp for thinking). After `normalizeMessages` split, thinking appeared at index 1 (after tool_use). After `reorderMessagesInUI` grouped `{tool_use → tool_result}`, thinking rendered after the tool_result row in Ctrl-O view.

**Fix**: Before the per-block `map()` in `normalizeMessages`, apply a stable partition: `[...content.filter(isThinking), ...content.filter(notThinking)]`. 12 lines. No-op for single-block messages or CC-canonical `[thinking, tool_use]` ordering.

## G10c — No-fabrication derived value directive

**Fix**: Added `[CRITICAL — payload 에 없는 derived value 추측 금지]` block between HIRA dgsbjt directive and existing PTY/SKY/VEC directive in `<output_style>`. Enumerates:
- 거리: only cite `distance` field; never compute from xPos/yPos
- 이동 시간: no "도보 X분" without payload
- ETA: no arrival time estimates
- 순위/평점: no arbitrary ranking
- 진료 가능 여부: no "현재 진료 중" without realtime data

## G10d — HIRA dgsbjt directive

**Fix**: Added `[CRITICAL — HIRA 병원 검색 시 dgsbjt 필드 사용 의무]` block. States that when citizen mentions a specialty (`내과`, `소아과`, `안과`, etc.) `dgsbjt` is mandatory. Without it, returns ~900 mixed results. Korean natural language names are accepted directly — adapter validator maps them to 2-digit codes.

## Manifest SHA-256 update

```
prompts/system_v1.md → sha256: 0e6b812843420bed61fe7879e3c318262aefdb85dde5a72a993bfbe4f7bf2b23
```

## Layer 1 verification

### Layer 1b — bun test

```
bun test tui/tests/keybindings/g2-autocomplete-help.test.ts tui/tests/keybindings/g2-overlay-dismiss.test.tsx
→ 15 pass / 0 fail (11 original + 4 new G10a tests)
```

### Layer 1a — pytest

```
pytest tests/llm/test_prompt_enum_mappings.py -v
→ 6 passed / 0 failed (4 original + 2 new G10c/d tests)
```

## Constraint compliance

- Single commit: `fix(2773-g10): Agents chord block + Ctrl-O thinking grouping + system prompt no-fabrication + HIRA dgsbjt directive (closes F-ε-05, F-alpha-09, F-W3-beta-A/B)`
- LoC: ~75 source lines + ~90 test lines = ~165 LoC total (≤200)
- Zero new runtime deps
- G8/G9/G11/G12 surfaces untouched

## Layer 5 re-smoke (deferred to Lead Opus)

- ε6: `/agents Esc dismiss` — verify F-ε-05 CLOSED
- α5b: Ctrl-O thinking order — verify F-alpha-09 CLOSED
- β5: HIRA dgsbjt + fabrication absence — verify F-W3-beta-A/B CLOSED
