# UX Snapshot Verification — Epic #1635 P4 UI L2

**Generated**: 2026-06-01
**Tool**: `tui/scripts/dump-ui-l2-snapshots.tsx`
**Method**: Each current UI L2 surface is rendered through the UMMAYA Ink runtime, normalized to plain text, and written to `specs/1635-ui-l2-citizen-port/ux-snapshots/*.txt` plus `INDEX.txt`.

## Summary

**26 / 26 surfaces rendered successfully** — 0 fail.

The script now verifies live components only. Stale surfaces that no longer exist in `tui/src/components` were removed from the snapshot set, and the replacement set covers the active citizen-facing surfaces:

- Welcome and grouped help surfaces.
- Primitive permission modals for `check`, reversible `send`, and irreversible `send`.
- `/consent` list and revoke-confirmation surfaces.
- Bypass-permissions, error-envelope, context quote, streaming, slash-autocomplete, and plugin-browser surfaces.
- Current primitive renderers for point, collection, detail, timeseries, find error, submit success, submit failure, and auth context.

## Reproduce

```bash
cd tui
bun run scripts/dump-ui-l2-snapshots.tsx
```

Expected result:

```text
Pass: 26 / Fail: 0 / Total: 26
```

## Scope

Covered:

- Component-level structural rendering.
- Text content and glyph presence in normalized terminal frames.
- Current permission, consent, plugin, slash-command, error, and primitive-render surfaces.

Not covered:

- Color-token fidelity after ANSI normalization.
- Interactive key traversal beyond focused component tests.
- Full operator-driven `bun run tui` walkthrough.
