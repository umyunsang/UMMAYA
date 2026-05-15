---
title: First Successful Session
description: What a successful first run should show, and what it must not claim.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
audience:
- new_user
- considering_user
- public_sector_evaluator
---

A first successful UMMAYA session proves a narrow but important path: the packaged command runs, the model provider is reachable, the query engine can process a citizen request, and the answer remains honest about Live, Mock, or Handoff state.

It does not prove that UMMAYA can complete every protected public-service action. The first run should test the harness with a safe public lookup, not with identity, payment, certificate issuance, tax filing, or official record changes.

## The First Session Timeline

A successful first session should be visible enough for a user to understand what happened. The exact UI may evolve, but the sequence should stay understandable.

```text
1. The `ummaya` command starts.
2. Provider setup or sign-in is available if needed.
3. The user asks a public-service question.
4. UMMAYA routes the request through the query engine.
5. A public adapter runs, or the system explains why no safe live action exists.
6. The final answer summarizes result, state, boundary, and next action.
```

The important part is not animation or branding. The important part is that the visible answer can be traced to a tool-backed path or a clear stop reason.

## A Good First Prompt

Use a prompt that is useful but low-risk:

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

This prompt gives a place, asks for public information, and asks for official/public grounding. It does not request identity verification, payment, certificate issuance, filing, or account-specific data.

## What The Answer Should Show

The answer should show enough structure for the user to trust the next step. It should include the public-service path, whether the step was Live, Mock, or Handoff, the source or adapter result that supports the answer, and a next action.

If UMMAYA cannot find a live public path, Handoff can still be a correct result. The product is behaving honestly when it refuses to invent official access.

## What Should Not Happen

A first session should not claim that UMMAYA issued a certificate, verified identity, paid a bill, submitted a tax return, changed an official record, or accessed personal account data. Those actions require official callable channels, credentials, explicit consent, and evidence.

The answer should also avoid vague authority. Phrases like `officially completed`, `verified`, `submitted`, or `paid` need live proof. Without that proof, the safer words are `prepared`, `found`, `explained`, or `handed off`.

## If The First Session Fails

Use the symptom to decide the next move. If the command is missing, return to Quickstart. If sign-in fails, fix provider setup. If the prompt returns Mock or Handoff, read the state label before treating it as a failure. If a public lookup fails, try a clearer location and one public information need.

The first session is successful when UMMAYA is honest and inspectable, not when it pretends to complete the hardest protected action.

## Where To Go Next

After the first public lookup, read [What You Can Ask](/en/start/what-you-can-ask/) to choose better prompts, then read [Live, Mock, And Handoff](/en/trust/live-mock-handoff/) before trying protected workflows.
