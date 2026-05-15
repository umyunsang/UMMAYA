---
title: Agentic RAG And Query Engine
description: How retrieval, reasoning, tool calling, permission gates, and stop reasons work in one UMMAYA turn.
llm_index: true
audience:
  - public_sector_evaluator
  - maintainer
  - llm_agent
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - specs/005-query-engine/spec.md
  - specs/006-tool-system/spec.md
  - specs/026-retrieval-dense-embeddings/spec.md
  - specs/032-stdio-tui-to-python-ipc-hardening/spec.md
---

UMMAYA uses retrieval for actions, not only for prose. The query engine receives a citizen request, retrieves adapter candidates, lets K-EXAONE choose a primitive, validates the call, checks permission, dispatches Live or Mock behavior, or produces Handoff. The final answer is synthesized from that evidence.

This page is for evaluators and maintainers who need to know whether UMMAYA is actually agentic or merely narrating search results. The answer is in the turn structure: retrieval narrows the action surface, reasoning chooses the next bounded action, tool execution produces evidence, and the stop reason decides whether the system can continue.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-03-query-engine-core.svg" alt="Minimal C4 component diagram: Context, Retrieve, Primitives, Validate, Gate, Dispatch, and Stop." />
  <figcaption>Query engine view: context, retrieval, primitive choice, validation, permission, dispatch, and stop are separate control steps.</figcaption>
</figure>

## One Turn In Detail

```text
1. User asks for a public-service outcome.
2. Context assembly packages session state, prior results, policy mode, and runtime facts.
3. Adapter retrieval ranks candidate tools by domain, hints, primitive support, tier, schema, and citation metadata.
4. The prompt receives the relevant adapter set and primitive contracts.
5. K-EXAONE chooses to answer, ask a question, or call a primitive.
6. The query engine validates the tool call envelope.
7. Permission classification decides safe, consent-gated, blocked, Mock, or Handoff behavior.
8. The adapter runs live, replays a mock, or emits handoff material.
9. Tool results are projected back into the model conversation.
10. The final answer states evidence, boundary, and next action.
```

The important point is ordering. UMMAYA should not write the answer first and then decorate it with sources. It should gather the minimum context needed to choose a tool, run the tool through validation and permission gates, then answer from the returned result or explain why the workflow stopped.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-04-public-lookup-flow.svg" alt="Minimal C4 dynamic diagram: Citizen asks, UI routes, Query Engine selects, Adapters call Public APIs, and UI answers." />
  <figcaption>Public lookup view: `find` can answer only after adapter evidence returns from a Live public channel.</figcaption>
</figure>

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-05-protected-handoff-flow.svg" alt="Minimal C4 dynamic diagram: Citizen asks, UI routes, Query Engine checks permission, Adapters reach Official Channels, and UI stops or hands off." />
  <figcaption>Protected action view: `check` and `send` must pass permission or stop at Handoff instead of pretending completion.</figcaption>
</figure>

## Why This Is Agentic RAG

Traditional RAG retrieves documents so the model can answer. UMMAYA retrieves tool candidates so the model can choose a safe action. The answer comes after tool results, permission events, and stop reasons are known.

That difference matters for national infrastructure. A document snippet can tell the user that a service exists, but a tool candidate can carry a schema, Live/Mock/Handoff status, credential requirement, citation, fixture, and permission metadata. The model is not only reading context; it is choosing from bounded public-service actions.

## Retrieval Inputs

Retrieval can use Korean and English search hints, public-service domain, agency metadata, primitive support, Live/Mock/Handoff state, schema shape, policy citation, and prior tool results.

The retrieval output is not the final answer. It narrows the model's decision space so the model does not need every national-infrastructure surface in the prompt.

| Retrieval signal | Why it matters |
|---|---|
| Korean and English `search_hint` | Citizens may ask in everyday Korean while adapters need stable metadata |
| Primitive support | The engine must know whether the candidate can `locate`, `find`, `check`, or `send` |
| Live/Mock/Handoff state | The answer must not overclaim execution authority |
| Schema shape | The model must provide valid arguments, not only a plausible intent |
| Policy citation | Protected actions need an external boundary, not UMMAYA-invented permission |
| Prior results | A later step should reuse resolved location, agency, or receipt context |

## Query Engine Responsibilities

The query engine is responsible for control, not only orchestration. It owns the loop that decides whether the next event is a model call, a tool call, a permission request, a stop reason, or a final answer. That responsibility keeps public-service work inspectable.

| Responsibility | What the engine checks | Failure mode if skipped |
|---|---|---|
| Context assembly | Session state, prior results, current user request, policy mode | The model repeats work or loses legal ordering |
| Candidate narrowing | Relevant adapters and primitive contracts | The prompt grows without improving decision quality |
| Tool-call validation | Envelope, schema, required fields, type constraints | Invalid public-service requests reach adapters |
| Permission gate | Public lookup vs protected action vs Handoff | The system sounds authorized when it is not |
| Result projection | Compact evidence back into the conversation | Final text becomes detached from tool results |
| Stop decision | Complete, ask user, retry, Mock, Handoff, or error | The loop spins or invents completion |

## Tool Calling Is A Contract

Tool calling in UMMAYA is not a generic function-call convenience. Each call is an agreement between the model, the primitive envelope, the selected adapter, and the permission pipeline. The model proposes an action; the engine verifies that the proposal is shaped correctly; the adapter produces evidence or refuses; the UI shows what happened.

This contract is why UMMAYA can support broad domains without giving the model unlimited authority. `locate` can turn a phrase like "near Dong-A University Seunghak Campus" into usable location context. `find` can fetch public emergency or weather data through a selected adapter. `check` can expose a protected eligibility boundary. `send` can prepare official continuation only when the channel and consent make that legitimate.

## Agentic RAG Failure Modes

The architecture is only useful if failures remain visible. UMMAYA treats these as first-class outcomes:

- retrieval found no relevant adapter;
- retrieval found a candidate but the requested operation is Handoff-only;
- the model proposed invalid arguments;
- the adapter requires a credential or consent that is not present;
- the live channel returned zero usable results;
- the response is Mock evidence and must be labeled as such;
- the context budget requires compression before the next turn;
- an official service must continue the workflow.

Each failure should leave a traceable reason. A user-facing answer can be short, but the system record should still show which layer stopped the workflow.

## Stop Reasons

Clear stop reasons make the system debuggable and safe:

- no adapter found;
- invalid arguments;
- permission denied;
- credential missing;
- protected channel unavailable;
- adapter error;
- max iterations or budget reached;
- official Handoff required.

A stop reason is useful when it tells the user or evaluator which layer blocked the flow.

## Traceability

A strong UMMAYA answer should be traceable from request to adapter selection, primitive call, permission decision, tool result, and final text. If the final answer cannot be traced to the loop, it should be treated as ungrounded.

The trace also supports documentation. Architecture prose should not claim a capability simply because the target state is desirable. It should point to adapter metadata, scenario coverage, schema files, generated LLM-readable outputs, CI checks, or a visible terminal behavior. That is the documentation version of the same rule the query engine follows at runtime: answer from evidence, and stop where evidence stops.
