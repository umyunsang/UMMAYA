---
title: Live, Mock, And Handoff
description: The status labels that keep UMMAYA honest about what it can actually do.
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - docs/api/README.md
---

Live, Mock, and Handoff are the trust language of UMMAYA. They tell the user whether the system actually called a configured channel, simulated a known workflow shape, or stopped because the next step belongs to an official service.

These labels are not implementation details. They are how UMMAYA avoids sounding more authoritative than its evidence allows.

## Live

Live means UMMAYA can call a configured public-service channel and ground the answer in the returned result. A Live answer should name the relevant source or adapter, summarize the result, and stay within what the result proves.

Live does not mean every action in the domain is available. A weather lookup may be Live while a user-specific disaster-support application is Handoff. A hospital public lookup may be Live while medical triage remains outside UMMAYA.

## Mock

Mock means UMMAYA can demonstrate the shape of a workflow without producing an official agency result. Mock is useful for testing tool calling, schemas, permission prompts, receipts, and UX before live credentials or official access are available.

Mock is dangerous when it sounds official. A mock payment is not paid. A mock certificate is not issued. A mock identity check is not identity verification. The word Mock must be visible near the result, not hidden in developer-only metadata.

## Handoff

Handoff means UMMAYA can prepare or explain the path, but the user must continue through an official service. Handoff is the correct result when the next step requires identity, payment, certificate issuance, tax filing, official record change, or another authority UMMAYA does not hold.

A good Handoff is still useful. It should name the official service or category, explain what UMMAYA prepared, identify what it did not do, and tell the user what evidence or credential would be required for a live path.

## How To Read A Status Label

Use the label before acting on the answer.

| Label | What happened | How to treat the result |
|---|---|---|
| Live | A configured channel returned evidence | Use the result within its stated scope |
| Mock | A known workflow shape was simulated | Treat it as demonstration, not official output |
| Handoff | UMMAYA stopped at an official boundary | Continue through the official service |
| Planned | The domain is part of the target state | Do not treat it as current capability |

If an answer does not expose a label for a consequential workflow, ask UMMAYA to clarify the state before acting.

## User Rule

Trust the boundary more than the fluency. A short answer that says "Handoff required" is safer than a fluent answer that implies hidden government access.

The product is working when it stops visibly. National-infrastructure AX is not the removal of official authority; it is the reduction of confusion until authority is required.
