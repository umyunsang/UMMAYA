# AGENTS.md — KOSMOS

> Entry point for AI coding agents. Imported by `CLAUDE.md`. Keep under 120 lines. Long-form details live under `docs/`.

## What KOSMOS is

A conversational multi-agent platform that **migrates the Claude Code harness** (tool loop, permission gauntlet, context assembly, TUI) from the developer domain to the Korean public-service domain. It orchestrates Korean public APIs from `data.go.kr` through a Claude Code-style tool loop, powered by LG AI Research's K-EXAONE. Student portfolio project. Not affiliated with Anthropic, LG AI Research, or the Korean government.

## **CORE THESIS — the unit of work**

**KOSMOS = CC-original harness + 2 swaps:** (a) LLM = K-EXAONE on FriendliAI; (b) tool surface = client-side caller for Korean public-service domain access. Everything else byte-identical with `.references/claude-code-sourcemap/restored-src/`.

KOSMOS is the **client-side reference implementation for Korea's national AX infrastructure** — the LLM-accessible secure-wrapped channels that the national policy stack (국가인공지능전략위원회 행동계획 + 공공AX + 범정부 AI 공통기반) drives agencies (홈택스 / 정부24 / 간편인증 / 모바일신분증 / 공동·금융인증서 / …) to expose. KOSMOS calls those channels on the citizen's behalf. International analogs: Singapore APEX, Estonia X-Road, EU EUDI Wallet, Japan マイナポータル API.

**The unit of work is wrapping one agency's LLM-callable module as one tool and registering it.** Public API + credential → Live tool. Channel exists or is policy-mandated, no credential → Mock tool mirroring the reference shape. OPAQUE-forever domain → no adapter, narrative scenario doc only. KOSMOS does **not** ask agencies to change anything — agencies change because of the policy mandate, and KOSMOS provides the open-source caller demonstrating how channels are consumed. KOSMOS does **not** invent permission policy — adapters cite the agency's own published policy and permission UX uses CC's canonical `<PermissionRequest>` pipeline.

Concrete schemas, transparency fields, citation requirements, mock fidelity grades, per-domain matrices live in `specs/<feature>/` under spec-driven workflow (`/speckit-*`), not in this file.

**Canonical sources** (cite all three in every spec and PR):
- `docs/vision.md` — thesis + six-layer design. Claude Code is the first reference for any unclear design decision.
- `docs/requirements/kosmos-migration-tree.md` — L1 pillars A/B/C · UI L2 · brand · P0–P6.
- `.references/claude-code-sourcemap/restored-src/` — Claude Code 2.1.88 byte-identical source-of-truth (research-only, never modify).

**Active Initiative**: #2290 — see GitHub for the live Epic + Phase sub-issue tree and the `specs/<feature>/` deliverables.

## L1 pillars (canonical)

- **L1-A LLM Harness** — Single-fixed provider `FriendliAI Serverless + K-EXAONE` (`LGAI-EXAONE/K-EXAONE-236B-A23B` — 236B MoE / 23B active, `enable_thinking=True` is the model-card default; KOSMOS toggles via `KOSMOS_K_EXAONE_THINKING` env, default `false`). CC agentic loop preserved 1:1 (byte-identical with CC restored-src). Native K-EXAONE function calling (Hermes-parser compatible). `prompts/system_v1.md` + compaction + prompt cache. Sessions in `~/.kosmos/memdir/user/sessions/` JSONL. 4-tier OTEL, zero external egress.
- **L1-B Tool System** — Each Korean agency API wrapped as one `GovAPITool` adapter, registered into `ToolRegistry` at boot. **Live** when we have the data.go.kr key; **Mock** when we don't (fixture replay, byte/shape-mirror per public spec). **OPAQUE** domains (홈택스 신고, 정부24-submit, 모바일ID 발급, KEC/yessign 서명, mydata-live) are never wrapped — LLM hands off via `docs/scenarios/`. Discovery via BM25 + dense `lookup`. Permission UX uses CC `<PermissionRequest>` with adapter's `real_classification_url` citation; **no KOSMOS-invented permission classification**.
- **L1-C Main-Verb Abstraction** — Four reserved primitives (`lookup · submit · verify · subscribe`) with shared `PrimitiveInput/Output` envelope. System prompt exposes primitive signatures only; BM25 surfaces adapters dynamically. Each adapter declares its real-domain policy by citation, not invention.

## Execution phases

P0 Baseline Runnable (#1632 merged) → P1 Dead-code + P2 Anthropic→FriendliAI (#1633 in progress) → P3 Tool-system wiring → P4 UI L2 → P5 Plugin DX → P6 Docs + smoke. Phase sequencing is canonical; spec PRs cite their phase.

## Stack

**Backend**: Python 3.12+ · FriendliAI Serverless (OpenAI-compatible) for K-EXAONE · `httpx` (async) · `pydantic` v2 · `pytest` + `pytest-asyncio` · `uv` + `pyproject.toml` · Apache-2.0.
**TUI**: Ink (React for CLIs) + Bun · TypeScript. Ref: Gemini CLI (Apache-2.0) + Claude Code reconstructed architecture.
Stack changes require an ADR under `docs/adr/`.

## Hard rules (never violate)

- All source text in English. Korean domain data is the only exception.
- Env vars prefixed `KOSMOS_`. Never commit `.env` or `secrets/`.
- Stdlib `logging` only; no `print()` outside CLI output layer.
- Pydantic v2 for all tool I/O. Never `Any`.
- Never call live `data.go.kr` APIs from CI tests.
- Never add a dependency outside a spec-driven PR.
- Never `--force` push `main`, `--no-verify`, or bypass signing.
- Never create `requirements.txt`, `setup.py`, or `Pipfile`.
- Never commit a file larger than 1 MB without asking.
- Never introduce Go or Rust. TypeScript is allowed only for the TUI layer (Ink + Bun).

## Issue hierarchy

`Initiative` → `Epic` → `Task` (Sub-Issues API, not body mentions). Initiatives/Epics: manual. Tasks: ONLY from `/speckit-taskstoissues`. Labels: `initiative`, `epic`, `agent-ready`, `needs-spec`, `parallel-safe`, `blocked`, `size/{S,M,L}`, plus layer labels.

**Issue tracking = GraphQL only.** Any enumeration of open epics, dependency/sub-issue graph walks, state-transition checks, or tracking-driven recommendations MUST go through `gh api graphql` with explicit field selection of the Sub-Issues API v2 connections (`issue.subIssues` / `issue.parent`, plus `pageInfo.hasNextPage` pagination). Do NOT use `trackedIssues` / `trackedInIssues` — those are the legacy body-mention task-list connection and return empty for issues linked via the "Convert to sub-issue" UI or `addSubIssue` mutation. `gh issue list/view` and REST `repos/.../issues` drop pages, miss Sub-Issues API edges, and hide projectV2 status — they are allowed ONLY for human-readable one-off glances, never as the basis for a tracking claim.

## Spec-driven workflow

Non-trivial features use [GitHub Spec Kit](https://github.com/github/spec-kit):

1. Create/verify **Epic** issue (label: `epic`)
2. `/speckit-specify` → `specs/NNN-slug/spec.md` → human review
3. `/speckit-plan` → `plan.md` → **read `docs/vision.md § Reference materials`** → human review
4. `/speckit-tasks` → `tasks.md` → human review
5. `/speckit-analyze` → constitution compliance check
6. `/speckit-taskstoissues` → create Task issues → link as sub-issues of Epic
7. `/speckit-implement` → Agent Teams parallel execution
8. PR with `Closes #EPIC` only (not Task sub-issues) → monitor CI → close Task sub-issues after merge

Small fixes (typos, one-line bugs, docs-only) skip the cycle.

**Reference source rule**: Every `/speckit-plan` Phase 0 must consult `.specify/memory/constitution.md` and `docs/vision.md § Reference materials`. Map each design decision to a concrete reference.
**Task-to-issue rule**: Tasks ONLY from `/speckit-taskstoissues`. Link as sub-issues of Epic via `gh api`. Code: `docs/conventions.md § Task linking`.
**PR close rule**: `Closes #EPIC` only — never Task sub-issues (GitHub fails at 50+). Close sub-issues after merge. Code: `docs/conventions.md § PR closing`.

## Agent Teams

The unit hierarchy is two-layer parallelism:

```
Initiative
├─ Epic α  →  Lead Opus α  +  Sonnet team α (sonnet-A1, A2, A3, ...)
├─ Epic β  →  Lead Opus β  +  Sonnet team β (sonnet-B1, B2, B3, ...)
├─ Epic δ  →  Lead Opus δ  +  Sonnet team δ (sonnet-D1, D2, D3, ...)
└─ ...
```

### Layer 1 — Epic-level parallelism (Lead Opus per Epic)

Each Epic is owned by exactly **one Lead (Opus)** for its full lifecycle: spec authoring, planning, dispatch-tree design, code review of teammate output, commit / push / PR / CI monitoring / Codex P1 handling, merge.

Multiple Epics with no dependency may run in parallel — that means **multiple Lead Opus agents** running concurrently in **separate sessions or worktrees**, NOT one Lead serializing through several Epics. "1 Lead Opus = N Epics" is forbidden — it exhausts the Lead's context just like the teammate-level mistake (verified by Initiative #2290 Epic β/δ failures, 2026-04-29, where one Lead drove both Epics' spec cycles back-to-back).

### Layer 2 — Task-level parallelism inside an Epic (Sonnet teammates)

Inside each Epic, Lead spawns **Sonnet teammates** at `/speckit-implement`. Teammate responsibility is **implementation only**: code edits + tests + WIP commit + tasks.md `[X]` marking. Sonnet does NOT do `git push` / `gh pr create` / `gh pr checks --watch` / Codex reply — those stay with Lead (sequential, after all teammates complete).

3+ independent tasks → parallel Sonnet teammates. 1-2 tasks → Lead solo.

### Dispatch unit (NON-NEGOTIABLE)

**The dispatch unit per Sonnet teammate is a task or task-group from `tasks.md`, NEVER an entire Epic.** A single Sonnet teammate gets ≤ 5 tasks AND ≤ 10 file changes. Anything larger MUST be subdivided. "1 Epic = 1 Sonnet teammate" is forbidden for the same context-exhaustion reason as the Lead rule above.

Lead reads `tasks.md` `[P]` markers — every `[P]` task or `[P]` task-group is an immediate parallel-dispatch candidate. User Story phases (US1 / US2 / US3) are independent by spec-kit definition → **separate** Sonnet teammates.

Sonnet teammate prompt MUST be ≤ 30 lines. Long instructions must reference `specs/<feature>/quickstart.md` or `research.md` rather than inlining.

### Dispatch tree (Lead draws explicitly before any Agent call)

For each `/speckit-implement`, Lead writes a dispatch tree mapping Task IDs → Sonnet teammates. Example:

```text
Phase 1 Setup (T001-T002): Lead solo
Phase 2 Foundational (T003-T005): sonnet-foundational
Phase 3 US1 (T006-T009): sonnet-us1            ┐
Phase 4 US2 (T010-T012): sonnet-us2            ├─ parallel
Phase 5 US3 (T013-T015): sonnet-us3            ┘
Phase 6 Polish (T016-T020): Lead solo
```

The tree is committed to `specs/<feature>/dispatch-tree.md` so any handoff session can reproduce both layers of parallelism.

### Role mapping

| Role | Agent | Model |
|------|-------|-------|
| Architecture | Software Architect | Opus |
| Backend | Backend Architect | Sonnet |
| CLI/Frontend | Frontend Developer | Sonnet |
| Tests | API Tester | Sonnet |
| Code review | Code Reviewer | Opus |
| Security | Security Engineer | Sonnet |
| Docs | Technical Writer | Sonnet |

## Commits, branches, PRs

Conventional Commits. Branches: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/`. PRs for code; direct `main` commits only for `docs:` / `chore:` touching no source. Full details: `docs/conventions.md`.

## Code review

After every push, read inline review comments left by **Codex** (`chatgpt-codex-connector[bot]`) on the PR and address them:

```bash
gh api repos/umyunsang/KOSMOS/pulls/<N>/comments \
  --jq '.[] | select(.user.login == "chatgpt-codex-connector[bot]") | "\(.path):\(.line) \(.body)"'
```

Codex flags issues with severity badges (P1/P2/P3). Fix or defer each with a reply. Codex auto-reviews on every push — no manual trigger needed.

## New tool adapter — the canonical work unit

Wrap one agency LLM-callable module as one tool. Pydantic v2 I/O · fail-closed defaults · Korean + English `search_hint` · Korean-primary `llm_description` · recorded fixture · happy + error path tests · no hardcoded keys · agency-published policy citation. KOSMOS does not invent permission classifications — adapters cite the agency's own policy at the URL the agency publishes.

**Decision** (any new agency module):
- Public API + credential → **Live tool**.
- Channel exists or is policy-mandated, no credential → **Mock tool** that mirrors the reference shape; swap to Live without shape change later.
- No LLM-callable channel exists or is planned → **No tool**; add a narrative scenario doc.

Concrete metadata schema, transparency fields, mock fidelity grades, citation enums — under the active Initiative spec (`specs/<feature>/`). External plugin contributors: `docs/plugins/quickstart.ko.md` + `docs/plugins/security-review.md`.

**External plugin contributors** (kosmos-plugin-store/`<repo>`): start at [`docs/plugins/quickstart.ko.md`](./docs/plugins/quickstart.ko.md). 50-item validation workflow (Q1-Q10) enforces all rules; PIPA §26 trustee acknowledgment SHA-256 must match canonical hash in [`docs/plugins/security-review.md`](./docs/plugins/security-review.md) when `processes_pii: true`.

## Testing
`uv run pytest` before every commit. Live-API tests marked `@pytest.mark.live`, skipped by default. Full guide: `docs/testing.md`.

## TUI verification (LLM-readable smoke) — **PR mandatory**

**Hard rule**: Any PR that modifies `tui/src/**` MUST capture (a) an interactive PTY scenario AND (b) per-frame text snapshots from `asciinema → pyte` replay AND (c) a vhs visual scenario that emits PNG keyframes, and commit the artefacts under `specs/<feature>/` BEFORE pushing. `bun typecheck` (KOSMOS narrows to `src/stubs/**` only) + `bun test` (REPL.tsx dynamic imports unchecked) + boot-only smoke all fail to catch stale-import regressions, dead JSX paths, AND transient repaint flashes (an ~80 ms wrong-state flash during partial-redraw is invisible to a single-shot end-of-run check). Skipping interactive verification is the #1 source of post-merge TUI breakage. Memory: `feedback_pr_pre_merge_interactive_test` + `feedback_vhs_tui_smoke` + `feedback_pty_log_full_inspection`.

Layered verification chain (all layers required for TUI-changing PRs). Numbering matches [`docs/testing.md § TUI verification methodology`](./docs/testing.md#tui-verification-methodology):

1. **Layer 1a — Python unit / fixture (`pytest`)**: backend module contracts.
2. **Layer 1b — Ink snapshot (`bun test` + `ink-testing-library` v4)**: component-level `render().frames` / `lastFrame()` tests — fastest TUI regression net (ms-fast, no terminal spawn). Necessary but not sufficient: REPL.tsx dynamic imports + ANSI cell-grid rendering still escape this layer.
3. **Layer 2 — stdio JSONL probe**: bypasses the TUI render entirely; proves the LLM tool-calling chain works.
4. **Layer 3 — interactive PTY text-log scenario**: `expect` / `asciinema` / `script` capture the full pty session running real slash commands, real input, real exit flow. Minimum scenario: spawn `bun run tui` → assert `tool_registry: \d+ entries verified` → assert `KOSMOS` branding → send `/help\r` → sleep 6s → send `\003\003` → expect eof.
5. **Layer 4 — vhs `.tape` visual scenario with PNG keyframes** (2026-04-29 promotion): the `.tape` file MUST emit BOTH the animated `Output ...gif` AND **3+ named `Screenshot <path>.png` keyframes** at the canonical scenario stages (boot+branding, input-accepted, post-action). Lead Opus uses the Read tool on each PNG (Claude / Codex multimodal vision) to verify rendered UI. **The animated `.gif` alone is insufficient** — agent Read renders only the first frame.
6. **Layer 5 — tmux capture-pane snapshots** (revised 2026-05-02, replaces asciinema-in-asciinema): run `scripts/tui-tmux-capture.sh <outdir> <scenario.sh>` which spawns `bun run tui` inside a detached `tmux new-session`, drives it with `tmux send-keys`, and snapshots via polled `tmux capture-pane -p` (plain UTF-8, no ANSI gymnastics). Scenarios MUST use `wait_for_pane <regex> <deadline_seconds>` instead of `Sleep <wallclock>` — this is the K-EXAONE-on-FriendliAI reasoning latency lesson from Spec 2521 (reasoning_content can stream 30-90 s; hardcoded sleep cannot bound it). The tmux pattern avoids asciinema's [PTY-nesting design constraint #250](https://github.com/asciinema/asciinema/issues/250). Output: `snap-NNN-<label>.txt` per scenario stage + `final.txt`. Detail: [`specs/debug-infra-rebuild/RFC.md § P2`](./specs/debug-infra-rebuild/RFC.md). The legacy `scripts/tui-text-debug.sh` (asciinema + pyte) is **deprecated** — use only for offline replay of older `*.cast` files.

   Inside Ink-side unit / fixture tests, use `tui/src/test-utils/waitForFrame.ts` (Spec debug-infra-rebuild § P1) — the `waitForFrame(predicate, {deadlineMs})` poll-with-deadline helper is the Ink port of Bubble Tea's `teatest.WaitFor` pattern. It REPLACES every `Sleep <wallclock>` in scripts. Sister helpers: `waitForText` / `waitForRegex` / `waitForStable` / `frameSequence` / `frameHash`.

   **Layer 5c — Ink frames sequence hash** (2026-05-02, Spec debug-infra-rebuild § P3/P4): `tui/src/test-utils/frameStreamSnapshot.ts` provides `assertFrameSequence(result, expected)` and `takeStreamSnapshot(result)`. These helpers operate on `ink-testing-library`'s `frames` array and assert the full de-duplicated frame hash sequence — not just `lastFrame()`. This is the permanent fix for AGENTS.md anti-pattern #1 ("Final-state fallacy"): 80ms transient flash states and intermediate render states are asserted explicitly. Layer 5c runs in-process (ms-fast, no terminal spawn) alongside Layer 5a (tmux capture-pane) and Layer 5b (pyte offline replay). The `kosmos.tui.frame_commit` OTEL event (`tui/src/utils/frameCommitOtel.ts`) is emitted on every Ink reconcile in `MessagesImpl`, enabling cross-correlation of frame timestamps with `kosmos.llm.chunk` events in Langfuse traces (Phase 5).

Mismatches between layers identify which layer regressed. PR description MUST cite the captured `specs/<feature>/scripts/smoke-*.expect` + `smoke-*-pty.txt` + `smoke-*.tape` + every `smoke-keyframe-*.png` the tape produced + the Layer 5 `frames/` directory (or `raw.cast` + `timeline.txt`). Full methodology + recipes: [`docs/testing.md § TUI verification methodology`](./docs/testing.md#tui-verification-methodology).

### Five mandatory probe points (add BEFORE claiming a TUI bug is fixed)

Per the methodology in [`docs/testing.md § TUI verification methodology`](./docs/testing.md#tui-verification-methodology):

1. **Input ingress** — log `KEYSTROKE ts=… txn=… key=… mode=…` at the keypress handler.
2. **IPC frame boundary** — log every `chat_request` / `assistant_chunk` / `tool_call` envelope with `correlation_id` (already required by Spec 032).
3. **Tool dispatch boundary** — log `TOOL ts=… txn=… tool_id=… status={dispatched|completed|errored}`.
4. **Render commit** — every Ink reconcile commits a frame; emit `RENDER ts=… txn=… frame_hash=…` so the timeline.txt cross-references frame_NNNN.txt.
5. **Snapshot trigger** — Layer 4 capture must run for every TUI-touching PR; absence of an `frames/` directory under `specs/<feature>/` is a CI bypass violation.

### Seven anti-patterns (the LLM-agent-debugging traps the user has flagged)

These are forbidden — each maps to a memory entry the agent has been corrected on:

1. **Final-state fallacy** — reading only `lastFrame()` / end-of-PTY-log, declaring the fix done, missing the 80 ms flash. Memory: `feedback_pty_log_full_inspection`. **Mandatory countermeasure: enumerate EVERY frame in `frames/` directory.**
2. **Grep-as-proof** — `grep -c "tool_call" smoke.txt` returning 0 ≠ "no tool call emitted". The grep may be looking for the wrong literal in an ANSI-leaking log. Memory: `feedback_pty_log_full_inspection`. **Countermeasure: full read after grep, never grep alone.**
3. **Snapshot blindness** — green `bun test` ≠ green TUI. Component snapshots can't prove the REPL.tsx dynamic-import path even compiled. **Countermeasure: Layers 2-4 are non-negotiable.**
4. **Tool-substitution for methodology** — adding more tools (vhs, asciinema) without anchoring them to a 5-step methodology. **Countermeasure: every captured artefact must answer a probe point above.**
5. **Skim-and-summarize** — reading first 200 lines of a 10k-line PTY log, hallucinating the middle. **Countermeasure: cast→pyte de-dups consecutive identical states; agent reads the deduped frame set in full.**
6. **Trusting one's own expect run** — same machine, same warm cache; flashes that humans see on cold start may not reproduce. **Countermeasure: vary `KOSMOS_*` startup env, run twice, diff frame sets.**
7. **Fix-the-symptom spiral** — three+ failed fixes in a row without questioning architecture. Memory: superpowers `systematic-debugging`. **Countermeasure: STOP at fix #3, capture frames, post timeline to user.**

**Bypass**: PRs that do not touch `tui/src/**` (Python backend / spec docs / workflow only) are exempt — declare `TUI no-change` in the PR description.

## Do not touch
`.specify/`, `.claude/skills/` (Spec Kit) · `LICENSE` (Apache-2.0, ADR required) · `docs/vision.md` layer names (ADR required) · `.env`, `secrets/` (never commit).

## Conflict resolution
Rules in this file win over individual specs. A spec conflicting with `docs/vision.md` is a blocker — open an issue before proceeding. When stuck, open a GitHub Discussion rather than guessing.
