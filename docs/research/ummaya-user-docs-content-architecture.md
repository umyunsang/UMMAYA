# UMMAYA User Documentation Content Architecture

Status: research and design proposal
Date: 2026-05-15
Scope: user-facing documentation content redesign, not runtime behavior

## Reference Bootstrap

- UMMAYA thesis and requirements:
  - `docs/vision.md`
  - `docs/requirements/ummaya-migration-tree.md`
  - `docs/api/README.md`
  - `docs/plugins/README.md`
  - `docs/configuration.md`
  - `docs/observability.md`
  - `evidence/scenarios/national_ax_citizen_requests_v1.yaml`
- Claude Code reference:
  - Official docs index: <https://code.claude.com/docs/llms.txt>
  - Official docs pages sampled: overview, quickstart, common workflows, how Claude Code works, permissions, troubleshooting
  - Restored source was only inspected for parity anchors (`query.ts`, skills loading, permission/settings surfaces); no runtime behavior is changed by this proposal.
- External docs patterns:
  - LLM-readable docs: Claude Code, CrewAI, LangChain/LangGraph, Pydantic AI, LlamaIndex, Google ADK, OpenAI Agents SDK, Mastra
  - Strongest agent-readable pattern: LlamaIndex-style raw Markdown plus search/read/list APIs
- Implementation constraints:
  - English source text only; Korean appears as domain examples, labels, and citizen prompts.
  - No new documentation stack dependency should be added outside a spec-driven PR.
  - Existing `docs/`, `docs/api/`, `specs/`, prompts, eval scenarios, schemas, and fixtures remain source-of-truth inputs.

## Why the Current Shape Is Not Enough

The current UMMAYA docs are rich internally but are not yet shaped as a product documentation site.
The repository already has strong material:

- README: good demo and top-level explanation
- `docs/vision.md`: deep architecture and thesis
- `docs/api/`: adapter catalog and JSON Schema references
- `docs/plugins/`: strong contributor guide
- `docs/configuration.md`: environment registry
- `docs/observability.md`: local Langfuse/OTEL guide
- `docs/design/verification-fabric-v2.md`: rigorous verification methodology
- `docs/scenarios/`: opaque-system narratives
- `evidence/scenarios/`: target-state citizen demand dataset

The missing layer is the user documentation experience:

- A citizen or public-sector evaluator should see what UMMAYA can do before reading architecture.
- A CLI user should know exactly how to install, log in, ask the first question, understand tool events, recover from failures, and resume sessions.
- A ministry or plugin contributor should have a separate guided path from ordinary users.
- A maintainer should have operational docs for evaluation, tracing, release evidence, and docs freshness.
- An LLM assistant should have a first-class index and raw Markdown surfaces to answer docs questions without hallucinating.

Claude Code solves this by organizing docs around user intent, not repository structure.
UMMAYA should do the same.

## Claude Code Content Model To Adapt

Claude Code's docs are not just a README expansion. The content model has several distinct layers:

1. Product entry
   - Overview
   - Quickstart
   - What you can do
   - Platform and interface choices
2. Everyday workflows
   - Prompt recipes
   - Resume sessions
   - Parallel sessions
   - Plan-before-editing
   - Delegate work
   - Pipe/script automation
3. Mental model
   - Agentic loop
   - Tools
   - What the agent can access
   - Sessions
   - Context window
   - Checkpoints and permissions
4. Configuration and control
   - Settings
   - Permissions
   - Environment variables
   - Terminal and keybindings
   - Managed organization policies
5. Extension
   - Skills
   - Subagents
   - Hooks
   - MCP
   - Plugins and marketplaces
6. Operations
   - Costs
   - Monitoring
   - Analytics
   - Secure deployment
   - Data usage
   - Enterprise network configuration
7. Reference
   - CLI reference
   - Tools reference
   - Commands
   - Error reference
   - Changelog
   - Glossary
8. Recovery
   - Troubleshooting
   - Debug configuration
   - Install/login troubleshooting

UMMAYA should adapt the structure, not copy the nouns.
The equivalent user unit is not "codebase task"; it is "citizen administrative outcome".

## Proposed Documentation Audiences

UMMAYA docs should explicitly serve five audiences:

| Audience | Primary question | Docs path |
|---|---|---|
| Citizen CLI user | "What can I ask and what will happen?" | Start, Workflows, Safety, Troubleshooting |
| Public-sector evaluator | "Is this a credible national AX reference implementation?" | Overview, Architecture, Coverage, Security, Evidence |
| Developer maintainer | "How do I run, test, trace, and release it?" | Configuration, Observability, Testing, Release |
| Adapter author | "How do I wrap one government channel correctly?" | Adapter guide, API catalog, Mock/Live/Scenario rules |
| Plugin contributor | "How do I ship an external tool safely?" | Plugin quickstart, security review, validation |

The site navigation should let each audience stay on its path without forcing them through the full architecture document.

## Proposed Top-Level Navigation

```text
Start
├─ Overview
├─ Quickstart
├─ What You Can Ask
├─ How UMMAYA Works
└─ Glossary

Use UMMAYA
├─ Common Citizen Workflows
├─ Local Lookup Workflows
├─ Identity And Eligibility Workflows
├─ Submission And Handoff Workflows
├─ Sessions And History
├─ Permissions And Consent
├─ Export And Receipts
└─ Troubleshooting

National AX Coverage
├─ Coverage Map
├─ Live, Mock, And Handoff
├─ Government24
├─ Hometax
├─ Mobile ID And Identity Rails
├─ Certificates And Signing
├─ Payments And Utilities
├─ Welfare And Healthcare
├─ Housing, Labor, Education
├─ Safety, Mobility, Weather
└─ Opaque-System Scenarios

Architecture
├─ Claude Code Harness Migration
├─ Agent Loop
├─ Main Primitives
├─ Tool Registry And Retrieval
├─ Permission Pipeline
├─ Context Assembly
├─ Sessions
├─ Error Recovery
├─ TUI Architecture
└─ Data And Storage Model

Build
├─ Install From Source
├─ Configuration
├─ FriendliAI And K-EXAONE
├─ Adapter Authoring
├─ API Catalog
├─ Plugin System
├─ Testing
├─ Observability
└─ Release And Packaging

Reference
├─ CLI Reference
├─ Slash Commands
├─ Environment Variables
├─ Tool Reference
├─ JSON Schemas
├─ Permission Tiers
├─ Error Reference
├─ Changelog
└─ LLM-Readable Docs
```

## Page-Level Content Design

### Start / Overview

Purpose: Make the product legible in the first screen.

Required sections:

- What UMMAYA is
- What it is not
- The one-sentence thesis: Claude Code harness plus K-EXAONE plus Korean public-service tool surface
- What users can do today
- What is live, mocked, or handed off
- Where data stays
- Minimal install path
- Next pages: Quickstart, What You Can Ask, Safety

Source inputs:

- README
- `docs/vision.md`
- `docs/requirements/ummaya-migration-tree.md`
- current package metadata

### Start / Quickstart

Purpose: Get a user from zero to one verified session.

Required sections:

- Before you begin
- Install with npm
- Install with Homebrew
- Start UMMAYA
- Log in with FriendliAI
- Ask the first public-service question
- Understand the visible tool timeline
- Resume a session
- Where to go when login or lookup fails

The first example should be live-public and safe:

```text
동아대 승학캠퍼스에서 친구가 갑자기 아프면 지금 바로 연락할 응급실 어디가 가까워?
```

Source inputs:

- README
- package release docs
- `docs/configuration.md`
- current TUI behavior

### Start / What You Can Ask

Purpose: Replace API-shaped thinking with citizen-outcome prompts.

Required sections:

- Nearby emergency care
- Weather and road risk
- Hospital or clinic lookup
- Welfare eligibility preparation
- Moving and address-change sequencing
- Tax filing target-state examples
- Identity and certificate target-state examples
- Payment and utility target-state examples
- What UMMAYA will not fake

Each workflow card should include:

- Citizen prompt in Korean
- What UMMAYA tries first
- Tools likely involved
- Live/Mock/Handoff status
- Permission level
- What the user sees
- Failure or handoff behavior

Source inputs:

- README prompt table
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml`
- `docs/api/README.md`
- `docs/scenarios/`

### Start / How UMMAYA Works

Purpose: Give users the mental model without making them read the full architecture.

Adapt Claude Code's "How Claude Code works" shape:

- The citizen agent loop
  - Understand request
  - Resolve context
  - Call tools
  - Verify result
  - Ask permission or hand off
- Models
  - FriendliAI Serverless
  - K-EXAONE
  - thinking toggle caveat
- Tools
  - `locate`
  - `find`
  - `check`
  - `send`
- What UMMAYA can access
  - local session data
  - configured credentials
  - live public-information APIs
  - mock-backed protected flows
  - no hidden government authority
- Sessions and context
- Safety: consent, receipts, and irreversible actions

Source inputs:

- `docs/vision.md`
- `docs/requirements/ummaya-migration-tree.md`
- `docs/api/README.md`
- `docs/configuration.md`

### Use / Common Citizen Workflows

Purpose: Provide recipe pages, not abstract feature lists.

Page structure:

- "I need emergency or healthcare information"
- "I need to understand weather, roads, or safety risk"
- "I moved and need a government checklist"
- "I want to prepare welfare support"
- "I need identity, certificate, or MyData verification"
- "I need to submit, pay, or get a receipt"
- "I need UMMAYA to explain why it stopped"

Each recipe:

- Situation
- Prompt
- Expected timeline
- What permission may appear
- What result should look like
- How to continue
- How to recover when no result is found

Source inputs:

- `evidence/scenarios/`
- `docs/api/`
- `docs/scenarios/`
- TUI smoke artifacts after implementation changes

### Use / Permissions And Consent

Purpose: Make trust behavior predictable.

Required sections:

- Public lookup vs personal-data action
- Permission tiers
- Consent receipt
- Session auto-approval
- Revocation
- What UMMAYA cannot bypass
- Why policy citations are shown
- What happens on timeout or denial

UMMAYA-specific content:

- Layer 1 public lookup
- Layer 2 identity-backed or delegated action
- Layer 3 high-assurance or irreversible action
- Adapter cites the agency policy; UMMAYA does not invent classification

Source inputs:

- `docs/security/permission-v2-threat-model.md`
- `docs/security/tool-template-security-spec-v1.md`
- `docs/api/README.md`
- permission TUI specs

### Use / Troubleshooting

Purpose: Route the user by symptom before giving low-level details.

Claude Code's troubleshooting page works because it starts with a symptom-to-page table.
UMMAYA should use the same pattern:

| Symptom | Go to |
|---|---|
| `ummaya` command not found | Install troubleshooting |
| `/login` fails | Authentication |
| FriendliAI response times out | Model and network |
| Public lookup returns no result | Tool result troubleshooting |
| Consent prompt appears unexpectedly | Permissions |
| TUI looks broken on Korean text | Terminal and IME |
| Session resume fails | Sessions |
| No traces appear in Langfuse | Observability |
| Plugin install fails | Plugin troubleshooting |

Source inputs:

- `docs/configuration.md`
- `docs/observability.md`
- `docs/design/verification-fabric-v2.md`
- TUI and packaging specs

### National AX Coverage / Coverage Map

Purpose: Show credible breadth without overclaiming.

Required sections:

- Coverage legend
  - Live
  - Mock
  - Handoff/Scenario
  - Planned
- Domain map
  - tax
  - civil affairs
  - identity
  - certificates
  - welfare
  - healthcare
  - housing
  - labor
  - education
  - immigration
  - safety
  - mobility
  - utilities
  - payments
- Adapter matrix
- Scenario matrix
- Evidence status
- Credential status
- Public policy citation status

Source inputs:

- `docs/api/README.md`
- `docs/scenarios/`
- `docs/mock/`
- `evidence/scenarios/national_ax_citizen_requests_v1.yaml`

### National AX Coverage / Live, Mock, And Handoff

Purpose: Explain the single most important product boundary.

Required sections:

- Why Live exists
- Why Mock exists
- Why Handoff exists
- What a mock proves
- What a mock does not prove
- How a scenario becomes mock
- How a mock becomes live
- What users see in each case

Source inputs:

- `docs/scenarios/README.md`
- `docs/mock/`
- `docs/api/README.md`
- adapter specs

### Architecture / Claude Code Harness Migration

Purpose: Preserve the thesis for evaluators and contributors.

Required sections:

- Developer harness to citizen harness
- The two sanctioned swaps
- Byte-parity policy
- What is original to UMMAYA
- Mapping table:
  - Read/Edit/Bash/Grep/WebFetch to locate/find/check/send
  - file permission to PIPA consent
  - project memory to citizen session memory
  - tool results to receipt/audit evidence

Source inputs:

- `docs/vision.md`
- restored-source research notes
- current primitive specs

### Architecture / Main Primitives

Purpose: Explain the small model-facing surface.

Required sections per primitive:

- What it does
- What it never does
- Example citizen prompt
- Example tool timeline
- Adapter discovery
- Permission behavior
- Live/Mock/Handoff examples
- JSON Schema link

Source inputs:

- `docs/api/schemas/{find,locate,check,send}.json`
- primitive source code
- `docs/api/README.md`

### Build / Adapter Authoring

Purpose: Make "one agency module = one tool" executable.

The current `docs/tool-adapters.md` is strong but contributor-heavy.
The user-facing docs site should split it into:

- Adapter authoring overview
- Pick Live, Mock, or Handoff
- Write the schema
- Write search hints
- Add policy citations
- Record fixtures
- Add tests
- Add docs
- Validate and submit

Source inputs:

- `docs/tool-adapters.md`
- `docs/api/README.md`
- `docs/plugins/`

### Build / LLMOps

Purpose: Treat docs, prompts, tools, and evals as one quality loop.

Required sections:

- Prompt manifest
- Scenario dataset
- Tool-call regression evals
- Trace IDs
- OTEL/Langfuse local stack
- Docs Q&A evals
- Docs freshness checks
- Citation checks
- Release evidence

Operational loop:

```text
citizen failure or trace
  -> classify failure
  -> update adapter / prompt / docs
  -> add or update eval scenario
  -> run regression gate
  -> publish docs with traceable evidence
```

Source inputs:

- `docs/design/verification-fabric-v2.md`
- `docs/observability.md`
- `prompts/manifest.yaml`
- `evidence/scenarios/`
- `specs/026-cicd-prompt-registry/`

### Reference / LLM-Readable Docs

Purpose: Make documentation consumable by UMMAYA, Codex, Claude, and external agents.

Required endpoints or generated artifacts:

- `/llms.txt`
- `/llms-full.txt`
- per-page raw Markdown
- docs search index JSON
- docs path list
- machine-readable front matter

Recommended local artifact layout before a full docs portal exists:

```text
docs/llms.txt
docs/llms-full.txt
docs/_llm/index.json
docs/_llm/pages.jsonl
docs/_llm/search-fixtures.yaml
```

Recommended future HTTP API:

```text
GET /api/docs/search?q=<query>&limit=10
GET /api/docs/read?path=<doc-path>&startLine=0&endLine=300
GET /api/docs/list?section=<section>&depth=2
GET /api/docs/grep?q=<regex>&context=2
```

Source inputs:

- all Markdown docs
- adapter YAML front matter
- JSON schemas
- prompt manifest
- eval scenario metadata

## Information Architecture By User Journey

### First-Time CLI User

```text
Overview
  -> Quickstart
  -> What You Can Ask
  -> How UMMAYA Works
  -> Permissions And Consent
  -> Troubleshooting
```

Success criterion: user can install, log in, ask one safe live public-service question, understand the tool timeline, and resume the session.

### Citizen With A Real Task

```text
What You Can Ask
  -> Common Citizen Workflows
  -> Live, Mock, And Handoff
  -> Permissions And Consent
  -> Export And Receipts
```

Success criterion: user understands whether UMMAYA can complete, simulate, or hand off the task.

### Public-Sector Evaluator

```text
Overview
  -> National AX Coverage
  -> Claude Code Harness Migration
  -> Permission Pipeline
  -> Live, Mock, And Handoff
  -> Observability
  -> Evidence And Evaluation
```

Success criterion: evaluator can tell what is implemented, what is policy-mandated, what is mocked, what is impossible without official access, and what evidence supports each claim.

### Adapter Author

```text
Adapter Authoring
  -> API Catalog
  -> Live, Mock, And Handoff
  -> Permission Tiers
  -> Fixture Recording
  -> Testing
  -> Submit Adapter PR
```

Success criterion: contributor can wrap one agency module without inventing permission policy or hardcoding credentials.

### Maintainer

```text
Install From Source
  -> Configuration
  -> Testing
  -> Observability
  -> LLMOps
  -> Release And Packaging
```

Success criterion: maintainer can run, verify, trace, evaluate, package, and release with evidence.

## Required Page Front Matter

Each documentation page should declare machine-readable metadata:

```yaml
---
title: "Permissions and consent"
audience:
  - citizen_user
  - public_sector_evaluator
surface:
  - tui
  - cli
source_of_truth:
  - docs/security/permission-v2-threat-model.md
  - specs/033-permission-v2-spectrum/spec.md
related_runtime:
  - src/ummaya/permissions/
llm_index: true
freshness_check:
  - permission_tier_matrix
  - consent_receipt_schema
---
```

This makes docs validation possible:

- stale source links can fail CI
- pages can be grouped by audience
- `llms.txt` can be generated deterministically
- docs Q&A evals can target the right page set

## Docs Quality Gates

The docs should be tested like product behavior.

Minimum gates:

- Link check for internal and external references
- `llms.txt` generation check
- JSON Schema link check for every adapter page
- Source-of-truth existence check for every page front matter entry
- Permission citation check for adapter docs
- Korean prompt examples linted as domain data exceptions
- Docs Q&A eval over common user questions
- Release gate verifying docs mention the current package version

Example docs Q&A eval prompts:

- "Can UMMAYA file my tax return today?"
- "Why did UMMAYA stop before submitting my welfare application?"
- "Where is my FriendliAI token stored?"
- "What does mock mean in UMMAYA?"
- "How do I resume a previous session?"
- "How do I add a new Government24 adapter?"

Expected behavior:

- Answer from docs only.
- Cite the source page.
- Distinguish Live, Mock, and Handoff.
- Do not claim official government affiliation.
- Do not invent agency permission policy.

## Migration From Current Docs

| Current file or directory | New docs role |
|---|---|
| `README.md` | Source for Overview, Quickstart, What You Can Ask |
| `docs/vision.md` | Source for Architecture and National AX thesis |
| `docs/requirements/ummaya-migration-tree.md` | Source for capability status and UI behavior |
| `docs/api/` | Source for API Catalog, Tool Reference, Coverage Map |
| `docs/scenarios/` | Source for Opaque-System Scenarios and Handoff docs |
| `docs/mock/` | Source for Mock fidelity docs |
| `docs/plugins/` | Source for Plugin System docs |
| `docs/configuration.md` | Source for Configuration and Env Vars reference |
| `docs/observability.md` | Source for Observability and LLMOps |
| `docs/design/verification-fabric-v2.md` | Source for Testing and TUI verification |
| `docs/release-*`, `docs/packaging.md` | Source for Release and Packaging |
| `evidence/scenarios/` | Source for Citizen Workflow examples and docs Q&A eval |
| `prompts/manifest.yaml` | Source for LLMOps and prompt registry docs |

## Deep Research Findings For The Docs Site

## Target Operating Model

UMMAYA should not merely publish a documentation website. It should operate documentation as a product surface in the same way Claude Code does.

Target behavior:

```text
code changes
  -> schemas, CLI reference, workflow examples, and docs index regenerate
  -> docs CI checks freshness, links, style, and claims
  -> PR preview shows the updated documentation site
  -> docs Q&A eval proves users and agents can find the right answer
  -> merge deploys static docs, llms.txt, llms-full.txt, and search index
  -> release verifies docs match the published package
```

This means the docs site has three consumers:

| Consumer | Surface |
|---|---|
| Human users | Product docs site with workflows, recipes, references, troubleshooting |
| AI agents | `llms.txt`, `llms-full.txt`, raw Markdown, docs search/read/list index |
| CI/CD | front matter contracts, drift checks, docs Q&A evals, release evidence |

The operating requirement is:

> A UMMAYA feature is not complete until its user-facing docs, LLM-readable docs, and CI freshness checks are updated in the same PR.

This is the documentation equivalent of UMMAYA's tool-adapter rule: one real capability needs one documented, searchable, verifiable public surface.

### What Claude Code-Style Docs Actually Require

Claude Code's docs site has four properties UMMAYA should reproduce:

1. Human-first product navigation
   - The first pages answer "what can I do?", "where do I run it?", and "what happens next?"
   - User paths are organized by workflows and surfaces, not by source-code directories.
2. Agent-readable documentation
   - `/llms.txt` exposes a machine-readable documentation index.
   - Page links include Markdown forms so an agent can fetch clean content directly.
   - `/llms-full.txt` gives a complete plain-text context surface.
3. Operational documentation
   - Permissions, settings, costs, sessions, context, troubleshooting, monitoring, and enterprise rollout are first-class pages.
   - The docs explain the harness, not only the install command.
4. CI-backed freshness
   - Docs pages are backed by metadata, OpenAPI/API references, link checks, style checks, and preview deployments.

The UMMAYA equivalent is:

```text
citizen outcome docs
  + national AX coverage docs
  + adapter/tool reference docs
  + permission and audit docs
  + LLMOps/eval docs
  + llms.txt / raw Markdown / docs API
```

### Stack Comparison

| Stack | Seen in comparable projects | Strengths | Risks for UMMAYA | Fit |
|---|---|---|---|---|
| Mintlify | Claude Code, CrewAI, LangChain/LangGraph | Polished docs, AI assistant, automatic `llms.txt`/`llms-full.txt`, OpenAPI pages, PR previews, CI checks, GitHub sync | SaaS dependency, paid advanced features, GitHub App access, less control over zero-egress/public-sector posture | Best reference, not default implementation |
| Astro + Starlight | Pydantic AI, LlamaIndex | Open source, static-first, Markdown/MDX, typed content collections, good i18n, easy custom routes for `llms.txt` and docs APIs | More custom work for API reference and preview polish | Recommended default |
| MkDocs Material | Google ADK, OpenAI Agents SDK | Python-friendly, simple, strong search, easy with `mkdocstrings`, good for API docs | Less product-polished; richer interactive pages require plugins/custom theme work | Good backend/API docs option |
| Docusaurus | Mastra and many OSS products | Mature docs framework, versioning, i18n, MDX/React, good community | React-heavy; another TypeScript/React stack beside TUI; versioning can duplicate docs | Strong alternative if versioned docs dominate |
| Sphinx/PyData | AutoGen | Excellent Python API reference | Less modern product-doc UX without significant theming | Use only for generated API reference fragments |
| Custom Next.js | Cursor, Vercel AI SDK | Maximum product polish and custom interaction | Highest maintenance; not docs-first; unnecessary for current UMMAYA | Avoid for now |

### Recommendation

Build a Mintlify-shaped documentation experience with a self-owned stack:

```text
Astro + Starlight
  + docs-as-code in this repository
  + generated llms.txt / llms-full.txt
  + generated API/tool references from Pydantic schemas
  + GitHub Actions preview/build/link/style/eval gates
  + optional future docs search/read API
```

Reasoning:

- UMMAYA already has Bun/TypeScript in the TUI layer, so Astro does not introduce a new language family.
- Starlight is static-first and documentation-oriented.
- Astro content collections provide typed front matter validation, which maps well to UMMAYA's need for source-of-truth metadata.
- UMMAYA needs custom generated docs from schemas, prompt manifests, eval scenarios, and adapter metadata; self-owned build scripts are safer than hiding that in a SaaS.
- Mintlify remains the product-quality benchmark: UMMAYA should copy its outputs (`llms.txt`, preview builds, OpenAPI-like pages, Ask AI later), not necessarily its hosting model.

## Writing Methodology

### Use Diataxis As The Structural Method

Every page should be classified as one of four documentation types:

| Type | UMMAYA examples | Rule |
|---|---|---|
| Tutorial | Quickstart, first safe public lookup, first plugin | Teach by walking through a concrete success path |
| How-to guide | Resume a session, add an adapter, configure Langfuse | Help users complete a task they already understand |
| Reference | CLI flags, env vars, JSON schemas, tool catalog | Optimize for lookup, scanning, exactness |
| Explanation | Claude Code harness migration, Live/Mock/Handoff, permission model | Build the mental model and explain tradeoffs |

This prevents README-style sprawl. A "What You Can Ask" page is a how-to/workflow surface. "How UMMAYA Works" is explanation. `docs/api/schemas/*.json` is reference. The first install flow is a tutorial.

### Use Claude Code's Product-First Page Pattern

For UMMAYA's product pages, adapt this Claude Code pattern:

```text
1. Plain statement of what the feature lets the user do
2. Before you begin
3. Minimal working path
4. What the user sees
5. Safety or permission boundary
6. Common variants
7. Troubleshooting or next page
```

For citizen workflow pages:

```text
1. Situation
2. Prompt in Korean
3. Expected tool timeline
4. Live / Mock / Handoff status
5. Consent boundary
6. Result shape
7. What to do if UMMAYA stops
8. Related official policy/source links
```

For adapter pages:

```text
1. What citizen task this adapter supports
2. Tool ID and primitive
3. Live / Mock / Handoff status
4. Inputs and outputs
5. Permission tier and citation
6. Worked example
7. Failure modes
8. Schema and fixture links
```

### Use Google-Style Editorial Rules, With UMMAYA Exceptions

Baseline writing rules:

- Put the user's task in the title for tutorials and how-to pages.
- Use noun-phrase titles for concepts and references.
- Use present tense.
- Use active voice.
- Prefer short paragraphs and scannable tables.
- Avoid vague claims such as "seamless", "powerful", or "secure" unless evidence follows immediately.
- Do not anthropomorphize UMMAYA beyond product shorthand.
- Define acronyms on first use.
- Keep code identifiers in English.
- Korean is allowed for citizen prompts, agency names, legal/domain terms, and UI examples.

UMMAYA-specific style rules:

- Always distinguish Live, Mock, and Handoff when a workflow touches government action.
- Always state "not an official government service" on product-entry and protected-work pages.
- Never claim submission, payment, identity verification, certificate issuance, or tax filing is complete unless a live official channel and credential are documented.
- Cite the agency's own policy for permission behavior; do not invent UMMAYA policy.
- Write citizen examples as outcome prompts, not endpoint names.

### Add Vale As A Prose Linter

Vale should enforce a UMMAYA docs style package:

```text
.vale.ini
styles/
  ummaya/
    accept.txt
    reject.txt
    live-mock-handoff.yml
    affiliation.yml
    vague-claims.yml
    korean-domain-exceptions.yml
```

Suggested checks:

- Flag "official government service" unless it appears in a disclaimer saying UMMAYA is not one.
- Flag "will submit", "will pay", "will verify identity" unless page metadata marks the workflow as `tier: live` and `credential_status: validated`.
- Require "Live", "Mock", or "Handoff" on pages under `workflows/` and `coverage/`.
- Flag unsupported superlatives and marketing claims.
- Allow Korean domain examples without forcing English-only linting.

## CI/CD Automation Strategy

### What Should Be Generated

UMMAYA already has enough structured source material to automate much of the docs site.

| Generated docs surface | Source of truth | Existing or new generator |
|---|---|---|
| Tool schema reference | Pydantic v2 models | Existing `scripts/build_schemas.py` |
| Adapter catalog | `src/ummaya/tools/`, `docs/api/*` front matter | Extend existing docs/api catalog check |
| Env var reference | source env reads + `docs/configuration.md` | Existing `scripts/audit-env-registry.py` |
| Plugin catalog docs | plugin manifests and catalog index | Existing `scripts/regenerate_catalog.py` pattern |
| Prompt registry page | `prompts/manifest.yaml` | New docs generator |
| Citizen workflow cards | `evidence/scenarios/national_ax_citizen_requests_v1.yaml` | New docs generator |
| CLI reference | `ummaya --help`, slash commands, package metadata | New snapshot generator |
| TUI keyboard shortcuts | TUI keybinding registry | New TypeScript generator |
| Changelog/release evidence | release manifests, GitHub Releases | New release-docs sync |
| `llms.txt` / `llms-full.txt` | docs front matter + generated pages | New docs index generator |

### Required GitHub Actions

UMMAYA should add a docs workflow rather than overload the current CI job:

```text
.github/workflows/docs.yml

pull_request:
  paths:
    - "docs/**"
    - "docs-site/**"
    - "src/ummaya/tools/**"
    - "src/ummaya/primitives/**"
    - "prompts/**"
    - "evidence/scenarios/**"
    - "tui/src/keybindings/**"
    - "package.json"
    - "pyproject.toml"
    - ".github/workflows/docs.yml"

jobs:
  derive:
    - build schemas in --check mode
    - generate docs metadata in --check mode
    - verify adapter docs match registry
    - verify env registry matches code

  lint:
    - markdownlint or equivalent
    - Vale prose lint
    - front matter schema validation
    - internal link check
    - external link check in scheduled mode only

  build:
    - install docs-site dependencies with frozen lockfile
    - build static site
    - upload build artifact

  docs-qa:
    - run deterministic docs retrieval checks
    - run docs Q&A eval in offline/fixture mode
    - assert no answer claims Live where source says Mock/Handoff

  preview:
    - deploy PR preview to GitHub Pages preview, Cloudflare Pages, Netlify, or Vercel
```

For `main`:

```text
push to main
  -> docs derive/check
  -> docs build
  -> deploy Pages artifact
  -> verify /llms.txt and /llms-full.txt are live
  -> post docs URL and docs scorecard to workflow summary
```

For releases:

```text
release tag
  -> build package
  -> generate versioned reference pages
  -> update changelog page
  -> verify docs mention the released version
  -> verify install smoke page matches published artifact
```

### Drift Gates

The docs workflow should fail when:

- A new adapter is registered but has no docs page.
- A docs adapter page references a schema file that was not generated.
- A Pydantic schema changes but `docs/api/schemas/*.json` is stale.
- A new `UMMAYA_*` env var appears in code but not `docs/configuration.md`.
- A new slash command or keybinding exists in TUI but not the CLI/TUI reference.
- A prompt manifest hash changes but the prompt registry docs are stale.
- A scenario dataset changes but the "What You Can Ask" workflow cards are stale.
- A workflow page does not declare Live/Mock/Handoff.
- `llms.txt` does not include a public indexed page.
- `llms-full.txt` contains pages marked `llm_index: false`.

### Preview Deployment Options

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| GitHub Pages + Actions | Native, simple permissions, no extra vendor | PR preview story is weaker without add-on tooling | Good default for public docs |
| Cloudflare Pages | Fast previews, good static hosting | New vendor integration | Good if custom domain and previews matter |
| Netlify | Strong previews and redirects | New vendor integration | Fine, not necessary |
| Vercel | Strong previews, good for Next/Astro | New vendor integration | Fine if using Astro |
| Mintlify hosted | Best docs-native previews and checks | SaaS lock-in and paid features | Benchmark or future option |

Default recommendation:

```text
GitHub Pages for first public docs site
  + Actions artifact deployment
  + generated llms.txt
  + docs build artifacts
  + optional Cloudflare Pages later if preview UX is inadequate
```

## Docs Site Repository Layout

Recommended future layout:

```text
docs-site/
  package.json
  astro.config.mjs
  src/
    content/
      docs/
        start/
        use/
        coverage/
        architecture/
        build/
        reference/
    components/
      StatusBadge.astro
      WorkflowCard.astro
      ToolTimeline.astro
      PermissionTier.astro
    data/
      generated/
        adapters.json
        workflows.json
        env-vars.json
        prompt-manifest.json
        schemas.json
  public/
    llms.txt
    llms-full.txt
    _llm/
      index.json
      pages.jsonl

scripts/
  docs_generate.py
  docs_check.py
  docs_qa_eval.py
```

Keep canonical long-form source under existing `docs/` and `specs/` while `docs-site/src/content/docs/` contains user-facing pages. Generated data should be committed only if it is intended as public reference and checked for drift.

## Docs Automation Methodology

### Single-Source Principle

Documentation must not become a second implementation. Every factual page should name its source:

```yaml
source_of_truth:
  - src/ummaya/tools/location_adapters.py
  - docs/api/locate/index.md
  - docs/api/schemas/locate.json
freshness_check:
  - adapter_registry
  - schema_hash
```

The docs build should treat these as contracts, not comments.

### Docs Pull Request Checklist

Every docs PR should answer:

- Which audience is served?
- Which Diataxis type is this page?
- What source-of-truth files back it?
- Does it need Korean domain examples?
- Does it touch Live/Mock/Handoff claims?
- Does it change `llms.txt` output?
- Does it need a docs Q&A eval case?

### LLM-Assisted Writing Loop

LLMs can draft and refactor documentation, but they should not be the authority.

Allowed LLM tasks:

- Turn source-of-truth material into a first draft.
- Reorganize a page into the correct Diataxis type.
- Generate workflow cards from eval scenarios.
- Suggest troubleshooting symptom tables from issues and traces.
- Compare docs against source files and propose missing links.

Required validation:

- Source citation present.
- Generated docs diff reviewed.
- Drift checks pass.
- Vale passes or has explicit inline exception.
- Docs Q&A eval answer remains grounded.

Prohibited LLM output:

- New claims about government access.
- New permission classifications.
- New legal interpretations.
- New endpoint behavior not supported by agency docs or fixtures.
- Marketing phrasing that hides Mock/Handoff status.

## Recommended Implementation Phases

### Phase 0: Content Restructure Without New Stack

- Add docs front matter to selected high-value pages.
- Add a generated or manually maintained `docs/llms.txt`.
- Add a user-doc landing page under `docs/user/README.md`.
- Add page stubs for Quickstart, What You Can Ask, Live/Mock/Handoff, Permissions, Troubleshooting.
- Keep GitHub Markdown as the rendering surface.

### Phase 1: Docs Portal Spec

- Open a Spec Kit feature for the docs portal.
- Decide between Astro/Starlight and MkDocs Material.
- Define IA, front matter schema, `llms.txt`, raw Markdown, and docs API contract.
- Add docs validation tasks and scorecard.

### Phase 2: LLM-Readable Docs Pipeline

- Generate `llms.txt`, `llms-full.txt`, and `docs/_llm/index.json`.
- Add docs Q&A eval using `evidence/scenarios/` plus hand-authored support questions.
- Store docs scorecards under `specs/<feature>/docs-scorecard.yaml`.

### Phase 3: Product Docs Site

- Publish a docs portal with audience-specific paths.
- Add search.
- Add raw Markdown copy/read surfaces.
- Add pages for every current adapter family and scenario family.
- Keep docs source in this repository.

## Open Decisions

| Decision | Default recommendation |
|---|---|
| Docs stack | Astro/Starlight for user docs; MkDocs only if Python API autogen dominates |
| Language policy | English source text, Korean domain examples and user-facing prompt examples |
| Public docs hosting | Static site first; no live secrets or live citizen infrastructure calls |
| Search | Local generated index first; HTTP docs API later |
| AI assistant in docs | Only after `llms.txt` and docs Q&A evals pass |
| Current README | Keep short; route depth into docs site |

## Non-Goals

- Do not make docs claim UMMAYA can complete protected government actions without official authority.
- Do not hide mock or handoff status behind marketing language.
- Do not move source-of-truth facts out of specs, schemas, prompts, tests, and official policy citations.
- Do not add a docs SaaS dependency before a spec-driven PR decides the stack.
- Do not use LLM-authored docs without citation and freshness validation.

## Research Sources

- Claude Code docs index and sampled pages:
  - <https://code.claude.com/docs/llms.txt>
  - <https://code.claude.com/docs/en/overview.md>
  - <https://code.claude.com/docs/en/quickstart.md>
  - <https://code.claude.com/docs/en/common-workflows.md>
  - <https://code.claude.com/docs/en/how-claude-code-works.md>
  - <https://code.claude.com/docs/en/permissions.md>
  - <https://code.claude.com/docs/en/troubleshooting.md>
- Mintlify docs:
  - <https://mintlify.mintlify.app/ai/llmstxt>
  - <https://mintlify.mintlify.app/deploy/ci>
  - <https://mintlify.mintlify.app/deploy/preview-deployments>
  - <https://mintlify.mintlify.app/deploy/github>
  - <https://mintlify.mintlify.app/api-playground/openapi-setup>
- Astro and Starlight:
  - <https://docs.astro.build/en/guides/content-collections/>
  - <https://starlight.astro.build/getting-started/>
  - <https://docs.astro.build/en/guides/deploy/github/>
- Docusaurus:
  - <https://docusaurus.io/docs>
  - <https://docusaurus.io/docs/docs-introduction>
  - <https://docusaurus.io/docs/versioning>
  - <https://docusaurus.io/docs/markdown-features>
  - <https://docusaurus.io/docs/i18n/introduction>
- MkDocs and mkdocstrings:
  - <https://squidfunk.github.io/mkdocs-material/>
  - <https://mkdocstrings.github.io/>
- Writing and linting:
  - <https://diataxis.fr/>
  - <https://developers.google.com/style/>
  - <https://developers.google.com/style/headings>
  - <https://docs.vale.sh/>
  - <https://vale.sh/docs/formats/markdown>
- GitHub Pages automation:
  - <https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages>
