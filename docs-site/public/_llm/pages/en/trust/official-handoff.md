---
title: Official Handoff
description: What should happen when UMMAYA reaches a boundary that only an official
  service can complete.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/api/README.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

Official Handoff is how UMMAYA stays useful without pretending to be the government. When a workflow reaches identity verification, certificate issuance, payment, filing, application submission, or official record change, the safest result is often to prepare the path and stop.

Handoff should not feel like abandonment. A good handoff tells the user what was prepared, what remains official, and what to carry into the official service.

## What A Good Handoff Includes

A good Handoff answer should include five pieces:

| Piece | Purpose |
|---|---|
| Official continuation path | tells the user where the real authority lives |
| Prepared context | preserves what UMMAYA already resolved or found |
| Missing authority | explains why UMMAYA stopped |
| Required evidence or credential | tells the user what the official step will need |
| Next action | turns the stop into a usable plan |

If the answer only says "go to the official site", it is too thin. If it says "completed" without live proof, it is unsafe.

## Example

```text
UMMAYA prepared the certificate issuance path and identified the official authentication step.
It did not verify identity or issue the certificate in this session.
Continue through the official certificate service with your required authentication method.
```

This wording is useful because it separates preparation from completion. It also tells the user what did not happen.

## Why Handoff Is A Product Feature

Handoff may look like a limitation, but it is part of the safety design. National-infrastructure work crosses legal authority, personal data, money, and official records. A system that cannot prove authority should stop clearly.

The user still benefits when UMMAYA reduces confusion before that stop. The system can explain the route, prepare documents, identify likely consent points, and preserve context for the official step.

## How Handoff Becomes Live

A Handoff path can become Live only when the project has an official callable channel, credential path, schema, permission metadata, sanitized artifacts, and tests that prove the adapter behavior. The docs should not promote a Handoff domain to Live because the target state is desirable.

Promotion changes the user's trust decision. That is why the evidence must change before the wording changes.

## Recovery

If the user wants to continue after Handoff, UMMAYA should help them prepare for the official service rather than bypass it. It can summarize what to bring, what login or certificate may be required, and what previous context should be reused.

The correct close is practical: `UMMAYA stopped here because official authority is required; here is the next official step.`
