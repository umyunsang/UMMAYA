## Summary

- Add session-scoped FriendliAI `/login` and `/logout` commands in the TUI.
- Allow boot without a FriendliAI key, but fail closed before any model/backend request until a key is provided.
- Keep keys process-scoped only: `/login` installs the key into the running process environment and `/logout` clears it without writing to disk.
- Replace Anthropic OAuth CLI behavior with KOSMOS FriendliAI session-auth guidance and status output.

## Verification

- `cd tui && bun test tests/unit/friendliAuth.test.ts tests/entrypoints/envGuard.test.ts tests/components/FriendliLoginDialog.test.tsx tests/ipc/handlers.test.ts tests/components/help/HelpV2Grouped.test.ts tests/components/PromptInput/SlashCommandSuggestions.test.tsx tests/commands/config.test.ts tests/components/config/ConfigOverlay.test.ts tests/components/onboarding/PreflightStep.test.tsx tests/commands/help.test.ts`
- `uv run pytest tests/llm/test_config.py`
- `cd tui && bun run typecheck`
- `cd tui && bun run test`
- `cd tui && bun run tui:smoke`
- `cd tui && NODE_ENV=test KOSMOS_FRIENDLI_TOKEN=test-token bun run src/entrypoints/cli.tsx auth status --json`
- `cd tui && NODE_ENV=test bun run src/entrypoints/cli.tsx auth login`
- `git diff --check`

`cd tui && bun run typecheck:full` still fails on the existing repo-wide full TypeScript surface; the project gating `bun run typecheck` passed.

## TUI Artefacts

- PTY scenario: `specs/friendli-session-auth/scripts/pty-login-flow.ts`
- PTY captures: `specs/friendli-session-auth/pty-final-success/`
- VHS scenario: `specs/friendli-session-auth/scripts/friendli-login-flow.tape`
- VHS captures: `specs/friendli-session-auth/vhs/`
- Verification index: `specs/friendli-session-auth/verification.md`

## References

- `docs/vision.md`
- `docs/requirements/kosmos-migration-tree.md`
- `.references/claude-code-sourcemap/restored-src/src/commands/login/login.tsx`
- `.references/claude-code-sourcemap/restored-src/src/commands/logout/logout.tsx`

Closes: none. No Epic issue was provided for this user-requested packaging auth follow-up, and no matching open FriendliAI auth Epic was found.
