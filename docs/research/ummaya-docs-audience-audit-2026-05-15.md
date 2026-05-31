# UMMAYA Docs Audience And Depth Audit

Status: audit baseline for the next docs rewrite
Date: 2026-05-15
Scope: `docs-site/src/content/docs/{en,ko,ch,jg}` and source artifacts used by the docs site

## Executive Judgment

The current docs site is structurally valid but audience-weighted incorrectly.
It reads like an inspectable project dossier for maintainers, evaluators, and future agents.
That is useful, but it should not be the first experience.

UMMAYA's exact purpose is Korean national-infrastructure AX. The product is not "a docs site for an agentic CLI" and not "a catalog of government APIs." It is a citizen-facing access layer for scattered public-service infrastructure: users should be able to express a public-service outcome as a simple query, and UMMAYA should analyze that request, route across wrapped domain tools, ask for permission where needed, use Claude Code-inspired harness mechanics, and preserve enough context for long administrative workflows.

The primary docs-site audience must be:

1. People who do not use UMMAYA yet and need to understand why it should exist.
2. People considering UMMAYA and deciding whether it is credible, safe, and useful.
3. New CLI users who want a successful first session.
4. Active users who need workflows, permission meaning, recovery, and limitations.
5. Evaluators, adapter authors, maintainers, and LLM agents.

The current site serves audiences 4 and 5 better than audiences 1, 2, and 3.
UMMAYA therefore lacks the product-documentation layer that Claude Code has: the pages that say,
"this is what the tool does for you, this is why it is worth trying, this is what happens next, and this is where it stops."

## Method

Applied:

- `ummaya-reference-first`
- `ummaya-doc-writing`
- creative-writing RAG principles: reader-first, 3C, MECE, Power Writing, five-part structure, Why/How ordering

Audited local sources:

- `docs-site/src/content/docs/en/**/*.md`
- `docs-site/src/content/docs/{ko,ch,jg}/**/*.md`
- `docs/research/ummaya-user-docs-content-architecture.md`
- `docs/research/release-packaging-deep-research.md`
- `docs/vision.md`
- `docs/requirements/ummaya-migration-tree.md`
- `docs/api/README.md`
- `docs-site/src/data/generated/adapters.json`
- `docs-site/src/data/generated/workflows.json`
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml`

External reference checked:

- Claude Code docs index: `https://code.claude.com/docs/llms.txt`
- Claude Code overview, quickstart, common workflows, troubleshooting, and install troubleshooting pages through the public docs/search snippets.

## Inventory

Current site size:

- 4 locales: `en`, `ko`, `ch`, `jg`
- 16 pages per locale
- 64 Markdown pages total

English source page depth:

| Page | Lines | Approx words | H2 count | Judgment |
|---|---:|---:|---:|---|
| `index.md` | 68 | 546 | 5 | Too internal for first contact |
| `start/overview.md` | 68 | 550 | 5 | Useful, but thesis-first instead of user-need-first |
| `start/quickstart.md` | 103 | 316 | 6 | Install path improved; still thin on visible first-run success |
| `start/what-you-can-ask.md` | 89 | 540 | 6 | Good idea; too primitive-oriented and not scenario-rich enough |
| `start/how-ummaya-works.md` | 107 | 675 | 8 | Stronger than before, but too technical for Start |
| `use/common-workflows.md` | 117 | 502 | 6 | Far too shallow relative to 24 target-state workflow scenarios |
| `use/permissions-and-consent.md` | 78 | 423 | 5 | Correct boundary model, but not yet trust-oriented enough |
| `use/troubleshooting.md` | 74 | 421 | 6 | Wrong first audience; starts with maintainer commands |
| `coverage/coverage-map.md` | 77 | 390 | 5 | Honest, but lacks user-readable current coverage table |
| `coverage/live-mock-handoff.md` | 69 | 325 | 5 | Important; should appear earlier in user trust path |
| `architecture/harness-migration.md` | 83 | 535 | 6 | Good evaluator sketch; not enough diagrams or migration evidence |
| `architecture/main-primitives.md` | 73 | 447 | 6 | Needs examples, timelines, and boundary cases per primitive |
| `architecture/agentic-rag-query-engine.md` | 100 | 530 | 6 | Improved but still not deep enough for serious architecture review |
| `build/adapter-authoring.md` | 89 | 377 | 5 | Contributor outline, not executable enough |
| `build/llmops.md` | 97 | 419 | 6 | Correct direction, but lacks concrete CI/docs automation contract |
| `reference/llm-readable-docs.md` | 65 | 304 | 5 | Acceptable as a reference stub |

Generated source material that is underused:

- `workflows.json`: 24 target-state citizen workflows across tax, civil affairs, payments, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, and safety.
- `adapters.json`: 21 current adapter entries.
- `docs/api/README.md`: 12 live `find` adapters, 5 live `locate` providers, 2 mock `send` entries, 6 mock `check` entries.
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml`: rich Korean citizen prompts and permission requirements.

## Main Finding

The docs currently explain UMMAYA from the inside out.
They should explain it from the outside in.

Current dominant frame:

```text
UMMAYA is a Claude Code-style harness with primitives, adapters, evidence, schemas, generated docs, and CI freshness.
```

Correct first-user frame:

```text
UMMAYA lets a citizen ask for a public-service outcome in one sentence.
It finds the public path, shows what can be checked now, asks before protected actions, and stops instead of pretending when an official channel is unavailable.
```

Architecture, schemas, primitive discipline, and CI-generated surfaces are supporting proof.
They should not be the first explanation.

## Canonical Purpose Statement

Use this as the internal source statement before rewriting user-facing prose:

```text
UMMAYA's ultimate goal is to AX Korean national infrastructure.
Korean national infrastructure is scattered across public-service domains: tax, civil affairs, identity, certificates, payments, utilities, welfare, healthcare, education, labor, safety, public data, and official handoff channels.
UMMAYA makes those scattered domains accessible from the user's point of view through one simple query surface and one approachable system.
It wraps scattered domain APIs and official channels as tools.
It uses an agentic LLM so those tools can be selected and used autonomously.
It uses a query engine to analyze user requests, decompose intent, route tool use, and stop safely.
It uses context assembly, compression, and related techniques so long cross-domain workflows remain coherent.
It references Claude Code because Claude Code is the strongest developer-domain harness pattern for tool loops, permission gauntlets, context assembly, and terminal UX; UMMAYA migrates that harness shape from developer work to national-infrastructure work.
```

This statement should shape wording, but it is not always the page order. The order must follow the reader:

- Non-user persuasion: purpose -> fragmented pain -> one-query outcome -> safety boundary -> proof.
- Considering user: current capability -> trust boundary -> examples -> limits -> install.
- New user: install -> first successful session -> what the timeline means -> recovery.
- Active user: situation -> prompt -> expected flow -> Live/Mock/Handoff -> next action.
- Evaluator: purpose -> architecture claim -> data flow -> evidence -> failure modes.

## Why This Order Is Defensible

This is not just a stylistic preference.

- GOV.UK/GDS content guidance says public-service content should start from a valid user need, and that people visit government services to complete tasks such as applying, paying, submitting, or changing records.
- GOV.UK design principles start with user needs, encourage reusable platforms and APIs, and distinguish service design from making a website.
- Plain-language guidance emphasizes writing for the specific audience and organizing content in the order users ask for it.
- Diátaxis separates documentation by user need: tutorials for learning, how-to guides for goals, reference for information, and explanation for understanding. That supports separating UMMAYA quickstart/workflows/trust/architecture/reference instead of forcing one page type to do everything.
- Claude Code docs justify the harness analogy: its agent loop evaluates a prompt, calls tools, receives results, and repeats until the task is complete; its custom tool surface can connect APIs and domain-specific operations; its context-window docs explain why tool definitions, history, and compaction matter in long sessions.

Therefore the recommended UMMAYA docs shape is:

```text
purpose-aware, user-need-led, task-readable, evidence-backed, architecture-supported
```

## Reader Journey That Should Drive The Site

### 1. Non-user or skeptical visitor

Reader question:

- Why does this exist?
- Why not just use Government24, Hometax, or a normal chatbot?
- What concrete pain does UMMAYA reduce?

Needed content:

- Fragmented public-service workflows before/after UMMAYA.
- Three concrete citizen stories: emergency lookup, moving-house checklist, welfare/tax preparation.
- Clear "not official, not magic, not a bypass" boundary.
- What works today versus what is target-state.

Current gap:

- The homepage starts with harness and evidence language.
- It does not lead with citizen pain, outcome, or before/after contrast.

### 2. Considering user or evaluator

Reader question:

- Is this safe enough to try?
- What can it actually do today?
- What is live, mock, or handoff?
- What data stays local?

Needed content:

- Current capability table by user task, not adapter ID.
- Trust page: permission prompts, credentials, local sessions, consent ledger, what UMMAYA cannot do.
- Clear examples of honest refusal and official handoff.

Current gap:

- Live/Mock/Handoff exists but is buried under Coverage.
- Permissions page is technically correct but not framed as "why you can trust the tool."

### 3. New CLI user

Reader question:

- How do I install it?
- What account/key do I need?
- What should I type first?
- What should I see if it works?
- What do I do when it fails?

Needed content:

- Packaged install first: installer, Homebrew, npm fallback.
- First launch screenshots or terminal transcript.
- FriendliAI login explanation.
- First prompt with expected visible timeline.
- Immediate recovery table for command not found, missing Bun/uv, FriendliAI key, slow response, no adapter.

Current gap:

- Quickstart now uses packaged install, but it still lacks a strong "successful first session" checklist.
- Troubleshooting starts with `git status`, `pytest`, `bun test`, and docs generation, which is wrong for ordinary users.

### 4. Active user

Reader question:

- What can I ask in real situations?
- Why did it stop?
- How do I resume?
- How do I read receipts, permission labels, and mode labels?

Needed content:

- Workflow pages by life situation.
- Korean-first examples with English explanations.
- Timeline examples: prompt -> locate -> find -> check/send or handoff.
- Permission/receipt examples.
- Session and history page.

Current gap:

- `common-workflows.md` compresses too many domains into five short sections.
- It does not exploit the 24 scenario dataset.

### 5. Evaluator, builder, maintainer, LLM agent

Reader question:

- Is the architecture defensible?
- Are claims traceable?
- How do I add one agency tool?
- How do docs stay synchronized with prompts, schemas, evals, and releases?

Needed content:

- Deep architecture pages.
- Adapter authoring and API catalog.
- LLMOps/docs automation contract.
- Generated LLM-readable references.

Current gap:

- These sections exist, but they are currently competing with beginner/user content instead of sitting behind it.

## Page-Level Diagnosis

### `index.md`

Problem:

- The first sentence is accurate but not persuasive.
- "This documentation is not a polished README" positions the site against a straw target.
- "Evidence Spine" appears too early for non-users.

Rewrite direction:

- Homepage should become a product adoption page.
- Lead with public-service fragmentation and one-sentence administrative outcomes.
- Then show three paths: try UMMAYA, understand trust boundaries, inspect architecture.
- Move evidence spine lower or into an evaluator path.

### `start/overview.md`

Problem:

- It opens with the thesis formula too early.
- It explains the project more than it motivates the reader.

Rewrite direction:

- Start with "what changes for the user."
- Use before/after examples.
- Put the thesis formula after the reader understands the benefit.

### `start/quickstart.md`

Problem:

- Installation order is now correct, but the page is too short for first success.
- It says what command to run, not what the terminal should look like when the flow works.

Rewrite direction:

- Add "Before you begin" with required tools and credentials.
- Add "You are successful when..." checklist.
- Add "What if it asks for a stronger credential?"
- Add first-run expected timeline and the first recovery table.

### `start/what-you-can-ask.md`

Problem:

- Good prompt pattern, but examples are too few and too abstract.
- It explains primitives to users earlier than necessary.

Rewrite direction:

- Organize by user intent: emergency, moving, welfare, weather/safety, tax/payment prep, identity/certificate handoff.
- Keep primitives as "what UMMAYA may do behind the scenes."
- Include richer Korean prompts from the scenario dataset.

### `start/how-ummaya-works.md`

Problem:

- This is architecture, not beginner start content.
- It contains useful mental model sections but too much IPC/TUI detail for a start path.

Rewrite direction:

- Split into:
  - `start/what-happens-after-you-ask.md`: user-level mental model.
  - `architecture/agent-loop.md`: evaluator-level implementation detail.

### `use/common-workflows.md`

Problem:

- 24 rich target-state workflows are collapsed into five shallow examples.
- It does not show enough realistic Korean citizen prompts.

Rewrite direction:

- Expand into multiple workflow pages:
  - Emergency, healthcare, weather, and safety.
  - Moving, housing, and local records.
  - Welfare and household support.
  - Tax, fines, payments, and utility bills.
  - Identity, certificates, MyData, and official handoff.
- Each workflow needs: situation, prompt, expected timeline, permission boundary, result shape, failure/handoff behavior.

### `use/permissions-and-consent.md`

Problem:

- Technically correct, but reads as compliance architecture.

Rewrite direction:

- Rename or pair with `Trust And Safety`.
- Explain user control first: "what UMMAYA can do without asking," "when it must ask," "what denial means," "where receipts live."
- Keep adapter policy citation as proof, not the opening concept.

### `use/troubleshooting.md`

Problem:

- It is a maintainer/debugging page mislabeled as user troubleshooting.
- First checks include repo commands ordinary users should not run.

Rewrite direction:

- Split:
  - `use/troubleshooting.md`: user symptom map.
  - `build/debugging.md`: maintainer debugging discipline.
- User page should begin with command not found, FriendliAI login, Bun/uv missing, slow response, no result, unexpected mock/handoff, terminal display/Korean text, session resume.

### `coverage/coverage-map.md`

Problem:

- Honest but not concrete enough.
- It lists domain families, not what current UMMAYA can do by user task.

Rewrite direction:

- Add current live/mock matrix:
  - Live public lookup: weather, forecast, road accident, emergency/hospital, welfare guidance, location providers.
  - Mock protected actions: traffic fine payment, welfare application, Digital OnePass, mobile ID, certificates, MyData.
  - Handoff/scenario: Government24, Hometax, opaque certificate/portal flows until callable channels exist.
- Show user task examples, not only adapter categories.

### `coverage/live-mock-handoff.md`

Problem:

- Strong concept but too isolated.

Rewrite direction:

- Promote this concept into homepage, overview, quickstart, workflow pages, and coverage.
- This is UMMAYA's main trust vocabulary.

### Architecture pages

Problem:

- They are directionally right but not deep enough for evaluator confidence.
- `agentic-rag-query-engine.md` is only 100 lines and lacks dataflow, failure modes, cache/retrieval decisions, prompt injection shape, tool result projection examples, and comparison to normal RAG.

Rewrite direction:

- Add a layered dataflow diagram in prose.
- Explain retrieval indices, candidate injection, primitive contract, validation, permission classification, adapter run mode, tool result projection, final answer synthesis, and stop reasons.
- Include example traces for a safe public lookup and a protected handoff.

### Build and reference pages

Problem:

- Valuable but thin and too visible for the primary audience.

Rewrite direction:

- Keep in a secondary "Build/Operate" path.
- Add concrete checklists and generated-doc contracts after user-facing pages are fixed.

## New Information Architecture

Recommended next structure:

```text
Start
├─ Why UMMAYA
├─ What UMMAYA Can Do Today
├─ Quickstart
├─ First Successful Session
├─ What You Can Ask
└─ What Happens After You Ask

Trust And Safety
├─ Live, Mock, And Handoff
├─ Permissions And Consent
├─ Data, Credentials, And Local Sessions
├─ What UMMAYA Will Not Do
└─ Official Handoff

Use UMMAYA
├─ Emergency, Healthcare, Weather, And Safety
├─ Moving, Housing, And Local Records
├─ Welfare And Household Support
├─ Tax, Fines, Payments, And Utility Bills
├─ Identity, Certificates, And MyData
├─ Sessions, Receipts, And History
└─ Troubleshooting

Coverage
├─ Current Coverage
├─ Domain Roadmap
├─ Adapter Matrix
└─ Scenario Matrix

Architecture
├─ Harness Migration
├─ Agent Loop
├─ Agentic RAG And Query Engine
├─ Tool Registry And Retrieval
├─ Main Primitives
├─ Permission Pipeline
├─ Context Assembly
├─ Sessions And Storage
└─ Error Recovery

Build And Operate
├─ Install From Source
├─ Configuration
├─ FriendliAI And K-EXAONE
├─ Adapter Authoring
├─ API Catalog
├─ Testing
├─ Observability
├─ LLMOps For Docs
└─ Release And Packaging

Reference
├─ CLI Reference
├─ Commands
├─ Environment Variables
├─ Tool Schemas
├─ LLM-Readable Docs
├─ Glossary
└─ Changelog
```

## Depth Standard For The Rewrite

Every substantial user-facing page must answer these questions:

1. Who is this page for?
2. What public-service outcome does it help with?
3. What can UMMAYA do now?
4. What boundary may stop the flow?
5. What will the user see in the terminal?
6. What proves the claim?
7. What should the user do next?

Every workflow page must include:

- situation;
- Korean citizen prompt;
- expected primitive timeline using current names: `locate`, `find`, `check`, `send`;
- Live/Mock/Handoff label;
- permission behavior;
- result shape;
- handoff behavior;
- failure recovery.

Every architecture page must include:

- why the design exists;
- data/control flow;
- key contracts;
- failure modes and stop reasons;
- trace/evidence points;
- at least one concrete turn example.

## Primitive Naming Note

Some older source artifacts and the target-state evaluation dataset still use names such as `lookup`, `resolve_location`, `verify`, and `submit`.
Current user docs must use the active UMMAYA names:

- `locate`
- `find`
- `check`
- `send`

When using old scenario material, translate the old terms into the current primitive names in the docs.
Do not reintroduce deprecated primitive labels into the user-facing site.

## Rewrite Priority

Priority 1:

- `index.md`
- `start/overview.md`
- `start/quickstart.md`
- `use/troubleshooting.md`
- new or rewritten Live/Mock/Handoff trust path

Priority 2:

- `start/what-you-can-ask.md`
- expanded workflow pages from `workflows.json` and `evidence/scenarios/national_ax_citizen_requests_v1.yaml`
- `coverage/coverage-map.md`

Priority 3:

- architecture deepening
- adapter authoring
- LLMOps/docs automation
- reference surfaces

## Acceptance Criteria For The Next Rewrite

- Homepage can persuade a non-user without requiring architecture knowledge.
- Quickstart gets from packaged install to one verified public-service answer.
- Troubleshooting begins with user symptoms, not maintainer commands.
- Current coverage is visible by user task and by adapter evidence.
- Workflow content uses the 24 scenario dataset instead of five compressed examples.
- Every page preserves honest Live/Mock/Handoff language.
- All locales are translated fully; no fallback-language body content remains.
- LLM-readable outputs are regenerated after source docs change.
