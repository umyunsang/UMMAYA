## LLM Swap-Surface Parity Audit

**Branch**: feat/2521-procedure-a-and-audit
**Run**: 2026-04-30T21:42:11Z
**Script version**: 2521.T034

### Per-file outcomes

| KOSMOS file | Procedure | Byte-copy SHA match | Swap commits | Unjustified hunks | Missing citations |
|---|---|---|---|---|---|
| tui/src/services/api/claude.ts | A | OK | 3 | 0 | 0 |
| tui/src/ipc/llmClient.ts | B | n/a | 0 | 0 | 0 |
| src/kosmos/llm/client.py | B | n/a | 0 | 0 | 0 |
| src/kosmos/ipc/stdio.py | B | n/a | 0 | 0 | 0 |

### Stream-event channel coverage (CC services/api/claude.ts:1980-2295)

| CC event kind | CC subtype | CC line | KOSMOS handler | Status |
|---|---|---|---|---|
| message_start | n/a | 1980 | tui/src/services/api/claude.ts:1980 | byte-copied |
| content_block_start | tool_use | 1997 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_start | server_tool_use | 2003 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_start | text | 2019 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_start | thinking | 2030 | tui/src/services/api/claude.ts:2030 | byte-copied |
| content_block_delta | text_delta | 2113 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_delta | input_json_delta | 2087 | tui/src/services/api/claude.ts:2087 | byte-copied |
| content_block_delta | thinking_delta | 2148 | tui/src/services/api/claude.ts:2148 | byte-copied |
| content_block_delta | signature_delta | 2127 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_delta | citations_delta | 2084 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_delta | connector_text_delta | 2068 | (skipped) | SKIPPED (KOSMOS-N/A) |
| content_block_stop | n/a | 2171 | tui/src/services/api/claude.ts:2171 | byte-copied |
| message_delta | n/a | 2213 | tui/src/services/api/claude.ts:2213 | byte-copied |
| message_stop | n/a | 2295 | tui/src/services/api/claude.ts:2295 | byte-copied |

### Summary

**Result**: PASS
**Total unjustified hunks**: 0
**Missing CC citations**: 0
**Warnings**: 0
