---
title: What Happens After You Ask
description: A user-level view of query routing, tool calls, permission gates, and final answers.
llm_index: true
audience:
  - new_user
  - active_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs-site/src/data/generated/adapters.json
---

After you ask a question, UMMAYA should not simply generate prose from memory. It turns the request into a controlled workflow that may resolve location, retrieve adapter candidates, call tools, ask permission, stop at Handoff, or synthesize a grounded answer.

This page explains the loop in user language. The architecture pages go deeper, but the user-level rule is simple: UMMAYA should show what it did, what evidence it used, and where it stopped.

## One Turn In Plain Language

One turn starts with your request and ends with either an answer, a question, or a visible stop.

```text
You ask for a public-service outcome
  -> UMMAYA keeps the session context
  -> relevant adapters are selected
  -> the model chooses `locate`, `find`, `check`, `send`, or an answer
  -> arguments are validated
  -> permission and mode are checked
  -> a Live adapter runs, a Mock is replayed, or Handoff is produced
  -> the result is returned to the answer
```

The loop may repeat when one result creates another need. A moving workflow may need location resolution before a checklist, and a protected submission step may stop at official Handoff.

## Why Tools Matter

Tools make the difference between a helpful explanation and a grounded public-service path. A chatbot can say what might be true. UMMAYA should show which public data, adapter metadata, schema, or handoff boundary shaped the answer.

This does not mean every answer becomes an action. Sometimes the right tool result is "no live path" or "official Handoff required." That is still more honest than an unsupported answer.

## Why Permission Matters

Public lookup can often proceed without a modal permission prompt. Protected actions cannot. Identity, certificate, payment, filing, account-specific lookup, and official record changes require explicit authority and evidence.

UMMAYA does not invent permission classes. The adapter must carry policy metadata and citations, and the permission pipeline enforces the boundary. If the boundary is missing, the system should stop rather than sound official.

## Why Context Matters

Administrative work can span many turns. The context layer keeps the system prompt, session history, adapter candidates, tool results, and permission state compact enough for the model to use.

Context compression exists because national AX workflows can be longer than a single lookup. It should preserve the important state: resolved location, selected adapter, Live/Mock/Handoff label, consent decision, result summary, and stop reason.

## What You Should See In The Answer

A good answer should include:

- what UMMAYA understood you wanted;
- what source or adapter it used;
- whether the path was Live, Mock, or Handoff;
- what result or stop reason came back;
- what remains official or user-controlled;
- what to do next.

If these pieces are missing, the answer may still be fluent, but it is not inspectable enough for national-infrastructure work.
