# Tool Selection Guidance Deep Research

**Date**: 2026-05-05
**Scope**: Improve how KOSMOS guides the runtime model to select tools without
static keyword routers or hardcoded service maps.

## Canonical KOSMOS constraints

Every design decision here remains inside the KOSMOS thesis:

- `docs/vision.md`: KOSMOS preserves the Claude Code harness shape and swaps only
  the LLM provider plus the Korean public-service tool surface.
- `docs/requirements/kosmos-migration-tree.md`: the five primitives
  (`lookup`, `resolve_location`, `submit`, `verify`, `subscribe`) remain the
  stable citizen-facing surface.
- `.references/claude-code-sourcemap/restored-src/`: Claude Code's ToolSearch
  pattern is the local source of truth for progressive tool disclosure. We use
  it for behavior research only and do not modify it.

## External source digest

| Source | Insight for KOSMOS |
|---|---|
| OpenAI latest model guidance | Put tool-specific guidance in tool descriptions: what/when/required inputs/side effects/retry safety/error modes. Keep stable prompt prefix stable and inject dynamic context late for cache reuse. Large catalogs should use tool search or equivalent deferred loading. |
| OpenAI function calling and tool search docs | Tool calls are a model request to application code; `tool_choice` can force or restrict callable tools. Tool search defers definitions and loads a relevant subset at the end of the context so cache prefixes survive. Client-executed tool search fits tenant/project/runtime-dependent tool catalogs. |
| Anthropic tool search docs | Deferred tools are loaded on demand, BM25 search accepts natural-language queries, and search matches names/descriptions/argument names/argument descriptions. Keep the most frequent tools non-deferred. |
| Anthropic tool definition docs | Detailed tool descriptions are the highest-impact factor: include what the tool does, when to use or avoid it, parameter semantics, and examples. `tool_choice` can force any/specific/no tool, but changing it can affect caching. |
| MCP tools spec and schema | Tool definitions consist of name, description, input schema, optional output schema, and behavior annotations. `ToolAnnotations` cover read-only, destructive, idempotent, and open-world hints, but the spec warns clients not to trust annotations from untrusted servers. |
| MCP Registry | Tool hubs are moving toward app-store style registries with namespace ownership, server validation, API stability windows, and community contribution channels. Registry metadata quality matters as much as search scoring. |
| Pydantic AI Toolsets | Toolsets can be composed, filtered, renamed, overridden per run, and generated dynamically from run context. This validates KOSMOS's runtime registry + per-turn candidate suffix rather than a static prompt table. |
| LangChain / LangGraph tools | Tool descriptions and type hints define model-visible schemas; hidden runtime context stays outside the model schema. `ToolNode` is the controlled execution boundary for parallelism, error handling, and state injection. |
| AnyTool / ToolLLM / API-Bank / ToolSandbox | Large-scale tool use fails on selection, argument construction, state dependency, canonicalization, insufficient information, and trajectory ordering. Evaluation must score the tool trajectory, not only the final answer. |

## Local Claude Code reference

Claude Code's restored `ToolSearchTool` implements three principles KOSMOS should
preserve:

1. **Progressive disclosure**: tools may be deferred and become callable only
   after search loads their full schema.
2. **Name and schema separation**: a deferred tool name is visible before its
   parameters; the model cannot call the tool until the full schema is loaded.
3. **Search is retrieval, not routing**: ToolSearch returns candidates by
   keyword/BM25-like matching. The model still must choose the appropriate tool
   and argument shape from the loaded definition.

KOSMOS cannot literally use Claude Code's ToolSearch tool against Korean
adapters because the K-EXAONE runtime exposes only the five primitive functions.
The correct equivalent is the existing backend-injected `<available_adapters>`
block: a per-turn, end-of-context, registry-derived candidate set with schemas
and policy metadata.

## Failure pattern from the real-use audit

The current real-use audit uncovered the predictable failure mode of large tool
surfaces: the model over-trusts the first retrieved `tool_id`.

- `mock_cbs_disaster_v1` appeared in BM25 results but is a `subscribe` adapter;
  K-EXAONE called it through `lookup` before `[primitive=subscribe]` was exposed.
- Privileged Hometax/Gov24 lookup candidates surfaced correctly, but the model
  needed a backend-enforced first `verify` when `citizen_facing_gate != read-only`.
- Location queries sometimes ended after `resolve_location`, even though the
  user asked for observable data that required a follow-up `lookup`.

These are not keyword-router problems. They are candidate-card completeness and
trajectory enforcement problems.

## Decision update

KOSMOS keeps the current dynamic selection architecture:

1. Use registry retrieval to inject a small `<available_adapters>` candidate
   set near the end of the context.
2. Keep `lookup(mode="search")` internal. The model only selects from the
   injected candidates and calls one of the five primitives.
3. Keep backend policy enforcement. If the top policy-positive candidate has a
   non-read-only `citizen_facing_gate`, the first callable primitive is forced to
   `verify`; prompt guidance is not trusted as the only control.
4. Treat BM25/dense rank as a shortlist, not a route. The model must choose the
   highest-ranked candidate whose primitive, gate, and schema match the citizen
   intent. If top-1 is the wrong primitive family, use the next matching
   candidate; if none match, ask one narrow clarification or state that the
   current registered tools cannot complete the request.

## Candidate card contract

Each candidate shown to the model should carry enough information to decide and
execute in one shot:

- `tool_id`
- retrieval score and short `search_hint`
- `primitive`
- `citizen_facing_gate`
- `delegation_source_tool_id` when a verify context is required
- `adapter_mode` (`live` or `mock`) when available
- agency policy citation URL when available
- concise `llm_description`
- exact input schema field names, required flags, types, patterns, enums, and
  field descriptions
- retry/idempotency guidance: do not repeat the same `tool_id + params` after
  no-data, empty, error, or repeat-blocked results

This mirrors OpenAI and Anthropic guidance that tool-specific usage guidance
belongs in the tool definition/card, while cross-tool operating policy stays in
the system prompt.

## Implementation status

Implemented in this pass:

- `AdapterCandidate.adapter_mode` now carries `GovAPITool.adapter_mode` through
  the search result model.
- `search.py` populates `adapter_mode` alongside `primitive`,
  `citizen_facing_gate`, `delegation_source_tool_id`, and
  `real_classification_url`.
- `discovery_bridge.py` marks bridged verify/submit/subscribe mock adapters as
  `adapter_mode="mock"` so the candidate card does not mislabel mock tools as
  live.
- `stdio.py` renders `[mode=...]` and `[policy_url=...]` in each
  `<available_adapters>` candidate line, and tells the model to treat retrieval
  rank as a shortlist rather than a route.

## Evaluation gates

Future prompt or suffix changes should score these axes against
`eval/scenarios/national_ax_citizen_requests_v1.yaml` plus real-use captures:

- `candidate_recall@5`: expected adapter appears in `<available_adapters>`.
- `primitive_precision@1`: first tool call uses the correct primitive family.
- `policy_first_action`: privileged candidates call `verify` before personal
  lookup/submit/subscribe.
- `schema_validity`: params use only visible schema fields and pass Pydantic
  validation.
- `trajectory_order`: required chains happen in order, e.g.
  `resolve_location -> lookup` for observable location data.
- `repeat_suppression`: no identical second call after no-data/error/empty.
- `unsupported_behavior`: no static-router fallback, no invented adapter, no
  direct site handoff before the tool chain has failed.

## Sources

- https://developers.openai.com/api/docs/guides/latest-model#using-reasoning-models
- https://developers.openai.com/api/docs/guides/function-calling#how-it-works
- https://developers.openai.com/api/docs/guides/function-calling#tool-choice
- https://developers.openai.com/api/docs/guides/tools-tool-search
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-combinations
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- https://modelcontextprotocol.io/specification/2025-06-18/schema
- https://github.com/modelcontextprotocol/registry
- https://pydantic.dev/docs/ai/tools-toolsets/toolsets/
- https://docs.langchain.com/oss/python/langchain/tools
- https://arxiv.org/abs/2402.04253
- https://arxiv.org/abs/2307.16789
- https://arxiv.org/abs/2304.08244
- https://aclanthology.org/2025.findings-naacl.65/
