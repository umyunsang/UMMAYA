# Codex Continuation Setup

This document is the handoff surface for continuing Claude Code-era KOSMOS work in Codex.
It captures the local setup, the Claude-to-Codex skill mapping, and the quality gates that
should be used before opening or updating a PR.

## Scope Boundary

Codex is the development agent for this repository. It is not the KOSMOS runtime model.
KOSMOS remains a FriendliAI Serverless + K-EXAONE client-side reference implementation, per
`AGENTS.md`, `docs/vision.md`, and `docs/requirements/kosmos-migration-tree.md`.

Do not replace `KOSMOS_FRIENDLI_MODEL` with GPT-5.5 in product code. Use GPT-5.5 for Codex
planning, code review, and research assistance only.

## Mandatory Codex Startup

Run this checklist at the start of a new Codex session or a new worktree:

```bash
codex --version
codex mcp list
uv sync --frozen --all-extras --dev
cd tui && bun install --frozen-lockfile
```

Expected Codex state:

- `openaiDeveloperDocs` is enabled in `codex mcp list`.
- The local project is trusted in `~/.codex/config.toml`.
- `.agents/skills/speckit-*` is available to Codex for Spec Kit workflows.
- `.claude/settings.local.json` is not copied into Codex.
- Branch names and PR titles follow `docs/conventions.md`, not Codex plugin defaults.

Repository-persisted setup surfaces:

- `AGENTS.md` contains the operational rule Codex must load first.
- This document contains the runnable setup and handoff checklist.
- `docs/research/codex-llm-quality-setup.md` contains the deeper LLM quality-gate proposal.
- `eval/scenarios/national_ax_citizen_requests_v1.yaml` is the target-state citizen-demand
  dataset for national infrastructure AX work.

## Codex Environment

The local Codex CLI is installed and configured globally in `~/.codex/config.toml`.
That file is user-local and must not be committed.

Expected local agent settings:

```toml
model = "gpt-5.5"
model_reasoning_effort = "xhigh"

[projects."/Users/um-yunsang/KOSMOS"]
trust_level = "trusted"

[mcp_servers.openaiDeveloperDocs]
url = "https://developers.openai.com/mcp"
```

Verify the setup:

```bash
codex --version
codex mcp list
```

The OpenAI Docs MCP server is documentation-only. Use it first for OpenAI API, Codex,
ChatGPT Apps SDK, model-selection, and prompting questions. If the MCP tools are not exposed
in the current session, restart Codex and verify `openaiDeveloperDocs` is enabled.

Official references:

- OpenAI Docs MCP: <https://developers.openai.com/learn/docs-mcp>
- Latest model guide: <https://developers.openai.com/api/docs/guides/latest-model>
- Reasoning guide: <https://developers.openai.com/api/docs/guides/reasoning>
- Codex cloud internet access: <https://developers.openai.com/codex/cloud/internet-access>

## Claude Skills In Codex

The repository has both `.claude/skills/` and `.agents/skills/`. They are byte-identical by
SHA-256 as of 2026-05-04. Codex loads the `.agents/skills/speckit-*` copies in this project,
so the Spec Kit workflow is usable from Codex without editing `.claude/skills/`.

Use the skill names directly in Codex requests:

- `speckit-specify`
- `speckit-clarify`
- `speckit-plan`
- `speckit-tasks`
- `speckit-analyze`
- `speckit-taskstoissues`
- `speckit-implement`
- `speckit-git-feature`
- `speckit-git-validate`
- `speckit-git-remote`
- `speckit-git-commit`
- `speckit-git-initialize`

Do not edit `.claude/skills/`; `AGENTS.md` marks it as a protected Spec Kit area. If a skill
needs to change, update the Codex-facing `.agents/skills/` copy only in a spec-driven PR, then
decide separately whether the Claude copy should be regenerated from the source template.

`.claude/settings.local.json` is Claude-local state, not a Codex input. Do not copy its allowlist
into Codex. Treat it as secret-adjacent local configuration because allowlist entries can embed
literal tokens or shell commands.

## Repository Bootstrap

From the repository root:

```bash
uv sync --frozen --all-extras --dev
cd tui
bun install --frozen-lockfile
```

Use `--all-extras --dev`, not only `--dev`; the optional dev extra contains TUI replay tooling
such as `pyte`, and CI also uses the all-extras shape.

Required runtime secrets for real local execution:

- `KOSMOS_KAKAO_API_KEY`
- `KOSMOS_FRIENDLI_TOKEN`
- `KOSMOS_DATA_GO_KR_API_KEY`

Never commit `.env`, `secrets/`, local Codex config, or Claude local settings.

## Baseline Verification

For non-TUI backend changes:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not live"
```

For TUI changes:

```bash
cd tui
bun run typecheck
bun run test
bun run tui:smoke
```

Any PR touching `tui/src/**` must also follow the five-layer interactive verification in
`AGENTS.md` and `docs/testing.md`, including PTY capture, vhs GIF plus text/ascii output,
PNG keyframes, and per-frame text snapshots under `specs/<feature>/`.

## Current Handoff Facts

As of 2026-05-04:

- Current local branch: `fix/resolve-location-keyword-fanout`.
- There are existing local untracked TUI smoke and frame artifacts; do not delete or normalize
  them unless the active task explicitly owns those artifacts.
- `src/kosmos/ipc/stdio.py` has local uncommitted edits related to a resolve-location chain
  enforcement gate. Preserve them unless the user asks to change that fix.
- GitHub Sub-Issues API reports Initiative #2290 and all eight of its sub-issue Epics closed,
  even though `AGENTS.md` still says it is active. Treat `AGENTS.md` as stale on that one
  tracking fact and verify current issue state with GraphQL before making planning claims.

Known documentation/config drift to resolve in a small follow-up PR:

- `AGENTS.md` and some specs state `KOSMOS_K_EXAONE_THINKING` defaults to `false`, while
  `src/kosmos/llm/client.py` currently defaults the environment read to `true`.
- `docs/configuration.md` lists `KOSMOS_LLM_SESSION_BUDGET` default as `100000`, while
  `src/kosmos/llm/config.py` defaults to `1_000_000`.
- `docs/testing.md` fixture recording still mentions the stale
  `KOSMOS_DATA_GO_KR_KEY` name; canonical config uses `KOSMOS_DATA_GO_KR_API_KEY`.
- `tui/package.json` declares Bun `<1.3.0`, while `.github/workflows/tui-smoke.yml` pins
  Bun `1.3.12`.
- `.specify/memory/constitution.md` says PRs close Task issues, while `AGENTS.md` says PRs
  close only the Epic. `AGENTS.md` wins for this repository.

## GPT-5.5 Usage Pattern For Codex Work

Use GPT-5.5 where it adds engineering value:

- Lead planning, architecture review, migration audits, and security review: `gpt-5.5` with
  `xhigh` reasoning.
- Normal code edits and test fixes: start at `medium` or `high`; raise to `xhigh` only when
  the failure spans multiple layers or has repeated failed fixes.
- Latency-sensitive quick checks: use lower effort, but do not use quick answers as the sole
  basis for claims about issue hierarchy, security, or TUI behavior.

OpenAI's current guidance for GPT-5.5 emphasizes the Responses API, model-dependent reasoning
effort, structured outputs, prompt caching, tool descriptions, tool search for large catalogs,
state compaction for long-running agents, and preserving returned state items when managing
multi-turn reasoning manually. These map to KOSMOS as development-methodology guidance, not as
a runtime provider migration.

## LLM Quality Management Recommendations

KOSMOS already has the right skeleton: Spec Kit, prompt manifests, OTEL spans, Langfuse local
stack, fixture-backed adapters, and strict TUI verification. The next quality step is to connect
them into a release gate.

Deep-dive setup proposal: `docs/research/codex-llm-quality-setup.md`.

Recommended additions:

1. Treat `eval/scenarios/national_ax_citizen_requests_v1.yaml` as the target-state citizen
   demand set for national administrative infrastructure AX.
2. Keep that dataset independent of current adapter IDs and fixtures; map scenarios to live,
   mock, handoff, or future-blocked channels only in the implementation scorecard.
3. Grade at two levels: deterministic contract checks first, then LLM-as-judge or human review
   only for answer quality and helpfulness.
4. Promote production or smoke failures into regression evals. New evals should come from real
   traces, frame captures, and user-visible failures, not only synthetic prompts.
5. Attach eval results to prompt-manifest changes. A prompt PR should show old-vs-new pass rate,
   tool-call precision, policy-citation pass rate, p95 latency, and token cost.
6. Use Langfuse/OTEL trace IDs as the join key across backend spans, tool calls, permission
   frames, and TUI frame snapshots.
7. Keep Codex cloud internet disabled by default. If a cloud environment needs network access,
   use an allowlist and GET/HEAD/OPTIONS-only where possible.

Official references:

- Evaluation best practices: <https://developers.openai.com/api/docs/guides/evaluation-best-practices>
- Trace grading: <https://developers.openai.com/api/docs/guides/trace-grading>
- Prompting and prompt versioning: <https://developers.openai.com/api/docs/guides/prompting>
- Langfuse docs: <https://langfuse.com/docs>
