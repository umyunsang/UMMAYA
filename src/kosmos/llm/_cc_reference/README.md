# `_cc_reference/` — Claude Code 2.1.88 Research-Use Mirror

> **Read-only.** Do not edit these files.
> Constitution §I file-lift policy applies — every file carries an `SPDX-License-Identifier: Apache-2.0 (Anthropic upstream) — research-use mirror` header citing its upstream path inside `.references/claude-code-sourcemap/restored-src/` at version `CC 2.1.88`.
>
> The KOSMOS-original code in `src/kosmos/llm/`, `src/kosmos/ipc/`, `tui/src/query/`, and `tui/src/store/` **adapts** these patterns rather than copying line-for-line. Pattern attribution lives in module headers ("Mirrors `_cc_reference/<file>:<symbol>`").

## Why mirror?

Claude Code is the canonical reference implementation of the agentic-loop + tool-use paradigm KOSMOS migrates to the Korean public-service domain (`docs/vision.md` thesis). Constitution Principle I requires every design decision to trace to a concrete reference; the local mirror lets KOSMOS modules cite line numbers in the cp'd files rather than hauling the full `restored-src/` tree into normal grep paths.

## Contents (13 files · ~18.8 KLOC)

| File | LOC | Upstream path | KOSMOS migration step (Epic #2077) |
|---|---:|---|---|
| `api.ts` | 718 | `src/utils/api.ts` | **Step 2** — `toolToAPISchema()` (line 119-266) drives `tui/src/query/toolSerialization.ts:toolToFunctionSchema()`. **Step 3** — `appendSystemContext()` drives `src/kosmos/llm/system_prompt_builder.py:build_system_prompt_with_tools()`. |
| `tools.ts` | 389 | `src/tools.ts` | **Step 4** — `assembleToolPool()` (line 345-367) and `getAllBaseTools()` drive `tui/src/query/toolSerialization.ts:getToolDefinitionsForFrame()` and the backend's `_ensure_tool_registry().export_core_tools_openai()` fallback. |
| `prompts.ts` | 914 | `src/constants/prompts.ts` | **Step 3** — dynamic system-prompt composition primitives. |
| `claude.ts` | 3419 | `src/services/api/claude.ts` | **Step 5** — `content_block_start` tool_use case (line 1995-2052) drives `tui/src/query/deps.ts` projection. **Step 6** — terminal `AssistantMessage` content-array assembly. Already cp'd in commit `fdfd3e9` for the streaming + thinking channel paint chain. |
| `client.ts` | 389 | `src/services/api/client.ts` | Streaming HTTP client + retry policy. Reference-only for KOSMOS's existing `kosmos.llm.client.LLMClient` (no migration in this epic). |
| `emptyUsage.ts` | 22 | `src/services/api/emptyUsage.ts` | Token-usage zero baseline; reference for OTEL span attribute defaults. |
| `errors.ts` | 1207 | `src/services/api/errors.ts` | Error envelope hierarchy; reference for `kosmos.llm._errors`. |
| `messages.ts` | 5512 | `src/utils/messages.ts` | **Step 5** — `normalizeContentFromAPI()` drives content-block routing in `handleMessageFromStream`. **Step 6** — `ensureToolResultPairing()` (line 1150-1250) drives the tool_use ↔ tool_result invariant in `tui/src/utils/messages.ts`. |
| `query.ts` | 1729 | `src/query.ts` | **Steps 5+6** — multi-turn closure body. Reference for `src/kosmos/ipc/stdio.py` agentic loop + `tui/src/query/deps.ts` stream-event projection. |
| `toolOrchestration.ts` | 188 | `src/services/tools/toolOrchestration.ts` | **Step 5** — `runTools()` async generator pattern (concurrent read / serial write). Reference only; KOSMOS executes tools server-side via `_dispatch_primitive`. |
| `toolExecution.ts` | 1745 | `src/services/tools/toolExecution.ts` | **Step 5** — `runToolUse()` → `ToolResultBlockParam` serialization shape. Reference for the envelope ↔ tool_result content block conversion in `deps.ts`. |
| `toolResultStorage.ts` | 1040 | `src/utils/toolResultStorage.ts` | Token budgeting + `processToolResultBlock()`. **Out of scope** for Epic #2077 (deferred) — referenced for future result-truncation work. |
| `permissions.ts` | 1486 | `src/utils/permissions/permissions.ts` | **Step 7** — full permission gauntlet flow. Reference for `tui/src/store/sessionStore.ts:setPendingPermission()` Promise + queue + timeout. KOSMOS Spec 033 Layer 2/3 receipt issuance is **deferred** (see #2105). |

## How to cite

In a KOSMOS source file's docstring or module header:

```
// Mirrors _cc_reference/api.ts:toolToAPISchema (line 119-266)
// Adapts to KOSMOS by routing through Zod's z.toJSONSchema() (zod/v4 preview)
// instead of CC's hand-curated BetaTool schema.
```

In a Pydantic docstring:

```python
"""Mirrors ``_cc_reference/api.ts:appendSystemContext``.

KOSMOS adaptation: the rendered ``## Available tools`` section is byte-stable
(``json.dumps(parameters, indent=2, sort_keys=True, ensure_ascii=False)``) so
the Spec 026 prompt-hash invariant survives. ``ensure_ascii=False`` keeps
Korean tool descriptions readable.
"""
```

## Reference verification (R-1 from `specs/2077-kexaone-tool-wiring/research.md`)

The single most consequential plan-time verification — `zod/v4`'s built-in `z.toJSONSchema()` emits **Draft 2020-12 natively** without any new runtime dependency:

```typescript
import { z } from 'zod/v4'

const search = z.object({ mode: z.literal('search'), query: z.string().min(1).describe('citizen prompt'), top_k: z.number().int().min(1).max(50).optional() })
const fetch  = z.object({ mode: z.literal('fetch'),  tool_id: z.string().min(1), params: z.record(z.string(), z.unknown()) })
const u = z.discriminatedUnion('mode', [search, fetch])
console.log(JSON.stringify(z.toJSONSchema(u), null, 2))
```

Output:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "anyOf": [
    {
      "type": "object",
      "properties": {
        "mode":  { "type": "string", "const": "search" },
        "query": { "description": "citizen prompt", "type": "string", "minLength": 1 },
        "top_k": { "type": "integer", "minimum": 1, "maximum": 50 }
      },
      "required": ["mode", "query"],
      "additionalProperties": false
    },
    { ... fetch variant ... }
  ]
}
```

This means `tui/src/query/toolSerialization.ts:toolToFunctionSchema()` can call `z.toJSONSchema(tool.inputSchema)` directly and get a spec-compliant JSON Schema parameters block without bringing in `zod-to-json-schema` (which would violate AGENTS.md "no new runtime dep").

Discriminated unions, `.describe()` strings, `.min()` / `.max()` / `.int()` modifiers, and optional fields all survive the conversion intact (verified against the active primitive Zod schemas).

## Index of KOSMOS modules that cite this directory

| KOSMOS module | Cites |
|---|---|
| `tui/src/query/toolSerialization.ts` *(NEW, T005)* | `api.ts:toolToAPISchema` · `tools.ts:assembleToolPool` |
| `src/kosmos/llm/system_prompt_builder.py` *(NEW, T008)* | `api.ts:appendSystemContext` · `prompts.ts` |
| `src/kosmos/ipc/stdio.py` *(M, T010)* | `tools.ts:assembleToolPool` (registry fallback) · `query.ts` (agentic loop) |
| `tui/src/query/deps.ts` *(M, T012)* | `claude.ts:1995-2052` (content_block_start tool_use) · `messages.ts:ensureToolResultPairing` (line 1150-1250) |
| `tui/src/store/sessionStore.ts` *(M, T018)* | `permissions.ts` (full gauntlet flow) |

## Spec links

- Constitution: `.specify/memory/constitution.md` § Principle I
- Plan: `specs/2077-kexaone-tool-wiring/plan.md` § Constitution Check
- Research: `specs/2077-kexaone-tool-wiring/research.md` § R-1 through R-7
- Migration tree: `docs/requirements/kosmos-migration-tree.md` § L1-A.A3 (K-EXAONE native FC) · § L1-B.B6 (composite removed) · § L1-C.C7 (`plugin.<id>.<verb>` reserved)
