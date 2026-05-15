---
title: Permissions And Consent
description: How UMMAYA separates public lookup from protected public-service actions.
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - specs/033-permission-v2-spectrum-consent-ledger/spec.md
  - docs/api/README.md
---

Permissions and consent protect the user from invisible authority jumps. UMMAYA can often fetch public information directly, but protected actions require a visible decision before the system proceeds.

The rule is simple: public lookup may be convenient; protected action must be explicit. Identity, certificates, payments, filings, account-specific data, welfare submissions, and official record changes cannot be treated like ordinary search results.

## Public Lookup

Public lookup is the lowest-risk path. UMMAYA may resolve a location, fetch weather, retrieve road information, or summarize public guidance when the adapter and source support that lookup.

Even public lookup needs grounding. The answer should say what source or adapter shaped the result and what uncertainty remains. Public does not mean unlimited; it means the workflow does not require the user's protected authority.

## Protected Actions

Protected actions require a stronger gate because they can affect identity, money, benefits, records, or rights. UMMAYA should check the action class, adapter mode, credential requirement, and user consent before continuing.

If those conditions are missing, the correct result is Mock or Handoff. The system should not convert a protected action into a confident sentence just because the user asked directly.

## Consent Records

A consent record should answer four questions: what action is being allowed, why it is needed, which adapter or official path is involved, and what result will be produced. Without those details, consent becomes decorative.

For evaluator review, the consent record should also connect to mode and stop reason. A protected flow that claims completion must show live authority and evidence. A mock flow must show that it stayed mock.

## Safe Defaults

UMMAYA should fail closed when permission is unclear. It should ask for clarification, stop, or hand off instead of guessing. This is especially important for identity, payment, certificates, tax, welfare applications, and record changes.

Safe defaults may make the product feel slower, but they make it inspectable. The user can see why the system stopped and what official path remains.

## What The User Should See

The user should see permission before protected work, not after. The answer should name the protected action, the reason for consent, the status label, and the next step if consent or authority is unavailable.

If the UI or final answer hides this information, the documentation should treat that as a trust gap. UMMAYA's value depends on visible boundaries.
