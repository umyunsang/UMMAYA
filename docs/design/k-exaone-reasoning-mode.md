# K-EXAONE Reasoning Mode Design

Date: 2026-05-26

## Scope

This design migrates Claude Code-style thinking/progress painting into UMMAYA
without changing permission modes. Permission mode state, Shift+Tab behavior,
and permission UI remain separate. The new axis is a K-EXAONE/FriendliAI
reasoning policy that controls provider payload, live rendering, session
settings, and verification.

The target user experience is:

1. The user asks a normal citizen question.
2. The query loop paints progress while it analyzes the request, chooses tools,
   waits for tool results, and synthesizes the answer.
3. When K-EXAONE reasoning is explicitly enabled, streamed provider
   `reasoning_content` appears in the same live progress surface.
4. Final answers remain concise user-facing prose and do not leak raw reasoning.

## Reference Inputs

### Local UMMAYA Sources

- `docs/vision.md`: UMMAYA is the Claude Code harness with two sanctioned swaps:
  K-EXAONE on FriendliAI and Korean public-service tools.
- `docs/requirements/ummaya-migration-tree.md`: L1-A requires the CC agent loop
  and native K-EXAONE function calling; L1-B/C keep the tool surface concrete
  and model-facing.
- `.references/claude-code-sourcemap/restored-src/`: CC source remains the
  reference for query loop ordering, stream event shape, and TUI rendering.
- `tui/src/services/api/client.ts`: current direct Friendli path converts
  `reasoning_content` to `thinking_delta`, but payload policy is still
  effectively `UMMAYA_K_EXAONE_THINKING` -> `chat_template_kwargs.enable_thinking`.
- `src/ummaya/llm/client.py`: backend path has the same basic conversion and
  explicitly logs reasoning length only.
- `docs/configuration.md`: current production default is
  `UMMAYA_K_EXAONE_THINKING=false`, which conflicts with the model-card default
  and must be resolved by an explicit UMMAYA policy layer rather than scattered
  booleans.

### 2026 External Sources

- FriendliAI's reasoning guide documents model-agnostic reasoning parsing and
  recommends explicit `parse_reasoning` / `include_reasoning` because endpoint
  defaults can vary. With parsing enabled and inclusion enabled, reasoning moves
  into `choices[].message.reasoning_content`.
  Source: https://friendli.ai/docs/guides/reasoning
- FriendliAI's Chat Completions schema includes `reasoning_effort`,
  `reasoning_budget`, `parse_reasoning`, `include_reasoning`, streaming, tool
  choice, and `parallel_tool_calls`.
  Source: https://friendli.ai/docs/openapi/container/chat-completions
- The official K-EXAONE model card says K-EXAONE defaults to
  `enable_thinking=True`, non-reasoning mode uses `enable_thinking=False`, and
  the vLLM serving recipe combines `--reasoning-parser deepseek_v3`,
  `--enable-auto-tool-choice`, and `--tool-call-parser hermes`.
  Source: https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B-FP8
- vLLM's latest reasoning output documentation treats reasoning extraction and
  thinking token budgets as first-class serving concerns. It exposes
  `--reasoning-parser`, `--reasoning-config`, and request-level
  `thinking_token_budget`.
  Source: https://docs.vllm.ai/en/v0.21.0/features/reasoning_outputs/
- vLLM issue #42021, opened 2026-05-08, reports a real parser/tool-call
  collision where `enable_thinking=true` caused non-standard tool-call output
  for Qwen3.5 while `enable_thinking=false` returned proper `tool_calls`. This
  does not prove the same bug exists for K-EXAONE, but it is enough to require
  explicit UMMAYA verification before making thinking mode the default tool-use
  path.
  Source: https://github.com/vllm-project/vllm/issues/42021
- "Adaptive Test-Time Compute Allocation for Reasoning LLMs" (2026-04-16)
  frames reasoning as a budgeted allocation problem: easy inputs should be
  answered cheaply and hard inputs can receive more compute.
  Source: https://arxiv.org/abs/2604.14853
- "Avoiding Overthinking and Underthinking" (2026-03/04) proposes
  budget-conditioned reasoning to balance quality and token efficiency.
  Source: https://arxiv.org/abs/2604.19780
- "AgentTrace" (AAAI 2026 Workshop LaMAS) argues for structured observability
  across operational, cognitive, and contextual surfaces.
  Source: https://arxiv.org/abs/2602.10133
- "Safer Reasoning Traces" (2026-03-05) shows that chain-of-thought can
  resurface PII, so raw reasoning must not be persisted or exported casually.
  Source: https://arxiv.org/abs/2603.05618
- OpenTelemetry GenAI semantic conventions define model-call and tool-execution
  spans, and explicitly warn that tool arguments/results may contain sensitive
  data.
  Source: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- Langfuse's current SDKs are OpenTelemetry-based, which makes it a compatible
  optional sink later, but UMMAYA should not add it as a P0 dependency.
  Source: https://langfuse.com/docs/observability/sdk/overview
- "Optimizing Agentic Workflows using Meta-tools" (2026-01/02) shows that
  traces can later identify redundant tool sequences and compress them into
  deterministic meta-tools. This is useful later, but not part of this reasoning
  mode migration.
  Source: https://arxiv.org/abs/2601.22037

## Design Decision

Create a dedicated `ReasoningMode` axis instead of overloading permission mode
or Claude Code `/effort`.

```ts
type ReasoningMode =
  | 'fast'
  | 'balanced'
  | 'deep'
  | 'diagnostic'
  | 'auto'
```

`/effort` remains the CC-compatible model-effort command. `/reasoning` becomes
the UMMAYA/K-EXAONE provider policy command. Existing thinking UI is migrated
from a boolean toggle to the same policy.

## Mode Semantics

| Mode | Provider intent | Payload policy | UI behavior | Persistence |
|---|---|---|---|---|
| `fast` | Latency-first citizen answer | `enable_thinking=false`, `parse_reasoning=true`, `include_reasoning=false` | deterministic query-loop progress only | no raw reasoning |
| `balanced` | Default production UX | same as `fast` for P0 | deterministic query-loop progress only | no raw reasoning |
| `deep` | Explicit high-accuracy reasoning | `enable_thinking=true`, `parse_reasoning=true`, `include_reasoning=true` | query-loop progress plus live provider thinking when present | no raw reasoning by default |
| `diagnostic` | Local debug / benchmark | same as `deep`; optional diagnostic capture gated by env | full live thinking/progress surface | local opt-in only, redacted/length-only logs |
| `auto` | Future adaptive compute | P0 maps to `balanced`; later route by cheap classifier and task risk | same as selected runtime mode | same as selected runtime mode |

Do not send `reasoning_effort`, `reasoning_budget`, or a vLLM
`thinking_token_budget` in P0 unless direct Friendli/K-EXAONE curl evidence
proves the currently deployed endpoint accepts and honors the field. The policy
object may reserve nullable fields for them, but payload emission must be behind
verified capability detection.

## Resolution Order

All provider payload generation must call one resolver:

```ts
resolveKExaoneReasoningPolicy({
  explicitSessionMode,
  userSettingsMode,
  cliMode,
  envMode,
  legacyThinkingEnv,
  modelId,
  endpointCapabilities,
})
```

Recommended precedence:

1. `UMMAYA_K_EXAONE_REASONING_MODE`: hard process override for CI and
   diagnostics; slash commands warn when this is active.
2. Session command `/reasoning ...`: current session value.
3. User settings: persisted default.
4. Legacy `UMMAYA_K_EXAONE_THINKING`: boot-time compatibility mapping only
   (`true -> deep`, `false -> fast`) when no new mode is configured.
5. Product default: `balanced`.

This preserves the current production latency default while acknowledging the
official K-EXAONE model default.

## Provider Payload Contract

Every Friendli chat completion request should receive explicit reasoning parser
fields so endpoint defaults cannot silently change UMMAYA behavior.

```json
{
  "chat_template_kwargs": {
    "enable_thinking": false
  },
  "parse_reasoning": true,
  "include_reasoning": false,
  "parallel_tool_calls": false
}
```

For `deep` / `diagnostic`, only `enable_thinking` and `include_reasoning` flip
to `true`.

Tool calling remains serial (`parallel_tool_calls=false`) because UMMAYA's
citizen workflows require observable tool-result review between steps.

## Query-Loop Painting

Use two separate live surfaces:

1. `progress_event`: deterministic harness progress, safe to persist.
   Examples: request classified, tool candidates available, tool dispatched,
   tool result received, answer synthesis started.
2. `thinking_delta`: provider reasoning, transient by default and rendered only
   when mode allows `include_reasoning=true`.

This distinction is important. Progress painting should not depend on raw
provider reasoning being enabled, and raw provider reasoning should not be used
as a substitute for auditable query-loop state.

Rendering order should follow CC semantics:

```text
user prompt
assistant progress/thinking
tool call
tool result
assistant progress/thinking
final answer
```

The existing UMMAYA renderer change that inserts a streaming thinking row before
tool rows is aligned with this target, but the event source must be fixed at the
query/provider boundary so the UI is not faking a final-state layout.

## TUI Components

Do not modify permission components in this migration.

Add or migrate these components:

- `/reasoning` command: `current`, `fast`, `balanced`, `deep`, `diagnostic`,
  `auto`.
- `ReasoningModePicker`: replaces the current boolean `ThinkingToggle` surface.
- `ReasoningIndicator`: compact footer/logo indicator, e.g.
  `Reasoning balanced` or `Reasoning deep`.
- `StreamingReasoningRow`: live row for `thinking_delta` and query-loop
  `progress_event`.

The UI should not claim raw chain-of-thought is saved. It should say "live
reasoning/progress" or "reasoning mode" rather than "show saved thoughts".

## Telemetry

Adopt OpenTelemetry-compatible naming without adding a new dependency in P0:

- `ummaya.turn`
- `ummaya.llm.request`
- `ummaya.llm.chunk`
- `ummaya.tool.dispatch`
- `ummaya.tool.result`
- `ummaya.render.commit`

Recommended attributes:

- `correlation_id`
- `reasoning.mode`
- `reasoning.enabled`
- `reasoning.parse`
- `reasoning.include`
- `reasoning.delta_chars`
- `tool.name`
- `tool.call_id`
- `error.type`

Do not export raw reasoning, raw tool arguments, or raw tool results unless a
future explicit diagnostic mode documents storage, redaction, and retention.

## Implementation Slices

### Slice 1: Policy Resolver

- Add `ReasoningMode` and `ResolvedReasoningPolicy`.
- Add table-driven tests for env/settings/session precedence.
- Keep legacy `thinkingEnabled` readable but stop letting it directly construct
  provider payload.

### Slice 2: Payload Wiring

- Apply resolver output in both direct TUI Friendli client and Python backend
  Friendli client.
- Always emit `parse_reasoning`.
- Emit `include_reasoning` according to policy.
- Keep `parallel_tool_calls=false`.
- Add tests in the existing Friendli payload/unit suites.

### Slice 3: Stream Event Hygiene

- Ensure reasoning gets a distinct content block or equivalent internal layout
  slot before tool blocks.
- Add regression tests for turns that contain both `thinking_delta` and
  `tool_call_delta`.
- Update the active message stream path so live thinking updates the rendered
  `streamingThinking` state, not only token length.

### Slice 4: Command And Settings UI

- Add `/reasoning`.
- Migrate the boolean thinking toggle into a mode picker.
- Add a separate reasoning indicator.
- Leave `/effort` and permission mode unchanged.

### Slice 5: Verification

- Unit: resolver matrix.
- Unit: Friendli payload matrix.
- Unit: thinking + tool collision.
- Component: streaming reasoning row before tool rows.
- Evidence Fabric: `uv run pytest tests/evidence tests/ci -q` and
  `uv run python -m ummaya.evidence --source-ref local --out .evidence/run.json`.
- TUI proof is attached only when the implementation changes the TUI query-loop
  path: run `bun run tui` with ordinary user phrasing, including weather/tool
  prompts and general prompts, and attach the recorded interaction as an
  Evidence Fabric UX artifact.
- Capture proof must show progress painting before the final answer and between
  tool calls, but the artifact format is owned by Evidence Fabric rather than a
  hardcoded TUI-only harness.

## Acceptance Criteria

1. `/reasoning current` reports the effective mode and the source that selected
   it.
2. `/reasoning deep` makes the next Friendli request send
   `enable_thinking=true`, `parse_reasoning=true`, and
   `include_reasoning=true`.
3. `/reasoning balanced` sends `enable_thinking=false`,
   `parse_reasoning=true`, and `include_reasoning=false`.
4. A normal user query such as "오늘 저녁 김해에서 서울 가는데 비행기 뜰만해?"
   paints progress before the final answer.
5. A tool-use turn that receives reasoning and a tool call renders reasoning
   before the tool row and does not corrupt the tool block index.
6. Logs and telemetry record reasoning lengths/counts but not raw reasoning
   text by default.
7. Permission mode behavior is byte-for-byte unaffected by this migration.

## Deferred Work

- Adaptive `auto` routing using a cheap classifier or confidence model.
- Friendli `reasoning_effort` / `reasoning_budget` after direct endpoint proof.
- vLLM self-host `thinking_token_budget` mapping.
- Trace-derived meta-tools for repeated government-service tool chains.
- Optional Langfuse/OpenTelemetry exporter integration.
