# TUI Raw JSON Tool-Call Recovery Research Note

Date: 2026-06-17

## Local Anchors

- `docs/vision.md`: UMMAYA preserves the Claude Code tool loop and swaps only the model provider and Korean public-service tool surface.
- `docs/requirements/ummaya-migration-tree.md`: L1-A requires FriendliAI + K-EXAONE with native function calling; L1-B requires registered public-service adapters; L1-C exposes `find`, `locate`, `send`, `check`, and `document`.
- `.references/claude-code-sourcemap/restored-src/src/query.ts`: Claude Code treats `tool_use` blocks as the loop-exit signal because stop reasons can be unreliable; tool execution must follow structured `tool_use`, not visible prose.
- `tui/src/services/api/ummaya/streaming.ts`: Friendli/OpenAI-compatible SSE parser boundary.
- `tui/src/query/run.ts`: local query loop boundary that yields assistant messages and dispatches `tool_use` blocks.

## 2026-Current Sources

- OpenAI Function Calling docs: tool calls are a structured response type over JSON-schema-defined tools; strict mode can reject incompatible schemas or fall back to best-effort in non-strict modes. Source: <https://developers.openai.com/api/docs/guides/function-calling>
- FriendliAI Tool Calling docs: Friendli follows OpenAI-compatible tool calling, returning `choices[].message.tool_calls[]` with `function.name` and JSON-stringified `function.arguments`. Source: <https://friendli.ai/docs/guides/tool-calling>
- Model Context Protocol tools spec: tools are uniquely identified by name and include schema metadata; UIs should clearly show exposed and invoked tools and keep human-in-the-loop approval for operations. Source: <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- Pydantic AI tool docs: tool arguments should be validated before execution/approval; validation failures become retry prompts back to the model. Source: <https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/>
- vLLM tool calling docs: open-source serving stacks use parser-boundary adapters for models that emit JSON-like tool-call formats, including Hermes/xLAM-style parsers, rather than renderer-side redaction. Source: <https://docs.vllm.ai/en/latest/features/tool_calling/>
- Berkeley Function Calling Leaderboard V4: current tool-call evaluation separates native function calling from prompt-format workarounds and includes format-sensitivity/multi-turn agentic evaluation. Source: <https://gorilla.cs.berkeley.edu/leaderboard.html>
- ToolSandbox and tau-bench: recent agent benchmarks emphasize stateful, multi-step tool execution and intermediate milestones, so a final visible text check is insufficient evidence. Sources: <https://arxiv.org/abs/2408.04682>, <https://arxiv.org/abs/2406.12045>

## Candidate Scorecard

| Candidate | Correctness | Security | CC parity | Maintenance | Selected |
|---|---:|---:|---:|---:|---|
| Renderer-only hiding of raw JSON | 1 | 2 | 1 | 2 | No |
| Prompt-only instruction to emit tool calls | 2 | 2 | 2 | 3 | No |
| Provider/query exact JSON proposal promotion plus fail-closed unknown-tool result | 5 | 4 | 5 | 4 | Yes |
| New generic parser dependency | 4 | 3 | 3 | 2 | No |

## Selected Approach

Promote only exact raw JSON tool-call proposals at the provider/query boundary:

- Accept only a top-level JSON object with exactly `name` and `arguments`.
- Require `arguments` to be an object or JSON object string.
- Convert the proposal to a normal `tool_use` block before rendering or dispatch.
- Preserve the existing dispatch gate: registered tools execute through the normal permission, schema validation, and adapter dispatch path; unregistered tools become a structured fail-closed `tool_unavailable` tool_result, not visible prose and not execution.
- Leave any non-exact object, extra-key payload, malformed JSON, or prompt-carrying wrapper as text so prompt-injection-like content cannot silently enter the tool loop.
- Add a domain-neutral terminal repair guard: after a structured `tool_unavailable` result, the model may recover only by calling a different registered tool; otherwise the loop closes with a generic blocked answer instead of trusting unsupported final prose.

## Rejected Approaches

- Renderer suppression: would hide the symptom while the query loop still terminates without tool execution.
- Prompt-only repair: current benchmarks and the observed transcript show format adherence is not reliable enough for a release gate.
- New parser package: vLLM/Hermes patterns validate the parser-boundary idea, but a dependency would be too broad for this narrow OpenAI-compatible `{name, arguments}` failure and would need a larger ADR.

## Tests And Evidence

- RED/GREEN provider test: exact raw JSON `emergency_facilities_search` text becomes `tool_use`, not `content_block_delta`, so the loop can fail closed through the tool boundary instead of painting JSON.
- RED/GREEN query-loop test: unregistered exact raw JSON becomes a structured unavailable tool_result, then unsupported final prose is rejected before rendering.
- Adversarial provider test: non-exact prompt-carrying raw JSON remains text and never becomes `tool_use`.
- Provider surface test: named-campus night ER requests expose location plus NMC/HIRA emergency adapter schemas before model generation.

## Addendum: Follow-Up Location Context And Reasoning Painting

Date: 2026-06-17

Trigger transcript:

- First user turn resolved `다대1동 지금 날씨알려줘` through `kakao_address_search` and KMA weather.
- Follow-up user turn asked `주위에 지금 바로 갈수있는 응급실 알려줘`.
- The provider emitted raw JSON text for an unregistered `find_hospital_by_location_rdd_da` function instead of calling a registered emergency adapter.

Updated source mapping:

- FriendliAI reasoning docs, last modified 2026-06-16, define `chat_template_kwargs.enable_thinking`, `parse_reasoning`, `include_reasoning`, and streamed `delta.reasoning_content`. Source: <https://friendli.ai/docs/guides/reasoning>
- FriendliAI tool-calling docs, last modified 2026-06-16, define OpenAI-compatible `tools`, named `tool_choice`, and `choices[].message.tool_calls[]`. Source: <https://friendli.ai/docs/guides/tool-calling>
- FriendliAI structured-output docs warn that provider schema support is constrained, which supports normalizing provider request schemas before generation. Source: <https://friendli.ai/docs/guides/structured-outputs>
- vLLM reasoning/tool-calling docs keep model-specific parsers at the serving/provider boundary, which matches UMMAYA's provider parser location rather than a render-only suppression. Sources: <https://docs.vllm.ai/en/latest/features/reasoning_outputs/> and <https://docs.vllm.ai/en/latest/features/tool_calling/>
- ToolSandbox and tau-bench emphasize stateful, multi-step tool-agent interaction; the regression test therefore preserves prior successful location evidence when selecting tools for a relative follow-up turn.

Selected correction:

- Tool selection now appends prior successful location evidence only to provider tool-selection text for relative health follow-ups. The persisted transcript is unchanged.
- The canonical emergency surface remains registered adapter schemas (`nmc_emergency_search`, `hira_hospital_search`); unknown raw JSON tool names are promoted only into the fail-closed `tool_unavailable` boundary and are not executed.
- Deep/diagnostic reasoning mode now sends FriendliAI reasoning parser fields and maps streamed `delta.reasoning_content` into CC-style `thinking_delta` events before `tool_use`.
- The provider stream parser stays responsible for raw JSON upgrade and reasoning painting; the TUI renderer receives normal CC-shaped blocks.

## Addendum: Static Route And Domain Hardcoding Removal

Date: 2026-06-17

Trigger transcript:

- The TUI answered a route query from only two `kakao_keyword_search` location
  results and invented transfer stations, bus numbers, fares, and travel time.
- Earlier repair attempts risked becoming domain-specific hotfixes because the
  failure was visible in concrete prompts such as emergency, weather, and
  transit. The root failure is broader: the loop treated a final assistant text
  answer as trustworthy even when the only successful evidence class was
  location lookup.

2026-current source mapping:

- FriendliAI Tool Calling documents an OpenAI-compatible tool contract with
  schema-aligned tool calls. Applicability: UMMAYA must keep real work inside
  structured `tool_use` and adapter schemas, not render-side prose repair.
  Source: <https://friendli.ai/docs/guides/tool-calling>
- vLLM Tool Calling documents that named function calls can be validly parsed
  while call quality remains a separate problem. Applicability: UMMAYA needs
  deterministic post-tool evidence gates because provider parsability does not
  imply the selected tool result supports the final claim. Source:
  <https://docs.vllm.ai/en/latest/features/tool_calling/>
- MCP Tools specification treats tools as named schema-bearing capabilities with
  metadata. Applicability: UMMAYA should reason from exposed tool capability and
  returned result class, not static service keyword tables. Source:
  <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- BFCL V4 evaluates function calling with real-world, multi-domain, executable
  calls. Applicability: the correction must be tested by execution relevance
  and multi-turn behavior, not by final-answer string snapshots alone. Source:
  <https://gorilla.cs.berkeley.edu/leaderboard.html>
- The BFCL PMLR paper frames function-calling evaluation around serial and
  parallel calls plus executable correctness. Applicability: repeated successful
  calls to the same effective tool need a loop-level guard and final answers
  need evidence adequacy checks. Source:
  <https://proceedings.mlr.press/v267/patil25a.html>
- vLLM upstream issue reports parser-level success can still fail in
  OpenAI-compatible post-processing for multi-tool calls. Applicability:
  compatibility boundaries must be tested at provider/query boundaries and
  through the rendered TUI path. Source:
  <https://github.com/vllm-project/vllm/issues/32638>

Scorecard:

| Candidate | Correctness | Anti-hardcoding | CC/tool-loop fit | UX safety | Selected |
|---|---:|---:|---:|---:|---|
| Prompt-only instruction to avoid unsupported routes | 2 | 3 | 2 | 2 | No |
| Domain keyword denylist for 부산/해운대/응급실/weather cases | 2 | 1 | 1 | 2 | No |
| Per-adapter special guard files for KMA/Kakao/NMC/TAGO | 3 | 1 | 2 | 3 | No |
| Evidence-class terminal boundary: location-only evidence cannot justify route detail claims | 4 | 4 | 4 | 5 | Yes |
| Add a new routing/transit dependency now | 4 | 5 | 3 | 3 | No, requires separate ADR/credential gate |

Selected correction:

- Remove static public-service guard files and service-specific repair branches
  from the TUI production path.
- Select adapters by registered metadata and useful discovery fields, not by
  domain-specific final routing tables.
- Treat repeated successful calls to the same effective tool as a query-loop
  concern, independent of adapter name.
- Add a generic evidence adequacy boundary: if the user asks for routing or
  realtime transit and the successful `tool_result` evidence only located
  places, final text must not contain route details such as transfer stations,
  bus numbers, fares, or travel times.
- The boundary is intentionally not a route solver. It fails closed and points
  the citizen to official map/transit channels until a real route/transit
  adapter exists and returns route-class evidence.

Rejected approaches:

- A weather/emergency/transit phrase table would reproduce the hardcoding
  problem and would not scale to new adapters.
- Renderer-only suppression would hide the bad text while still letting the
  query loop accept unsupported claims.
- Adding a map/transit dependency here would be a new integration, not a
  verification cleanup; it needs endpoint, credential, policy, license, and
  release-gate evidence.

Tests and evidence:

- RED/GREEN test now asserts that unsupported route details are blocked without
  sending another prompt-only repair turn.
- Focused TUI query tests cover raw JSON tool-call upgrade, repeated tool-call
  blocking, adapter selection, public-data terminal guard, and follow-up
  emergency location context.
- Live TUI evidence must confirm the rendered surface shows intermediate
  reasoning/progress, tool calls, tool results, and a grounded final or blocked
  answer without static route details.

## Addendum: Current-Turn Evidence Boundary For Stale Tool Results

Date: 2026-06-18

Trigger transcript:

- In one TUI session, the user first asked for `다대1동` weather and then nearby
  emergency rooms. The emergency turn returned `큐병원` from an
  `nmc_emergency_search` tool result.
- A later fresh prompt asked `부산역 근처 야간에 바로 갈 수 있는 병원 알려줘`.
  The loop resolved `부산역`, called a current-turn hospital adapter, but the
  final answer also reused the prior `큐병원` emergency result as if it were
  current 부산역 evidence.

2026-current source mapping:

- FriendliAI Tool Calling keeps the provider contract OpenAI-compatible and
  schema-driven. Applicability: stale-state prevention must happen around
  structured tool boundaries, not by matching a concrete hospital or station
  name. Source: <https://friendli.ai/docs/guides/tool-calling>
- vLLM Tool Calling warns that validly parsable function calls are not a
  guarantee of high-quality tool choice. Applicability: UMMAYA needs a
  deterministic post-tool evidence adequacy gate for the final answer. Source:
  <https://docs.vllm.ai/en/latest/features/tool_calling/>
- OpenAI Function Calling defines tool-call outputs as responses tied to a
  specific model tool call. Applicability: final-answer evidence should be
  tied to the current tool-call/result sequence, not any earlier transcript
  result that happens to be visible in context. Source:
  <https://developers.openai.com/api/docs/guides/function-calling>
- Anthropic tool-use docs require client tool results to immediately follow the
  matching `tool_use`, and tool results are untrusted external content.
  Applicability: UMMAYA keeps CC-shaped `tool_use`/`tool_result` pairing and
  treats prior result content as evidence with scope, not as evergreen memory.
  Source:
  <https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls>
- Anthropic Manage Tool Context recommends context editing once old
  `tool_result` blocks are no longer relevant. Applicability: for UMMAYA's
  local loop, a lighter-weight current-turn boundary is safer than deleting
  durable transcript history. Source:
  <https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context>
- MCP Tools identifies tools by name and schema metadata. Applicability:
  evidence adequacy is checked from returned tool-result blocks and registered
  tool boundaries, not from static route or hospital keyword tables. Source:
  <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- BFCL/PMLR and BFCL V4 emphasize stateful, multi-step agentic evaluation and
  show memory/dynamic decision-making remain open challenges. Applicability:
  release proof must include multi-turn real-use transcripts and stale-result
  adversarial tests, not only single-turn parser tests. Sources:
  <https://proceedings.mlr.press/v267/patil25a.html> and
  <https://gorilla.cs.berkeley.edu/leaderboard.html>
- The 2026 MCP tool-description empirical paper reports that tool metadata and
  descriptions are central to correct tool selection, while extra context can
  increase execution steps. Applicability: the fix should be a compact
  evidence-boundary guard, not another prompt blob or hardcoded route table.
  Source: <https://arxiv.org/html/2602.14878v1>

Scorecard:

| Candidate | Correctness | Anti-hardcoding | CC/tool-loop fit | Context safety | Selected |
|---|---:|---:|---:|---:|---|
| Hardcode the 부산역/큐병원 transcript as a blocked pattern | 2 | 1 | 1 | 2 | No |
| Prompt-only instruction to avoid stale prior results | 2 | 4 | 2 | 2 | No |
| Delete all previous tool results before every new prompt | 3 | 4 | 2 | 5 | No |
| Current-turn evidence boundary that blocks prior-only tool-result claims unless the user explicitly asks to reuse prior results | 5 | 5 | 4 | 5 | Yes |
| Add a new hospital-routing aggregator dependency now | 4 | 5 | 3 | 3 | No, separate integration gate |

Selected correction:

- Keep transcript history intact for CC parity and auditability.
- At final-answer time, compare candidate text against salient phrases present
  only in successful tool results before the latest citizen prompt.
- Allow reuse when the latest citizen prompt explicitly asks for prior/previous
  results; otherwise block a final answer that cites prior-only result phrases
  while current-turn tool results exist.
- The boundary is generic over tool-result content. It does not name 부산역,
  다대1동, 큐병원, NMC, HIRA, Kakao, or any agency-specific table.
- When blocked, finish with a Korean explanation that the answer cannot reuse
  earlier tool evidence as current evidence and that a fresh matching adapter
  result is required.

Rejected approaches:

- Entity-specific denylist or Korean prompt table would recreate the static
  hardcoding problem.
- Removing old transcript results would damage session auditability and CC
  parity; context editing is a future optimization, not this regression fix.
- Adding another live healthcare dependency would expand scope beyond the
  pre-release query-loop verification objective.

Tests and evidence:

- Add a RED/GREEN query-loop test that simulates a prior emergency result,
  then a fresh 부산역 night-hospital prompt whose final answer cites a
  prior-only hospital name. The expected behavior is a blocked Korean answer,
  not stale result reuse.
- Rerun the exact C003 tmux session after the fix. PASS requires no raw JSON
  prose, visible reasoning/progress/tool boundaries, and no prior-only
  emergency result claim in the 부산역 answer.

## Addendum: Provider Tool Surface Boundary For Citizen Turns

Date: 2026-06-18

Trigger:

- The C003 rerun no longer leaked raw textual tool-call JSON, but an ordinary
  lifestyle weather prompt selected workspace tools before calling a weather
  adapter. Route diagnostics showed an empty adapter projection for that turn,
  while the provider surface still exposed non-adapter base tools.

Updated research anchors:

- FriendliAI's OpenAI-compatible tool calling frames the application as the
  owner of the tool list supplied to each model request. Source:
  <https://friendli.ai/docs/guides/tool-calling>
- OpenAI's function-calling flow likewise begins with the application sending
  the tools the model could call. Source:
  <https://developers.openai.com/api/docs/guides/function-calling>
- MCP Tools identifies each tool by name plus schema metadata; a client should
  expose the relevant tool surface, not a broad ambient capability set. Source:
  <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- BFCL V4 evaluates tool selection in stateful agentic settings, reinforcing
  that multi-turn release proof must include real tool-surface behavior rather
  than only parser-level tests. Source:
  <https://gorilla.cs.berkeley.edu/leaderboard.html>
- The 2026 MCP tool-description study reports that tool descriptions and
  surrounding context materially affect tool choice, while extra context can
  inflate execution steps. Source: <https://arxiv.org/html/2602.14878v1>

Scorecard:

| Candidate | Correctness | Anti-hardcoding | CC/tool-loop fit | Release risk | Selected |
|---|---:|---:|---:|---:|---|
| Prompt-only instruction: "do not use workspace tools for weather" | 2 | 3 | 2 | 2 | No |
| Hardcode the exact failed weather prompt as a special case | 1 | 1 | 1 | 1 | No |
| Always expose all base tools and rely on repeated-tool guards | 1 | 4 | 2 | 1 | No |
| Expose zero ambient base tools in main citizen turns; recover support tools only from explicit support intent; force a requested base tool only when the loop has already selected it | 5 | 5 | 5 | 4 | Yes |
| Move all route selection to a new external router dependency now | 4 | 5 | 3 | 2 | No |

Selected correction:

- Main-thread citizen requests start with an empty provider tool surface.
- Concrete public-service adapters are added only through the registered
  adapter manifest projection.
- Workspace/support tools are recovered only from explicit support-tool intent,
  preserving Claude Code-style support behavior without leaking it into normal
  citizen-service turns.
- Forced tool choice may still add an adapter or support tool, because that is
  already an explicit query-loop decision rather than ambient exposure.
- The provider-side adapter preselector now mirrors the local Python routing
  policy at the intent-family level: lifestyle weather, emergency medical,
  Gov24 read/action, welfare, utilities, civil death, and handoff domains.
- Relative-location follow-up prompts may receive compact prior location
  context, but prior non-location tool results remain unavailable as current
  evidence.

Rejected approaches:

- Prompt-only fixes leave the same workspace tool schemas visible to the
  model.
- Per-prompt deny lists repeat the static-hardcoding failure mode.
- Keeping all base tools in the provider request makes the repeated-tool guard
  a late symptom filter instead of fixing the model's available action space.
- A new router dependency would expand the release gate without proving the
  current architecture.

Follow-up corrections from C003 rerun:

- The first follow-up-location test used a direct `result` wrapper, but the
  real concrete adapter path returns a dispatch envelope under `data.result`.
  The extractor now unwraps both shapes before building compact prior-location
  context. This is a schema-boundary fix, not a prompt workaround.
- Located hospital and night-care requests are now treated as a healthcare
  intent family even when the Korean text does not include the exact emergency
  word. This prevents weather or air-quality neighbors from entering the
  provider surface merely because their descriptions mention health-adjacent
  words.
- The correction remains family-level and manifest-shaped: it classifies
  healthcare/location/forecast/utility/welfare families, then lets the
  registered concrete adapters supply the exact executable tool schema.
