---
title: UMMAYA Docs
description: Documentation for using, evaluating, and extending UMMAYA as a Korean national-infrastructure AX harness.
llm_index: true
audience:
  - non_user
  - considering_user
  - new_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/research/ummaya-docs-audience-audit-2026-05-15.md
  - docs/vision.md
---

UMMAYA is a conversational agent harness for Korean national-infrastructure AX. It lets a user ask for a public-service outcome through one approachable query surface while the system handles decomposition, tool selection, permission boundaries, evidence, and official handoff.

This documentation is written for four reader stages: people deciding whether UMMAYA is useful, new users trying the packaged CLI, evaluators checking whether claims are grounded, and contributors extending the adapter surface.

## Start Here

If you are new, read the Start section in order. It explains the user problem, current capability, installation path, first successful session, prompt shape, and what happens after a query.

| Page | Use it when |
|---|---|
| [Why UMMAYA](/en/start/why-ummaya/) | you need the product purpose |
| [What UMMAYA Can Do Today](/en/start/what-ummaya-can-do-today/) | you want current capability and limits |
| [Quickstart](/en/start/quickstart/) | you want to install and run the CLI |
| [First Successful Session](/en/start/first-successful-session/) | you want to know what success looks like |
| [What You Can Ask](/en/start/what-you-can-ask/) | you want better prompts |
| [What Happens After You Ask](/en/start/what-happens-after-you-ask/) | you want the user-level system loop |

The Start section should make UMMAYA understandable before the architecture becomes necessary.

## Trust Before Protected Work

Read the Trust section before testing identity, payments, certificates, welfare applications, tax filing, or official record changes. These workflows are where UMMAYA must be most careful.

Trust pages explain Live, Mock, Handoff, permission, consent, data, credentials, local sessions, official handoff, and explicit non-goals. They help the user distinguish public lookup from protected action and preparation from completion.

## Use UMMAYA By Situation

The Use section is organized by real public-service situations: emergency and safety, moving and housing, welfare, tax and payments, identity and certificates, sessions and receipts, and troubleshooting.

Each page should answer the same practical questions: what can I ask, what should happen, where can UMMAYA act, where must it stop, and what should I do next?

## Evaluate Coverage And Architecture

Coverage pages show current capability, [Live Adapters](/en/coverage/live-adapters/), adapter evidence, target-state scenarios, and roadmap logic. Architecture pages explain why UMMAYA migrates the Claude Code-style harness, how primitives work, and how the query engine coordinates retrieval, tool calls, permission, and stop reasons.

Use coverage to check what is supported. Use architecture to check whether the system design can support the national AX goal.

## Build And Reference

Build pages are for adapter authors and maintainers. They explain adapter authoring and LLMOps for keeping docs, generated metadata, and deployment outputs aligned.

Reference pages expose LLM-readable docs so future agents can inspect the same boundaries as human readers.

## Reading Rule

Whenever a page makes a capability claim, look for its state label and evidence. If a task is Live, the docs should say what supports it. If it is Mock or Handoff, the docs should make that boundary visible before the user acts.
