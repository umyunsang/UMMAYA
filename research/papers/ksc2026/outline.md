# KSC 2026 Paper Outline

Refreshed: 2026-05-29 KST.

The official KSC 2026 CFP was not visible in the checked KIISE HTML on
2026-05-29 KST. This outline therefore defines the research argument and
evidence plan, not final page limits or submission metadata.

## Working Title

**UMMAYA: Migrating a Claude Code-Style Tool Harness to Korean National
Administrative Infrastructure AX**

Korean working title:

**UMMAYA: Claude Code형 도구 하네스의 대한민국 국가행정 인프라 AX 적용**

## Authors

- Um Yunsang (affiliation TBD)
- Advisor (TBD, if required)

## Thesis

UMMAYA shows that the coding-agent harness pattern can be migrated to
citizen-facing public-service execution. The system keeps the Claude Code-style
tool loop, permission request path, context assembly, and TUI discipline, then
swaps the runtime model to K-EXAONE/FriendliAI and the tool surface to Korean
public-service adapters.

## Abstract Structure

1. **Problem**: Korean public-service work is fragmented across portals,
   agencies, identity rails, payment rails, certificate systems, and data APIs;
   citizens must know the institution map before they can act.
2. **Approach**: UMMAYA treats that work as a tool-loop problem: decompose the
   citizen request, discover registered adapters, establish authority with
   `check`, execute read/write primitives under permission boundaries, and
   return receipt or handoff evidence.
3. **System**: active primitives `find`, `locate`, `send`, and `check`; Pydantic
   v2 adapter schemas; Live/Mock/Handoff classification; Evidence Fabric v2.
4. **Evaluation**: scenario contract coverage, tool-surface schema quality,
   permission-boundary correctness, TUI/tool-loop ordering, and manual live
   canary evidence where credentials exist.
5. **Conclusion**: UMMAYA is an open-source client-side reference pattern for
   consuming national AX channels, not a government-endorsed service or a
   generic RAG chatbot.

## Contributions

- **C1. Harness migration argument**: formalizes the mapping from Claude Code's
  developer harness to a citizen-facing administrative harness.
- **C2. Authority-aware primitive abstraction**: separates public lookup,
  location resolution, identity/delegation, and side-effecting submission into
  `find/locate/check/send`.
- **C3. Adapter authority boundary**: classifies every public-service channel as
  Live, Mock, or Handoff and makes mock/handoff non-overclaiming part of the
  system contract.
- **C4. Evidence Fabric v2**: evaluates the system with scenario contracts,
  schema checks, prompt integrity, observability join keys, UX artifacts, and
  manual live canaries instead of answer-only grading.

## Paper Structure

### 1. Introduction

- Citizen problem: public-service execution is institution-centered, not
  outcome-centered.
- Research gap: RAG and chatbot interfaces can explain procedures but do not
  safely execute permissioned administrative work.
- Core claim: a Claude Code-style harness can be reused for public-service
  execution when authority, schema, and receipt boundaries are explicit.
- Contribution summary.

### 2. Background And Related Work

- Tool-using LLM agents and ReAct-style reasoning/action loops.
- Coding-agent harnesses, especially Claude Code-style tool loops and TUI
  permission UX.
- Agent framework references: OpenAI Agents SDK, Pydantic AI, AutoGen,
  LangGraph, Google ADK, MCP tool metadata.
- Korean public AX context: Korea AI Action Plan 2026-2028, Open API/OpenMCP
  direction, public-service channel fragmentation.
- Positioning: UMMAYA is not a general framework and not a document RAG system.

### 3. System Design

- Architecture overview: six layers from `docs/vision.md`.
- Active primitive surface:
  - `find`: public/delegated data search and fetch
  - `locate`: place/address/coordinate resolution
  - `check`: identity, consent, credential, and delegation ceremony
  - `send`: submission, payment, filing, registration, and other side effects
- Adapter registry: concrete tool IDs, Pydantic v2 input/output, JSON Schema,
  `search_hint`, policy citation, and permission metadata.
- Authority classification: Live/Mock/Handoff.
- Query/TUI boundary: tools-aware `chat_request`, NDJSON frames, `correlation_id`
  and `frame_hash`.

### 4. Implementation

- Runtime stack: Python 3.12+, FriendliAI Serverless,
  `LGAI-EXAONE/K-EXAONE-236B-A23B`, Pydantic v2, httpx, pytest, Ink + Bun.
- Claude Code reference-first migration method:
  `.references/claude-code-sourcemap/restored-src/` is the structural baseline.
- Current adapter families:
  - live/public lookup adapters where official public API contracts and
    credentials exist
  - mock/shape-mirrored identity and transactional adapters
  - handoff-only surfaces for opaque official portals
- Safety rules: no live citizen-infrastructure calls in CI, no fake completion,
  no fallback routing before endpoint/credential/parameter evidence.

### 5. Evaluation

#### 5.1 Scenario Contract Coverage

- Dataset: `evidence/scenarios/national_ax_citizen_requests_v1.yaml`.
- Report coverage by lifecycle domain, priority, public/protected route, and
  expected primitive chain.

#### 5.2 Tool-Surface Contract Quality

- Validate tool schemas, required fields, descriptions, and primitive coverage.
- Negative checks: model-visible dataset must not leak adapter IDs, fixtures, or
  expected tool IDs.

#### 5.3 Permission And Authority Boundary

- Measure fail-closed behavior on missing delegation.
- Verify `check -> send` chaining and irreversible-action confirmation.
- Verify mock disclosure and handoff clarity.

#### 5.4 Tool-Loop And TUI Ordering

- Confirm input, progress, tool dispatch, tool result, and final answer order.
- Verify frame join keys: `scenario_id`, `trace_id`, `correlation_id`,
  `prompt_manifest_hash`, `tool_catalog_hash`, `frame_hash`.

#### 5.5 Retrieval And Cost

- Compare deferred adapter discovery against naive all-tool exposure.
- Metrics: candidate recall, schema count, prompt token budget, latency, and
  prompt-cache stability.

### 6. Discussion

- Live access depends on official credentials and public contracts.
- Mock tools are shape-mirrors only and must not be presented as real
  administrative completion.
- Handoff remains the honest result for opaque portals.
- `subscribe` is intentionally deferred until UMMAYA owns an app/push runtime.
- Generalization: the method can transfer to other countries only if their
  public-service channels expose clear authority and receipt boundaries.

### 7. Conclusion

- Restate harness migration and authority-aware tool execution as the paper's
  central contribution.
- Future work: stronger live canary matrix, app/push runtime for notification
  workflows, broader handoff receipts, and stronger user-facing UX studies.

## Figures And Tables Needed

| Item | Purpose | Source |
|---|---|---|
| Fig. 1 | CC harness to UMMAYA harness mapping | `docs/vision.md` |
| Fig. 2 | `find/locate/check/send` primitive surface | `src/ummaya/primitives/__init__.py` |
| Fig. 3 | Live/Mock/Handoff adapter classification | adapter metadata + docs/api |
| Fig. 4 | Evidence Fabric v2 gate flow | `docs/design/verification-fabric-v2.md` |
| Fig. 5 | TUI tool-loop artifact sequence | current wireframes or captured UX artifact |
| Table 1 | Scenario coverage by domain | `evidence/scenarios/national_ax_citizen_requests_v1.yaml` |
| Table 2 | Tool-surface/schema coverage | generated docs/api schemas |
| Table 3 | Permission-boundary test matrix | tests around `check`/`send` |

## References To Include

- UMMAYA local canonical sources:
  - `docs/vision.md`
  - `docs/requirements/ummaya-migration-tree.md`
  - `docs/onboarding/five-primitive-harness.md`
  - `docs/design/verification-fabric-v2.md`
- Restored Claude Code source:
  - `.references/claude-code-sourcemap/restored-src/`
- Model/runtime sources:
  - LG AI Research K-EXAONE technical report / model card
  - FriendliAI K-EXAONE Serverless announcement and tool-calling docs
- Agent/tool-loop sources:
  - ReAct
  - Toolformer
  - AutoGen
  - OpenAI Agents SDK
  - Pydantic AI
  - LangGraph
  - MCP tool metadata
- Evaluation sources:
  - Terminal-Bench 2.0
  - TerminalWorld
  - BenchJack
  - SpecBench
  - OpenTelemetry GenAI semantic conventions
  - Harbor Framework task/dataset registry
- Policy sources:
  - Korea AI Action Plan 2026-2028
  - relevant agency/OpenAPI docs for adapters discussed in the results

## Open Items Before Final Submission

- Confirm official KSC 2026 CFP, template, page count, and track when KIISE
  publishes them.
- Replace all placeholder author/affiliation metadata.
- Generate final coverage tables from current tests and Evidence Fabric output.
- Replace historical v0.1-alpha UI frames with current protected and public
  scenario artifacts.
- Add exact citations for any live adapter evidence used in the results section.
