# UMMAYA UI Wireframes

Interactive Ink wireframe previews for the KSC 2026 story and TUI design
handoff. Refreshed 2026-05-29 KST.

The active UI thesis is the same as the product thesis: keep Claude Code's
terminal harness behavior first, then apply UMMAYA's Korean public-service
wording, permission/authority boundaries, and `find/locate/check/send` tool
surface.

## File Inventory

| File | Purpose | Current use |
|---|---|---|
| `_shared.mjs` | Shared CC-style primitives: Box, Text, condensed logo, notices, prompt band, tool-use block | Active wireframe support |
| `proposal-iv.mjs` | Main KSC demo surface: empty state, public lookup, cross-agency planning, `/agents`, `/plugins` | Current presentation baseline |
| `ummaya-mascot-proposal.mjs` | Terminal mascot and home-call brand signal | Current brand reference |
| `ui-b-repl-main.mjs` | REPL main details: streaming, scroll, markdown, errors, context, autocomplete | Needs parity check before product work |
| `ui-c-permission.mjs` | Permission Gauntlet: Layer 1/2/3, receipt, history, revoke, mode switch | Needs `check/send` wording refresh before product work |
| `ui-e-auxiliary.mjs` | Help, config, plugin browser, export, history | Needs runtime parity check before product work |
| `ui-d-extensions.mjs` | Agent panel and swarm threshold exploration | Historical L2 proposal; current work should verify backend emit path first |
| `ui-a-onboarding.mjs` | Earlier 5-step onboarding proposal | Historical proposal; current `docs/vision.md` keeps setup aligned with the Claude Code runtime path |

## Run

```bash
cd tui

# Main presentation surface
bun ../docs/wireframes/proposal-iv.mjs
bun ../docs/wireframes/ummaya-mascot-proposal.mjs

# Drilldowns
bun ../docs/wireframes/ui-b-repl-main.mjs
bun ../docs/wireframes/ui-c-permission.mjs
bun ../docs/wireframes/ui-e-auxiliary.mjs
bun ../docs/wireframes/ui-d-extensions.mjs
bun ../docs/wireframes/ui-a-onboarding.mjs
```

## Active Design Rules

- Use ported Claude Code visual primitives first. New UI component shapes need a
  concrete product reason.
- Korean is primary. English is allowed for agency codes, model names, and
  developer-facing command names.
- The active primitive roots are `find`, `locate`, `check`, and `send`.
- `subscribe` is deferred until UMMAYA owns an app/push delivery runtime.
- Dot color encodes the primitive family, not the agency:
  - blue: `find`
  - cyan: `locate`
  - red: `check`
  - orange: `send`
  - purple: plugin namespace
- Mock and handoff boundaries must be disclosed in result copy or evidence. Do
  not rely on dot color to make authority claims.
- Protected flows should show `check` before `send`; public location/data flows
  should show `locate` before concrete `find` when location is needed.
- Any future product implementation must compare against
  `.references/claude-code-sourcemap/restored-src/` before inventing a new TUI
  path.

## KSC Presentation Use

Use `proposal-iv.mjs` as the thumbnail test for the talk:

1. Empty state should communicate "UMMAYA is a CC-style terminal harness."
2. Public lookup should show `find` or `locate -> find`, not generic RAG.
3. Protected execution should show `check -> send` with receipt/handoff wording.
4. `/agents` should be framed as coordination visibility, not proof that every
   agency integration is Live.
5. `/plugins` should show contributor extensibility without implying official
   endorsement.

## See Also

- `docs/vision.md`
- `docs/requirements/ummaya-migration-tree.md`
- `docs/onboarding/five-primitive-harness.md`
- `docs/design/verification-fabric-v2.md`
- `.references/claude-code-sourcemap/restored-src/src/components/`
