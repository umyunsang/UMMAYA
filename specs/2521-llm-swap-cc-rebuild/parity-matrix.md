# Parity Matrix — LLM Swap-Surface CC Byte-Copy + Bounded Swap Migration

**Spec**: [spec.md](./spec.md) | **Status**: skeleton — populated incrementally during `/speckit-implement`
**Date**: 2026-05-01

This matrix is the canonical authoritative artifact of the rebuild. Each row maps a CC reference handler to its KOSMOS resolution. Audit script (`scripts/llm_swap_parity_audit.sh`) reads this file as input.

## File-level rows

**Baselines captured 2026-05-01 (T001 + T002).**

| KOSMOS file | Procedure | CC source / analog | CC SHA-256 / lines | Current KOSMOS SHA-256 / lines | Expected post-byte-copy SHA-256 | Drift evidence |
|---|---|---|---|---|---|---|
| `tui/src/services/api/claude.ts` | A | `services/api/claude.ts` | `6d3fd16e608120d502e70ec461ffb66bcbca12fa86862859606c9118f977a999` / 3419 lines | `cb7ea2545f37fe91ecd147f1aa7d4220e80e495be9f1cd6e59690f4bf70e3195` / 1101 lines | `6d3fd16e608120d502e70ec461ffb66bcbca12fa86862859606c9118f977a999` (= CC) | **2318 lines missing** — silent feature drop confirmed; byte-copy will reintroduce them, then Step B labeled swaps re-apply justified deletions |
| `tui/src/ipc/llmClient.ts` | B | `services/api/claude.ts:1980-2295` (analog) + `query.ts:120-410` | (analog — n/a for byte-copy) | `7e19ae12bbafd1339836fccd3c31cd1585c2858361fdd911e9539b570a19b485` / 661 lines | n/a (Procedure B — citations required, not byte-copy) | partial chunk.thinking plumbing added 2026-05-01; ~5 channels missing CC citations |
| `src/kosmos/llm/client.py` | B | `services/api/claude.ts` (whole file analog) | (analog — n/a) | `47a344e7bdf087226b5dc7607a0b0a2e5ffc0248717d7cac4ef6a06da7b68306` / 1030 lines | n/a (Procedure B) | reasoning_content forwarding correct (line 788); other branches need citations |
| `src/kosmos/ipc/stdio.py` | B | `QueryEngine.ts` (1295 lines) + `query.ts` (1729 lines) | (analog — n/a) | `f1a398782c375bbe46975ca69f43dc50bfdc63077f9e4e0ec804ed9fc1fb5e26` / 1909 lines | n/a (Procedure B) | `_ensure_tool_registry` lazy-init applied 2026-05-01; agentic loop needs CC analog citations |

## Stream-event channel rows (per `services/api/claude.ts:1980-2295`)

**KOSMOS handler column convention** — `<file>:<line>` resolves the actual line where KOSMOS emits or accepts that channel. byte-copied entries point at `tui/src/services/api/claude.ts` (the byte-equal copy) AND at the live KOSMOS-IPC consumer at `tui/src/ipc/llmClient.ts` where the channel is forwarded to citizen-visible state.

| CC line | CC event | CC subtype | KOSMOS handler | Status | Justification |
|---|---|---|---|---|---|
| 1980 | message_start | (n/a) | `tui/src/services/api/claude.ts:1980` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:344-358` | byte-copied | preserves CC pattern |
| 1995 | content_block_start | tool_use (1997) | `tui/src/services/api/claude.ts:1997` (byte-copy); live tool_call frame branch at `tui/src/ipc/llmClient.ts:491-521` | byte-copied | KOSMOS dispatches tools via IPC, but the start event is universal |
| 1995 | content_block_start | server_tool_use (2003) | (skipped) | skipped-N/A | KOSMOS-N/A: server-side tools not used; `// SKIPPED — KOSMOS-N/A` comment at `tui/src/ipc/llmClient.ts:329` |
| 2019 | content_block_start | text | `tui/src/services/api/claude.ts:2019` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:371-378` | byte-copied | citizen-visible answer text channel |
| 2030 | content_block_start | thinking | `tui/src/services/api/claude.ts:2030` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:387-395` | byte-copied | K-EXAONE reasoning channel — primary US1 deliverable |
| 2053 | content_block_delta | text_delta (2113) | `tui/src/services/api/claude.ts:2113` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:411-415` + Python source at `src/kosmos/llm/client.py:786` | byte-copied | text content streaming |
| 2053 | content_block_delta | input_json_delta (2087) | `tui/src/services/api/claude.ts:2087` (byte-copy); KOSMOS pre-buffers tool args at backend (`src/kosmos/llm/client.py:805`) and emits complete `tool_use` block in single `ToolCallFrame` (collapsed at `tui/src/ipc/llmClient.ts:484-490`) | byte-copied | tool args streaming — collapsed by IPC adapter |
| 2053 | content_block_delta | thinking_delta (2148) | `tui/src/services/api/claude.ts:2148` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:398-407` + `src/kosmos/llm/client.py:802` (reasoning_content forwarding) | byte-copied | reasoning_content channel — US1 |
| 2053 | content_block_delta | signature_delta (2127) | (skipped) | skipped-N/A | KOSMOS-N/A: K-EXAONE/FriendliAI does not emit thinking signatures; `// SKIPPED — KOSMOS-N/A` at `tui/src/ipc/llmClient.ts:325` |
| 2053 | content_block_delta | citations_delta (2084) | (skipped) | skipped-N/A | KOSMOS-N/A: citations live in tool_result envelopes, not stream events; `// SKIPPED — KOSMOS-N/A` at `tui/src/ipc/llmClient.ts:327` |
| 2053 | content_block_delta | connector_text_delta (2068) | (skipped) | skipped-N/A | KOSMOS-N/A: Anthropic connector blocks not used; `// SKIPPED — KOSMOS-N/A` at `tui/src/ipc/llmClient.ts:331` |
| 2171 | content_block_stop | (n/a) | `tui/src/services/api/claude.ts:2171` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:466` (text) + `:511-513` (tool_use) | byte-copied | universal block termination |
| 2213 | message_delta | (n/a, includes stop_reason + usage) | `tui/src/services/api/claude.ts:2213` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:469-474` | byte-copied | turn finalization — CC pattern preserved |
| 2295 | message_stop | (n/a) | `tui/src/services/api/claude.ts:2295` (byte-copy); live emission at `tui/src/ipc/llmClient.ts:476-477` | byte-copied | message termination |

## Procedure-B per-handler rows (citations required)

| KOSMOS file | KOSMOS function/handler | CC analog reference | Notes |
|---|---|---|---|
| `tui/src/ipc/llmClient.ts` | `stream` async generator | `services/api/claude.ts:1980-2295` | every event handler in the generator (`message_start`, `content_block_start` text/thinking/tool_use, `content_block_delta` text_delta/thinking_delta/input_json_delta, `content_block_stop`, `message_delta`, `message_stop`) carries `CC reference: services/api/claude.ts:<line>` comment plus `// SKIPPED — KOSMOS-N/A` lines for `signature_delta` / `citations_delta` / `connector_text_delta` / `server_tool_use` (verified by grep — see audit script T029 check) |
| `tui/src/ipc/llmClient.ts` | `_TurnAccumulator.thinkingBlockIndex` | `services/api/claude.ts:2030,2148` | thinking block lazy-init — added 2026-05-01 |
| `src/kosmos/llm/client.py` | `_stream_response` | `services/api/claude.ts:1980-2295` | FriendliAI OpenAI-compat → AssistantChunkFrame |
| `src/kosmos/llm/client.py` | reasoning_content branch (line 788) | `services/api/claude.ts:2148` | thinking_delta channel forwarding |
| `src/kosmos/ipc/stdio.py` | `_handle_chat_request` outer loop | `QueryEngine.ts` (whole) + `query.ts:120-410` | agentic loop pattern |
| `src/kosmos/ipc/stdio.py` | `_dispatch_primitive` | `services/tools/toolOrchestration.ts:19-72` (`runTools`) | tool dispatch — partition policy deferred |
| `src/kosmos/ipc/stdio.py` | `_ensure_tool_registry` | (no direct CC analog — KOSMOS-only IPC adaptation) | lazy-init per Spec 1634; SWAP/llm-provider justification |

## Swap commit log (populated incrementally)

### 2026-05-01 retroactive labels (T007 — applied via this Epic)

These four fixes were applied 2026-05-01 BEFORE this Epic was specified. Per spec § Methodology Step B, each is retroactively labeled with one of the four allowed swap categories. Auditable via `git log` after the rebuild commits land.

| Original commit | Retroactive category | Files affected | Justification |
|---|---|---|---|
| `_ensure_tool_registry` lazy-init in `src/kosmos/ipc/stdio.py:548` (calls `register_all_tools` exactly once on first IPC dispatch) | `SWAP/llm-provider` | `src/kosmos/ipc/stdio.py` | CC's `QueryEngine.ts` assumes `ToolRegistry` populated at SDK construction time (Anthropic SDK new()); KOSMOS's stdio JSONL backend must populate lazily on first `_dispatch_primitive` call. Without this swap the BM25 search returns `reason="empty_registry"` and the citizen sees `검색 결과가 없습니다`. |
| `<turn_order>` section in `prompts/system_v1.md` + manifest SHA-256 update `c49f384...` → `da2adc2a...` | `SWAP/llm-provider` | `prompts/system_v1.md`, `prompts/manifest.yaml` | CC's `prompts.ts:420` "Lead with the action, not the reasoning. Skip filler words, preamble" is part of CC's system prompt assembly. KOSMOS's K-EXAONE on FriendliAI does NOT inherit CC's system prompt (it's a different LLM provider) so the equivalent guidance must be ported into KOSMOS's `prompts/system_v1.md`. The `<turn_order>` section is the KOSMOS port of CC's behavior contract. |
| `enable_thinking=true` default in `src/kosmos/llm/client.py:858` (was `false` before 2026-05-01) | `SWAP/llm-provider` | `src/kosmos/llm/client.py` | K-EXAONE-236B-A23B model card recommends `enable_thinking=True` as default; τ²-Bench scores (Retail 78.6 / Airline 60.4 / Telecom 73.5) are measured with thinking ON. KOSMOS prior default `false` was a misconfiguration that suppressed the reasoning_content channel entirely. |
| `KosmosThinkingDelta` type added to `tui/src/ipc/llmTypes.ts` + thinking branch added to `tui/src/ipc/llmClient.ts` AssistantChunkFrame handler | `SWAP/llm-provider` | `tui/src/ipc/llmTypes.ts`, `tui/src/ipc/llmClient.ts` | CC's `services/api/claude.ts:2148` handles `thinking_delta` content_block_delta natively. KOSMOS's IPC bridge layer needed to forward `AssistantChunkFrame.thinking` field to the same content_block_delta shape so the existing `AssistantThinkingMessage` component renders. Without this swap the K-EXAONE reasoning channel is silently dropped at the TUI consumer. |

### Procedure-A Step A + Step B commits (populated during T010-T013)

| Commit SHA | Category | Files affected | CC reference | Justification |
|---|---|---|---|---|
| `3175862` | byte-copy | `tui/src/services/api/claude.ts` | `services/api/claude.ts` (whole, 3419 lines, SHA `6d3fd16e608120d502e70ec461ffb66bcbca12fa86862859606c9118f977a999`) | Step A initial byte-copy — overwrites prior 1101-line KOSMOS variant; SHA verified `6d3fd16e=6d3fd16e` |
| `4d6b9a1` | SWAP/llm-provider | `tui/src/services/api/claude.ts` | `services/api/claude.ts:1-115` (5 import statements) | replace `@anthropic-ai/sdk` (3 sub-paths) + `@anthropic-ai/sdk` + `@anthropic-ai/sdk/error` with `'../../sdk-compat.js'` re-exports; SDK no longer in runtime graph (FR-001 / SC-002) |
| `3139e4c` | SWAP/anti-anthropic-1p | `tui/src/services/api/claude.ts` | `services/api/claude.ts` (file header) | document 1P call-graph deadening — KOSMOS support modules `services/claudeAiLimits.ts` + `utils/auth.ts` already inert (Epic #1633 stubs); 1P symbols in byte-copied claude.ts resolve to no-ops at runtime; zero callers in tui/src reach this file post-Spec-2293 (doubly dead) |
| `07d23f8` | SWAP/identifier-rename | `tui/src/services/api/claude.ts` | `services/api/claude.ts:2942` + `:3322` (2 doc-comment hits) | citizen-visible "Anthropic streaming API" → "upstream streaming API"; "Claude Code infrastructure" → "KOSMOS infrastructure"; internal SDK type names left sdk-compat-aliased per T011 to keep audit-replay diff clean |

## Reading guide

- **byte-copied** rows: byte-equal with CC at the byte-copy commit. Subsequent swap commits MAY modify but each modification carries a category and citation.
- **skipped-N/A** rows: explicit skip with reason. Audit script verifies the comment exists in the KOSMOS file as `// SKIPPED — KOSMOS-N/A: <reason>`.
- **kosmos-extension** rows (none yet): KOSMOS-only handlers with no CC analog. Each requires Procedure-B-style `CC reference:` citation pointing to the closest analog (or `(no direct CC analog)` with reason).

## Updates

This file is updated incrementally as the rebuild progresses. Tasks in `tasks.md` (generated by `/speckit-tasks`) include "update parity-matrix.md row N" per swap commit.
