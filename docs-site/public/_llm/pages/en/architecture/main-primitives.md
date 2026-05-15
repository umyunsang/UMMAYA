---
title: Main Primitives
description: The small verb surface UMMAYA exposes to the model while adapters carry
  domain detail.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs/requirements/ummaya-migration-tree.md
- docs/api/README.md
- docs-site/src/data/generated/adapters.json
- docs/api/schemas/find.json
- docs/api/schemas/locate.json
- docs/api/schemas/check.json
- docs/api/schemas/send.json
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

UMMAYA exposes a small primitive surface because national-infrastructure domains are too broad to place every agency verb in the model prompt. The model should reason over the user's outcome and call one of a few stable verbs. The adapter layer carries the domain-specific details.

The primitive layer is the compression point between a citizen sentence and a fragmented state infrastructure. It prevents two failures at once: the user should not have to speak in agency API names, and the model should not receive a prompt stuffed with every possible ministry operation. UMMAYA keeps a small root vocabulary and lets retrieval inject the right adapter details only for the current turn.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="Minimal C4 component diagram: Context, Retrieve, Primitives, Validate, Gate, Dispatch, and Stop." />
  <figcaption>Primitive view: retrieval narrows the surface, primitives choose the verb, validation and gates keep the action bounded.</figcaption>
</figure>

## Primitive Summary

| Primitive | Meaning | Typical user wording | Boundary |
|---|---|---|---|
| `locate` | Resolve place, address, coordinate, or administrative area | near me, this district, this address | Public unless provider or input changes the risk |
| `find` | Fetch public information through a selected adapter | find, show, retrieve, source says | Fetch-only; backend retrieval selects candidates first |
| `check` | Evaluate a condition through a live or mock protected path | am I eligible, verify requirements | Requires classification and often consent |
| `send` | Prepare or submit through a wrapped channel when allowed | submit, file, pay, request | Live only with official channel, credential, consent, and evidence |

## Why Primitives Stay Small

The user should not need to know agency APIs. The model should not memorize every agency surface. Retrieval finds relevant adapters and injects descriptions for the current turn. The model then chooses the smallest primitive that can move the workflow forward.

This is a deliberate tradeoff. A larger root verb set would look expressive at first, but it would leak domain assumptions into the model-facing surface. `pay`, `issue_certificate`, `apply_for_welfare`, and `change_address` sound useful, but each one hides agency-specific authority, credential, policy, and receipt requirements. UMMAYA keeps those details in adapters so every domain can carry its own evidence and permission boundary.

## How A Primitive Becomes A Real Action

```text
User wording
  -> intent and context assembly
  -> adapter retrieval
  -> primitive choice
  -> schema validation
  -> permission classification
  -> Live, Mock, or Handoff result
```

The primitive is not the adapter. `find` does not mean "search the whole internet"; it means "fetch public information through a selected adapter." `send` does not mean "submit anything the user asked for"; it means "prepare or execute a wrapped channel only when official authority, credential, consent, and evidence exist."

## Example Timelines

```text
User asks for nearby emergency information
  -> `locate` normalizes the place
  -> `find` calls a public emergency or hospital adapter
  -> final answer cites the result and urgent official boundary
```

```text
User asks to issue a certificate
  -> `find` may retrieve public guidance
  -> `check` may show a mock identity boundary
  -> Handoff occurs unless live issuance authority exists
```

```text
User asks about welfare support
  -> `find` retrieves public program information
  -> `check` evaluates requirements only through a classified path
  -> `send` prepares an official-path checklist or stops at Handoff
```

## Where Domain Knowledge Lives

| Layer | What belongs there | What must not leak there |
|---|---|---|
| Primitive | Stable action shape and input/output envelope | Ministry-specific policy or credential logic |
| Adapter | Agency endpoint, schema, citation, fixture, Live/Mock/Handoff status | Hidden recovery paths not proven by evidence |
| Permission pipeline | Consent gate and protected-action classification | UMMAYA-invented authority |
| Final answer | Grounded result, boundary, and next action | Claims not backed by the tool result |

This separation keeps UMMAYA scalable. Adding one more agency should mean adding one more evidence-bearing adapter and registering it, not teaching the model a new root verb for every public-service workflow.

## Schema Discipline

Each primitive uses a structured envelope. The current `find` contract is fetch-only: candidate search happens before the call. This prevents hidden search modes from becoming an undocumented second tool system.

The discipline matters most during failure. If arguments are invalid, the primitive call fails at validation. If the adapter is Mock, the answer must say so. If no official channel exists, `send` becomes Handoff material rather than fictional completion. The small verb surface is useful only because every call is tied to schema, evidence, and a visible stop condition.
