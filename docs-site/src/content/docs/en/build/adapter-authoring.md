---
title: Adapter Authoring
description: How contributors should wrap one public-service channel as one evidence-bearing UMMAYA adapter.
llm_index: true
audience:
  - adapter_author
  - maintainer
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - docs/plugins/security-review.md
---

An adapter is the unit of UMMAYA expansion. One adapter should wrap one public-service channel, mockable policy shape, or official handoff path as one tool entry with schema, citation, state label, and permission metadata.

Adapter authoring is not only backend work. The adapter determines what the docs may honestly claim, what the model may call, what permission the user sees, and what evidence the final answer can cite.

## Choose The Correct State First

Before writing code, classify the channel.

| State | Use when | Documentation consequence |
|---|---|---|
| Live | official callable channel and credential path exist | docs may describe evidence-backed execution within scope |
| Mock | channel shape is known or policy-mandated, but live access is unavailable | docs must label simulation |
| Handoff | next step belongs to an opaque official service | docs should prepare the path and stop |
| Planned | target-state demand exists but shape/evidence is not ready | docs may describe roadmap, not current capability |

This decision must happen first because it changes schema, tests, permission wording, and user-facing claims.

## Required Contents

A useful adapter needs enough structure for the query engine and docs to agree.

| Requirement | Why it matters |
|---|---|
| primitive | ties the adapter to `locate`, `find`, `check`, or `send` |
| input/output schema | prevents plausible but invalid tool calls |
| Live/Mock/Handoff state | controls user-facing authority language |
| permission tier | separates public lookup from protected action |
| public or policy citation | prevents UMMAYA-invented authority |
| fixture or artifact | makes Mock or Live behavior inspectable |
| search hints | lets retrieval find the adapter from citizen language |

If the adapter lacks these fields, the docs should not promote it as evidence for a user workflow.

## User Documentation Requirement

Every adapter that affects user-facing coverage needs prose. The prose should say what the adapter can support, what it cannot support, what status label applies, and what answer language is safe.

For example, a public weather adapter can support Live weather lookup. It cannot support personal disaster benefit eligibility unless a separate protected path exists. The docs should keep those claims separate.

## Promotion Requirement

Promotion from Mock to Live requires evidence, not optimism. The project needs official endpoint or channel validation, credential handling, schema validation, permission metadata, sanitized request/response artifacts, and tests that do not call live citizen infrastructure from CI.

After promotion, regenerate the docs surfaces and review affected pages:

```bash
npm run docs:generate
npm run docs:check
```

If the generated adapter metadata changes, user docs and LLM-readable docs must change with it.

## Failure Mode

The common failure is adding a tool and then writing broad marketing copy. UMMAYA should do the reverse: prove the channel shape, define the boundary, then let the docs claim only what the evidence supports.
