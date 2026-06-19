# Pre-Release Tool Surface Deep Research Note

Date: 2026-06-17

Scope: pre-package source-tree verification and hardening for UMMAYA TUI/provider tool
selection, Gov24 read-only guidance, protected action gating, and lookup argument
normalization.

## Local Anchors

- `docs/vision.md`: UMMAYA preserves the Claude Code tool loop but maps it to
  citizen-facing public infrastructure. Public lookup can run through `find` and
  protected action flows start with `check` before downstream `send`.
- `docs/requirements/ummaya-migration-tree.md`: `send` and `document` are heavy-gated;
  `check` is the protected-domain entry point; `find` is read-oriented.
- `docs/design/verification-fabric-v2.md`: tool-surface behavior must be proved with
  joinable evidence, denied permission states, and TUI-facing artifacts.
- Restored Claude Code status: this change stays inside the existing client-owned TUI
  provider-selection and backend IPC normalization boundaries. No new framework or
  runtime is introduced.

## 2026-Current Sources

- OpenAI function-calling docs:
  https://developers.openai.com/api/docs/guides/function-calling
  The app gives the model a list of tools, receives tool calls, executes them
  application-side, then feeds tool outputs back for final synthesis.
- OpenAI Agents SDK docs:
  https://developers.openai.com/api/docs/guides/agents
  Use application-owned orchestration, tool execution, approvals, and state when the
  app needs that control.
- Anthropic tool-use docs:
  https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
  Auto tool choice depends on the user request and exposed tool descriptions; strict
  tool schemas improve conformance but do not replace orchestration policy.
- MCP Authorization spec 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
  Authorization is transport-scoped; STDIO implementations should retrieve
  credentials from the environment rather than treating tool exposure as auth.
- NSA MCP security guidance, May 2026:
  https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf
  MCP-style automation is now widely deployed; secure-by-default behavior depends on
  implementation rigor, clear specs, and robust validation tools.
- "Mind the GAP: Text Safety Does Not Transfer to Tool-Call Safety in LLM Agents",
  arXiv 2602.16943:
  https://arxiv.org/html/2602.16943v1
  Text refusal and tool-call safety diverge; tool-call-level measurement and runtime
  mitigation are required.
- "Blue Teaming Function-Calling Agents", arXiv 2601.09292:
  https://arxiv.org/html/2601.09292v1
  Direct prompt injection, simple tool poisoning, and renaming tool poisoning affect
  function-calling agents; no single defense is comprehensive.
- "To Call or Not to Call", arXiv 2605.00737:
  https://arxiv.org/html/2605.00737v1
  Tool-call decisions should be assessed by necessity, utility, and affordability;
  always-calling tools is suboptimal.
- Berkeley Function Calling Leaderboard V4:
  https://gorilla.cs.berkeley.edu/leaderboard.html
  Current function-calling evaluation covers real-world data, multi-turn behavior,
  dynamic decision-making, and abstention.
- Open-source ecosystem signal:
  https://github.com/mlabonne/llm-datasets
  2026 agent/function-calling datasets such as AgentTrove and Nemotron-SFT-Agentic-v2
  show a maturing evaluation/training ecosystem, but they do not justify adding a
  new dependency for this release gate.

## Scorecard

Weights: correctness 25, safety/privacy 25, UMMAYA contract fit 20, migration cost 10,
testability 10, user-visible quality 10.

| Approach | Correctness | Safety | Contract fit | Cost | Testability | UX | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Prompt-only instruction to avoid premature Gov24 submit | 10 | 8 | 8 | 10 | 4 | 5 | 45 |
| Request-scoped concrete tool-surface pruning plus backend schema normalization | 23 | 24 | 19 | 9 | 10 | 9 | 94 |
| Adopt a new agent/tool framework for routing | 18 | 16 | 10 | 2 | 5 | 7 | 58 |
| Force lookup/check through `tool_choice` for all Gov24 prompts | 15 | 15 | 12 | 7 | 8 | 5 | 62 |

## Selected Approach

Use request-scoped concrete tool-surface pruning and backend schema normalization:

- read-only Gov24 certificate guidance exposes `mock_lookup_module_gov24_certificate`
  but withholds `mock_verify_module_simple_auth`, `mock_verify_ganpyeon_injeung`,
  `mock_verify_mobile_id`, and `mock_submit_module_gov24_minwon`;
- explicit Gov24 application wording still exposes the protected `check` and `send`
  chain;
- backend lookup dispatch fills deterministic Gov24 certificate parameters when the
  model emits the correct adapter with missing `certificate_type` or `purpose`;
- no new dependency is added.

This follows the current research: limit available tools before generation, validate
and normalize at the host boundary, and verify with real rendered TUI artifacts rather
than relying on model text or prompt nudges.

## Rejected Approaches

- Prompt-only safety copy: rejected because 2026 tool-call safety work shows text-level
  safety and tool-call behavior diverge.
- New OSS agent framework: rejected because UMMAYA already has the Claude Code-shaped
  TUI/provider/IPC boundary; importing another runtime would increase migration cost
  without solving this scoped release blocker.
- Force all Gov24 requests into tool calls: rejected because read-only guidance may be
  answerable after one lookup and should not make protected action tools available.

## Evidence To Maintain

- RED: read-only Gov24 provider request exposed protected action tools.
- GREEN: provider request now exposes lookup only for read-only guidance and preserves
  check/send for explicit application prompts.
- RED: Gov24 lookup adapter failed when the model omitted `certificate_type` and
  `purpose`.
- GREEN: backend normalization fills deterministic Gov24 lookup parameters.
- Surface: rerun tmux TUI scenario and verify no premature permission prompt for the
  read-only guidance prompt.
