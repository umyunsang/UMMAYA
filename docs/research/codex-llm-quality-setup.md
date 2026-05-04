# Codex LLM Quality Setup Proposal

Date: 2026-05-04

This proposal covers development setup beyond basic bootstrap. It is for Codex-led
construction and quality management of KOSMOS. It does not propose changing the KOSMOS
runtime provider: production/runtime LLM behavior remains FriendliAI Serverless plus
K-EXAONE unless a future ADR and spec-driven PR explicitly change that boundary.

## Research Basis

Primary references reviewed:

- OpenAI Docs MCP: <https://developers.openai.com/learn/docs-mcp>
- OpenAI GPT-5.5 guide: <https://developers.openai.com/api/docs/guides/latest-model>
- OpenAI reasoning guide: <https://developers.openai.com/api/docs/guides/reasoning>
- OpenAI evaluation best practices:
  <https://developers.openai.com/api/docs/guides/evaluation-best-practices>
- OpenAI trace grading: <https://developers.openai.com/api/docs/guides/trace-grading>
- Codex cloud internet access:
  <https://developers.openai.com/codex/cloud/internet-access>
- OpenAI skills catalog: <https://github.com/openai/skills>
- Langfuse docs: <https://langfuse.com/docs>
- OpenTelemetry GenAI semantic conventions:
  <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- OWASP Top 10 for LLM Applications:
  <https://owasp.org/www-project-top-10-for-large-language-model-applications/>
- NIST AI Risk Management Framework:
  <https://www.nist.gov/itl/ai-risk-management-framework>

## Constraints

KOSMOS-specific constraints that shape the setup:

- Runtime model and provider stay fixed to K-EXAONE on FriendliAI.
- Do not add dependencies outside a spec-driven PR.
- CI must not call live `data.go.kr` APIs.
- Every non-trivial feature must pass the Spec Kit flow.
- Prompt, tool, and adapter I/O must remain typed and fixture-backed.
- TUI changes require the repository's layered interactive verification chain.
- Development agents may use GPT-5.5 for planning, review, and research, but not as an
  implicit product runtime dependency.

## Core Insight

The next useful setup is not another framework. KOSMOS already has enough building blocks:
Spec Kit, prompt manifests, pytest, fixture-backed tools, OpenTelemetry, Langfuse, and strict
TUI smoke methodology. The gap is a single LLM quality gate that joins these pieces into a
repeatable release decision.

The recommended pattern is:

1. Define target-state citizen demand scenarios as versioned data, independent of the current
   adapter inventory.
2. Run deterministic contract graders before any model judge.
3. Trace-grade the full agent loop, not only the final answer.
4. Attach scorecards to prompt, tool, and adapter PRs.
5. Promote real failures into regression scenarios.

## Recommended Setup

### Phase 0: Immediate, No New Dependencies

Keep the current Codex setup:

- `~/.codex/config.toml` uses `gpt-5.5` with high or extra-high reasoning for lead work.
- `openaiDeveloperDocs` MCP is enabled for OpenAI and Codex questions.
- `.agents/skills/speckit-*` is the Codex-facing copy of the Claude Spec Kit skills.
- Bootstrap uses `uv sync --frozen --all-extras --dev` and `bun install --frozen-lockfile`.

Add one working rule:

- Any agentic behavior claim must cite a trace, fixture, frame snapshot, or eval result.
  Grep-only evidence is not enough.

### Phase 1: Spec-Driven LLM Quality Gate

Create a new Spec Kit feature, tentatively `llm-quality-gate`, with no dependency changes.
The feature should promote the target-state scenario dataset into deterministic graders and
then map scenarios onto live, mock, or handoff channels as implementation catches up.

The dataset must be demand-first: it should model what citizens ask when one LLM can operate
national administrative infrastructure. It must not be derived from current `ToolRegistry`
entries, adapter IDs, or fixture files.

Scenario file:

```text
eval/scenarios/national_ax_citizen_requests_v1.yaml
```

Scenario shape:

```yaml
- id: TAX-001
  priority: P0
  lifecycle_domain: tax
  citizen_segment: individual_taxpayer
  request_ko: "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘."
  agencies_or_infrastructure:
    - National Tax Service Hometax
    - simple authentication
    - bank account verification
  citizen_intent_verbs:
    - file_tax
    - get_refund
    - register_account
  expected_ax_chain:
    - primitive: verify
      purpose: identity_and_tax_delegation
    - primitive: lookup
      purpose: collect_income_withholding_deductions_and_prior_filing_status
    - primitive: submit
      purpose: file_tax_return_after_final_citizen_confirmation
  permission_requirements:
    identity_assurance: high
    user_confirmations:
      - tax_return_submission
      - refund_account_registration
    sensitive_data:
      - income
      - deductions
      - resident_registration_number
      - bank_account
```

Proposed tests:

- `tests/eval/test_national_ax_citizen_requests.py`
- Structural checks that the dataset covers tax, civil affairs, payments, utilities,
  identity, welfare, healthcare, housing, mobility, business, labor, education, safety,
  immigration, legal, and personal-data workflows.
- Guard checks that banned current-code keys such as `tool_id`, `adapter_id`,
  `expected_tool_id`, and `fixture_refs` do not enter the target-state dataset.
- No live network access.

Proposed command:

```bash
uv run pytest tests/eval -m "not live"
```

This matches OpenAI's current eval guidance: evaluate instruction following, functional
correctness, tool selection, tool argument precision, and edge cases separately. For KOSMOS,
the first gate is target coverage and citizen-demand fidelity. Tool-call correctness and
policy-citation correctness become deterministic gates after each target scenario is mapped to
an implemented live, mock, or handoff channel.

### Phase 2: Trace Grading

Add trace-grade records for complete agent runs. The grade should cover each step of the loop:

- Prompt manifest hash and system prompt version.
- Request/session/correlation IDs.
- Primitive chosen.
- Tool adapter selected.
- Tool arguments.
- Permission request shown.
- Fixture or live/mock mode.
- Final answer contract.
- TUI frame hash sequence when the TUI path is involved.

Proposed score fields:

```yaml
scenario_id: TAX-001
trace_id: "..."
prompt_manifest_hash: "..."
tool_precision_pass: true
tool_argument_pass: true
policy_citation_pass: true
permission_ux_pass: true
final_answer_pass: true
latency_ms: 1234
token_count_input: 0
token_count_output: 0
notes: ""
```

KOSMOS already has `src/kosmos/observability/`, `docs/observability.md`, and Langfuse in the
dev extra. The implementation should extend existing OTEL and Langfuse paths instead of adding
a new observability framework.

The important join keys are:

- `scenario_id`
- `trace_id`
- `correlation_id`
- `prompt_manifest_hash`
- `channel_id`
- `tool_id`
- `frame_hash`

### Phase 3: Prompt And Tool Change Scorecards

Any PR touching these surfaces should include an eval scorecard:

- `prompts/**`
- `src/kosmos/llm/**`
- `src/kosmos/tools/**`
- `src/kosmos/permissions/**`
- `tui/src/**` when the displayed agent loop changes

Minimum scorecard:

```yaml
baseline_ref: main
candidate_ref: HEAD
scenario_count: 0
contract_pass_rate: 0.0
tool_precision_pass_rate: 0.0
policy_citation_pass_rate: 0.0
permission_ux_pass_rate: 0.0
answer_quality_reviewed: false
known_regressions: []
```

Store scorecards under the active feature directory, for example:

```text
specs/<feature>/quality-gate/scorecard.yaml
```

Do not use LLM-as-judge as the first gate. Use it only after deterministic checks pass and only
for answer usefulness, tone, completeness, or ambiguity handling. Human review remains the
highest-confidence path for sensitive public-service flows.

### Phase 4: KOSMOS-Specific Codex Skills

The Claude-era Spec Kit skills are usable in Codex through `.agents/skills/`. The next step is
to add KOSMOS-specific skills after the quality gate exists.

Recommended skills:

- `kosmos-tool-adapter`: author one `GovAPITool` adapter with fixture, policy citation, tests,
  and registry entry.
- `kosmos-tui-verify`: execute the repository's PTY, vhs, PNG, text, ascii, and frame snapshot
  methodology for TUI PRs.
- `kosmos-pr-scorecard`: collect test, eval, trace, and TUI evidence into a PR-ready summary.

Each skill should ship with its own small eval pack. Do not add a process skill that cannot be
tested, scored, or improved.

### Phase 5: Codex Cloud Network Policy

Codex cloud internet access should stay off by default. If a cloud environment needs internet,
use an allowlist and prefer `GET`, `HEAD`, and `OPTIONS` only.

Suggested allowlist for research and dependency bootstrap:

- `developers.openai.com`
- `platform.openai.com`
- `github.com`
- `githubusercontent.com`
- `pypi.org`
- `pythonhosted.org`
- `npmjs.com`
- `npmjs.org`
- `bun.sh`

Do not allow live public-service API domains in CI or generic cloud agent phases unless the
active spec explicitly calls for a live manual verification path and secrets are injected by the
user outside the repository.

## Latest-Stack Decisions

Adopt now:

- OpenAI Docs MCP for Codex/OpenAI documentation lookup.
- GPT-5.5 as the Codex lead model for planning, review, and research.
- Existing Langfuse local stack for trace and eval reporting.
- Existing OpenTelemetry integration, aligned where possible with GenAI semantic conventions.
- Scenario evals and deterministic graders using pytest and YAML/JSON fixtures.
- Codex skills as repeatable playbooks, only after they have eval coverage.

Do not adopt now:

- Runtime migration from K-EXAONE/FriendliAI to OpenAI.
- LangGraph, Guardrails, or new orchestration packages without a spec and ADR.
- Hosted eval services that require external egress for CI.
- Broad dependency upgrades while the current branch has failing validation.
- Porting `.claude/settings.local.json` into Codex.

## Security Mapping

OWASP LLM risks map directly to KOSMOS gates:

- Prompt injection: treat external pages, issue bodies, and tool outputs as untrusted input.
- Insecure output handling: validate model-selected tool arguments with Pydantic and adapter
  contracts before dispatch.
- Sensitive information disclosure: prevent secrets from entering prompts, traces, fixtures,
  and screenshots.
- Insecure plugin design: require policy citations, least-privilege tool interfaces, and
  fixture-backed tests for every adapter.
- Excessive agency: keep permission UX in the canonical Claude Code-style permission pipeline.
- Overreliance: require deterministic eval evidence and human review for sensitive flows.

NIST AI RMF and its Generative AI profile support the same direction: manage AI risk through
documented design, evaluation, monitoring, and explicit trustworthiness criteria. For KOSMOS,
that means every agency adapter and prompt change should carry evidence of correctness,
privacy, permission handling, and traceability.

## First Ten Tasks For The Proposed Spec

1. Create an Epic for `llm-quality-gate`.
2. Run `speckit-specify` with this document as research input.
3. Preserve `eval/scenarios/national_ax_citizen_requests_v1.yaml` as the target-state demand set.
4. Add a scenario loader in tests only.
5. Add deterministic target-coverage, primitive-chain, permission, and confirmation graders.
6. Map each scenario to an implementation state: live, mock, handoff, or future blocked.
7. Add a scorecard artifact template under the feature spec.
8. Extend existing observability events with `scenario_id`, `channel_id`, and
   `prompt_manifest_hash`.
9. Add a local quality-gate command that runs evals without live external channels.
10. Create follow-up tasks for the three KOSMOS-specific Codex skills after the gate is green.

## Success Criteria

The setup is complete when a future prompt, tool, or TUI-agent-loop PR can answer these
questions with committed evidence:

- Which scenarios ran?
- Which prompt manifest and tool registry were used?
- Which tools were selected and with what arguments?
- Which permission request was shown?
- Which policy and data-source citations were required and present?
- Which trace and frame hashes prove the behavior?
- What regressed compared with `main`?
