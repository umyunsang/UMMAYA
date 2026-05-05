# G5 Render commit / JSON 절단 / Ctrl-O sanitizer — Deep research

> Lead Opus G5 — Wave-2 (2026-05-05). Pattern P-E (universal JSON 절단) + P-F (raw 내부 필드 + Ctrl-O 누출).
> Targets: F-beta-05 (universal), F-alpha-08, F-alpha-09, F-alpha-10, F-beta-06, F-beta-09 (자동 회복), F-known criterion #2/#3.

## Phase 1 — Reproduce + log

### F-beta-05 root cause — `LookupPrimitive.renderToolResultMessage` slice without ellipsis

`tui/src/tools/LookupPrimitive/LookupPrimitive.ts:387-405` — collection / timeseries / record fetch path:

```ts
// lines 387-397 (Array branch — collection, timeseries):
summaryRows = adapterResult.slice(0, 3).map((item: unknown, i: number) => {
  const summary =
    typeof item === 'object' && item !== null
      ? JSON.stringify(item).slice(0, 120)        // ← HARD CUT, no ellipsis
      : String(item).slice(0, 120)                // ← HARD CUT, no ellipsis
  return React.createElement(Text, { key: i, dimColor: true }, `  ${i + 1}. ${summary}`)
})

// lines 398-405 (single object branch — record):
const summary =
  typeof adapterResult === 'object'
    ? JSON.stringify(adapterResult).slice(0, 240)  // ← HARD CUT, no ellipsis
    : String(adapterResult).slice(0, 240)
```

Evidence (β1, snap-005-answer-data.txt:15-17):

```
  ⎿  timeseries — 24건
       1. {"timestamp_iso":"2026-05-05T12:00:00",..."sky_code":"1","interval
       2. {...,"sky_code":"1","interval
```

The cut lands mid-key (`"interval`...) with **no `…` indicator**. F-known criterion #2 universal regression confirmed at this exact code site. Affects every `kma_*` adapter response (timeseries) and every record-shape response.

The other Wave-1 finding `terminal.ts:renderTruncatedContent` already implements ellipsis correctly (line 105-109: `… +N lines (Ctrl-O to expand)`). It is **not used** by LookupPrimitive's summary path — the primitive bypasses the canonical truncation helper.

### F-alpha-08 root cause — Ctrl-O reveals LLM thinking text verbatim

`tui/src/components/messages/AssistantThinkingMessage.tsx:39-87` — when `isTranscriptMode || verbose` is true, the entire `thinking` string is passed straight to `<Markdown dimColor>{thinking}</Markdown>`. There is no sanitizer.

The leak is not the system prompt itself. It is the LLM's own chain-of-thought, in which K-EXAONE quotes:

- `lookup`, `resolve_location`, `submit`, `subscribe`, `verify` (5 primitive names)
- `available_adapters` block
- `tool_id`
- 6 verbatim adapter ids (`hira_hospital_search`, `kma_current_observation`, `kma_forecast_fetch`, `kma_pre_warning`, `kma_short_term_forecast`, `koroad_accident_hazard_search`)
- system-prompt phrasing ("외부 도메인 API …를 조회하는 추상 도구")

Surface = `snap-003-after-ctrl-o-collapse.txt:13-19, 41-54`.

CC byte-identical match: `.references/claude-code-sourcemap/restored-src/src/components/messages/AssistantThinkingMessage.tsx` is identical in shape — CC has the same `Markdown {thinking}` render. CC never had this problem because the Anthropic system prompt didn't contain primitive enums or adapter ids; KOSMOS' system prompt does. The fix has to live one layer up: a citizen-mode sanitizer that redacts internal symbols before the Markdown renderer sees them.

### F-alpha-09 root cause — thinking AFTER answer in Ctrl-O path

In `snap-003-after-ctrl-o-collapse.txt`, the answer (lines 1-7) is followed by `∴ Thinking…` (line 9) and then the thinking body (lines 11-56). PR #2772 added a render-order fix on the streaming path. Ctrl-O / transcript path uses `transcriptMessages` (REPL.tsx:5270) which is the assembled session message log — the order is whatever the message array was constructed in. In transcript mode, the assistant message rendered **last** (final answer text) is shown after the thinking block by message-position, but in our snap the thinking block was emitted as the *last* message in stream order — meaning the K-EXAONE FriendliAI provider emitted final assistant text first, then a closing `reasoning_content` chunk that was appended as a separate thinking block at the end of the message list.

The PR #2772 streaming fix reorders within the **streaming** ChatRequest. It does not touch the post-stream assembled message array used by transcript mode. Fix candidates:
1. `Messages.tsx` filter that, when rendering grouped assistant content, re-sorts thinking-blocks to come *before* their associated text-block within the same `assistant_message`.
2. Backend post-process: discard `reasoning_content` chunks that arrive after the first non-empty `content` token from K-EXAONE (closing-thought emissions).

For G5 we choose approach (2)-lite at the renderer level: ignore trailing thinking blocks in the **same** assistant message group. This is the cheaper, lower-risk fix and is in-scope for "render commit" theme.

### F-alpha-10 — Ctrl-O semantics

The audit's stated expected was "default = full, Ctrl-O = collapse". Verified against CC restored-src `AssistantThinkingMessage.tsx`:

```
const shouldShowFullThinking = isTranscriptMode || verbose
if (!shouldShowFullThinking) { /* render "∴ Thinking" only */ }
return /* render full Markdown */
```

CC's default IS collapsed; Ctrl-O #1 expands. KOSMOS matches CC byte-identical here. **F-alpha-10 is a misread of CC convention** — the current behaviour is correct. Document this in the fix report rather than invert. (The audit author may have been confused by `isTranscriptMode` always being false at first paint — that IS the CC default.)

### F-beta-06 root cause — pty enum leak

`prompts/system_v1.md` carries no enum mapping for `pty` (precipitation type). The LLM receives `pty: 0` from `kma_*` adapters and types `(강수형태 0)` verbatim in its answer.

The `kma_current_observation.py:149-153` Pydantic field has the mapping in a Python docstring (`0=none, 1=rain, 2=rain+snow, 3=snow, 5=drizzle, 6=drizzle+snow, 7=snow flurry`) but **Pydantic JSON schema does not export field docstrings**, so the suffix renderer (`stdio.py:_build_available_adapters_suffix`) never sees it. The mapping has to be either:
- (a) appended to `KmaCurrentObservationOutput.pty` field's pydantic `Field(description=...)` so it surfaces via `properties.<field>.description`, OR
- (b) inlined in the system prompt as a small enum table, OR
- (c) both (defense-in-depth).

For G5, choose (c): add a tiny "<output_enum_mappings>" block to `system_v1.md` covering pty + sky + vec→16방위, and add `Field(description=...)` to the affected output models.

But output schema fields don't surface in `_build_available_adapters_suffix` — only `input_schema_json`. For output-side enum mapping, the prompt is the only knob. Choose (b)+(a-input-side-only): system_v1.md inline enum mappings table, plus reinforced llm_description in the adapter (already present for VEC, missing for PTY).

### F-beta-09 — auto-recover

NMC β5 phone hallucination is gated on F-beta-05 fix. Once the JSON has explicit `…` ellipsis, downstream auditing can grep the unredacted JSON for `02-2001-2001`. If still absent → escalate. **Out of scope for the G5 code change**, but the truncation fix unblocks verification.

## Phase 2 — Diff with CC restored-src

| Surface | KOSMOS | CC restored-src | Verdict |
|---|---|---|---|
| `AssistantThinkingMessage.tsx` | KOSMOS adds collapsed-mode preview (Spec 2521 swap), full body identical | CC has only "∴ Thinking" stub when collapsed | KOSMOS is a superset; sanitizer needed for full-body path |
| `MessageResponse.tsx` | Identical | Identical | No change |
| `terminal.ts:renderTruncatedContent` | Identical (already has `…` ellipsis) | Identical | No change |
| `LookupPrimitive` | KOSMOS-original (CC has no Lookup primitive) | N/A | Must fix in-place |
| `verboseRender.ts` | KOSMOS-original | N/A | Already JSON-shape, but Ctrl-O exposes; sanitize at the AssistantThinkingMessage layer instead |
| `system_v1.md` | KOSMOS-original | N/A | Add `<output_enum_mappings>` block |
| `kma_current_observation.py` Field(description) | VEC has 16-direction inline; PTY has only docstring | N/A | Add PTY description |

CC's truncation pattern (BashTool / WebFetchTool) uses `renderTruncatedContent` which already prints `… +N lines (Ctrl-O to expand)`. KOSMOS LookupPrimitive bypasses it via `slice(0, N)`. The cleanest fix is to delegate to `renderTruncatedContent` — but the rendering shape is different (each item is a separate `<Text>` row, not a single content blob), so we need a small **JSON-aware truncate helper** that ensures either:
- valid JSON closing brace, OR
- explicit `…` indicator suffixed.

We choose the second (simpler + lossless to LLM context).

## Phase 3 — Fix design (3 minimal patches)

### Patch A — JSON-aware ellipsis in `LookupPrimitive`

```ts
// new helper at top of LookupPrimitive.ts (or _shared/jsonTruncate.ts)
function truncateJson(s: string, max: number): string {
  if (s.length <= max) return s
  return s.slice(0, Math.max(0, max - 1)) + '…'
}
```

Replace the three `slice(0, N)` calls with `truncateJson(s, N)`. The `…` is a single Unicode code-point (U+2026), 1 column wide — fits Ink's column budget. Does not affect typecheck because string return type is unchanged. Backward-compatible to ink-testing-library snapshots only at the visible-cell level (the cut character moves by 1 — acceptable).

### Patch B — Ctrl-O thinking sanitizer

Add `tui/src/components/messages/sanitizeThinking.ts`:

```ts
const REDACT_TOKENS = [
  // 5 primitive names (the suffix exposes these, but they shouldn't appear as
  // the model's verbatim quote of internal scaffolding):
  /\bavailable_adapters\b/g,
  /\btool_id\b/g,
  // Brand the redaction so QA can grep for it
] as const

const ADAPTER_ID_RE =
  /\b(?:hira|kma|koroad|nmc|nfa119|mohw)_[a-z_]+\b/g

export function sanitizeThinking(thinking: string): string {
  let out = thinking
  for (const re of REDACT_TOKENS) out = out.replace(re, '⟨내부⟩')
  out = out.replace(ADAPTER_ID_RE, '⟨adapter⟩')
  return out
}
```

Wired into `AssistantThinkingMessage.tsx`:

```ts
const visibleThinking = sanitizeThinking(thinking)
// ... use visibleThinking in collapsed-preview slice + full Markdown body
```

This redacts only what the user-facing surface shows. The raw `thinking` channel that goes back to the LLM in subsequent turns is **not** modified — agentic context is preserved.

The allow / deny list:

| Pattern | Action | Replacement | Rationale |
|---|---|---|---|
| `\bavailable_adapters\b` | redact | `⟨내부⟩` | F-alpha-08 — internal block name |
| `\btool_id\b` | redact | `⟨내부⟩` | F-alpha-08 — internal field name |
| Adapter IDs (`hira_*`, `kma_*`, `koroad_*`, `nmc_*`, `nfa119_*`, `mohw_*`) | redact | `⟨adapter⟩` | F-alpha-08 — registry id leak |
| 5 primitive names (`lookup`/`resolve_location`/`submit`/`verify`/`subscribe`) | **NOT redacted** | — | These are also citizen-facing ("이 결과는 lookup 도구로…") and CC convention shows tool names in transcripts. Citizen sees the same names already in the `⏺ lookup(...)` line. |
| Korean prose | preserve | — | Citizen needs LLM's reasoning |

### Patch C — Trailing thinking block discard (F-alpha-09)

Update `Messages.tsx` (or `AssistantThinkingMessage.tsx` parent group renderer) to drop trailing thinking blocks when there is a preceding text block in the same assistant message group. Implementation: filter at the message-grouping level, not at the per-message render level.

For G5 minimal-touch we instead use the `hideInTranscript` prop already present in `AssistantThinkingMessage.tsx:17`. When `isTranscriptMode === true` AND the thinking block is preceded by a text block in the same group, set `hideInTranscript={true}`.

**Decision**: Patches A + B are guaranteed minimal-risk and address P0/P1 concerns. Patch C is more invasive (touches Messages.tsx grouping logic) and has higher regression surface; defer to separate Wave-3 fix issue per "Single commit" constraint and "Don't touch G6/G7" constraint. Document deferral.

### Patch D — system_v1.md enum mappings + PTY field description

Add a `<output_enum_mappings>` block after `<output_style>` in `prompts/system_v1.md`:

```
<output_enum_mappings>
**[CRITICAL — 도구 응답 raw 코드 → 시민 자연어 변환 의무]** 도구 응답에 다음 enum 코드가 포함되면 시민에게 답변 시 반드시 한국어 자연어로 변환하십시오. raw 코드 (`pty: 0`, `sky: 1`, `vec: 271` 등) 를 그대로 답변에 노출 금지.

**PTY (강수형태)** — `pty=0` → "강수 없음", `pty=1` → "비", `pty=2` → "비/눈", `pty=3` → "눈", `pty=5` → "이슬비", `pty=6` → "이슬비/눈", `pty=7` → "눈날림". 자연어 답변 시 코드 자체는 생략 — 예: "비는 오지 않습니다" (NOT "강수형태 0").

**SKY (하늘상태)** — `sky=1` → "맑음", `sky=3` → "구름많음", `sky=4` → "흐림". raw 코드 `sky_code` 답변에 노출 금지.

**VEC (풍향, 도)** — 0=북, 90=동, 180=남, 270=서. 16방위 매핑: N(348.75-11.25), NNE(11.25-33.75), NE(33.75-56.25), ENE(56.25-78.75), E(78.75-101.25), ESE(101.25-123.75), SE(123.75-146.25), SSE(146.25-168.75), S(168.75-191.25), SSW(191.25-213.75), SW(213.75-236.25), WSW(236.25-258.75), W(258.75-281.25), WNW(281.25-303.75), NW(303.75-326.25), NNW(326.25-348.75). 답변 예: vec=271 → "서풍 (271°)", vec=315 → "북서풍 (315°)". 도수 추측 금지 — 매핑 표 사용.
</output_enum_mappings>
```

Also add `Field(description=...)` to `KmaCurrentObservationOutput.pty` / `KmaShortTermForecastOutput.pty` so the input/output schema export carries enum semantics for the suffix builder. (Note: `_build_available_adapters_suffix` only renders **input** schemas, not output. So Field description is documentation-only here; the system prompt addition is the load-bearing fix.)

## Phase 4 — TDD plan

### Layer 1b — Ink snapshot

`tui/src/__tests__/lookup-truncation.test.tsx` (new):
- Render `LookupPrimitive.renderToolResultMessage` with a 30-item timeseries → assert each row ends with `…`
- Render with a 1-item record + 300-char JSON → assert single row ends with `…`
- Render with a short 50-char JSON → assert no `…`

`tui/src/__tests__/sanitizeThinking.test.ts` (new):
- `sanitizeThinking("available_adapters 에서 hira_hospital_search 를 골라")` → `"⟨내부⟩ 에서 ⟨adapter⟩ 를 골라"`
- `sanitizeThinking("일반 한국어 텍스트는 보존")` → unchanged
- `sanitizeThinking("kma_current_observation 와 koroad_accident_hazard_search")` → `"⟨adapter⟩ 와 ⟨adapter⟩"`

### Python pytest — system prompt manifest hash

`tests/prompts/test_enum_mappings.py` (new):
- Load `prompts/system_v1.md`, assert `<output_enum_mappings>` block exists
- Assert PTY mapping covers 0/1/2/3/5/6/7
- Assert manifest.yaml SHA-256 still matches (rebuild)

### Layer 5 — re-run α5/α5b + β1-β5

After patches: re-run with tmux capture-pane and verify:
- β1 snap-005-answer-data.txt JSON rows end with `…`
- β2 final answer does NOT contain `강수형태 0`
- α5b snap-003-after-ctrl-o-collapse.txt thinking does NOT contain `available_adapters` or `tool_id` or adapter ids verbatim

## Conclusion + commit plan

Single commit per spec:
```
fix(2773-g5): Message renderer JSON ellipsis + Ctrl-O sanitizer + system prompt enum mappings (closes F-beta-05/06, F-alpha-08, partial F-alpha-09/10)
```

Files touched:
1. `tui/src/tools/LookupPrimitive/LookupPrimitive.ts` — replace 3 `slice(0,N)` with `truncateJson(s,N)` helper (F-beta-05).
2. `tui/src/components/messages/sanitizeThinking.ts` — new module (F-alpha-08).
3. `tui/src/components/messages/AssistantThinkingMessage.tsx` — wire sanitizer in both collapsed-preview and full-body paths.
4. `prompts/system_v1.md` — add `<output_enum_mappings>` block (F-beta-06).
5. `prompts/manifest.yaml` — recompute SHA-256 prefix.
6. `src/kosmos/tools/kma/kma_current_observation.py` — add `Field(description=...)` for `pty` / `sky_code` mention (defense-in-depth).
7. `tui/src/__tests__/sanitizeThinking.test.ts` — new bun test.
8. `tui/src/__tests__/lookup-truncation.test.tsx` — new bun test.
9. `tests/prompts/test_enum_mappings.py` — new pytest.

Deferred (next-spec):
- F-alpha-09 (trailing thinking re-order in transcript) — Wave-3 G2-adjacent.
- F-alpha-10 — documented as **CC-byte-identical, not a regression**.
- F-beta-09 NMC phone hallucination — auto-checks after F-beta-05 truncation lifted.
