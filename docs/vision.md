# KOSMOS — Platform Vision

> This document is the canonical architectural vision for KOSMOS. It is the single source of truth for *what we are trying to build* and *why*. Specs under `specs/` describe how to build individual features; this document describes the whole.
>
> Any spec, ADR, or implementation decision must align with this vision. If a later insight contradicts it, update this file in the same pull request.
>
> **Migration status (2026-04-26; primitive correction 2026-05-07)** — KOSMOS v0.1-alpha shipped. The six-Phase migration (P0 #1632 → P1+P2 #1633 → P3 #1634 → P4 #1847 → P5 #1927 → P6 #1637) completed under Initiative #1631. The harness migration described below is no longer aspirational: the LLM Harness pillar runs through FriendliAI Serverless + K-EXAONE with Claude Code's agent loop preserved; the Tool System pillar exposes active adapters across seven Korean ministries through `lookup` / `resolve_location` / `submit` / `verify` primitives, all documented in [`docs/api/`](./api/) with Pydantic v2 envelopes and Draft 2020-12 JSON Schemas; the 5-tier plugin DX (Spec 1636) is open for external citizen and ministry contributors. Live API regression, an app/push-notification runtime, and the in-TUI marketplace browser are tracked as deferred follow-ups.
>
> **Vision scope correction (2026-05-04)** — `data.go.kr` public APIs are one useful adapter family, not the product boundary. The target is national administrative and public-infrastructure AX: Hometax tax handling, Government24 civil-affairs submission, Wetax/local payments, certificates, mobile ID, simple authentication, public utility bills, welfare, healthcare, housing, education, labor, immigration, safety, and other citizen-facing state infrastructure exposed through one LLM-mediated execution surface.

## The ambition

Turn fragmented national administrative and public-infrastructure channels into a single
conversational execution surface where a citizen can ask for an outcome, not a portal. KOSMOS
should route, verify, submit, pay, or hand off across agencies and infrastructure
operators without requiring the citizen to know which institution owns each step.

`data.go.kr` is an important source of open and semi-open public data. It is not enough. The
real target includes transactional and identity-bearing infrastructure: Hometax, Government24,
Wetax/local tax, mobile ID, simple authentication, certificates, utility billing, public
payments, welfare portals, health insurance, education administration, labor and employment
systems, immigration services, disaster response, and local civil-affairs channels.

```
Citizen:  "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘."
KOSMOS:   verifies identity + retrieves Hometax tax data + prepares filing
          + asks final confirmation + submits or hands off with receipt evidence

Citizen:  "이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘."
KOSMOS:   sequences Government24 residence transfer before dependent vehicle,
          health-insurance, and education address updates

Citizen:  "이번 달 재산세랑 자동차세, 과태료 밀린 거 확인하고 납부 가능한 건 처리해줘."
KOSMOS:   discovers each bill source + itemizes amounts and deadlines
          + requests payment confirmation + executes only selected payments

Citizen:  "부모님 지역에 폭염, 미세먼지, 정전, 단수 알림을 묶어서 받아보고 싶어."
KOSMOS:   identifies the official notification channels and handoff/app path
          while separating public area alerts from delegated personal records
```

The citizen does not learn which ministry, portal, certificate rail, payment rail, or utility
operator owns the work. KOSMOS does the decomposition and routing.

## The thesis — harness migration from developer to citizen

KOSMOS's deeper claim is not "connect many public APIs." It is: **the Claude Code harness — the tool loop, the permission gauntlet, the context assembly, the TUI — is a general substrate for any domain that reduces to "call the right tools in the right order." Claude Code proved it for software development. KOSMOS migrates that harness from the developer domain to Korean national administrative infrastructure.**

| | Claude Code | KOSMOS |
|---|---|---|
| Who is it for? | Software developers | Citizens using national infrastructure |
| Tool surface | File system, shell, git, editors | National infrastructure channels: APIs, portals, identity rails, certificates, payments, utility operators, and official handoff paths |
| Primitive verbs | Read, Edit, Bash, Grep, WebFetch | lookup, resolve_location, submit, verify |
| Permission concerns | Dangerous shell commands, file overwrites | PIPA (PII protection), identity verification, legal ordering |
| Deployment | Developer laptop + IDE | Citizen laptop (TUI) → eventually mobile/web |

This framing has three consequences for every decision in this document:

1. **Claude Code is the first reference.** When the right design is unclear, read Claude Code (via the reconstructed sourcemaps in `Reference materials`) before inventing something new. Most Layer 1, 5, and 6 patterns come directly from Claude Code; they are not open for redesign without cause.
2. **Domain additions require justification.** Public-service constraints (PIPA, identity verification, ministry-specific consent, legally-ordered multi-step workflows) force additions Claude Code does not need — most visibly Layer 3 (Permission Pipeline) and the `browser_cdp`-style auth flows for `pay`/`issue_certificate` tools. These additions must be documented via ADR, not scattered as implicit design choices.
3. **Success is measured by citizen experience parity with developer Claude Code experience.** If a citizen asking "출산 보조금 신청하고 싶어" does not feel as magical as a developer typing `claude "fix the failing test"`, the harness migration is incomplete — regardless of how many APIs are wired up.

### Methodology parity — how main tools are discovered

Claude Code's ~5 main tools (Read, Edit, Bash, Grep, Glob, WebFetch) were not designed from first principles. They were **distilled from empirical observation of the most frequent, most general categories of developer work** — file reading, file editing, shell execution, content search, path matching, web fetching cover the bulk of what developers do; everything else is composition of these primitives.

KOSMOS must apply the identical method to citizen-government interaction — not copy Claude Code's verbs, but copy Claude Code's **discovery method**:

1. **Survey the full space.** Citizen-facing national infrastructure, not only public-data APIs and not cherry-picked demo scenarios. Tax, civil affairs, payments, identity, welfare, health, housing, mobility, business, labor, education, safety, immigration, legal documents, and personal-data rights must all be in scope.
2. **Extract cross-domain verbs.** What actions recur across institutions regardless of topic? (조회·신청·납부·발급·예약·알림 등)
3. **Weight by empirical frequency and consequence.** Use annual transaction volume where available, but also weight rare high-consequence workflows such as disaster relief, immigration deadlines, tax submission, and identity issuance. `data.go.kr` usage metrics are only one input.
4. **Distill to 6–8 always-loaded verbs.** Everything else is lazily discovered via `search_tools`. The upper bound matches Claude Code's cognitive budget for tool schemas in the system prompt.

**Spec 031** executed this method and originally ratified five domain-agnostic harness primitives. The active surface is now four (`lookup`, `resolve_location`, `submit`, `verify`). `subscribe` is deferred because official Korean notification delivery is anchored in authenticated app/mobile push channels, and KOSMOS does not yet own an app runtime that can receive or schedule push notifications. An earlier 8-verb proposal (with domain-tinted names such as `pay`, `issue_certificate`, `submit_application`, `reserve_slot`, `subscribe_alert`, `check_eligibility`) has been **retired** for leaking ministry knowledge into the main surface; domain specialization belongs in adapters (`src/kosmos/tools/<ministry>/<adapter>.py`), not in LLM-visible verb names. The method that produced the verb list is what is canonical — if a later survey contradicts a candidate, we re-run the method and update, rather than patching conclusions while keeping stale premises.

The ambition above describes **what** this migration enables. The methodology here fixes **how we decide which tools serve it**. The six layers below describe **how the migration is structured**. All three serve the same thesis.

## Inspiration and reference sources

KOSMOS adapts architectural patterns from the conversational AI agent ecosystem to the Korean public-service domain. We actively reference all available sources — open-source repos, official documentation, reconstructed architecture analyses, and leaked-source review documents — to build the best possible implementation.

### Reference materials

| Source | License / Type | What we adapt |
|---|---|---|
| Claude Agent SDK (`anthropics/claude-agent-sdk-python`) | MIT | Async generator tool loop, permission types, agent definitions, context management |
| OpenAI Agents SDK (`openai/openai-agents-python`) | MIT | Guardrail pipeline, retry matrix with composable policies, agent handoff patterns |
| Pydantic AI (`pydantic/pydantic-ai`) | MIT | Schema-driven tool registry, graph-based state machine, Pydantic v2 message assembly |
| AutoGen (`microsoft/autogen`) | MIT | AgentRuntime mailbox IPC, InterventionHandler for permission interception, cooperative cancellation |
| Anthropic Cookbook (`anthropic-cookbook`) | MIT | Orchestrator-workers pattern, multi-agent coordination examples |
| Anthropic, OpenAI official documentation | Public | Tool use protocols, prompt caching, context window management |
| Ink (`vadimdemedes/ink`) | MIT | React-based terminal UI framework — Claude Code's TUI framework |
| Gemini CLI (`google-gemini/gemini-cli`) | Apache-2.0 | Full Ink + React + Yoga TUI implementation, component hierarchy, hooks, themes |
| Claude Code sourcemap (`ChinaSiro/claude-code-sourcemap`) | Reconstructed | Tool loop internals, permission model, context assembly, TUI component structure |
| Claude Reviews Claude (`openedclaude/claude-reviews-claude`) | Analysis | Detailed architectural review, state management, rendering pipeline, design rationale |
| Claw Code (`ultraworkers/claw-code`) | Harness/Fork | Leaked source repackaged as harness — runtime behavior, hook system, tool execution flow |
| PublicDataReader (`WooilJeong/PublicDataReader`) | MIT | Korean `data.go.kr` API wire format ground truth — auth patterns, XML/JSON response normalization, inconsistent field names across ministries |
| "Don't Break the Cache" (arXiv 2601.06007) | Open access | Empirical prompt caching study: dynamic tool results at end preserve cache prefix, 41–80% cost cut in 30–50+ tool-call sessions |
| NeMo Guardrails (`NVIDIA/NeMo-Guardrails`) | Apache-2.0 | Colang 2.0 declarative tool-call validation rails — whitelist-of-approved-actions model, auditable policy language for PIPA compliance |
| Google ADK (`google/adk-python`) | Apache-2.0 | Runner-level plugin pattern for centralized permission enforcement, reflect-and-retry tool failure handling |
| LangGraph (`langchain-ai/langgraph`) | MIT | `RetryPolicy` per-node exponential backoff, `ToolNode(handle_tool_errors=True)` — Pydantic `ValidationError` fail-closed lesson at tool boundary |
| Mastra (`mastra-ai/mastra`) | Apache-2.0 | TypeScript agent framework — typed tool workflow graphs with loops, branching, human-in-the-loop (reference only; not used for Phase 2 TUI after ADR-003/004) |
| Korean Public APIs index (`yybmion/public-apis-4Kr`) | MIT | Curated `data.go.kr` API discovery index with auth type annotations — tool registry `search_hint` population |
| stamina (`hynek/stamina`) | MIT | Production-grade async retry with enforced jitter and capped backoff — Layer 6 retry policy foundation |
| aiobreaker (`arlyon/aiobreaker`) | MIT | Asyncio-native circuit breaker for per-API failure isolation — Layer 6 circuit breaker pattern |
| @inkjs/ui (`vadimdemedes/ink-ui`) | MIT | Official Ink component library (TextInput, Spinner, Select, theming) — TUI widget foundation |
| string-width (`sindresorhus/string-width`) | MIT | CJK full-width character column width calculation — Korean text terminal layout |
| K-AI2026 (`hollobit/K-AI2026`) | Public dashboard | 국가인공지능전략위원회 · 대한민국 인공지능행동계획 (AI Action Plan 2026-2028) live tracker — authoritative source for 공공AX 원칙 8/9 task alignment and ministry-program traceability |
| `kosmos-plugin-store` GitHub org | Apache-2.0 | KOSMOS plugin catalog — Tier 1 template + 4 example repos + index. SLSA v1.0 provenance source URI prefix (Spec 1636 R-3 + ADR-008). |
| slsa-framework/slsa-verifier | Apache-2.0 | Vendored Go binary (~10 MB) for SLSA v1.0 provenance verification at install time (Spec 1636 R-3 + ADR-008). |

Spec 031 records the original primitive survey; the active primitive list lives in `src/kosmos/primitives/__init__.py`.

### What is original to KOSMOS

The patterns above are general-purpose. KOSMOS's contribution is adapting them to the government public-service domain, which introduces constraints absent from coding agents:

- **Bilingual channel discovery** over heterogeneous public APIs, civil-affairs portals, identity rails, certificate systems, payment rails, utility operators, and official handoff paths
- **Bypass-immune permission pipeline** for citizen PII protection (governed by Korea's PIPA, not developer convenience)
- **Multi-institution agent coordination** where dependency ordering is dictated by law (e.g., residence transfer must precede vehicle registration)
- **Prompt cache partitioning** for cost-efficient government AI services (taxpayer-funded budget constraints)
- **Fail-closed API adapters** where the safe default is deny, not allow

## Six-layer architecture

KOSMOS is built around six architectural layers, each adapting a pattern family into the public-service domain.

| # | Layer | Role | Pattern family |
|---|---|---|---|
| 1 | **Query Engine** | The `while(True)` tool loop that resolves a civil-affairs request | Async generator state machine |
| 2 | **Tool System** | Registry and factory for national-infrastructure channel adapters | Schema-driven tool modules |
| 3 | **Permission Pipeline** | Citizen authentication and personal-data protection gate | Multi-step bypass-immune gauntlet |
| 4 | **Agent Swarms** | Ministry-specialist agents coordinated by an orchestrator | AsyncLocalStorage in-process coordinator (CC parity) + file-based mailbox IPC for crash resilience (KOSMOS Spec 027 extension) |
| 5 | **Context Assembly** | The 3-tier context the LLM sees each turn | System + memory + attachments |
| 6 | **Error Recovery** | Resilience against public-service channel outages, rate limits, maintenance, and handoff boundaries | `withRetry`-style error matrix |

The rest of this document walks each layer in detail.

---

## Layer 1 — Query Engine

The query engine is the heartbeat of a KOSMOS session. It runs an async generator loop that does not terminate until the citizen's request is resolved or unrecoverably blocked.

### Loop skeleton

```
async generator query(session):
    while True:
        1. Pre-process: load citizen context → compress prior turns
                         → identify relevant institutions and channels
        2. Call LLM: intent analysis + task decomposition
        3. Post-process: execute selected channel tools,
                         parse results, handle errors
        4. Decide: more info needed (tool_use) or civil-affairs
                   resolved (end_turn)
```

### Three design decisions carried over

**Async generators as the communication protocol.** No callbacks, no event buses. The loop `yield`s progress events; the caller applies backpressure by consuming at its own rate; cancellation propagates naturally when the consumer stops. A citizen pressing "cancel" must abort every in-flight API call — async generator cancellation gets this right without extra machinery.

**Mutable conversation history plus immutable per-call snapshots.** The conversation list is mutated in place as tools append results, but each LLM call receives an immutable copy. This is the single most important trick for keeping the prompt cache alive as the session grows. Without it, every tool response invalidates the cache and costs multiply.

**Multi-stage preprocessing pipeline.** Before each LLM call, the loop runs compression passes: tool-result budget, snip, microcompact, collapse, autocompact. A citizen doing residence transfer + vehicle address change + health insurance update in one session will blow the context window fast without this pipeline.

### Query state

```
QueryState:
    citizen_session       # auth level, profile, consent flags
    messages              # mutable conversation history
    active_agents         # currently spawned domain workers
    usage_tracker         # per-channel call budget and rate-limit accounting
    pending_channel_calls # in-flight tool invocations
    resolved_tasks        # completed civil-affairs sub-goals
```

### QueryDeps injection boundary

The query loop receives its LLM client, tool registry, permission policy, and telemetry emitter via an explicit `QueryDeps` dataclass at loop construction time — never imported from module scope inside the loop. This boundary is how Claude Code keeps the engine test-isolatable (parity with `src/query/deps.ts`) and how KOSMOS keeps E2E scenarios runnable without side effects on live government, payment, identity, or utility channels. Every new coordinator, worker, or replay harness constructs its own `QueryDeps` with the dependencies it needs; nothing implicit crosses the boundary.

### Termination conditions

```
StopReason:
    task_complete           # civil-affairs resolved
    needs_citizen_input     # awaiting clarification
    needs_authentication    # identity verification required
    api_budget_exceeded     # daily quota hit
    error_unrecoverable     # no fallback path
```

### Cost accounting as a first-class concern

Every LLM call and every infrastructure-channel call is debited against a session budget. Public APIs may have per-key quotas; portals, payment rails, identity providers, and utility operators may have rate limits, maintenance windows, or irreversible transaction semantics. The engine tracks remaining budget per channel and can substitute cached results, alternative channels, reminders, or official handoff guidance when direct execution is unsafe or unavailable. Observability hooks (OpenTelemetry-style counters) emit metrics for model tokens, cache hits, and per-institution call counts.

### Query ↔ TUI transport

The Python query loop never touches the terminal directly. Every progress event, tool call, permission prompt, and backpressure signal crosses the process boundary as a **single-line NDJSON frame on stdout** — the 21-arm discriminated union (`src/kosmos/ipc/frame_schema.py`). Spec 032 (`specs/032-ipc-stdio-hardening/spec.md`) established the original 19-arm baseline (Spec 287: 10 arms; Spec 032: 9 additions); Epic #1636 added `plugin_op` (arm 20); Spec 1978 ADR-0001 added `chat_request` (arm 21) — a tools-aware chat request from the TUI that carries the full conversation history and available tool definitions to the query engine (see `specs/1978-tui-kexaone-wiring/contracts/chat-request-frame.md`). KOSMOS uses the CC query-engine architecture (not academic ReAct): the TUI drives the conversation loop and the backend is a stateless responder. The JSON Schema at `tui/src/ipc/schema/frame.schema.json` is the versioned contract; its SHA-256 digest is emitted as the `kosmos.ipc.schema.hash` OTEL attribute at backend startup (FR-037). Envelope fields (`session_id` / `correlation_id` / `frame_seq` / `transaction_id`) thread every span so a citizen's turn is reconstructible end-to-end from Langfuse alone. `parse_ndjson_line` is fail-closed (FR-035): malformed bytes drop with a structured log, never aborting the session — Spec 032 T057 proves this on a 1000-frame / 5%-malformed stress stream (SC-007).

---

## Layer 2 — Tool System

Each public-service channel is wrapped as a **tool module** with a schema-driven registration and fail-closed defaults. A channel may be a public API, authenticated API, official portal flow, certificate issuance path, payment rail, utility operator endpoint, fixture-backed mock, or narrative handoff for opaque domains.

### Tool definition shape

```
GovAPITool:
    id                        # "koroad_accident_info"
    name_ko                   # "교통사고정보"
    provider                  # "도로교통공단"
    category                  # ["교통", "안전"]
    endpoint                  # API, portal, payment, identity, utility, or handoff URL
    auth_type                 # public | api_key | oauth | delegated_auth | handoff
    input_schema              # Pydantic model
    output_schema             # Pydantic model
    requires_auth             # default True
    is_concurrency_safe       # default False
    is_personal_data          # default True
    cache_ttl_seconds         # default 0
    rate_limit_per_minute     # default 10
    search_hint               # Korean + English discovery keywords
```

New adapters declare only the fields that deviate from the conservative defaults. This fail-closed posture means a new contributor adding an adapter cannot accidentally expose a personal-data-handling channel as public.

### Prompt cache partitioning

The tool registry orders tools into two partitions: **core tools** (always loaded, stable across sessions) form the prompt prefix, and **situational tools** (discovered on demand via tool search) form the suffix. Because the prefix is stable, its tokens remain cache-hit across sessions, dramatically lowering the amortized cost of the system prompt.

When a citizen switches from a transport question to a welfare question, the core tool schemas stay cached; only the welfare-specific tools incur a fresh encoding cost.

### Lazy tool discovery

With a national administrative surface, shipping every schema in the prompt is infeasible. The system keeps a small core set of high-frequency primitives always loaded, and exposes a `search_tools(query)` meta-tool that finds additional channel adapters by `search_hint` keywords and policy metadata.

```
Citizen:  "출산 보조금 신청하고 싶어요"
LLM:      search_tools("출산 보조금 복지부")
          → discovers welfare benefit, Government24 submission, local benefit,
             and payment-voucher channels
LLM:      calls only the channels that are allowed for the citizen's confirmed intent
```

---

## Layer 3 — Permission Pipeline

Public data is not the same as unconstrained data. Citizens' personal information flows through KOSMOS and must be gated.

### PermissionMode spectrum

Layer 3 inherits Claude Code's four-mode `PermissionMode` (`default`, `plan`, `acceptEdits`, `bypassPermissions`) as a first-class concept. KOSMOS tightens `bypassPermissions` under a PIPA-specific killswitch (parity with `src/utils/permissions/bypassPermissionsKillswitch.ts`) and adds a `citizen-ident-verified` precondition for tools whose `auth_level ∈ {AAL2, AAL3}`. The TUI mode-toggle shortcut (`shift+tab`, CC `chat:cycleMode`) cycles only through the modes the current citizen is permitted to enter; a session without AAL1 cannot reach `acceptEdits` at all.

### Multi-step gauntlet

Every tool invocation passes through a sequence of checks:

1. **Configuration rules** — per-channel access tier (public, authenticated, restricted, handoff-only)
2. **Intent analysis** — does the natural-language request justify this tool?
3. **Parameter inspection** — do the arguments contain personal identifiers the citizen is not entitled to query?
4. **Citizen authentication** — is the required identity verification level in place?
5. **Institution terms-of-use** — has the citizen consented to this agency, portal, utility, identity, or payment channel's data usage terms?
6. **Sandboxed execution** — the channel call runs in an isolated context with no ambient credentials
7. **Audit log** — every call is logged with timestamp, citizen id, channel, parameters, and outcome

### Bypass-immune steps

Certain checks **cannot be overridden** by any mode, including automation or administrator bypass modes. These include: querying another citizen's personal records, accessing medical records without explicit consent, and writing actions (application, modification, cancellation) without the identity verification level they require. A future "YOLO mode" must still respect these walls.

### Classifier separation of concerns

When LLM-based classifiers are used for intent risk assessment, they see **only the proposed tool calls and their arguments** — never the assistant's own justifying text. This prevents the model from talking the classifier into approving an action by writing convincing prose.

### Refusal circuit breaker

If the same session triggers a configurable number of consecutive refusals, KOSMOS stops retrying and routes the citizen to a human channel (call center or in-person service). This avoids infinite loops where the agent keeps trying variations of a disallowed action.

---

## Layer 4 — Agent Swarms

For multi-institution requests, a single monolithic agent is insufficient. KOSMOS uses a coordinator-and-workers swarm.

### Mailbox IPC

Workers and the coordinator communicate through a durable message mailbox rather than in-process callbacks. Initial implementation uses a file-based mailbox for simplicity; production scaling can migrate to a message queue (Redis Streams or similar) while keeping the same interface.

Why a mailbox: cross-process communication, crash resilience (messages persist), trivial debugging (inspect the mailbox contents directly), and no service discovery or daemon orchestration needed at small scale.

### Coordinator workflow

The coordinator is not a task dispatcher — it is a **synthesis engine**. Its workflow is always `Research → Synthesis → Implementation → Verification`:

```
Citizen: "이사 준비 중인데, 전입신고랑 자동차 주소변경이랑
         건강보험 주소변경 다 해야 하는데"

Coordinator:
  Research (parallel workers):
    ├─ Civil affairs agent → Government24 residence transfer requirements
    ├─ Mobility agent      → vehicle registration address change
    └─ Health agent        → health insurance address change

  Synthesis (coordinator, never delegated):
    "All three require residence transfer to happen first.
     After that, vehicle and health insurance can run in parallel."

  Implementation:
    Step 1: residence transfer (sequential — prerequisite)
    Step 2: vehicle + health insurance (parallel — independent)

  Verification (parallel):
    └─ confirm each transaction succeeded
```

The coordinator owns synthesis. Workers return raw findings; the coordinator integrates them into a plan.

### Permission delegation across agents

When a worker needs a permission its caller did not grant (for example, the transport agent needs the citizen's digital certificate for a vehicle address change), it sends a `permission_request` message up to the coordinator. The coordinator asks the citizen, receives the credential, and returns a `permission_response`. The worker then proceeds. Permissions never flow laterally between workers.

---

## Layer 5 — Context Assembly

The LLM sees a layered context on every turn.

### Memory tiers

```
1. System   — platform-wide policies (one file, applies to everyone)
2. Region   — region-specific rules (e.g., Busan ordinances)
3. Citizen  — the authenticated citizen's profile (age, residence, family)
4. Session  — what has been established in this conversation
5. Auto     — prior civil-affairs history (auto-memorized patterns)
```

Memory files support conditional activation. A rule block for senior-welfare APIs can be gated on `age >= 65` so younger citizens never see those tools, reducing prompt surface and avoiding irrelevant suggestions.

### Phase-1 delivered scope

Of the five memory tiers described above, Phase 1 (on `main` as of 2026-04-19) delivers only **System prompt assembly** (Spec 026 Prompt Registry) and **Session turn compaction** (`microCompact` + `autoCompact` parity with `.references/claude-code-sourcemap/restored-src/src/services/compact/`). The **Region**, **Citizen**, and **Auto** tiers — Claude Code's equivalent `src/memdir/` layer — are deferred to Phase 2+; no KOSMOS component currently reads or writes memdir-style files. Declaring this prevents vision drift and keeps the memdir port scoped under the CC→KOSMOS Phase 2 Migration meta-Epic (sub-Epic D).

### Per-turn attachments

Each turn the loop collects fresh dynamic context with a short timeout budget:

- Current authentication level and expiry
- In-flight civil-affairs state (what tools were called last turn)
- Relevant benefit programs derived from the citizen profile
- Live API health monitor (what is currently under maintenance)
- Session-scoped call count and remaining quota

### Reminder cadence

Long sessions drift. Every N turns the loop injects a reminder: unfinished tasks, authentication expiry warning, suggested related services. This keeps the model oriented without requiring the citizen to repeat themselves.

---

## Layer 6 — Error Recovery

Public-service infrastructure fails in predictable ways. The engine routes each failure class to a specific recovery strategy.

```
Channel call → error?
  ├── 429 Rate limited      → exponential backoff (base 1s, cap 60s)
  ├── 503 Maintenance       → search for alternative API → else advise citizen
  ├── 401 Auth expired      → refresh token, retry once
  ├── Timeout               → retry ×3, fall back to cached result
  ├── Data inconsistency    → cross-verify with a second authoritative channel
  └── Hard failure          → graceful message + in-person service guidance
```

**Foreground vs background distinction.** A citizen actively waiting on a response is a foreground query — aggressive retry is appropriate. A background batch (statistics refresh, auto-memory cleanup) is not worth extending an API outage for; it fails fast.

---

## TUI experience surface

The six layers above describe how KOSMOS reasons. This section describes how a citizen touches KOSMOS. The TUI (Ink + React + Bun, ported from `.references/claude-code-sourcemap/restored-src/` per ADR-004) is the Phase-1 and Phase-2 surface; mobile and web surfaces are out of scope for this document.

### Citizen onboarding

First-launch presents a dedicated onboarding sequence derived from Claude Code's step registry (`src/components/Onboarding.tsx`) with the developer-domain steps (API key, OAuth, terminal fonts) replaced by citizen-domain equivalents:

1. **KOSMOS brand splash** — renders the orbital-ring logo (`assets/kosmos-logo-dark.svg` / icon-component equivalent) with the wordmark `KOSMOS` and the subtitle `KOREAN PUBLIC SERVICE MULTI-AGENT OS`. The canonical palette is extracted directly from the SVG assets: background `#0a0e27` → `#1a1040` (gradient); orbital ring `#60a5fa` → `#a78bfa`; core `#818cf8` → `#6366f1`; wordmark `#e0e7ff`; subtitle `#94a3b8`; satellite nodes `#34d399` / `#f472b6` / `#93c5fd` / `#c4b5fd`. The current `tui/src/theme/dark.ts` `background` token (placeholder `rgb(0,204,204)`) is replaced with navy `#0a0e27` in the same PR that ports the onboarding splash.
2. **PIPA consent** — KOSMOS-original step with no Claude Code analog. Mandatory under PIPA §15 before any Layer-2 adapter executes; records consent version, timestamp, and the authenticated AAL gate.
3. **Infrastructure scope acknowledgment** — enumerates the agencies, portals, identity providers, payment rails, utility operators, and public-data sources the session may touch, plus their data categories; the citizen must acknowledge before adapters go live.
4. **Theme picker** — deferred until a light / high-contrast theme ships; Phase 1 runs the `dark` theme only.

### Keyboard-shortcut migration

Claude Code defines 65 bindings across 20 contexts (`src/keybindings/defaultBindings.ts`). KOSMOS currently implements 5 (Enter, y/Y, n/N/Esc, Backspace/Delete, IME passthrough for modifiers). The tiered migration scope is:

- **Tier 1 (pre-citizen-launch blocker)**: `ctrl+c` (interrupt active agent), `ctrl+d` (clean exit), `escape` in InputBar (cancel draft, gated on `!ime.isComposing`), `ctrl+r` (history search), `up`/`down` in InputBar (history prev/next, gated on empty buffer), `shift+tab` (cycle PermissionMode), `ctrl+o` (toggle transcript view — promoted from Tier 2 in Epic #2766 follow-up after the chord-registry-vs-fallback root-cause fix; see `tui/src/keybindings/types.ts:84` + `tui/src/keybindings/defaultBindings.ts:81`).
- **Tier 2 (post-launch hardening)**: `pageup`/`pagedown`, `ctrl+l` (redraw), `shift+tab` (cycle PermissionMode — binds to the Layer 3 spectrum), `ctrl+_` (undo), `ctrl+shift+c` (copy selection).
- **Tier 3 (deferred until dependent specs)**: `ctrl+x ctrl+k` (killAll — requires multi-worker), `ctrl+e` (external editor), `meta+p` (modelPicker — KOSMOS uses K-EXAONE only), `ctrl+s` (stash), `ctrl+v` (image paste).

IME safety rule: every binding that mutates the input buffer MUST check `!useKoreanIME().isComposing` before acting. Hangul composition must not be interrupted by a shortcut. The current `tui/src/hooks/useKoreanIME.ts` exposes the required predicate.

### TUI ↔ backend IPC

The Ink TUI reads the backend's stdout as an NDJSON stream and validates every line through the Zod discriminated union generated from the same schema the Python side emits (`tui/src/ipc/codec.ts` + `tui/src/ipc/frames.generated.ts`, bootstrapped by Spec 032 T018). Three resilience stories land in Phase 2:

- **Resume on stdio drop (FR-018..025).** The backend keeps a 256-frame `SessionRingBuffer` per session. When the TUI reconnects it emits a `resume_request(last_seen_frame_seq, tui_session_token)`; the backend replies with `resume_response(replay_count, resumed_from_frame_seq)` and replays exactly the missed frames — Spec 032 quickstart § 2 probes this end-to-end (`src/kosmos/ipc/demo/session_backend.py` ↔ `tui/src/ipc/demo/resume_probe.ts`).
- **Upstream 429 HUD (FR-014..016).** `BackpressureController.emit_upstream_429` converts an upstream Retry-After header into a `backpressure(signal="throttle")` frame with bilingual `hud_copy_ko` / `hud_copy_en` so the citizen sees a calm Korean banner with a live countdown (Spec 032 quickstart § 3, `tui/src/ipc/demo/hud_probe.ts`).
- **Critical-lane bypass (FR-017).** CBS 재난문자 and other `severity=critical` frames (notably `notification_push`) skip the pause gate regardless of ring/queue state — a flood-warning push must reach the HUD even when the session is throttled upstream.

Every TUI ↔ backend frame carries the same `correlation_id` the Python query loop already tags to its OpenTelemetry spans, so a "clicked this button" trace maps one-to-one onto the "called this adapter" trace without bespoke plumbing.

---

## Citizen scenarios (design targets)

KOSMOS success means a citizen can ask for real administrative outcomes without first knowing
the agency map. The target-state eval seed is
[`eval/scenarios/national_ax_citizen_requests_v1.yaml`](../eval/scenarios/national_ax_citizen_requests_v1.yaml).
Representative conversations:

1. **Tax execution** — "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘." → Hometax data retrieval, final review, filing or official handoff, receipt evidence
2. **Life-event bundle** — "이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘." → legally ordered cross-agency updates
3. **Payment consolidation** — "재산세, 자동차세, 과태료 밀린 거 확인하고 납부 가능한 건 처리해줘." → itemized bill discovery, explicit payment selection, payment receipt
4. **Birth and welfare bundle** — "아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘." → family registry, welfare, voucher, and insurance coordination
5. **Housing transaction** — "전세 계약했어. 확정일자, 임대차 신고, 전세보증 관련 절차를 처리해줘." → document checks, risk flags, filing, guarantee handoff
6. **Business start** — "카페 창업하려고 해. 사업자등록, 영업신고, 위생교육, 카드가맹, 세금 준비까지 순서대로 처리해줘." → business, licensing, training, merchant, and tax sequence
7. **Emergency and safety** — "집이 침수됐어. 피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 도와줘." → crisis-aware reporting, relief, inspection, and official notification-channel handoff
8. **Personal-data rights** — "정부기관들이 내 정보를 어디에 쓰고 있는지 확인하고 잘못된 주소나 연락처는 고쳐줘." → cross-agency data inventory, correction request, consent tracking

These are acceptance tests for the end-state direction. Current-code scenarios may be smaller,
but they must be justified as stepping stones toward this dataset rather than treated as the
product boundary.

## Roadmap

- **Phase 1 — Harness and public-data baseline** — FriendliAI Serverless + high-value public-data adapters + single query engine + CLI/TUI baseline.
- **Phase 2 — Transactional national-infrastructure mocks** — Hometax, Government24, Wetax, identity, certificate, payment, welfare, housing, labor, education, safety, immigration, and utility flows represented as mock or handoff channels with target-state shape fidelity.
- **Phase 3 — Verified live/handoff execution** — Live channels where credentials and public contracts exist; handoff channels where official portals remain opaque; full permission pipeline, identity verification, audit logging, and scorecard-backed acceptance tests.

## Code scope estimates

Approximate implementation sizes per layer, for rough planning only:

| Layer | Estimate |
|---|---|
| Query Engine | ~5,000 lines |
| Tool System | ~2,000 lines + N adapters |
| Permission Pipeline | ~6,000 lines |
| Agent Swarms | ~8,000 lines |
| Context Assembly | ~5,000 lines |
| Error Recovery | ~3,000 lines |

Total target: ~30,000 lines for the platform core, plus adapter modules.

---

## Non-goals

- KOSMOS is not a general-purpose coding agent. It does not edit files or run shell commands in a developer workspace.
- KOSMOS is not a government-endorsed service. It consumes public data but makes no claim of official authority.
- KOSMOS is not a chat wrapper around a single API. A chat wrapper would not need six architectural layers.

## Engineering values

KOSMOS is a foundation project (`속이 꽉찬 기초와 토대가 튼튼한 프로젝트`), not a demo. The values below gate every PR. They are deliberately phrased as principles, not metrics, because the failure modes they prevent (band-aid debt, hallucinated invention, surface-only polish) cannot be unit-tested. `AGENTS.md § Engineering principles` carries the operational rules.

1. **Root-cause over symptom.** Fix the architectural decision that allowed the bug, not the visible failure. Don't add `useInput` fallbacks for broken chord registries; don't `try/except`-swallow wrong contracts; don't stub over stale imports. Three failed symptom-fixes in a row → STOP and choose the root-cause path.
2. **Reference before invention.** The CC restored-src + the catalog in `Reference materials` answer most design questions. When they don't, escalate to a deep-research pass and add the new source to the catalog in the same PR. Never ship a guess (`feedback_check_references_first`).
3. **Foundations over surface gloss.** KOSMOS' worth is the depth of the swap (CC harness + 2 swaps, byte-identical otherwise), not how the splash screen looks. The 5-layer TUI verification chain (`docs/testing.md § TUI verification methodology`) and the integration-verification capture artefacts under `specs/integration-verification/` exist because surface tests pass while underlying registries silently break.
4. **Fallbacks are audited and time-bound.** Any fallback merged to `main` MUST cite its root cause (`file:line`) and the follow-up Epic that retires it. The Ctrl+O `useInput` fallback (PRs #2754 / #2767, retired in Epic #2766 follow-up by promoting `app:toggleTranscript` to Tier 1) is the canonical example of the band-aid → root-cause migration this rule enforces.

## How this document evolves

This file is expected to change as we learn. Rules of change:

1. Any change that alters a layer's contract must also update `AGENTS.md` and any dependent spec in the same pull request.
2. The six-layer breakdown is load-bearing. Do not collapse or rename layers without an ADR.
3. Additions are easier than changes. If in doubt, add a new sub-section rather than rewriting an existing one.
