# FriendliAI Session Auth Verification

This directory contains PR verification artefacts for the FriendliAI session-scoped `/login` and `/logout` flow.

- `scripts/pty-login-flow.ts` drives the real TUI in a PTY with no Friendli credential present at boot.
- `pty-final-success/` stores plain-text PTY snapshots and frame samples from `scripts/bun-pty-capture.ts`.
- `scripts/friendli-login-flow.tape` drives the vhs visual smoke.
- `vhs/` stores GIF, TXT, ASCII, and PNG keyframes for boot, login dialog, masked input, login success, and logout success.
