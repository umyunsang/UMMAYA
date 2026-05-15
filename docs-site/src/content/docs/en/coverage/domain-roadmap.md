---
title: Domain Roadmap
description: How UMMAYA moves domains from target-state scenario to mock to live capability.
llm_index: true
audience:
  - considering_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
  - docs/api/README.md
---

The domain roadmap explains how UMMAYA grows without overclaiming. A domain can matter to national AX before it is live, but the docs must label its current state honestly.

The roadmap is not a wish list. It is a promotion ladder: scenario, mock, live, and then richer live workflows as official channels and credentials become available.

## Target Domains

UMMAYA's target map follows citizen work, not agency org charts.

| Domain | Target user work |
|---|---|
| Safety and healthcare | find public safety, hospital, emergency, weather, and hazard information |
| Housing and local records | prepare moving, address, housing, and local-service workflows |
| Welfare and household support | find guidance, prepare documents, expose eligibility boundaries |
| Tax, fines, payments, utilities | prepare filings, payment paths, receipt expectations, and official handoff |
| Identity, certificates, MyData | explain official paths, consent points, and protected data flows |
| Labor, education, immigration, legal | map multi-agency guidance and target-state workflows |

This table defines demand. It does not say every row is Live today.

## Promotion Logic

A domain moves from scenario to Mock when the public shape is clear enough to mirror responsibly. It moves from Mock to Live only when the project has an official callable channel, credential path if needed, schema, permission metadata, sanitized request/response artifact, and test strategy.

The promotion rule prevents the docs from turning ambition into a false current-state claim. A target-state domain can stay valuable as Handoff while the official channel is unavailable.

## Why Planned Domains Still Matter

National AX is judged by the full citizen journey. A student portfolio project cannot live-complete every protected system today, but it can show the caller architecture, evidence ladder, and honest gap for each domain.

Planned domains give the query engine, adapter model, permission UX, and docs a future-facing test. They also show where public infrastructure would need callable, consented, LLM-safe channels for UMMAYA to become more complete.

## Roadmap Evidence

Roadmap claims should trace to at least one artifact: target-state scenario, adapter metadata, public API documentation, policy citation, schema, fixture, or issue/spec. If none exists, the domain should be described as a research target rather than a planned capability.

This evidence rule keeps the roadmap useful for contributors. It tells them whether the next action is research, mock adapter, live credential validation, permission design, or docs update.

## Next Step

Use the roadmap with [Current Coverage](/en/coverage/current-coverage/) and [Adapter Matrix](/en/coverage/adapter-matrix/). Together they answer three different questions: what users need, what UMMAYA can do now, and what evidence would justify promotion.
