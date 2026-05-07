# KOSMOS Tool System Migration Plan

> Scope: Close the structural gap between Claude Code 2.1.88 (CC) Tool system and KOSMOS public-API harness. Preserve harness invariants (active primitive envelope, Pydantic v2 schemas, Layer-3 auth gate) while porting CC file layout, deferred-loading mechanism, and per-tool Result components.
>
> Authored by: Software Architect (Opus) · 2026-04-23 · Read-only investigation

---

## 1. Executive Summary

**Core findings**
1. KOSMOS already has a **more rigorous security model than CC** (V1–V6 validators on `GovAPITool`, dual auth dispatch with Layer-3 gate in `executor.invoke`), but its tool surface layout diverges from CC sharply: CC groups *all* assets for a tool under `src/tools/<ToolName>/{Tool.ts, UI.tsx, prompt.ts, …}`, whereas KOSMOS groups by **ministry** (`src/kosmos/tools/{koroad,kma,hira,…}`) with **no per-tool UI** in the TUI layer. The TUI renders everything through one generic `PrimitiveDispatcher` (`tui/src/components/primitive/index.tsx:139`).
2. The **main-tool router is already primitive-first**: the LLM sees `resolve_location`, `lookup`, `submit`, and `verify`. This matches the *main_verb = primitive* rule and is ahead of CC conceptually — CC's Tool interface is still per-verb (Read, Bash, Edit, …).
3. **Live-capable adapters today**: 10 real HTTP-calling adapters (KOROAD×2, KMA×6, HIRA×1) + 1 composite, plus 2 **Layer-3-gated stubs** (NMC, NFA 119, MOHW/SSIS) that are wired into the registry but intentionally return `LookupError(auth_required)` until personal-data auth is provisioned. Mock adapters (`src/kosmos/tools/mock/`) cover the active *submit/verify* primitives — all evidence-backed under `docs/mock/` per the Mock-vs-Scenario rule. `subscribe` is deferred until KOSMOS owns an app/push delivery runtime.
4. CC's **per-tool file bundle** (`UI.tsx`, `prompt.ts`, `permissions logic`, `ToolSearch searchHint`, preapproved hostnames) has **no KOSMOS analogue** today — the closest we have is `llm_description` on `GovAPITool` and a 16-file shared `primitive/` directory. This is the biggest structural gap for Epic #287 "90% file-layout match".
5. **Deferred tool loading** (ToolSearch) is idiomatic in CC — `shouldDefer=true` tools ship with stub schemas and require an explicit `ToolSearchTool` call to load. KOSMOS's `lookup(mode="search")` is *equivalent in behaviour* but *inequivalent in shape* — it produces `LookupSearchResult.candidates` rather than a schema-hydration side effect.

**Recommended migration path** (one paragraph): Preserve KOSMOS's primitive-first envelope and Pydantic-v2 security stack as the source-of-truth, but re-layer the per-adapter code into a CC-style `src/kosmos/tools/<AdapterName>/` bundle (`adapter.py`, `prompt.py`, `UI.tsx`, `permissions.py`). Introduce a thin `KosmosTool` protocol over the existing `GovAPITool` + primitive dispatchers so the TUI can look up per-adapter React renderers and decision-reason text the way CC's `renderToolResultMessage` does, without re-plumbing the backend envelope. Keep `PrimitiveDispatcher` as a fall-through default. Promote live adapters first, port seed-stubs (NMC/NFA/SSIS) into the new layout while still fail-closed on auth, and phase in CC-style per-tool `UI.tsx` for the eight Phase-1 adapters. Mock adapters stay ministry-grouped under `src/kosmos/tools/mock/` because their evidence docs (`docs/mock/<system>/README.md`) are already ministry-scoped and byte/shape-mirror bound.

---

## 2. KOSMOS Current Tool System

### 2.1 Directory tree (counts from `find … | wc -l`)

```
src/kosmos/tools/                  (70 .py files)
├── __init__.py · bm25_index.py · envelope.py · errors.py · executor.py
├── lookup.py · main_router.py · models.py · mvp_surface.py
├── rate_limiter.py · register_all.py · registry.py · resolve_location.py
├── search.py · tokenizer.py
├── geocoding/            backend-only (kakao_client.py, juso.py, sgis.py, region_mapping.py)
├── hira/                 1 adapter  (hospital_search.py)
├── kma/                  6 adapters + grid_coords + projection
├── koroad/               2 adapters + code_tables
├── mock/                 6 verify mocks + barocert / cbs / data_go_kr / mydata / npki_crypto / omnione
├── nfa119/               1 adapter (Layer-3 gated stub)
├── nmc/                  1 adapter + freshness
├── retrieval/            backend.py · bm25_backend.py · dense_backend.py · hybrid.py · degrade.py · manifest.py
└── ssis/                 1 adapter + codes.py

src/kosmos/primitives/
├── submit.py · verify.py · _errors.py · __init__.py

src/kosmos/permissions/            ~25 files incl. pipeline_v2.py, modes.py, ledger.py, steps/

tui/src/components/primitive/     18 .tsx files (850 LOC total)
└── PrimitiveDispatcher + 16 sub-renderers (AddressBlock, CoordPill, CollectionList, …)
```

**Total python tool-surface LOC** (excluding tests): 70 files, roughly 10–12k LOC.

### 2.2 Main-tool envelope (primitive-first, active surface)

| Primitive | Entry point | Shape | Code |
|-----------|-------------|-------|------|
| `lookup` | `kosmos.tools.lookup.lookup(inp)` | `LookupInput` discriminated on `mode` → `LookupOutput` (5 variants) | `src/kosmos/tools/lookup.py:33` |
| `resolve_location` | `mvp_surface.RESOLVE_LOCATION_TOOL` | `ResolveLocationInput` → `ResolveLocationOutput` (6 variants) | `src/kosmos/tools/mvp_surface.py:47` / `src/kosmos/tools/resolve_location.py` |
| `submit` | `kosmos.primitives.submit.submit(tool_id, params)` | `SubmitInput` → `SubmitOutput` (deterministic `transaction_id`) | `src/kosmos/primitives/submit.py:410` |
| `verify` | `kosmos.primitives.verify.verify(family, session_context)` | `VerifyInput` → discriminated `DigitalOnepassContext | … | VerifyError` | `src/kosmos/primitives/verify.py` |

Every dispatcher owns its own in-process registry (`_ADAPTER_REGISTRY`) parallel to the main `ToolRegistry`, so adapter registration is **primitive-scoped** (`register_submit_adapter`, `register_verify_adapter`) at import time — `src/kosmos/primitives/submit.py:149`. The legacy `GovAPITool` + `ToolExecutor` path handles `lookup(mode="fetch")` via BM25 retrieval then typed Pydantic invocation.

**Key invariant**: `LookupInput.tool_id` is the single routing key; `params: dict[str, object]` is opaque at the envelope layer and validated against `adapter.input_schema` only at invocation time (`src/kosmos/tools/executor.py:206`). This is the *shape-only harness* contract from Spec 031 — the main tool never names a ministry.

### 2.3 Adapter registry pattern

Two registries coexist:

1. **`ToolRegistry`** (`src/kosmos/tools/registry.py:164`) — holds every `GovAPITool` instance used by `lookup(mode="fetch")`. Builds a `Retriever` (BM25 by default, dense-embeddings via `KOSMOS_RETRIEVAL_BACKEND`) so `lookup(mode="search")` can rank adapters by Korean+English `search_hint`. Includes a `register()` backstop for V3/V6 security invariants that defends against `model_construct` bypasses (`registry.py:220-…`).
2. **Primitive registries** — one dict per active primitive (`_ADAPTER_REGISTRY` in `submit.py`, `_VERIFY_ADAPTERS` in `verify.py`), populated at adapter-module import. First-wins on `tool_id` collision (`AdapterIdCollisionError`, Spec 031 FR-020, `submit.py:169`).

Both paths share `AdapterRegistration` (Spec 031, `registry.py:93`) as the metadata schema — `(primitive, published_tier_minimum, nist_aal_hint, auth_type, auth_level, pipa_class, is_irreversible, dpa_reference, nonce)`.

### 2.4 Currently live-capable adapters

Source-of-truth: `src/kosmos/tools/register_all.py:33-115` (registration order).

| # | tool_id | Ministry | Endpoint (public) | Live? | Auth | PIPA | Evidence |
|---|---------|----------|-------------------|-------|------|------|----------|
| 1 | `resolve_location` | KOSMOS meta | `internal://resolve_location` | yes (no key if KAKAO/JUSO/SGIS set) | `public` | non_personal | `mvp_surface.py:47` |
| 2 | `lookup` | KOSMOS meta | `internal://lookup` | yes | `public` | non_personal | `mvp_surface.py:95` |
| 3 | `koroad_accident_search` | KOROAD | `apis.data.go.kr/B552061/frequentzoneLg/getRestFrequentzoneLg` | **yes** (data_go_kr key) | `api_key` / AAL1 | non_personal | `koroad/koroad_accident_search.py:343` |
| 4 | `koroad_accident_hazard_search` | KOROAD | same endpoint, `adm_cd` input | **yes** | `api_key` / AAL1 | non_personal | `koroad/accident_hazard_search.py:865` |
| 5 | `kma_weather_alert_status` | KMA | `apis.data.go.kr/B552061/…` (alert status) | **yes** | `api_key` / AAL1 | non_personal | `kma/kma_weather_alert_status.py:302` |
| 6 | `kma_current_observation` | KMA | KMA getUltraSrtNcst | **yes** | `api_key` / AAL1 | non_personal | `kma/kma_current_observation.py:365` |
| 7 | `kma_short_term_forecast` | KMA | KMA getVilageFcst | **yes** | `api_key` / AAL1 | non_personal | `kma/kma_short_term_forecast.py:339` |
| 8 | `kma_ultra_short_term_forecast` | KMA | KMA getUltraSrtFcst | **yes** | `api_key` / AAL1 | non_personal | `kma/kma_ultra_short_term_forecast.py:279` |
| 9 | `kma_pre_warning` | KMA | KMA 기상예비특보목록 | **yes** | `api_key` / AAL1 | non_personal | `kma/kma_pre_warning.py:252` |
| 10 | `kma_forecast_fetch` | KMA | same as getVilageFcst (lat/lon → LCC grid) | **yes** | `api_key` / AAL1 | non_personal | `kma/forecast_fetch.py:342` |
| 11 | `hira_hospital_search` | HIRA | `apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList` | **yes** | `api_key` / AAL1 | non_personal | `hira/hospital_search.py:226` |
| 12 | `nmc_emergency_search` | NMC | `api1.odcloud.kr/api/nmc/v1/realtime-beds` | **gated stub** — Layer-3 refuses until auth provisioned | AAL2 | personal_standard | `nmc/emergency_search.py:253` |
| 13 | `nfa_emergency_info_service` | NFA 119 | NFA getEmg*Info endpoints | **gated stub** | AAL2 | personal_standard | `nfa119/emergency_info_service.py:276` |
| 14 | `mohw_welfare_eligibility_search` | MOHW/SSIS | SSIS NationalWelfarelistV001 | **gated stub** | AAL2 | personal_standard | `ssis/welfare_eligibility_search.py:168` |

Composite tools have been removed (Epic #1634); the LLM now chains primitive adapters end-to-end through `lookup` per migration tree § L1-B B6.

Mock-only (under `mock/`, evidence in `docs/mock/<system>/`):
- **verify primitive**: `mock_verify_digital_onepass`, `mock_verify_ganpyeon_injeung`, `mock_verify_geumyung_injeungseo`, `mock_verify_gongdong_injeungseo`, `mock_verify_mobile_id`, `mock_verify_mydata` — shape-mirror of OpenDID / PASS / 공동인증서 / 모바일신분증 / MyData APIs. (`src/kosmos/tools/mock/verify_*.py`).
- **submit primitive**: `mock_traffic_fine_pay_v1` (data_go_kr), `mock_welfare_application_submit_v1` (mydata). (`mock/data_go_kr/fines_pay.py:1`, `mock/mydata/welfare_application.py:1`).
- **subscribe primitive**: removed from active code. National alert/RSS delivery requires a future app/push runtime.

### 2.5 Active primitive TUI renderer layout

`tui/src/components/primitive/` (18 files, 850 LOC). Single entry `PrimitiveDispatcher` (`index.tsx:139`) switches on `payload.kind` (5 arms + Unknown) and sub-dispatches:

- `lookup` → subtype discriminator → {PointCard, TimeseriesTable, CollectionList, DetailView, ErrorBanner}.
- `resolve_location` → renders subset of {CoordPill, AdmCodeBadge, AddressBlock, POIMarker}.
- `submit` → ok? SubmitReceipt : SubmitErrorBanner.
- `verify` → ok? AuthContextCard : AuthWarningBanner.
- Unknown `kind` → `UnrecognizedPayload` (FR-033 harness discipline: never guess).

The dispatcher is *tool-agnostic*: a KOROAD hazard search and an NMC ER bed lookup both render through `CollectionList`. There is **no per-adapter React component** today.

### 2.6 Permission pipeline + Audit + Observability integration

- **Permissions**: Spec 033 v2 pipeline (`src/kosmos/permissions/pipeline_v2.py:1`). Ordered gauntlet `killswitch → mode → rule → prompt`, AAL backstop pre-dispatch (FR-F02), PermissionMode spectrum `{default, plan, acceptEdits, bypassPermissions, dontAsk}` (`modes.py:21`) ported from CC 2.1.88's own `PermissionMode.ts`. Shift+Tab cycle limited to low/mid-risk modes.
- **Layer-3 auth gate**: enforced inside `ToolExecutor.invoke` before any adapter call — short-circuits to `LookupError(auth_required)` if `tool.requires_auth and session_identity is None` (`executor.py:173`). Zero upstream traffic on rejection (FR-025/FR-026).
- **Audit**: `ToolCallAuditRecord` schema lives in `src/kosmos/security/audit.py`; Spec 024 invariants I1–I4 enforced via `GovAPITool` V1–V5 model validators (`models.py:231`). Persistence is **deferred** (harness-only ledger is implemented at `src/kosmos/permissions/ledger.py` with HMAC-chained entries, but per-tool append is out of scope until Spec 024 Phase 2).
- **Observability**: Spec 021 OTEL spans emitted by `ToolExecutor.dispatch` (`executor.py:314`) — `gen_ai.operation.name`, `gen_ai.tool.name`, `gen_ai.tool.call.id`, `kosmos.tool.adapter`, `kosmos.tool.outcome`. Safety overlay: ingress scanner+redactor runs on every adapter output before envelope normalization (`executor.py:250-275`).
- **Ministry-scope guard**: `main_router.resolve_with_scope_guard` reads the citizen's Spec 035 consent memdir and refuses any `<ministry>_*` tool_id whose ministry is opted-out **before** any network call (`src/kosmos/tools/main_router.py:207`).

---

## 3. Claude Code Tool System

### 3.1 Directory tree

```
.references/claude-code-sourcemap/restored-src/src/
├── Tool.ts                       ← Tool<Input,Output,P> interface (793 LOC, this is the contract)
├── tools.ts                      ← registry + assembly (dispatcher list, feature-flagged)
├── tools/                        ← 184 files under 43 top-level tool directories
│   ├── AgentTool/
│   ├── AskUserQuestionTool/
│   ├── BashTool/                 ← bashPermissions.ts · bashSecurity.ts · BashTool.tsx · UI.tsx · prompt.ts · …
│   ├── BriefTool/
│   ├── ConfigTool/
│   ├── EnterPlanModeTool/ · EnterWorktreeTool/ · ExitPlanModeTool/ · ExitWorktreeTool/
│   ├── FileEditTool/ · FileReadTool/ · FileWriteTool/
│   ├── GlobTool/ · GrepTool/
│   ├── ListMcpResourcesTool/ · LSPTool/ · McpAuthTool/ · MCPTool/ · ReadMcpResourceTool/
│   ├── NotebookEditTool/ · PowerShellTool/ · REPLTool/
│   ├── RemoteTriggerTool/ · ScheduleCronTool/ · SleepTool/ · SyntheticOutputTool/
│   ├── SendMessageTool/ · SkillTool/ · TaskCreateTool/ · TaskGetTool/ · TaskListTool/
│   ├── TaskOutputTool/ · TaskStopTool/ · TaskUpdateTool/ · TeamCreateTool/ · TeamDeleteTool/
│   ├── TodoWriteTool/ · ToolSearchTool/ · WebFetchTool/ · WebSearchTool/
│   └── shared/ · testing/ · utils.ts
└── hooks/useCanUseTool.tsx       ← central permission arbiter (ported to tui/src/hooks/useCanUseTool.ts)
```

A typical tool bundles 6–18 files. BashTool has 18 (`bashCommandHelpers.ts`, `bashPermissions.ts`, `bashSecurity.ts`, `BashTool.tsx`, `BashToolResultMessage.tsx`, `commandSemantics.ts`, `commentLabel.ts`, `destructiveCommandWarning.ts`, `modeValidation.ts`, `pathValidation.ts`, `prompt.ts`, `readOnlyValidation.ts`, `sedEditParser.ts`, `sedValidation.ts`, `shouldUseSandbox.ts`, `toolName.ts`, `UI.tsx`, `utils.ts`). FileReadTool is minimal (5: `FileReadTool.ts`, `imageProcessor.ts`, `limits.ts`, `prompt.ts`, `UI.tsx`).

### 3.2 Tool interface summary

`Tool<Input, Output, P>` (`Tool.ts:362`) — key fields by purpose:

| Purpose | Fields |
|---------|--------|
| Identity | `name`, `aliases?`, `searchHint?`, `userFacingName()`, `getToolUseSummary?`, `getActivityDescription?` |
| Schema | `inputSchema` (Zod), `inputJSONSchema?`, `outputSchema?`, `strict?` |
| Lifecycle | `call(args, context, canUseTool, parentMessage, onProgress?)`, `validateInput?`, `checkPermissions(input, context)`, `prompt({ getToolPermissionContext, tools, agents, … })` |
| Concurrency | `isConcurrencySafe(input)`, `isReadOnly(input)`, `isDestructive?(input)`, `interruptBehavior?()`, `isOpenWorld?(input)` |
| Permission model | `preparePermissionMatcher?(input)`, `backfillObservableInput?(input)`, `toAutoClassifierInput(input)` |
| Rendering | `renderToolUseMessage(input,opts)`, `renderToolUseTag?`, `renderToolUseProgressMessage?`, `renderToolResultMessage?`, `renderToolUseRejectedMessage?`, `renderToolUseErrorMessage?`, `renderGroupedToolUse?`, `renderToolUseQueuedMessage?`, `isResultTruncated?`, `extractSearchText?` |
| API integration | `mapToolResultToToolResultBlockParam(content, toolUseID)`, `mcpInfo?`, `isMcp?`, `isLsp?`, `isTransparentWrapper?` |
| Deferred loading | `shouldDefer?`, `alwaysLoad?` |
| Persistence | `maxResultSizeChars` (tool-result spill threshold) |

Defaults supplied by `buildTool()` (`Tool.ts:757`) — `isEnabled=true`, `isConcurrencySafe=false`, `isReadOnly=false`, `isDestructive=false`, `checkPermissions → allow`, `toAutoClassifierInput → ''`, `userFacingName → name`. Fail-closed: concurrency/destructive both default to the *more restrictive* value.

### 3.3 Tool lifecycle

```
LLM emits tool_use block
  → findToolByName(tools, name)
  → tool.validateInput?(input)          // shape guards, e.g. path exists
  → tool.checkPermissions(input, ctx)    // returns {behavior:'allow'|'ask'|'deny', updatedInput, decisionReason}
  → useCanUseTool(tool, input, …)        // hook: shows PermissionRequest, uses ToolPermissionContext
  → tool.call(args, ctx, canUseTool, parentMsg, onProgress?)
  → tool.renderToolUseMessage / renderToolUseProgressMessage   (live UI while running)
  → tool.renderToolResultMessage(output, progressMsgs, opts)    (final UI)
  → tool.mapToolResultToToolResultBlockParam(content, toolUseID) (API-bound payload for next turn)
```

`ToolPermissionContext` (`Tool.ts:123`) is deeply immutable and carries `mode: PermissionMode`, `alwaysAllow/Deny/AskRules`, `additionalWorkingDirectories`, `isBypassPermissionsModeAvailable`. CC's `PermissionMode` is the exact superset KOSMOS already ports in `permissions/modes.py:21`.

### 3.4 Per-tool component/policy co-location

Every CC tool owns:
- **schema**: Zod `inputSchema` / `outputSchema` in the `.ts` file (e.g. `WebFetchTool.ts:24-46`).
- **prompt**: `prompt.ts` (per-tool DESCRIPTION + `renderPromptTemplate` emitted to the LLM).
- **permission policy**: `checkPermissions` closure + optional preapproved lists (`WebFetchTool/preapproved.ts`, `BashTool/bashPermissions.ts`).
- **UI**: `UI.tsx` exports `renderToolUseMessage`, `renderToolResultMessage`, `renderToolUseErrorMessage` (e.g. `FileReadTool/UI.tsx` has 5 switch arms: image / notebook / pdf / parts / text / file_unchanged).
- **cross-tool wiring**: `toolName.ts` exports a constant consumed by `tools.ts` registry.

Deferred tools (`shouldDefer=true`, e.g. WebFetchTool at `WebFetchTool.ts:71`) ship with schema stubs; the model must call `ToolSearchTool({query:"select:<name>"})` to hydrate the schema before issuing the actual call. KOSMOS's `lookup(mode="search")` is conceptually identical but returns structured `AdapterCandidate` rows rather than injecting a `<functions>` block.

---

## 4. Gap Matrix

Legend — **Impact**: L = low (cosmetic, optional), M = medium (requires refactor), H = high (structural migration blocker).

| # | Concern | CC approach | KOSMOS today | Gap | Impact |
|---|---------|-------------|--------------|-----|--------|
| G1 | Tool layout | 1 dir per tool, 6–18 files, colocated | 1 dir per ministry, 1 py per adapter, no per-tool dir | KOSMOS has **no per-tool dir** | **H** |
| G2 | Tool interface | Single `Tool<Input,Output,P>` with 40+ optional methods | `GovAPITool` pydantic record + external `ToolExecutor` callable | No unified TS-facing interface; KOSMOS has active primitive dispatchers instead | **M** (by design, aligns with main-verb-primitive) |
| G3 | Input schema | Zod `lazySchema()` (TS, single language) | Pydantic v2 (Python only) | Backend/TUI schema sharing relies on `inputSchema.model_json_schema()` → `to_openai_tool()` | M |
| G4 | Output schema | Optional Zod | Pydantic v2 discriminated union (5 variants for lookup, 6 for resolve_location, 4 for verify) | KOSMOS stricter; migration should keep KOSMOS discriminators | L |
| G5 | Permission gate | `tool.checkPermissions(input, ctx)` + `useCanUseTool` | Layer-3 gate in `ToolExecutor.invoke` + Spec 033 pipeline_v2 external to adapter | KOSMOS centralises; CC is per-tool. Port CC's `checkPermissions()` **optional** hook per adapter so tools can declare preapproved values (e.g. domain whitelist for WebFetch-style citizen services) | M |
| G6 | Rendering — use | `renderToolUseMessage(input,opts)` per tool | Generic — none per tool; `AssistantToolUseMessage` renders tool_id + summary only | Need per-adapter `renderToolUseMessage` (e.g. KOROAD: "도로 사고 다발 지역 조회 (서울 강남구, 2024)") | M |
| G7 | Rendering — result | Per-tool `renderToolResultMessage(output, progressMsgs, opts)` | Generic `PrimitiveDispatcher` sub-dispatches on `payload.subtype` | KOSMOS underfits: 10 live adapters share 5 renderers. Port per-adapter variants (e.g. `HiraHospitalResultMessage`, `KoroadHazardResultMessage`) **on top of** PrimitiveDispatcher fallback | M |
| G8 | Error rendering | `renderToolUseErrorMessage(result, opts)` per tool | Single `ErrorBanner` / `SubmitErrorBanner` / `AuthWarningBanner` | Per-adapter hints (e.g. "KOROAD year < 2019 → use …") | L |
| G9 | Deferred loading | `shouldDefer=true` + `ToolSearchTool({query:"select:X"})` schema hydration | `lookup(mode="search")` returns ranked candidates, `lookup(mode="fetch")` runs adapter | Semantically equivalent; syntactically not. Keep KOSMOS envelope; **do not** port CC's `shouldDefer` flag — the main-verb primitive supersedes it | L |
| G10 | Audit | Not enforced at the interface (CC is developer-domain, low-stakes) | `ToolCallAuditRecord` schema I1-I4; `GovAPITool` V1-V6 validators; Layer-3 gate | KOSMOS stricter — no port needed. Keep | L |
| G11 | Streaming | `onProgress?: ToolCallProgress<P>` callback + `renderToolUseProgressMessage` | No active adapter-level streaming | Future app/push runtime required before notification streams return | L |
| G12 | `userFacingName` | Per-tool function | `name_ko` field on `GovAPITool` | Port — add `userFacingNameForAdapter(tool_id, partialInput)` to the KOSMOS bridge layer for consistency | L |
| G13 | Search hint | `searchHint?: string` (free-text) | `search_hint: str` (bilingual Korean+English required) | KOSMOS stricter — keep; extend schema to `{ko: list[str], en: list[str]}` already used by `AdapterRegistration.search_hint` | L |
| G14 | Tool result size | `maxResultSizeChars` with auto-persist to disk | Safety detector+redactor runs, but no spill-to-disk policy | Port CC's spill policy if we add tools with large payloads (e.g. SSIS welfare PDFs) | L |
| G15 | File watchers / autoload | `isEnabled()`, `feature()` bundle-time gate | `register_all.register_all_tools()` — static | Port dynamic enablement only if MCP adapters land in KOSMOS | L |
| G16 | MCP support | First-class (`MCPTool`, `McpAuthTool`, `ReadMcpResourceTool`, `ListMcpResourcesTool`) | None | Explicit non-goal today (KOSMOS MCP will be a separate spec); document the gap | L |

---

## 5. Live API Permission Matrix

Evidence: `.env.example:1-30` (keys KOSMOS currently holds), `register_all.py:33-115`, `docs/mock/<system>/README.md`, `MEMORY.md § reference_koroad_portal`.

### 5.1 Ministries with live key today

| Provider | Key env var | Endpoint pattern | Live adapters bound | Notes |
|----------|-------------|------------------|---------------------|-------|
| data.go.kr (KOROAD/KMA/HIRA/NMC) | `KOSMOS_DATA_GO_KR_API_KEY` | `apis.data.go.kr/…` | 10 adapters (rows 3-12 in §2.4) | Single key covers four providers — memory §reference_koroad_portal |
| Kakao Local | `KOSMOS_KAKAO_API_KEY` | `dapi.kakao.com/v2/local/…` | `resolve_location` (internal) | Backend-only, not LLM-visible |
| JUSO | `KOSMOS_JUSO_CONFM_KEY` (optional) | `business.juso.go.kr/addrlink/addrLinkApi.do` | `resolve_location` (internal) | Log-and-skip when unset |
| SGIS | `KOSMOS_SGIS_KEY` + `KOSMOS_SGIS_SECRET` (optional) | `sgis.kostat.go.kr/…` | `resolve_location` (internal) | Log-and-skip when unset |

### 5.2 Ministries WITHOUT live auth (Layer-3 gated stubs or not yet wired)

| Provider | Proposed tool_id | Public spec | KOSMOS status | Mock viability (5-pt) |
|----------|-----------------|-------------|---------------|-----------------------|
| NMC (국립중앙의료원) | `nmc_emergency_search` | Documented at `api1.odcloud.kr/api/nmc/v1/realtime-beds`, OpenAPI partial | **live-gated stub** (Layer-3 refuses) | 4 — endpoint public, schema recordable once auth issued |
| NFA 119 (소방청) | `nfa_emergency_info_service` | EmergencyInformationService public endpoints | **live-gated stub** | 4 — 4 sub-operations documented on data.go.kr |
| MOHW / SSIS (복지로) | `mohw_welfare_eligibility_search` | NationalWelfarelistV001 XML spec (v2.2 §1.1) | **live-gated stub** | 4 — XML shape stable, fixtures recordable |
| KFTC MyData | (mock only) `mock_welfare_application_submit_v1` | MyData v2.0 2024-09-30 spec | Mock (shape-mirror) | 5 — public KFTC spec; `docs/mock/mydata/README.md` |
| data_go_kr traffic fine pay | (mock only) `mock_traffic_fine_pay_v1` | data_go_kr REST gateway | Mock (shape-mirror) | 4 — sandbox access requires agency approval |
| Digital Onepass + PASS/Kakao/Naver/Toss 간편인증 + 공동/금융인증서 + 모바일신분증 + MyData verify | `mock_verify_*` (6 adapters) | OmniOne OpenDID Apache-2.0 + published-tier docs | Mock (shape-mirror) | 4 — OpenDID OSS available, non-credentialed delegation |
| 정부24 제출 | **scenario only** | Not publicly disclosed | `docs/scenarios/gov24_submission.md` | 1 — OPAQUE, never mock |
| KEC XML signature | **scenario only** | XSD+keys withheld | `docs/scenarios/kec_xml_signature.md` | 1 — OPAQUE |
| NPKI portal session | **scenario only** | Proprietary browser-plugin handshake | `docs/scenarios/npki_portal_session.md` | 1 — OPAQUE |

**Evidence rule enforcement (`feedback_mock_evidence_based`)**: every row with score ≥ 4 cites a public spec. Rows with score 1 sit in `docs/scenarios/` and MUST NOT gain a mock adapter (`tests/test_no_opaque_mock_adapter.py` guards this).

### 5.3 Ingestion grade (Live / Mock / Scenario) per LLM-visible tool_id

| Grade | Adapters | Count |
|-------|----------|-------|
| **Live (CI-skipped, live on user machine)** | KOROAD×2, KMA×6, HIRA×1, composite×1 | 10 |
| **Live-gated stub** (Layer-3 refuses until auth issued) | nmc_emergency_search, nfa_emergency_info_service, mohw_welfare_eligibility_search | 3 |
| **Mock (byte/shape-mirror, evidence-backed)** | mock_verify×6, mock_traffic_fine_pay_v1, mock_welfare_application_submit_v1 | 8 |
| **Scenario (OPAQUE, no adapter)** | gov24_submission, kec_xml_signature, npki_portal_session | 3 |

---

## 6. Migration Recommendation

### 6.1 Target layout (per-adapter CC-style bundle)

```
src/kosmos/tools/<adapter_id>/
├── __init__.py                   # registration entry — re-exports GOV_API_TOOL + register()
├── tool.py                       # GovAPITool instance + input/output pydantic models
├── adapter.py                    # async handle() coroutine
├── prompt.py                     # Korean + English llm_description, search_hint, plus session guidance notes
├── permissions.py                # optional check_permissions() — per-adapter preapproved list or PIPA disclosure
├── fixtures/
│   └── happy_path.json           # recorded fixture (data_go_kr key redacted)
└── ui.tsx                        # (symlinked / mirrored into tui/src/components/tools/<adapter_id>/UI.tsx)
                                   # exports renderToolUseMessage, renderToolResultMessage, renderToolUseErrorMessage

tui/src/components/tools/<adapter_id>/
├── UI.tsx                        # per-adapter React renderers (takes LookupOutput, emits Ink nodes)
└── index.ts                      # registers the renderers in the per-tool component registry
```

Rationale: **file-layout match with CC** (G1) without giving up the primitive-first envelope. Each adapter still registers into `ToolRegistry` / primitive `_ADAPTER_REGISTRY` via `__init__.py`; the new `ui.tsx` layer is opt-in — `PrimitiveDispatcher` remains the default fallback.

### 6.2 `KosmosTool` protocol (bridge layer)

Introduce a TypeScript protocol in `tui/src/tools/KosmosTool.ts` (new file, **not** yet written — this is the proposal):

```ts
// Shape-compatible with CC's Tool<Input, Output, P>, narrowed to KOSMOS primitives.
export interface KosmosTool<Payload extends PrimitivePayload = PrimitivePayload> {
  readonly tool_id: string                    // e.g. 'koroad_accident_hazard_search'
  readonly name_ko: string                    // GovAPITool.name_ko
  readonly primitive: 'lookup' | 'resolve_location' | 'submit' | 'verify'
  readonly searchHint?: string                // derived from GovAPITool.search_hint
  userFacingName(input: Partial<Record<string,unknown>> | undefined): string
  getToolUseSummary?(input: Partial<Record<string,unknown>> | undefined): string | null
  getActivityDescription?(input: Partial<Record<string,unknown>> | undefined): string | null
  renderToolUseMessage(
    input: Partial<Record<string,unknown>>,
    opts: { theme: ThemeName; verbose: boolean }
  ): React.ReactNode
  renderToolResultMessage?(
    payload: Payload,
    opts: { theme: ThemeName; verbose: boolean }
  ): React.ReactNode
  renderToolUseErrorMessage?(
    payload: Extract<Payload, { kind: 'lookup'; subtype: 'error' } | { ok: false }>,
    opts: { theme: ThemeName; verbose: boolean }
  ): React.ReactNode
}
```

Backend side: add a thin `kosmos.tools.metadata.manifest()` generator that serialises every `GovAPITool` + `AdapterRegistration` into `tui/src/tools/generated/manifest.ts` at build time (one-way: Python → TS), so the TS side always reflects the source-of-truth Pydantic registry. No runtime dependency on Python in TS.

### 6.3 Tool deprecation list (CC-specific, DO NOT port)

| CC tool | Why skip |
|---------|----------|
| BashTool / PowerShellTool / REPLTool | Developer shell execution — no citizen-service parallel |
| FileReadTool / FileEditTool / FileWriteTool / NotebookEditTool | Filesystem editor — citizen apps never edit local files |
| GlobTool / GrepTool | Code search primitives |
| LSPTool | IDE language server |
| AgentTool / TaskCreateTool / TaskGetTool / TaskListTool / TaskOutputTool / TaskStopTool / TaskUpdateTool | Developer task orchestration (replaced by KOSMOS agents coordinator/worker) |
| TodoWriteTool | Developer task list |
| TeamCreateTool / TeamDeleteTool | Developer-team management |
| EnterPlanModeTool / ExitPlanModeTool / EnterWorktreeTool / ExitWorktreeTool | Developer workflow modes |
| ScheduleCronTool / RemoteTriggerTool | Self-hosted dev triggers |
| SkillTool / BriefTool | Claude Code-specific scoped skills |
| MCPTool / McpAuthTool / ListMcpResourcesTool / ReadMcpResourceTool | MCP integration — out of scope until KOSMOS MCP spec lands |
| SleepTool / SendMessageTool / SyntheticOutputTool | Dev-harness utilities |
| ConfigTool / TestingPermissionTool | CC-internal config surface |

**Retain/port**: `AskUserQuestionTool` (becomes a **new KOSMOS primitive candidate**, or folded into the permission prompt pipeline); `ToolSearchTool` already has a KOSMOS analogue as `lookup(mode="search")`; `WebFetchTool` pattern informs how a future `public_info_fetch` citizen tool could be built (with a preapproved domain list restricted to `.go.kr`).

### 6.4 Adapter promotion roadmap (Waves within Phase C-2)

#### Wave C-2.1 — Layout port for existing live adapters (≤11 files per Teammate)

| Task | Owner | Files touched |
|------|-------|---------------|
| T1: Port `koroad_accident_search` to `src/kosmos/tools/koroad_accident_search/` bundle + TUI `UI.tsx` | Sonnet-A | 5 py + 2 tsx = 7 |
| T2: Port `koroad_accident_hazard_search` similarly | Sonnet-A | 7 |
| T3: Port `kma_weather_alert_status` | Sonnet-B | 7 |
| T4: Port `kma_current_observation` | Sonnet-B | 7 |
| T5: Port `kma_short_term_forecast` + `kma_forecast_fetch` (shared projection.py) | Sonnet-C | 9 |
| T6: Port `kma_ultra_short_term_forecast` + `kma_pre_warning` | Sonnet-C | 9 |
| T7: Port `hira_hospital_search` | Sonnet-D | 7 |

Dependencies: T1–T7 are independent. (An early Wave C-2.1 included a port of a composite adapter, which has since been removed per Epic #1634 / migration tree § L1-B B6.)

#### Wave C-2.2 — Layer-3 gated stubs (NMC / NFA / MOHW)

| Task | Owner | Files |
|------|-------|-------|
| T9: Port `nmc_emergency_search` to new layout, keep fail-closed behaviour | Sonnet-A | 7 |
| T10: Port `nfa_emergency_info_service` | Sonnet-B | 7 |
| T11: Port `mohw_welfare_eligibility_search` | Sonnet-C | 7 |

#### Wave C-2.3 — Mock adapters (primitive-scoped, keep ministry grouping)

| Task | Owner | Files |
|------|-------|-------|
| T12: Add per-mock `UI.tsx` renderers for `mock_verify_*` (6 adapters) | Sonnet-A | 6 tsx + 1 registry |
| T13: Add per-mock `UI.tsx` for `mock_traffic_fine_pay_v1` / `mock_welfare_application_submit_v1` | Sonnet-B | 2 tsx + 1 registry |

Mock python modules remain in `src/kosmos/tools/mock/<ministry>/` — evidence docs at `docs/mock/<system>/README.md` are ministry-scoped and rebundling would break the mock-drift fixture recording process.

#### Wave C-2.4 — Bridge layer + manifest generation

| Task | Owner | Files |
|------|-------|-------|
| T15: `tui/src/tools/KosmosTool.ts` protocol | Sonnet-A | 1 |
| T16: `src/kosmos/tools/metadata.py::manifest()` generator + `tui/src/tools/generated/manifest.ts` build step | Sonnet-B | 3 |
| T17: `tui/src/tools/registry.ts` per-tool React renderer lookup | Sonnet-A | 2 |
| T18: `tui/src/components/messages/AssistantToolUseMessage.tsx` — delegate to `registry.renderToolUseMessage(tool_id, input)` with PrimitiveDispatcher fallback | Sonnet-B | 1 |
| T19: `tui/src/components/messages/` generic tool-result renderer — delegate similarly | Sonnet-B | 1 |

#### Wave C-2.5 — New candidate adapters (if ministry-scope opt-in covers them)

Candidate list (live API exists, no KOSMOS adapter yet — public spec verified, evidence-backed):

- **경찰청 실시간 교통정보** (police traffic) — data.go.kr public endpoint, AAL1
- **환경부 대기질 실시간 조회** (airkorea.or.kr public) — AAL1
- **국토교통부 버스도착정보 서비스** — AAL1
- **산림청 산불 발생 현황** — AAL1
- **기상청 지진/특보 이력** — AAL1 (complement to existing KMA adapters)

Each requires `/speckit-specify` of its own Epic; this plan only identifies them as Wave candidates.

### 6.5 Non-goals (this plan)

- MCP adapter support (defer to its own spec).
- Audit-record persistence (deferred per Spec 024 — only the schema lives today).
- Dense-retrieval embeddings tuning (Spec 585 live, not a tool-layout concern).
- Porting CC's `AskUserQuestionTool` — candidate for a *separate* primitive spec.

---

## 7. Immediate Phase C-2 Wave Dispatch (Teammate-scoped)

**Wave dispatch summary** — dependency DAG:

```
C-2.1 (8 tasks, ≤11 files each)
    ├── T1, T2  (KOROAD)           ← Sonnet-A, parallel-safe within Wave
    ├── T3, T4  (KMA atoms)        ← Sonnet-B
    ├── T5, T6  (KMA forecast)     ← Sonnet-C
    ├── T7      (HIRA)             ← Sonnet-D
    └── T8      (composite)        ← Sonnet-D, depends on T1-T6
         ↓ merge-fence
C-2.2 (3 tasks)   NMC/NFA/MOHW gated stubs  ← fan-out 3 Sonnets
         ↓ merge-fence
C-2.3 (3 tasks)   Mock UI.tsx renderers      ← fan-out 3 Sonnets, parallel-safe
         ↓ merge-fence
C-2.4 (5 tasks)   Bridge layer + manifest    ← 2 Sonnets, T15-T17 sequential, T18-T19 parallel
         ↓ merge-fence
C-2.5 New adapter specs                      ← Lead-solo, per-adapter /speckit-specify
```

**Parallel-safe rule**: within a Wave, no two tasks touch the same file. Wave boundary is a **hard merge fence**: the Lead integrates + reviews + runs `uv run pytest && bun test` before opening the next Wave.

**File budget per Teammate per Wave**: ≤11 files (matches the Wave-B / Batch-2 convention enforced in prior epics). Tasks T5, T6, T14 are the heaviest at 9 files each — still under budget.

**Blocker list before Wave C-2.1 can begin**:
1. `KosmosTool` protocol MUST exist (T15) so UI.tsx files have a type target — **elevate T15 to Wave C-2.0**.
2. Metadata generator (T16) MUST run in CI so TS manifest stays in lockstep with Python registry — **elevate T16 to Wave C-2.0**.
3. Phase 034 TUI Component Catalog SHOULD be frozen (it defines the Ink design tokens the new UI.tsx files reference).

Revised Wave C-2.0 (prerequisite, 2 Teammates):
- T15 (KosmosTool protocol), T16 (manifest generator). 4 files total. Blocks all downstream waves.

---

## 8. Memory rule compliance checklist

| Rule | Compliance |
|------|------------|
| **Harness not reimpl** | Plan preserves `GovAPITool` + primitive dispatchers; new layout is file-relocation + TS bridge, not a reimplementation. NMC/NFA/MOHW stay Layer-3 gated — no live-auth backfill attempted here. |
| **Main verb = primitive** | Main surface stays `resolve_location` + `lookup` + `submit` + `verify`; `subscribe` is deferred until app/push delivery exists. Ministry-specific vocabulary lives in adapters only. New per-adapter UI.tsx is rendering-only; it does not leak ministry shape into the envelope. |
| **Mock evidence-based** | Live/Mock/Scenario matrix in §5 cites public specs per row. No adapter proposed without verified public shape. Scores ≥ 4 all carry a link in `.env.example` / `docs/mock/<system>/README.md`. |
| **Mock vs Scenario** | Six `docs/mock/` systems retained (data_go_kr, cbs, mydata, barocert, omnione, npki_crypto). Three OPAQUE items (gov24 / kec xml signature / npki portal session) remain in `docs/scenarios/` only, with no adapter proposed. |
| **No hardcoding** | The LLM continues to drive tool choice via `lookup(mode="search")`. Per-tool `searchHint` stays a bilingual metadata field (`GovAPITool.search_hint`), not a static keyword router. No new static tokenisers / salvage code proposed. |

---

## 9. Artifacts referenced

All paths are absolute and read-only during this investigation.

- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/main_router.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/lookup.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/envelope.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/models.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/registry.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/register_all.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/executor.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/tools/mvp_surface.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/primitives/submit.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/permissions/pipeline_v2.py`
- `/Users/um-yunsang/KOSMOS/src/kosmos/permissions/modes.py`
- `/Users/um-yunsang/KOSMOS/tui/src/components/primitive/index.tsx`
- `/Users/um-yunsang/KOSMOS/tui/src/components/primitive/types.ts`
- `/Users/um-yunsang/KOSMOS/tui/src/hooks/useCanUseTool.ts`
- `/Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src/Tool.ts`
- `/Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src/tools.ts`
- `/Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src/tools/FileReadTool/FileReadTool.ts`
- `/Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src/tools/WebFetchTool/WebFetchTool.ts`
- `/Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src/tools/ToolSearchTool/ToolSearchTool.ts`
- `/Users/um-yunsang/KOSMOS/docs/mock/*/README.md`
- `/Users/um-yunsang/KOSMOS/docs/scenarios/README.md`
- `/Users/um-yunsang/KOSMOS/.env.example`
