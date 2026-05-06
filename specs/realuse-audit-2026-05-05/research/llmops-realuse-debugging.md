# LLMOps Real-Use Debugging Notes

Date: 2026-05-05
Scope: real-use KOSMOS TUI and agent-loop debugging after the CC-alignment cleanup.

## External references checked

- OpenTelemetry GenAI semantic conventions define agent, model, event, exception, metric, and MCP semantic surfaces. KOSMOS should continue using OTEL-compatible event names for LLM chunks, tool calls, and TUI frame commits.
- OpenInference defines a trace as the full request path from user input through LLM, tool, retrieval, and final response. Its span-kind taxonomy reinforces that KOSMOS real-use tests must inspect `AGENT`, `LLM`, `TOOL`, `GUARDRAIL`, `EVALUATOR`, and UI-adjacent events, not only the final assistant text.
- Langfuse positions traces, sessions, timelines, agent graphs, dashboards, and evaluations as one lifecycle. The useful KOSMOS equivalent is a local-first run directory containing snapshots, frame timelines, tool-call evidence, and scenario-level scores.
- OpenAI agent eval guidance recommends starting with traces for debugging workflow-level behavior, then moving to datasets and eval runs once the desired behavior is known. This maps directly to KOSMOS: use live real-use traces for diagnosis, then freeze stable prompts into replayable scenario scripts.
- Pydantic Evals models evaluation as dataset, case, experiment, task, and evaluator. KOSMOS already has the target-state YAML dataset; the missing layer is per-case run scoring over the captured artifacts.
- Google ADK callbacks call out before/after model and before/after tool control points for observability, guardrails, and state management. KOSMOS already has IPC and primitive boundaries; the audit needs to tag failures at those boundaries.
- Bun PTY support is the right path for Escape and control-byte scenarios because the child process sees a real TTY. KOSMOS already has `scripts/bun-pty-capture.ts` for timing-critical key delivery.
- `ink-testing-library` exposes every rendered frame via `frames[]`. KOSMOS already has frame-sequence helpers, but real-use tmux runs also need viewport-level distinct-frame capture.
- `tmux capture-pane` is appropriate for human-visible TUI state snapshots and supports persistent pane inspection. KOSMOS already uses this as Layer 5a.
- TRAJECT-Bench emphasizes trajectory-level diagnostics: tool selection, argument correctness, and order/dependency satisfaction. KOSMOS scenario verdicts must grade the tool trajectory, not only whether an answer was produced.
- Community discussions around agent observability repeatedly identify a gap between LLM call tracing and agent state-transition debugging. KOSMOS should record goal/constraint/tool/permission/render evidence in one run folder so a reviewer can reconstruct why a turn went wrong.

## Current KOSMOS coverage

- Backend contract checks: `uv run pytest`, fixture-backed adapters, and primitive tests.
- Component rendering: `bun test` with Ink snapshots and frame-sequence helpers.
- Real backend probe: stdio JSONL bridge scripts and IPC frame schemas.
- Interactive TUI: tmux capture harness with `wait_for_pane` predicates and named snapshots.
- Keystroke-critical TUI: Bun-native PTY harness for Escape, BackTab, and raw control bytes.
- UI frame telemetry: `kosmos.tui.frame_commit` hook in the TUI.

## Gap closed in this pass

Before this pass, `scripts/tui-tmux-capture.sh` only saved named snapshots plus final state. That can miss short-lived repaint anomalies between snapshots.

The harness now supports:

```bash
KOSMOS_TMUX_SAMPLE_FRAMES=1 scripts/tui-tmux-capture.sh <out-dir> <scenario.sh>
```

When enabled, it writes:

- `frames/timeline.tsv`
- `frames/frame_0000_<hash>.txt`
- one file per distinct pane state sampled during the scenario

This closes the real-use testing gap between named scenario checkpoints and continuous user-visible painting flow.

## Scoring rules for the next loop

Each scenario run is graded on these axes:

- `uiux_flow`: CC-aligned surfaces, no obsolete KOSMOS HUD, no stale import crash, no duplicated panels.
- `backend_flow`: backend boot, IPC frame continuity, no unhandled Python or JS exception.
- `reasoning_flow`: no unsupported claim, no fake completion of live identity/payment/submit actions, no drift from the user request.
- `tool_flow`: expected primitive family, correct adapter selection, bounded duplicate retries, sane argument shape, no permission gate where the adapter is read-only.
- `permission_flow`: canonical CC PermissionRequest path only, correct allow/deny/cancel behavior.
- `visual_flow`: no transient wrong-state frame in `frames/`, no overlapping text, no frozen spinner after completion.
- `safety_flow`: no live irreversible action in test, no committed PII, no secret echo.

## Sources

- https://opentelemetry.io/docs/specs/semconv/gen-ai/
- https://arize-ai.github.io/openinference/spec/
- https://langfuse.com/docs
- https://developers.openai.com/api/docs/guides/agent-evals
- https://pydantic.dev/docs/ai/evals/evals/
- https://adk.dev/callbacks/
- https://bun.com/docs/runtime/child-process
- https://app.unpkg.com/ink-testing-library@3.0.0/files/readme.md
- https://man7.org/linux/man-pages/man1/tmux.1.html
- https://huggingface.co/papers/2510.04550
