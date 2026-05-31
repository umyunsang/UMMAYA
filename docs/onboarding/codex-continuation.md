# Codex Continuation Setup

This document is the handoff surface for continuing Claude Code-era UMMAYA work in Codex.
It captures the local setup, the Claude-to-Codex skill mapping, and the quality gates that
should be used before opening or updating a PR.

## Scope Boundary

Codex is the development agent for this repository. It is not the UMMAYA runtime model.
UMMAYA remains a FriendliAI Serverless + K-EXAONE client-side reference implementation, per
`docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`, and the local agent setup
files restored in each developer checkout.

Do not replace `UMMAYA_FRIENDLI_MODEL` with GPT-5.5 in product code. Use GPT-5.5 for Codex
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
- `.agents/skills/speckit-*` is restored locally and available to Codex for Spec Kit workflows.
- `.claude/settings.local.json` is not copied into Codex or committed.
- Branch names and PR titles follow `docs/conventions.md`, not Codex plugin defaults.

Tracked setup surfaces:

- This document contains the runnable setup and handoff checklist.
- `docs/vision.md`, `docs/requirements/ummaya-migration-tree.md`, `docs/conventions.md`,
  and `docs/design/verification-fabric-v2.md` contain the shared engineering contract.
- `prompts/manifest.yaml` and `prompts/*.md` are production prompt assets and stay versioned.
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml` is the target-state citizen-demand
  dataset for national infrastructure AX work.

Ignored local LLMOps surfaces:

- `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md`, `CODEX.local.md`, `.agents/`, `.claude/`,
  and `.codex/` are local agent runtime files for this checkout.
- Keep machine-local runbooks, scratchpads, and auto-memory under `.llmops/` or
  `*.local.md`; do not place them under `docs/` unless they are intended to be reviewed and
  versioned.
- If these files are lost after pulling or recloning, restore them from local git history or
  your local backup; do not reintroduce them to GitHub unless the project deliberately changes
  its agent-instruction policy.

## Codex Environment

The local Codex CLI is installed and configured globally in `~/.codex/config.toml`.
That file is user-local and must not be committed.

Expected local agent settings:

```toml
model = "gpt-5.5"
model_reasoning_effort = "xhigh"

[projects."/Users/um-yunsang/UMMAYA"]
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

The local checkout has both `.claude/skills/` and `.agents/skills/`. They are ignored by Git and
act as developer-local LLMOps runtime files. Codex loads the `.agents/skills/speckit-*` copies
in this project, so the Spec Kit workflow is usable from Codex without editing
`.claude/skills/`.

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

Do not edit `.claude/skills/` for product behavior. If a skill needs to change, update the
Codex-facing `.agents/skills/` copy in the local checkout first, verify it, then decide
separately whether the change belongs in a tracked project document, a reusable skill package,
or local-only memory.

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
and CI uses the same all-extras shape.

Operator-managed live-adapter secrets for real local execution:

- `UMMAYA_KAKAO_API_KEY`
- `UMMAYA_DATA_GO_KR_API_KEY`

`UMMAYA_FRIENDLI_TOKEN` is a user session credential. Public CLI users enter it through `/login`;
do not store it in Infisical operator environments.

Never commit `.env`, `secrets/`, local Codex config, local agent memory, or Claude local
settings.

## Release Packaging Operational Memory

npm release publishing uses npm Trusted Publishing, not a long-lived `NPM_TOKEN`.
If Trusted Publisher setup is required for `ummaya`, use an interactive TTY so npm can
open the browser 2FA flow for WebAuthn/passkey/fingerprint accounts:

```bash
npx -y npm@11.14.1 trust github ummaya \
  --file publish-npm.yml \
  --repo umyunsang/UMMAYA \
  --env npm \
  --yes
```

Do not run that command through a non-TTY shell call. In non-TTY mode npm cannot invoke
`webAuthOpener`, masks the `/auth/cli/...` URL, and fails with `EOTP`. If the user uses
fingerprint/passkey 2FA, do not ask for an OTP first; open the TTY browser flow and have
the user approve it in the browser.

After the trust relationship exists, release through `.github/workflows/publish-npm.yml`
and verify the exact package version with `npm view ummaya@<version> version`.

For every release bump, keep these version sources synchronized before packing:
root `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `pyproject.toml`,
`uv.lock`, and `tui/package.json`. The TUI `--version` output reads
`tui/package.json` through `tui/src/stubs/macro-preload.ts`, so root-only bumps
can publish a new tarball whose CLI still reports the previous version.

All-platform release rule:

- A release is incomplete until the final `main` commit is green, `vX.Y.Z` points at that
  final commit, GitHub Release exists and is current, npm `ummaya@X.Y.Z` is published,
  Homebrew/Cask version and SHA match the npm registry tarball, and a clean install smoke
  has run from the published artifact.
- Do not stop after a version bump, npm publish, tag push, or GitHub Release creation.
- After every push, tag push, workflow dispatch, GitHub Release publish, npm publish,
  Homebrew/Cask update, or deployment dispatch, monitor GitHub Actions to terminal state.
- If npm asks for browser/WebAuthn/passkey/fingerprint approval, use the interactive
  TTY/browser approval path. Do not ask for an OTP first unless npm explicitly requires OTP.
- The final release report must include a matrix for commit, tag, GitHub Release, npm,
  Homebrew/Cask, CI, and clean install smoke.

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
```

For evidence changes, prompt changes, tool-selection behavior, query-loop rendering,
or adapter-routing behavior:

```bash
uv run pytest tests/evidence tests/ci -q
uv run python -m ummaya.evidence \
  --source-ref local \
  --dataset-ref ummaya/national-ax-core@local \
  --out .evidence/run.json
```

Interactive TUI proof is still required when the implementation touches the
query-loop render path, but the artifact is attached to the Evidence Fabric run
instead of the retired five-layer TUI-only harness.

## Current Handoff Facts

As of 2026-05-04:

- Current local branch: `fix/resolve-location-keyword-fanout`.
- There are existing local untracked TUI smoke and frame artifacts; do not delete or normalize
  them unless the active task explicitly owns those artifacts.
- `src/ummaya/ipc/stdio.py` has local uncommitted edits related to a resolve-location chain
  enforcement gate. Preserve them unless the user asks to change that fix.
- GitHub Sub-Issues API reports Initiative #2290 and all eight of its sub-issue Epics closed,
  even though `AGENTS.md` still says it is active. Treat `AGENTS.md` as stale on that one
  tracking fact and verify current issue state with GraphQL before making planning claims.

Known documentation/config drift to resolve in a small follow-up PR:

- Historical Spec 2521 notes state `UMMAYA_K_EXAONE_THINKING` defaults to `true`; the
  production source of truth now defaults it to `false` so visible answers arrive on
  the content channel. Treat old `true` references as historical unless a task is
  explicitly about reasoning-channel benchmarks.
- `docs/configuration.md` lists `UMMAYA_LLM_SESSION_BUDGET` default as `100000`, while
  `src/ummaya/llm/config.py` defaults to `1_000_000`.
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
multi-turn reasoning manually. These map to UMMAYA as development-methodology guidance, not as
a runtime provider migration.

## LLM Quality Management Recommendations

UMMAYA already has the right skeleton: Spec Kit, prompt manifests, OTEL spans, fixture-backed
adapters, and scenario-level evidence. The active quality step is Evidence Fabric v2, which
connects them into one release gate.

Deep-dive setup: `docs/design/verification-fabric-v2.md`.

Recommended additions:

1. Treat `evidence/scenarios/national_ax_citizen_requests_v1.yaml` as the target-state citizen
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
