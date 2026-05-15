---
title: What UMMAYA Can Do Today
description: Current capability explained by user task, status label, and evidence
  boundary.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- considering_user
- new_user
- public_sector_evaluator
---

UMMAYA can already demonstrate the core national AX pattern: a user asks for a public-service outcome, the system resolves intent, selects a tool path, and answers with a visible status boundary. The current surface is strongest for public lookup, location-dependent information, and preparation flows.

Protected actions are mostly Mock or Handoff until live authority, credentials, official callable channels, consent, and evidence are available. That limitation is not hidden. It is part of the product's trust model.

## Current Capability By User Task

Read this table by task, not by internal adapter name. A task may be useful today even when the final protected action is not live.

| User task | Current state | What UMMAYA should do |
|---|---|---|
| Find nearby hospitals or emergency-related public information | Live for public lookup adapters | Resolve place, call public healthcare or emergency adapters, and summarize source-backed results |
| Check weather, forecast, warning, road, or safety information | Live for public-data adapters | Retrieve public data, state recency and uncertainty, and avoid personal-account claims |
| Resolve addresses, coordinates, or administrative areas | Live for location adapters | Normalize location before public-service lookup |
| Explore welfare information and preparation | Live for public guidance, Mock/Handoff for protected applications | Find guidance, prepare documents, and mark official eligibility boundaries |
| Try identity, certificate, MyData, or authentication flows | Mock or Handoff | Show expected consent shape without claiming verification |
| Pay fines, submit applications, file tax, or change official records | Mock or Handoff unless a live channel is configured | Prepare, label, or hand off; never claim official completion without evidence |

The important word is "state." A Live public lookup and a Mock protected workflow are both useful, but they mean different things and must sound different in the final answer.

## What You Should Try First

Start with a safe public lookup. Give a location and ask for official public information.

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

This prompt is a good first test because it gives a place, requests public information, and does not ask UMMAYA to verify identity, pay, file, issue, or change an official record.

## How To Read Live, Mock, And Handoff

Live means UMMAYA can call a configured channel and ground the answer in the result. Mock means the workflow shape can be demonstrated, but it is not an official agency result. Handoff means the user must continue through an official service because UMMAYA does not have a safe callable path.

This distinction is not a legal footnote. It tells the user whether they are looking at evidence, simulation, or a next official step. The answer should make that state visible before the user acts.

## What Is Target-State

The target-state scenario dataset covers tax, civil affairs, payments, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, safety, immigration, legal, and personal-data workflows. Those scenarios are not all live today.

They define what a national AX system must eventually handle and how UMMAYA should label the gap while official channels mature. A domain can be part of the goal without being falsely described as complete today.

## Next Step

After reading capability, install the packaged CLI in [Quickstart](/en/start/quickstart/) and run one public lookup. Then read [Live, Mock, And Handoff](/en/trust/live-mock-handoff/) before testing protected workflows.
