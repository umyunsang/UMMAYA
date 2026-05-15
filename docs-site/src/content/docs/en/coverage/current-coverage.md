---
title: Current Coverage
description: Current UMMAYA capability by user task, status label, and evidence source.
llm_index: true
audience:
  - considering_user
  - public_sector_evaluator
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

Coverage means what public-service path UMMAYA can represent with evidence. It does not mean every task in a domain can be completed today.

Read coverage by user outcome and state label. Live, Mock, Handoff, and Planned are different promises, and the docs should not blur them.

## Coverage Summary

| User outcome | Current state | Evidence source |
|---|---|---|
| Weather, forecast, warning, and public safety lookup | Live | KMA and related public-data adapters where configured |
| Road accident and hazard lookup | Live | KOROAD public-data adapters where configured |
| Hospital and emergency information lookup | Live | HIRA, NMC, NFA119-style public adapters where configured |
| Location and administrative area resolution | Live | JUSO, Kakao, SGIS-style location adapters where configured |
| Welfare public guidance | Live for public guidance | MOHW public guidance/search surfaces where configured |
| Traffic fine payment and welfare application submission | Mock | Shape-faithful `send` adapters |
| Digital OnePass, simple auth, mobile ID, certificates, MyData | Mock or Handoff | `check` mock adapters and scenario docs |
| Government24/Hometax final submissions | Handoff or target-state | Requires official callable channel, credential, consent, and artifacts |

The table is a current-state map, not a product promise for every subtask. A domain can be represented in a target-state scenario and still be Handoff today.

## How To Read A Coverage Claim

A strong coverage claim has three parts: user task, state label, and evidence. "Healthcare is supported" is too broad. "Nearby public hospital lookup is Live where the configured public adapter returns evidence" is a better claim.

This wording protects the user from assuming that public lookup, personal medical records, triage, and emergency dispatch are the same capability. It also gives evaluators a concrete artifact to inspect.

## What Evaluators Should Check

Evaluators should look for false promotion. A page is wrong if it describes Mock as official completion, protected workflow without consent evidence, public-data answer without a source, or target-state channels as current Live capability.

The adapter matrix, generated metadata, scenario matrix, and architecture pages should agree. If one surface says Live and another says Handoff, treat that as documentation drift until the underlying evidence is reconciled.

## What Users Should Do Next

Start with Live public lookup tasks, then try Mock or Handoff flows only after reading the trust pages. If you need a binding official action, continue through the official service unless UMMAYA shows live authority and receipt evidence.
