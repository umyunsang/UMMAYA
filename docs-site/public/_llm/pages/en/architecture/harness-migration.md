---
title: Harness Migration
description: Why UMMAYA migrates Claude Code harness mechanics from developer work
  to national-infrastructure work.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/vision.md
- docs/requirements/ummaya-migration-tree.md
- .references/claude-code-sourcemap/restored-src/
- specs/2521-llm-swap-cc-rebuild/spec.md
audience:
- public_sector_evaluator
- maintainer
- llm_agent
---

UMMAYA's architecture starts from a product claim: Korean national infrastructure needs a user-facing agent harness. Claude Code is the reference because it already demonstrates the harness shape UMMAYA needs: a user states an outcome, the system assembles context, calls tools, asks permission, preserves session state, and renders a usable terminal experience.

The migration is not a metaphor. It is a control-system decision. Claude Code proved that a difficult domain becomes usable when the user can state an outcome, the harness can gather context, the model can call bounded tools, and the UI can show enough evidence for the user to trust the next step. UMMAYA applies that same structure to national-infrastructure work, where the tools are not files and shell commands but public-service channels, official handoff paths, and policy-shaped mocks.

Each architecture diagram below answers one question. The context view answers "where does UMMAYA sit?" The loop view answers "what happens first when a user asks?" Deeper pages then zoom into primitives, retrieval, permission, and stop reasons.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-01-national-ax-context.svg" alt="Minimal C4 context diagram: Citizen asks UMMAYA; UMMAYA reasons with K-EXAONE and uses Public APIs or Official Channels." />
  <figcaption>Context view: one query surface, one model, and two public-service boundaries.</figcaption>
</figure>

## The Design Claim

UMMAYA should feel like one query surface, but it must behave like a disciplined public-service client. The citizen should not need to know whether a task belongs to Government24, Hometax, Wetax, a local government, an identity rail, a certificate provider, a utility operator, a weather source, or a public-data API. The harness must discover the relevant channel, expose the boundary, and stop before it pretends to hold authority it does not have.

That is why the architecture starts with the harness instead of with a list of APIs. A portal list would move the burden from one screen to another. A harness can preserve the user's intent across multiple turns, carry tool results forward, ask for consent at the right moment, and explain why a workflow became Live, Mock, or Handoff.

## The Two Sanctioned Swaps

| Harness component | Claude Code role | UMMAYA role |
|---|---|---|
| Model provider | Claude model family | K-EXAONE on FriendliAI Serverless |
| Tool surface | developer filesystem, shell, git, and code tools | Korean public-service adapters and official handoff paths |

The surrounding harness discipline remains conceptually stable: query loop, tool-call protocol, permission request path, context assembly, terminal UI, session persistence, and evidence-oriented debugging.

<figure class="architecture-diagram">
  <img src="/architecture/c4/structurizr-02-query-loop.svg" alt="Minimal C4 dynamic diagram: Citizen, UI, Query Engine, Sessions, Registry, K-EXAONE Client, K-EXAONE, and Answer." />
  <figcaption>Query loop view: ask, route, gather context, select tools, reason, answer.</figcaption>
</figure>

These diagrams are generated from `docs/architecture/c4/workspace.dsl`. Regenerate them with `npm run docs:c4` after changing the architecture model. Keep each diagram small enough to explain a single reader task.

## What Stays Stable

The stable part is the operational loop: gather context, choose a bounded action, execute the action, project the result back into the conversation, and repeat until the work is resolved or safely stopped. This is the part UMMAYA should not casually redesign, because it is what separates an agent harness from a chatbot transcript.

The visible UI also stays important. A user should be able to see that UMMAYA first resolved a place, then fetched public information, then reached a protected boundary. Without that visible sequence, the final answer sounds magical but is not inspectable.

## What Changes

UMMAYA changes the risk model. A developer harness worries about file overwrites, destructive shell commands, and broken project state. A national-infrastructure harness worries about PIPA, identity verification, certificate issuance, tax filing, payments, official records, and agency-specific consent. The shape is familiar, but the consequences are civic rather than local.

| Claude Code concern | UMMAYA concern | Required discipline |
|---|---|---|
| Dangerous shell command | Protected public-service action | Permission must be explicit and policy-cited |
| File overwrite | Official record change | No fake completion without live authority |
| Project memory | Citizen session context | Local persistence must remain inspectable |
| Tool result | Public-service evidence or receipt | Final answers must be grounded in returned data |
| Permission prompt | Consent and agency boundary | The UI must show what is being allowed |
| Context window | Long administrative workflow | Context assembly and compression must preserve decisions |

## The Migration Path In One Request

```text
Citizen asks for an outcome
  -> query engine preserves intent and session context
  -> retrieval narrows possible public-service adapters
  -> K-EXAONE chooses locate, find, check, or send
  -> permission pipeline classifies the action
  -> adapter returns Live evidence, Mock evidence, or Handoff material
  -> the UI shows the sequence and the answer states the boundary
```

This path is deliberately narrow. If a workflow requires identity, payment, certificate issuance, or official submission authority, the harness does not hide that boundary in a confident paragraph. It asks, stops, or hands off.

## Why Migration Beats Reinvention

A public-service agent cannot be a loose chatbot. It needs a loop that can call tools, handle permission, preserve context, stop safely, and show the user what happened. Claude Code is the strongest reference because it already solved those harness problems for developers, and UMMAYA's thesis is that the same harness can be migrated to citizen-facing national AX.

UMMAYA's originality is the domain migration: PIPA, identity, certificates, payments, agency policy citations, Live/Mock/Handoff labeling, official handoff paths, and Korean-first public-service language. Those are not decorative additions. They are the conditions that let a model use public-service tools without sounding more authoritative than it is.

## What Must Stay Disciplined

If the UI looks persuasive but the query loop loses tool evidence, the migration fails. If a mock sounds official, the migration fails. If a protected action bypasses consent, the migration fails. If a long session loses the reason a prior agency step stopped, the migration fails.

The test for this page is simple: UMMAYA should reduce the user's portal burden without reducing the user's ability to understand what happened. Harness migration is valuable only when it makes national AX easier and safer at the same time.
