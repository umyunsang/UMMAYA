## Summary

- Add session-scoped FriendliAI `/login` and `/logout` through the CC local command router.
- Allow boot without a FriendliAI key, but fail closed before any model/backend request until a key is provided.
- Keep keys process-scoped only: `/login` installs the key into the running process environment and `/logout` clears it without writing to disk.
- Keep the CC login/logout/agents command structure and existing Dialog/TextInput UI while swapping credential handling to FriendliAI.
- Remove KOSMOS-only `/agents` swarm UI and SubscribePrimitive from the TUI, LLM, IPC, backend, schema, docs, and test surfaces; active primitives are now `lookup`, `resolve_location`, `submit`, and `verify`.
- Defer `subscribe` until KOSMOS has a real app/push-notification runtime instead of fabricating CLI-only notification UI.

## Verification

- `cd tui && bun test`
- `cd tui && bun run typecheck`
- `uv run pytest`
- `uv run pytest tests/llm/test_config.py`
- `uv run python scripts/build_schemas.py --check`
- `cd tui && bun run tui:smoke`
- `cd tui && NODE_ENV=test KOSMOS_FRIENDLI_TOKEN=test-token KOSMOS_FRIENDLI_SESSION_ACTIVE=1 bun run src/entrypoints/cli.tsx auth status --json`
- `cd tui && NODE_ENV=test bun run src/entrypoints/cli.tsx auth login`
- `git diff --check`

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
- `https://www.ips.go.kr/pot/forwardMain.do`
- `https://www.ips.go.kr/cht/ptl/main/gccJoinGdView.ndo`
- `https://www.law.go.kr/LSW/admRulSideInfoP.do?admRulSeq=2100000193836&chrClsCd=010202&docCls=jo&joBrNo=00&joChgYn=N&joNo=0002&langType=Ko&urlMode=admRulScJoRltInfoR`

Closes: none. No Epic issue was provided for this user-requested packaging auth follow-up, and no matching open FriendliAI auth Epic was found.
