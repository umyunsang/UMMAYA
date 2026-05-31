# Conventions

Detailed development conventions for UMMAYA. `AGENTS.md` summarizes the cross-cutting rules; this file is the long form.

## Source code language

All source code text must be in English: comments, docstrings, log messages, error messages, CLI output strings, commit messages, PR titles and bodies, variable and function names.

**Exception**: Korean domain data — real civil-affairs content, legal terms, `data.go.kr` response fields as returned by Korean ministries, citizen-facing example dialogues in design docs — is preserved as-is. Do not translate real data.

Rationale: keeps the project legible to international contributors while respecting that the target domain is Korean.

## Environment variables

All environment variables must be prefixed `UMMAYA_`.

| Variable | Purpose |
|---|---|
| `UMMAYA_FRIENDLI_TOKEN` | FriendliAI Serverless API token |
| `UMMAYA_DATA_GO_KR_KEY` | data.go.kr API key |
| `UMMAYA_LOG_LEVEL` | stdlib logging level (default `INFO`) |

- Document every required variable in `.env.example`
- Never commit `.env` or any file under `secrets/`
- Never hardcode keys in source, tests, or fixtures

## Logging

- Use stdlib `logging` with module-level loggers: `logger = logging.getLogger(__name__)`
- Default level `INFO`, configurable via `UMMAYA_LOG_LEVEL`
- No `print()` outside the CLI output layer (which uses `rich`)
- Never log personal data, API keys, or full citizen profiles — log IDs and categories only

## Commit messages

UMMAYA uses [Conventional Commits](https://www.conventionalcommits.org/).

Format: `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`

Examples:
```
feat(tools): add KOROAD traffic accident adapter
fix(query-engine): prevent cache invalidation on tool result push
docs(vision): clarify 7-step permission gauntlet
chore(deps): bump httpx to 0.28
```

Rules:
- Keep commits atomic — one logical change per commit
- Subject in imperative mood, under 72 characters
- Body explains *why*, not *what* — the diff shows *what*
- Squash noise before opening a PR

## Branches

| Prefix | Purpose |
|---|---|
| `feat/<scope>` | new feature |
| `fix/<scope>` | bug fix |
| `docs/<scope>` | documentation only |
| `refactor/<scope>` | internal restructuring |
| `test/<scope>` | tests only |
| `chore/<scope>` | tooling, CI, dependencies |

Examples: `feat/koroad-adapter`, `fix/cache-invalidation`, `docs/vision-layer-3`.

## Pull requests

- Prefer PRs for code changes. Direct commits to `main` are acceptable only for `docs:` and `chore:` changes touching no source code
- Keep PRs focused — a 2,000-line PR touching five layers is hard to review; split it
- Link the issue with `Closes #N`
- Fill out the PR template completely
- Ensure CI is green before requesting review
- Do not force-push after review starts unless asked

## CI checks

All PRs run the following status checks. Ensure CI is green before requesting human review.

### Required checks

| Check | Source | Fail action |
|---|---|---|
| Lint & Type Check | GitHub Actions | Fix lint/type errors |
| Test (Python 3.12) | GitHub Actions | Fix failing tests |
| Test (Python 3.13) | GitHub Actions | Fix failing tests |
| Conventional Commits (PR title) | GitHub Actions | Fix PR title format |
| CodeQL SAST | GitHub Actions | Fix security findings |
| Secret Detection | GitHub Actions | Remove secrets from code |
| Dependency Vulnerability Audit | GitHub Actions | Update vulnerable deps |

### Copilot Review Gate (advisory)

The **Copilot Review Gate** is a custom GitHub App (Cloudflare Worker) that bridges Copilot Code Review into the Checks tab. It is currently **non-required** (advisory).

**How it works:**
1. PR opened → `in_progress` check, waits for Copilot's first review
2. New commits pushed → `in_progress` check + GraphQL `requestReviewsByLogin` triggers Copilot re-review
3. Copilot review arrives → check updated based on severity classification

**Pass/fail criteria (severity-based):**

| Condition | Result |
|---|---|
| 0 inline comments | **pass** |
| 1+ `🔴 CRITICAL` comments | **fail** |
| 3+ `🟡 IMPORTANT` comments (no critical) | **fail** |
| 1–2 `🟡 IMPORTANT` + any `🟢 SUGGESTION` | **pass** (comments noted) |
| Only `🟢 SUGGESTION` comments | **pass** |

**When the gate fails:**
1. Open the PR **Checks** tab → click **Copilot Review Gate** → read the summary
2. Review Copilot's inline comments on the **Files changed** tab
3. Address critical/important issues, push fixes → Copilot re-reviews automatically
4. The `copilot-review-bypass` label skips the gate (emergency hotfixes only)

**Configuration:**
- Severity prefixes are instructed via `.github/copilot-instructions.md`
- Worker source: `infra/copilot-gate-app/src/index.ts`
- Copilot comments without a recognized prefix default to `🟡 IMPORTANT`

## Task linking

Task issues come **only** from reviewed `tasks.md` via `/speckit-taskstoissues`. After creation, link each as a sub-issue of its Epic:

```bash
TASK_ID=$(gh api graphql -f query='query{repository(owner:"umyunsang",name:"UMMAYA"){issue(number:TASK_NUM){id}}}' --jq '.data.repository.issue.id')
gh api repos/umyunsang/UMMAYA/issues/EPIC_NUM/sub_issues --method POST -f sub_issue_id="$TASK_ID"
```

## PR closing

Every PR body must include `Closes #EPIC` for each Epic it completes. **Do NOT include Task sub-issues** — GitHub fails to auto-close when there are too many (50+).

```
Closes #EPIC_1
Closes #EPIC_2
```

After merge, verify Epics are closed and manually close any remaining Task sub-issues:

```bash
gh api repos/umyunsang/UMMAYA/issues/EPIC_NUM/sub_issues --jq '.[].number' | while read num; do
  gh issue close "$num" --comment "Completed in PR #NNN"
done
```

## Git safety

Never:
- `git push --force` on `main`
- `git commit --no-verify` (skip hooks)
- `git commit --no-gpg-sign` (bypass signing)
- `git reset --hard` on published commits
- Amend commits that are already pushed to `main`

## Code style

- **Python**: PEP 8, type-hint public APIs, `ruff` + `mypy` when configured
- **Imports**: stdlib → third-party → local, separated by blank lines
- **Line length**: 100 characters (ruff default)
- **Docstrings**: Google style, one-liner for trivial functions, full form for public APIs
- **Pydantic**: v2 only, never `Any` for tool inputs or outputs

## Prompt Registry (Spec 026 / Epic #467)

Runtime prompts live under `prompts/` and are addressed by a SHA-256-integrity manifest.

Every prompt change follows this loop:
1. Edit or add a file under `prompts/` (e.g., `prompts/system_v2.md`).
2. Regenerate `prompts/manifest.yaml` via `uv run python -m ummaya.context.prompt_loader --regenerate-manifest`.
3. Open the PR — the Evidence Fabric workflow fires automatically on any PR touching `prompts/**`, validates the scenario contract, and emits a typed `.evidence/run.json` artifact for review.
4. The `lint` lane validates `prompts/manifest.yaml` against `specs/026-cicd-prompt-registry/contracts/prompts-manifest.schema.json`; schema drift fails the PR.

Fail-closed rules at boot (enforced by `PromptLoader`):
- Missing file listed in manifest → `PromptRegistryError`.
- SHA-256 mismatch between file bytes and manifest entry → `PromptRegistryError`.
- Orphan `.md` under `prompts/` not listed in manifest → `PromptRegistryError`.

Korean content is permitted inside prompt bodies only. All other source text remains English.
