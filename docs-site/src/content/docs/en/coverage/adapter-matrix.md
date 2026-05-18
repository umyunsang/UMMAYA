---
title: Adapter Matrix
description: The evidence ledger behind UMMAYA coverage, adapter status, and primitive support.
llm_index: true
audience:
  - public_sector_evaluator
  - adapter_author
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
  - docs/api/verified-data-go-kr/README.md
---

The adapter matrix is the evidence ledger behind user-facing coverage. Each adapter wraps one public-service channel or mockable shape as one tool entry. Without this ledger, the docs would be only claims.

Users do not need to read adapter IDs first, but evaluators and contributors do. A Live statement should trace back to an adapter or generated metadata entry that explains primitive, state, permission, schema, and citation.

## Current Shape

The generated adapter data currently represents three broad groups:

- 42 live `find` adapters for public lookup domains such as weather, road, bus, hospital, emergency, welfare guidance, jobs, procurement, legal/public records, and statistics;
- location and administrative-area adapters that support `locate`;
- mock `check` or `send` adapters for identity, certificate, authentication, MyData, protected submission, or payment-shaped workflows.

Registry count evidence separately validates the 4 main primitive surfaces: `find`, `locate`, `check`, and `send`, plus non-core adapter registry entries. This split mirrors UMMAYA's trust model. Public lookup can often be Live earlier. Protected completion requires stronger authority and usually remains Mock or Handoff until official access exists. Read [Live Adapters](/en/coverage/live-adapters/) for user-task grouping, then use this matrix and `docs/api/README.md` for canonical row-level evidence.

## What Each Adapter Must Carry

A useful adapter is not only a function. It must carry enough metadata for the query engine, permission layer, docs, and evaluator to agree.

| Field | Why it matters |
|---|---|
| tool ID | stable reference for docs, traces, and generated metadata |
| primitive | tells the model whether the path is `locate`, `find`, `check`, or `send` |
| tier | distinguishes Live, Mock, Handoff, or Planned state |
| permission tier | prevents protected work from becoming silent execution |
| schema path | validates arguments and output shape |
| citation or source | proves that the adapter follows an external boundary |

If a field is missing, the adapter may still be code, but it is not ready to support a strong documentation claim.

## Why This Matters To Users

The matrix protects users from vague coverage language. When a page says UMMAYA can find public safety information, the adapter evidence should show which public lookup path supports that claim. When a page says a payment flow is Mock, the matrix should prevent the final answer from sounding like a paid bill.

That is why adapter metadata is part of user trust, not only developer inventory.

## Where To Inspect

The canonical adapter catalog lives in `docs/api/README.md`. Generated metadata merges catalog rows with individual adapter front matter, then copies the result into `docs-site/src/data/generated/adapters.json` and `/_llm/generated/adapters.json`.

After adapter changes, run:

```bash
npm run docs:generate
npm run docs:check
```

If generated metadata changes but prose does not, review the affected pages before publishing. That is the docs drift gate.
