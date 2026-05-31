# Tool Schema Loop Deep Reference Digest - 2026-05-27

## Scope

This digest upgrades the reference-first gate for the current real-use validation work. The immediate live failure is:

- Ordinary citizen query: "부산역 근처에 사람이 쓰러졌어. 지금 어디로 가야 해?"
- Deterministic adapter context now surfaces emergency room, AED, and location adapters.
- Live `bun run tui` still loops on malformed primitive calls such as `locate(kakao_keyword_search)` with missing `tool_id`/`params` or missing adapter `query`.

The next implementation step must therefore treat the problem as a model-facing schema surface and loop-recovery issue, not as a static routing problem.

## Local Canonical Sources

- `docs/vision.md`: UMMAYA thesis is Claude Code harness plus K-EXAONE/FriendliAI plus Korean public-service tool surface.
- `docs/onboarding/codex-continuation.md`: requires Evidence Fabric v2 and interactive TUI proof for query-loop/tool-call rendering changes.
- `.references/claude-code-sourcemap/restored-src/src/query.ts`: restored Claude Code query-loop source for tool-use and tool-result sequencing.
- `.references/claude-code-sourcemap/restored-src/src/Tool.ts`: restored Claude Code tool abstraction and model-facing schema boundary.
- `prompts/system_v1.md` and `prompts/session_guidance_v1.md`: current primitive envelope guidance.
- `tui/src/tools/_shared/rootPrimitiveInput.ts`, `tui/src/tools/LookupPrimitive/LookupPrimitive.ts`, `tui/src/tools/ResolveLocationPrimitive/ResolveLocationPrimitive.ts`: current TUI primitive schema surface.
- `src/ummaya/ipc/stdio.py`, `src/ummaya/engine/engine.py`, `src/ummaya/tools/search.py`: backend adapter context, dispatch, and retrieval behavior.

## Official Contract Sources

- OpenAI function calling docs: https://developers.openai.com/api/docs/guides/function-calling
  - Insight: tool calls should be constrained by the supplied function schema; strict mode requires `additionalProperties: false` and all fields represented in `required` with nullable types for optional values. Applicability: when a concrete UMMAYA adapter is supplied as a function, the model must call that concrete function with adapter schema fields only, not a nested `{tool_id, params}` wrapper.
- Anthropic/Claude tool definition docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
  - Insight: each tool definition has a name, detailed description, and an `input_schema`; the model emits an input object conforming to that schema. Applicability: UMMAYA's concrete adapter tool names and root primitive wrapper names must not be taught as the same callable surface in the same turn.
- Model Context Protocol tools spec, 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
  - Insight: a tool definition includes unique `name`, human description, `inputSchema`, optional `outputSchema`, and annotations. Applicability: a concrete adapter exposed in tools[] is a callable tool, while root primitives remain compatibility wrappers only when no concrete adapter function is loaded.

## Production and Open-Source Sources

- Restored Claude Code source under `.references/claude-code-sourcemap/restored-src/`.
  - Insight: UMMAYA should preserve CC's tool-use and tool-result loop semantics before UMMAYA-specific public-service swaps.
- LangGraph `ToolNode`: https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/tool_node.py
  - Insight: mature agent runtimes centralize tool execution, validation errors, injected/system arguments, and error handling at the tool-node boundary rather than scattering per-tool recovery branches. Applicability: UMMAYA should return a recoverable, schema-specific tool result and avoid hardcoded adapter fallbacks.

## Recent Research and Benchmarks

- IFEval-FC, "Instruction-Following Evaluation in Function Calling for Large Language Models" (submitted 2025-09-22): https://arxiv.org/abs/2509.18420
  - Insight: even frontier models can fail fine-grained parameter-format instructions embedded in tool schemas. Applicability: tests must verify actual tool-call arguments, not just final answers or candidate rankings.
- ToolSandbox, "A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities" (v2 2025-04-16): https://arxiv.org/abs/2408.04682
  - Insight: state dependency, canonicalization, and insufficient-information cases remain hard in multi-step tool use. Applicability: emergency-room flow needs stateful validation from locate result to downstream region/coordinate calls.
- MetaTool, ICLR 2024: https://proceedings.iclr.cc/paper_files/paper/2024/hash/bc12914d66b41b6bfc2d3a5decdb498b-Abstract-Conference.html
  - Insight: correct tool-use awareness and tool selection remain separate from parameter correctness. Applicability: deterministic retrieval green does not prove live TUI tool execution is green.

## Ecosystem and Hub Signals

- LangChain issue on invalid tool calls and retry feedback: https://github.com/langchain-ai/langchain/issues/33504
  - Signal only: malformed tool calls need feedback that keeps the agent loop alive. This is not a design authority, but it matches the observed live failure mode where the model sees repeated validation errors without a successful canonical retry.

## Applicability Map

| Evidence | Adopt | Reject | Affected work |
|---|---|---|---|
| CC restored query/tool loop | Preserve tool-result sequencing and export concrete adapter Tool objects in the same loop shape | Do not create TUI-only fallback routes | `tui/src/query.ts`, primitive tools, `src/ummaya/ipc/stdio.py` |
| OpenAI/Claude/MCP schema docs | Make callable schema exact and unambiguous; concrete adapter functions receive adapter fields, root wrappers receive `{tool_id, params}` | Do not rely on examples that contradict the actual callable schema | `rootPrimitiveInput.ts`, primitive prompts, adapter manifest sync |
| LangGraph ToolNode | Centralize validation/error feedback at dispatch boundary | Do not add per-adapter hardcoded retry code | backend primitive dispatch and tests |
| IFEval-FC | Add argument-level regression tests | Do not treat final answer or candidate rank as enough | tests for root primitive envelopes and live-like tool call recovery |
| ToolSandbox | Test multi-step state transfer from locate to downstream tool | Do not stop at a one-turn static matrix | emergency/AED real-use scenarios |
| MetaTool | Keep separate tests for no-tool, wrong-tool, right-tool-wrong-args | Do not conflate retrieval green with execution green | deterministic matrix plus TUI proof |

## Current Decision Constraints

- Candidate retrieval fixes may remain only if they broaden natural-language recall while still selecting registered adapters.
- The next root-cause fix must inspect the actual TUI model-facing concrete adapter schema, legacy root wrapper schema, and backend validation path.
- A successful claim requires both static gates and an ordinary-language live TUI run showing bounded recovery or successful downstream emergency/AED flow.
