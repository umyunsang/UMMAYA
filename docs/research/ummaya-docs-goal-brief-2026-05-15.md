# UMMAYA Docs Goal Brief

Status: binding goal brief for the active docs-site rewrite
Date: 2026-05-15
Related goal: UMMAYA docs-site rewrite for national-infrastructure AX

## Canonical Purpose

UMMAYA's ultimate goal is to AX Korean national infrastructure.

Korean national infrastructure is scattered across public-service domains: tax, civil affairs, identity, certificates, payments, utilities, welfare, healthcare, housing, education, labor, safety, public data, and official handoff channels. From the user's point of view, those domains should be reachable through one simple query and one accessible system instead of requiring the user to know every agency, portal, certificate rail, payment rail, or infrastructure operator.

UMMAYA solves this by wrapping scattered domain APIs, official channels, mockable policy shapes, and handoff paths as tools. An agentic LLM uses those tools by itself instead of only producing prose. The query engine analyzes the user's request, decomposes the work, chooses the right tools, handles stop reasons, and returns grounded results. Context assembly, compression, and related techniques exist so long cross-domain administrative workflows remain coherent over time.

UMMAYA references Claude Code because Claude Code is the strongest developer-domain harness pattern for the needed architecture: tool loop, permission gauntlet, context assembly, terminal UX, and agentic execution discipline. UMMAYA migrates that harness shape from developer work to national-infrastructure work.

## Writing Implication

The docs must not present tool wrapping, agentic LLM, query engine, context compression, or Claude Code reference as isolated engineering bragging points.
They are supporting architecture for the same product promise:

```text
scattered Korean national infrastructure
  -> one simple user query and accessible system
  -> domain APIs and official channels wrapped as tools
  -> agentic LLM selects and uses those tools
  -> query engine analyzes, decomposes, routes, and stops safely
  -> context compression keeps long administrative workflows usable
  -> Claude Code harness reference gives the architecture a proven execution model
```

## Reader-Driven Page Order

Use `purpose -> user need -> action path -> supporting architecture` when it helps the reader understand and trust UMMAYA.
Do not force that order onto every page.

| Reader/page type | Best order |
|---|---|
| Non-user persuasion | purpose -> fragmented pain -> one-query outcome -> safety boundary -> proof |
| Considering user | current capability -> trust boundary -> examples -> limits -> install |
| New user | install -> first successful session -> visible timeline -> recovery |
| Active user | situation -> prompt -> expected flow -> Live/Mock/Handoff -> next action |
| Evaluator | purpose -> architecture claim -> data flow -> evidence -> failure modes |
| Adapter author | one agency module -> tool contract -> schema -> citation -> fixture/test -> docs |

## Reference Basis

This docs rewrite uses the following reference logic:

- `docs/vision.md`: canonical UMMAYA purpose, national-infrastructure AX scope, Claude Code harness migration.
- `docs/requirements/ummaya-migration-tree.md`: L1 pillars, active primitives, tool system, permission gauntlet, UI requirements.
- `docs/api/README.md`: current live/mock adapter evidence.
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml`: target-state citizen demand across domains.
- `docs-site/src/data/generated/adapters.json`: generated adapter data.
- `docs-site/src/data/generated/workflows.json`: generated scenario/workflow data.
- Creative-writing RAG: 3C, POWER, MECE, Hi Five, five-part structure.
- GOV.UK user-needs/content-design guidance: public-service content starts from user tasks and user needs.
- Diataxis: docs split by reader need: tutorial, how-to, reference, explanation.
- Claude Code docs: agent loop, tools, custom tools/API surface, context window, and compaction as harness reference.

## Acceptance Criteria

- The homepage makes the national-infrastructure AX purpose understandable before architecture.
- The overview explains why scattered public-service domains need one query surface.
- User pages teach what a person can do, what they will see, where UMMAYA stops, and why that stop is honest.
- Coverage pages show current capability by user task and by adapter evidence.
- Workflow pages use target-state citizen scenarios and active primitive names: `locate`, `find`, `check`, `send`.
- Architecture pages tie every component back to the national AX purpose.
- Every locale (`en`, `ko`, `ch`, `jg`) carries the same purpose, promise, boundary, and evidence.
- Generated LLM-readable outputs and build checks pass after rewriting.
