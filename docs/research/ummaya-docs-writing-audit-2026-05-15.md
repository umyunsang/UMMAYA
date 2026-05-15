# UMMAYA Docs Writing Audit

Date: 2026-05-15

## Scope

Architecture pages are excluded because the user approved their paragraph structure,
logic, and depth. This audit covers the remaining English source pages and then
requires equivalent `ko`, `ch`, and `jg` rewrites with no fallback content.

## Method

The audit uses the rewritten `ummaya-doc-writing` skill:

- original creative-writing PDF as method source;
- 3C for correctness, concision, clarity;
- reader-first page card;
- Why/How frame selection;
- MECE body axes;
- Power 1-2-3-4 paragraph test;
- Live/Mock/Handoff boundary check;
- first-class locale equivalence.

## Findings

Architecture now meets the target style, but most other pages still read like
expanded notes rather than fully developed documentation. The failure pattern is
consistent:

- headings are good, but many sections contain only one short paragraph;
- lists and tables appear before the reader is told how to use them;
- scenario pages name user prompts but do not always show expected behavior,
  stop reason, and recovery;
- trust pages state prohibitions but need more causal explanation and visible
  user consequences;
- coverage pages list status but need stronger evidence and evaluation guidance;
- build/reference pages name artifacts but need drift gates and operating
  boundaries.

## Metric Snapshot

English pages outside architecture: 26.

Pages with four or more short H2 sections:

- `build/adapter-authoring.md`
- `build/llmops.md`
- `coverage/adapter-matrix.md`
- `start/first-successful-session.md`
- `start/quickstart.md`
- `start/what-happens-after-you-ask.md`
- `trust/what-ummaya-will-not-do.md`
- `use/emergency-healthcare-weather-safety.md`
- `use/sessions-receipts-history.md`
- `use/tax-fines-payments-utilities.md`
- `use/troubleshooting.md`
- `use/welfare-household-support.md`

Pages with empty or prompt-only sections:

- `use/emergency-healthcare-weather-safety.md`
- `use/identity-certificates-mydata.md`
- `use/moving-housing-local-records.md`
- `use/tax-fines-payments-utilities.md`
- `use/welfare-household-support.md`

Pages with weak evidence/trace language:

- `build/llmops.md`
- `coverage/scenario-matrix.md`
- `reference/llm-readable-docs.md`

## Rewrite Direction

Use page-type patterns from the skill:

- Start pages: problem, promise, concrete action, honest boundary, next page.
- Use pages: scenario, expected flow, good answer shape, boundary, recovery.
- Trust pages: protected action, why boundary exists, visible system behavior,
  what UMMAYA will not do, official handoff.
- Coverage pages: current status, evidence source, gap, roadmap or contribution.
- Build/reference pages: task, required file/schema, validation command, drift
  gate, contribution boundary.

## Completion Gate

The docs rewrite is not complete until:

- every non-architecture page has a clear opening claim;
- no H2 section is only a heading plus a hollow sentence;
- every user-facing workflow page has example prompt, expected flow, answer
  shape, stop boundary, and recovery/next action;
- every trust/coverage/build/reference page names evidence or a drift gate;
- `en`, `ko`, `ch`, and `jg` retain equivalent heading hierarchy and meaning;
- `npm run docs:generate` and `npm run docs:check` pass.
