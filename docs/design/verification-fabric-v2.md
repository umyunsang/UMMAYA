# Evidence Fabric v2

Date: 2026-05-26

## Decision

Evidence Fabric v2 replaces the previous verification surfaces:

- standalone retrieval/shadow-eval workflows
- TUI-only smoke workflows and capture scripts
- `docs/testing.md`
- historical per-feature smoke artifacts under `specs/`
- labeled model-visible eval files that exposed implementation identifiers

The new gate verifies UMMAYA as a full citizen-facing agent system: scenario
contract, tool-surface contract, prompt integrity, observability join keys,
adversarial leakage resistance, UX artifacts, and manual live canaries.

## Research Basis

The 2026 agent-evaluation trend is moving away from isolated answer grading and
toward environment-grounded, traceable, leakage-resistant verification:

| Source | Signal Used |
|---|---|
| Terminal-Bench 2.0 (`arxiv.org/abs/2601.11868`) | real terminal tasks expose failures that final-state unit tests miss |
| TerminalWorld (`arxiv.org/abs/2605.22535`) | long-horizon local workflows need reproducible interaction evidence |
| BenchJack (`arxiv.org/abs/2605.12673`) | benchmark leakage and implementation hints must be actively excluded |
| SpecBench (`arxiv.org/abs/2605.21384`) | scenario/spec compliance matters more than raw answer similarity |
| OpenTelemetry GenAI semantic conventions | model, tool, and agent spans need stable join attributes |
| Langfuse OpenTelemetry integration | traces can be attached later without changing the local evidence schema |
| MCP tools draft specification | tool contracts need explicit schemas and capability boundaries |
| OpenAI agent evals and guardrails docs | eval datasets, graders, and guardrails should remain separate layers |
| Harbor Framework task/dataset registry | task = instruction + environment + verifier; dataset = task collection resolved from a registry |

UMMAYA-specific interpretation: the model-visible user demand set must remain
natural and citizen-facing. Adapter IDs, fixture names, expected tool IDs, and
other internal implementation hints belong in hidden scorecards or run evidence,
never in the prompt-facing scenario text.

## Scope

Evidence Fabric covers these surfaces:

| Surface | Gate |
|---|---|
| Scenarios | `evidence/scenarios/national_ax_citizen_requests_v1.yaml` parses and covers the required citizen infrastructure domains |
| Tool contracts | model-visible datasets cannot leak adapter IDs, fixture references, or expected tool IDs |
| Prompts | prompt changes trigger Evidence Fabric and retain manifest integrity through existing prompt-loader checks |
| Observability | run evidence carries join keys for `scenario_id`, `trace_id`, `correlation_id`, `prompt_manifest_hash`, `tool_catalog_hash`, and `frame_hash` |
| UX | interactive TUI artifacts attach to a run when the query-loop render path changes |
| Live APIs | live checks remain manual-only and are never called from CI |

## Harbor-Style Task Registry

Evidence Fabric uses a local Harbor-style registry instead of embedding task
selection directly in the runner.

Registry entrypoint:

```text
evidence/registry.yaml
```

Default dataset ref:

```text
ummaya/national-ax-core@local
```

Each task is a directory with the Harbor-style boundary:

```text
evidence/tasks/national-ax-core/
├── instruction.md
├── task.toml
└── tests/test.sh
```

UMMAYA deliberately keeps this local-only:

- no package download
- no container runtime
- no live public-service calls
- no model-visible adapter IDs, fixture references, or expected tool IDs

`task.toml` provides task metadata, environment constraints, and verifier
configuration. `instruction.md` states the evaluator intent. `tests/test.sh`
is the verifier entrypoint for future sandbox-compatible runs, but CI currently
invokes the deterministic Python runner directly.

## Run Evidence Contract

`python -m ummaya.evidence` emits a typed JSON document:

```json
{
  "schema_version": "evidence.v2",
  "run_id": "ev-...",
  "source_ref": "...",
  "dataset_id": "...",
  "task_registry_id": "ummaya/evidence-task-registry",
  "dataset_ref": "ummaya/national-ax-core@local",
  "task_count": 1,
  "task_ids": ["ummaya/national-ax-core"],
  "scenario_count": 16,
  "scenario_ids": ["..."],
  "gates": [
    {"name": "contract", "status": "pass"},
    {"name": "scenario", "status": "pass"},
    {"name": "observability", "status": "pass"},
    {"name": "adversarial", "status": "pass"},
    {"name": "ux", "status": "skip"},
    {"name": "live_canary", "status": "skip"}
  ],
  "trace_join_keys": ["scenario_id", "trace_id", "correlation_id"]
}
```

The CI runner is deterministic and local. It does not call FriendliAI, KMA,
data.go.kr, identity providers, payment services, or any public-service channel.

## Commands

Focused local gate:

```bash
uv run pytest tests/evidence tests/ci -q
uv run python -m ummaya.evidence \
  --source-ref local \
  --dataset-ref ummaya/national-ax-core@local \
  --out .evidence/run.json
```

Backend regression gate:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not live"
```

TUI regression gate:

```bash
cd tui
bun run typecheck
bun run test
```

When a TUI change modifies query-loop painting or tool-call rendering, attach an
interactive `bun run tui` artifact to the Evidence Fabric run. The artifact must
show the ordinary user utterance, progress before the final answer, tool
dispatch/result boundaries, and final answer. The artifact format can evolve;
the invariant is that it must be readable by reviewers and joinable through the
same `correlation_id` / `frame_hash` evidence keys.

## CI

`.github/workflows/evidence.yml` runs on changes to:

- `evidence/**`
  - `evidence/registry.yaml`
  - `evidence/tasks/**`
- `src/ummaya/evidence/**`
- `tests/evidence/**`
- `tests/ci/**`
- `prompts/**`
- backend query-loop, IPC, LLM, and tool surfaces
- `tui/src/**`

It runs the focused evidence tests, emits `.evidence/run.json`, and uploads the
artifact. Prompt, adapter, query-loop, and TUI-facing changes therefore share
one evidence entrypoint instead of separate stale workflows.

## Migration Notes

Deleted surfaces must not be reintroduced as parallel gates:

- `.github/workflows/eval.yml`
- `.github/workflows/shadow-eval.yml`
- `.github/workflows/tui-ipc-drift.yml`
- `.github/workflows/tui-smoke.yml`
- `docs/testing.md`
- `docs/research/codex-llm-quality-setup.md`
- `eval/retrieval_queries*.yaml`
- `src/ummaya/eval/**`
- `tests/eval/**`, `tests/retrieval/**`, `tests/shadow_eval/**`, `tests/e2e/**`
- TUI smoke/capture scripts under `scripts/` and `tui/scripts/`

Focused unit or integration tests may still exist under the relevant subsystem
directory. What is retired is the old standalone verification pipeline and its
hardcoded TUI-only artifact methodology.
