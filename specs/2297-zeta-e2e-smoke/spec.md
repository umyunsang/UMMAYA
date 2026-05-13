# Feature Specification: Zeta E2E Smoke — TUI Primitive Wiring + Citizen Tax-Return Chain Demonstration

**Feature Branch**: `2297-zeta-e2e-smoke`
**Created**: 2026-04-30
**Status**: Draft
**Input**: User description: "Phase 0 TUI primitive call() wiring (replace stubs with real IPC tool_call/tool_result dispatch) + Phase 1 E2E citizen tax-return PTY+vhs smoke + policy-mapping doc + 5 OPAQUE scenario docs."

**Tracking**: Initiative #2290 · Epic ζ #2297 · supersedes the Phase 0 wiring mandate added 2026-04-30 to the Epic body. Prerequisite: Epic η #2298 (commit `1321f77`, merged 2026-04-30) which shipped `prompts/system_v1.md` rewrite + `src/ummaya/tools/mvp_surface.py` 5-tool LLM surface (`resolve_location` + `lookup` + `verify` + `submit` + `subscribe`, all `is_core=True`). Sub-issue #2481 ("verify dispatcher tool_id↔family_hint translation") inherited from η — this Epic resolves it.

## Mid-Epic findings carried from Epic η (2026-04-30)

Epic η T011 live smoke produced **0 receipts** across 3 attempts. Root-cause investigation by Lead Opus on 2026-04-30 identified three layered gaps:

1. **System prompt did not teach 4-primitive vocabulary** — fixed by Epic η (`prompts/system_v1.md` v2 with `<primitives>` / `<verify_families>` / `<verify_chain_pattern>` / `<scope_grammar>` nested XML tags + 10 mock_verify_* tool_id mapping; manifest SHA `bda67fb…`).
2. **LLM-visible 5-tool surface not registered as core** — fixed by Epic η (`src/ummaya/tools/mvp_surface.py` extended; registry 16 → 19; `verify` / `submit` / `subscribe` GovAPITool definitions added with Spec 025 V6 `auth_type ↔ auth_level` invariant satisfied).
3. **Backend `_VerifyInputForLLM` schema mismatch with the LLM-taught call shape** — **Epic ζ owns this fix (the actual citizen-blocker).** `src/ummaya/tools/mvp_surface.py:243` declares `_VerifyInputForLLM { family_hint: str; session_context: dict[...] }`, but `prompts/system_v1.md` v2 `<verify_chain_pattern>` (η-shipped, manifest hash `bda67fb…`, FR-022 immutable) teaches the LLM to call `verify(tool_id="mock_verify_module_<family>", params={...})`. The OpenAI-compat schema published to K-EXAONE shows `family_hint` while the prompt teaches `tool_id` — the LLM hits this contradiction and falls back to a conversational response (verifiable in `specs/2298-system-prompt-rewrite/smoke-citizen-taxreturn-pty.txt` tail: "현재 공공서비스 시스템에는 종합소득세 신고 기능이 제공되지 않고 있습니다" — 0 `tool_call` emitted, despite the system prompt teaching the chain). Fix: extend the backend schema with a `@model_validator(mode="before")` pre-validator that accepts BOTH shapes, deriving `family_hint` from `tool_id` via the canonical map sourced at boot from `prompts/system_v1.md`. See FR-008 / FR-008a / FR-008b.
4. **TUI primitive `call()` returns `{status: 'stub'}` regardless of input** — **secondary correctness concern (not the citizen-blocker).** `tui/src/tools/{Lookup,Verify,Submit,Subscribe}Primitive/*.ts:248-330` still contain Epic 1634 P3 stub bodies. Code reading (2026-04-30) confirms backend `_handle_chat_request` self-loops the agentic dispatch via `_dispatch_primitive` (server-side), and the TUI's `tool.call()` runs in parallel via `tui/src/services/tools/toolExecution.ts:1207`. Backend dispatch wins the race for in-memory mocks (the citizen-visible result is the backend's, not the TUI stub's), so this gap is masked at the citizen layer but is a real correctness bug — replaced regardless. See FR-001–FR-007.

The η `smoke-citizen-taxreturn-pty.txt` artefact (committed in η, line 21+) corroborates finding 3: spinner anim states ("Lollygagging…" / "Hatching…" / "Boogieing…") flash briefly during the LLM stream, then a conversational response arrives WITH NO `tool_call` emit. The η Lead's "TUI stub blocker" diagnosis was incomplete — the actual root cause is the backend schema↔prompt contradiction. This Epic closes both gaps for completeness.

**Canonical references** (every reference must be reread by `/speckit-plan` Phase 0):

- `docs/vision.md` § Reference materials — Claude Code is the first reference for any unclear design decision.
- `docs/requirements/ummaya-migration-tree.md` § L1-A A2 (Agent loop CC byte-identical) and § L1-C C1 (4 primitive `lookup` / `submit` / `verify` / `subscribe` reserved) and § L1-C C5 (Permission Adapter-level only, no primitive default).
- `prompts/system_v1.md` (η v2, manifest SHA `bda67fb…`) — citizen `verify → lookup → submit` chain pattern + 10-row tool_id ↔ family_hint canonical map embedded in `<verify_families>` block.
- `prompts/manifest.yaml` — Spec 026 fail-closed boot invariant; this Epic does NOT touch `prompts/`, manifest hash MUST remain unchanged.
- `specs/2298-system-prompt-rewrite/spec.md` — Epic η scope, FR-021–FR-023 (5-tool surface), Acceptance Scenario 1 (the same chain this Epic demonstrates end-to-end).
- `specs/2298-system-prompt-rewrite/smoke-citizen-taxreturn-pty.txt` — η T011 attempt 3 PTY log; the failure mode this Epic must invert.
- `specs/2296-ax-mock-adapters/contracts/delegation-token-envelope.md` § 1 (Issuance), § 2 (Consumption), § 3 (Scope grammar) — vocabulary the chain consumes.
- `specs/1979-plugin-dx-tui-integration/delegation-flow-design.md` § 12.4 (FINAL canonical AX-infrastructure caller diagram), § 12.5 (verify→submit chain), § 12.7 (mock fidelity grading).
- `src/ummaya/ipc/stdio.py` — `ChatRequestFrame` arm (Epic #1978, 2026-04-27) emits `tool_call` frames + fires `_dispatch_primitive` as background task (lines 1425–1500); `_dispatch_primitive` emits `tool_result` frames (line 1121); `_pending_calls` future-registry pattern (line 1462).
- `src/ummaya/primitives/{lookup,verify,submit,subscribe}.py` — server-side dispatchers; `verify.py` lines 35–42 `FamilyHint` Literal; lines 351–365 11-arm `AuthContext` discriminated union.
- `tui/src/tools/{Lookup,Verify,Submit,Subscribe}Primitive/*.ts:248-330` — the four `call()` stubs to replace.
- `tui/src/services/llmClient.ts` (or equivalent IPC bridge) — frame ingress/egress used by TUI primitive `call()`.
- `tests/integration/test_e2e_citizen_taxreturn_chain.py` — backend-only chain test asserting 3 ledger lines share the same `delegation_token`; this Epic adds a TUI-mediated counterpart.

**Hard rules carried** (from AGENTS.md):

- Zero new runtime dependencies (Python or TypeScript).
- All source text in English; Korean only for citizen-facing prompts/responses and existing Korean-domain strings.
- Spec 026 invariant: `prompts/**` untouched; manifest hash unchanged; shadow-eval workflow MUST report no diff for prompt files on this branch.
- TUI verification chain (AGENTS.md § TUI verification methodology): Layers 0/1/2/3/4 ALL required because this Epic touches `tui/src/**`.
- 1 Lead Opus = 1 Epic, dispatch unit = task/task-group (≤5 task / ≤10 file).
- push/PR/CI/Codex sequencing = Lead.
- PR title first character lowercase.
- GraphQL Sub-Issues API only for issue tracking.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Citizen tax-return chain renders a receipt id end-to-end (Priority: P1)

A citizen launches `bun run tui`, the UMMAYA welcome screen renders, and the citizen types `종합소득세 신고해줘`. The LLM (taught by η's system prompt rewrite) emits `verify(tool_id="mock_verify_module_modid", params={"scope_list": ["find:hometax.simplified", "send:hometax.tax-return"], "purpose_ko": "종합소득세 신고", "purpose_en": "Comprehensive income tax filing"})`. The TUI's `VerifyPrimitive.call()` — no longer a stub — forwards this call to the backend via the existing IPC frame protocol, awaits the matching `tool_result` frame, and returns the resolved `DelegationToken` envelope to the LLM loop. The LLM then emits `lookup(mode="fetch", tool_id="mock_lookup_module_hometax_simplified", params={"delegation_context": <token>})`, the TUI dispatches it identically, the prefilled hometax data is returned, and finally the LLM emits `submit(tool_id="mock_submit_module_hometax_taxreturn", params={"delegation_context": <token>, …})`. The backend mock submit adapter generates a synthetic `접수번호` of the form `hometax-YYYY-MM-DD-RX-XXXXX`, the TUI renders the citizen-facing Korean response with the receipt number cited, and the spinner closes within the harness's normal turn-completion time budget.

**Why this priority**: This Epic exists exclusively to land this end-to-end chain. Epic η shipped the prompt + tool surface; without TUI `call()` actually dispatching, no receipt can ever surface. Every later citizen-OPAQUE work (additional ministry adapters, multi-turn delegation, new families) is gated on this Epic's E2E proof.

**Independent Test**: Run the canonical Layer 4 vhs scenario (`specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.tape`) which produces 3+ `Screenshot` PNG keyframes (boot+branding → input-accepted/spinner-active → post-submit response with receipt id). Lead Opus uses the Read tool on each PNG (multimodal vision) to assert keyframe-3 contains text matching the regex `접수번호: hometax-2026-\d\d-\d\d-RX-[A-Z0-9]{5}`. Independently run the PTY Layer 2 expect script (`specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.expect`) and grep the captured `.txt` log for the literal string `CHECKPOINTreceipt token observed` (a synthetic checkpoint marker emitted by the smoke harness once the receipt arm is parsed). Independently run the TUI-mediated integration test `tests/integration/test_tui_primitive_dispatch_e2e.py` and assert ≥3 `tool_call` frames + ≥3 `tool_result` frames are observed across one chain. All three checks must pass on the same head; any failing is a P1 blocker.

**Acceptance Scenarios**:

1. **Given** a fresh UMMAYA TUI session on `2297-zeta-e2e-smoke` HEAD with `prompts/manifest.yaml` boot validation passing AND backend `mvp_surface.register_mvp_surface()` registering 5 core tools, **When** the citizen submits `종합소득세 신고해줘`, **Then** the LLM emits exactly three primitive tool_calls in order — `verify` (with a `tool_id` whose canonical-map family resolves to `modid`), `lookup(mode="fetch", tool_id="mock_lookup_module_hometax_simplified")`, `submit(tool_id="mock_submit_module_hometax_taxreturn")` — and the citizen-facing response cites a receipt id matching `hometax-YYYY-MM-DD-RX-XXXXX`.
2. **Given** the same chain has run, **When** the test reads `~/.ummaya/memdir/user/consent/<YYYY-MM-DD>.jsonl`, **Then** exactly three new lines exist, all referencing the same `delegation_token` value, with kinds `delegation_issued` / `delegation_used` (consumer = lookup) / `delegation_used` (consumer = submit, `receipt_id` populated, `outcome="success"`).
3. **Given** the same chain has run, **When** the test inspects the PTY-captured frame log, **Then** for each of the three primitive calls a matched `tool_call` ↔ `tool_result` pair is observed and the TUI's primitive `call()` returns the `tool_result` payload (NOT `{status: 'stub'}`).
4. **Given** the existing lookup-only path `날씨 알려줘 강남역`, **When** the LLM responds on this branch, **Then** the LLM still uses `resolve_location` → `lookup(mode="search")` → `lookup(mode="fetch")` (no spurious `verify` call) — the wiring change does NOT regress the 6 KMA / HIRA / NMC / KOROAD / NFA119 / MOHW lookup scenarios shipped in P6.

---

### User Story 2 — All 15 mock adapters are exercised at least once across the full scenario set (Priority: P2)

The UMMAYA mock surface defined by Epic ε #2296 + Epic η #2298 contains 15 mock adapters: 10 verify families (`simple_auth_module` / `modid` / `kec` / `geumyung_module` / `any_id_sso` / `gongdong_injeungseo` / `geumyung_injeungseo` / `ganpyeon_injeung` / `mobile_id` / `mydata`), 2 submit (`hometax_taxreturn` / `gov24_minwon`), 2 lookup OPAQUE-prefill mocks (`hometax_simplified` / `gov24_minwon_form`), and 1 subscribe mock (`hometax_status_stream`). This Epic's broader scenario battery — extending beyond the P1 single chain — exercises each mock at least once via citizen prompts that map to the appropriate family.

**Why this priority**: Demonstrates the mock surface is *callable*, not just *registered*. Sub-issue #2481 also requires this — the canonical `tool_id ↔ family_hint` map (10 verify rows + the broader scope grammar) must work for any of the 10 active verify families, not only `modid`. P2 because the demo headline is the P1 single chain; full-coverage validation is the next layer.

**Independent Test**: Add 5 fixture prompts to `tests/fixtures/citizen_chains/` — one each for the 5 ε-introduced families (`simple_auth_module`, `modid`, `kec`, `geumyung_module`, `any_id_sso`) plus 5 fixtures covering the 5 inherited families (`gongdong_injeungseo`, `geumyung_injeungseo`, `ganpyeon_injeung`, `mobile_id`, `mydata`). Each fixture pairs a citizen prompt with the expected first tool_call (canonical map enforced). The test harness drives `bun run tui` programmatically (or the new TUI-mediated integration test fixture from User Story 1), runs each fixture, and asserts: (a) each verify mock receives ≥1 invocation; (b) each submit/lookup/subscribe mock receives ≥1 invocation across the relevant fixtures; (c) no fixture errors out with `family_hint` mismatch.

**Acceptance Scenarios**:

1. **Given** the 10-fixture verify-family battery, **When** the harness runs all fixtures, **Then** each of the 10 verify mock adapters logs at least one `delegation_issued` event in the consent ledger.
2. **Given** the same battery extended with submit/lookup/subscribe scenarios, **When** the harness completes, **Then** all 15 mock adapters appear at least once in the captured PTY log's tool_call sequences.
3. **Given** a citizen prompt `사업자 등록증 발급해줘` (corporate authoritative), **When** the LLM responds on this branch, **Then** the first tool_call is `verify(tool_id="mock_verify_module_kec", …)` resolved by the canonical map to `family_hint="kec"` — not `modid`.

---

### User Story 3 — Sub-issue #2481 resolved: tool_id ↔ family_hint translation is deterministic and auditable (Priority: P1)

The TUI-emitted `verify(tool_id="mock_verify_module_<family>", params=…)` call must reach the backend dispatcher as `verify(family_hint="<family>", session_context=…)` with no LLM-visible round-trip ambiguity. The translation MUST occur at exactly one well-defined layer (TUI-side OR backend-side, chosen explicitly by this spec — see FR-008), be backed by the canonical map shipped in `prompts/system_v1.md` `<verify_families>` block, log the translation step in the audit trail (so a malformed `tool_id` produces a clear error rather than silently mismatching a family), and be covered by a regression test that asserts the canonical map's 10 entries each translate correctly.

**Why this priority**: Without a deterministic translation, the chain may pass for `modid` (the P1 demo path) but silently mistranslate for the other 9 families, producing dispatcher errors the citizen-facing UI cannot recover from. The Codex P1 #1 blocker from η explicitly named this as the dispatcher contract gap.

**Independent Test**: Add `tests/integration/test_tool_id_to_family_hint_translation.py` containing 10 parametrised cases — one per verify family in the canonical map. Each case constructs a `verify(tool_id="mock_verify_module_<family>", …)` call at the TUI boundary, observes the resulting backend dispatcher invocation, and asserts `family_hint == "<family>"`. An additional case asserts that an unknown `tool_id` (e.g. `mock_verify_module_xxx`) produces a structured error envelope (NOT a silent mistranslation or stack trace).

**Acceptance Scenarios**:

1. **Given** the canonical map's 10 verify families, **When** the translation test runs, **Then** all 10 cases pass with the expected `family_hint`.
2. **Given** an unknown `tool_id` `mock_verify_module_xxx`, **When** the TUI emits the call, **Then** the citizen-facing UI surfaces a structured error matching the existing TUI error envelope (`{ok: false, error: …}`) and the consent ledger logs no `delegation_issued` line for that call.
3. **Given** the translation layer is in place, **When** an auditor inspects an arbitrary chain run's frame log, **Then** for every `verify` call there is exactly one observable `tool_id` (TUI side) and exactly one corresponding `family_hint` (backend side) and the mapping matches the canonical map.

---

### User Story 4 — Policy mapping doc cites international gateway specs (Priority: P3)

UMMAYA's positioning as the client-side reference implementation for Korea's national AX infrastructure (CORE THESIS, AGENTS.md) requires a public-facing mapping document showing the correspondence between UMMAYA adapters and the four canonical international analogs: Singapore APEX, Estonia X-Road, EU EUDI Wallet, Japan マイナポータル API. The doc lives at `docs/research/policy-mapping.md`, is bilingual (ko-primary, en-fallback), cites each foreign spec by name and stable URL, and tabulates which UMMAYA adapter family corresponds to which foreign primitive type (data-pull vs identity-assertion vs delegated-submit vs subscription).

**Why this priority**: Publication-quality artefact for the demo + KSC 2026 narrative. Not a runtime gate. P3 because the demo headline is the P1 chain; the mapping doc is supporting prose.

**Independent Test**: Run `markdownlint` (existing project lint) and `linkchecker` (or equivalent stdlib HTTP HEAD probe in a small script) against `docs/research/policy-mapping.md`. Assert: (a) doc renders without lint errors; (b) every cited URL returns 2xx or 3xx within 5s; (c) the mapping table contains exactly 4 columns (UMMAYA adapter family / Singapore APEX / Estonia X-Road / EU EUDI / Japan マイナポータル) and ≥10 rows (one per active UMMAYA adapter family + one per primitive). Lead Opus reads the doc and confirms: each UMMAYA adapter row has at least one non-null mapping cell.

**Acceptance Scenarios**:

1. **Given** the doc is committed, **When** a reader opens `docs/research/policy-mapping.md`, **Then** the doc opens with a bilingual title, a 1-2 paragraph thesis statement linking AGENTS.md § CORE THESIS to the international analogs, and a single canonical mapping table.
2. **Given** the same doc, **When** the link probe runs, **Then** all foreign-spec URLs resolve.
3. **Given** the doc, **When** an auditor checks the citation footnotes, **Then** each foreign-spec citation includes at least one canonical URL (the agency's own spec, not a third-party blog) and a one-sentence quote of the mapped concept.

---

### User Story 5 — 5 OPAQUE-domain scenario docs explain hand-off (Priority: P3)

For the 5 UMMAYA-declared OPAQUE-forever domains (per `docs/requirements/ummaya-migration-tree.md` § L1-B "OPAQUE-forever"), one narrative scenario doc each must exist under `docs/scenarios/` — `hometax-tax-filing.md` / `gov24-minwon-submit.md` / `mobile-id-issuance.md` / `kec-yessign-signing.md` / `mydata-live.md`. Each doc explains, in citizen-narrative form (Korean primary), how UMMAYA hands off to the agency's own UI when no LLM-callable channel exists or is policy-mandated, and what the citizen sees in the TUI at each hand-off step.

**Why this priority**: Required by AGENTS.md § "OPAQUE domains are never wrapped — LLM hands off via `docs/scenarios/`." P3 because the 5 docs are narrative artefacts, not runtime code, and do not block the P1 demo.

**Independent Test**: For each of the 5 docs, assert presence + minimum 5 narrative steps (citizen action → TUI message → hand-off URL → return path → confirmation) + a footer pointing to the canonical agency UI URL the LLM hands off to. Lint-only; no runtime test.

**Acceptance Scenarios**:

1. **Given** the 5 docs exist at `docs/scenarios/{hometax-tax-filing,gov24-minwon-submit,mobile-id-issuance,kec-yessign-signing,mydata-live}.md`, **When** a reader opens any one, **Then** the doc has a Korean-primary title, a 1-paragraph "Why no adapter" thesis, a numbered citizen narrative (≥5 steps), and a footer `## Hand-off URL` section.
2. **Given** the docs are committed, **When** an auditor checks AGENTS.md § OPAQUE-forever paragraph + `docs/requirements/ummaya-migration-tree.md` § L1-B B3 for cross-reference, **Then** every OPAQUE-forever family named in those canonical docs has a matching scenario file.

---

### Edge Cases

- **Citizen submits a non-Korean prompt** (e.g. English `"file my income tax"`): The LLM should still emit the same chain (verify → lookup → submit) because `purpose_en` field exists in the scope grammar; the citizen-facing response should match the citizen's input language.
- **Backend dispatcher times out** (mock adapter sleeps >30s by misconfiguration): TUI `VerifyPrimitive.call()` MUST surface a timeout error envelope (NOT hang indefinitely). Existing IPC frame timeout mechanism is reused.
- **K-EXAONE emits malformed function_call args** (JSON parse fails): Backend already handles via `args_obj = {"_raw": slot["args"]}` (stdio.py line 1437). TUI MUST tolerate the resulting tool_result error envelope and render a citizen-facing "내부 오류" message rather than crash.
- **K-EXAONE emits an unknown primitive name** (e.g. `query` instead of `lookup`): Backend already handles via `unknown_tool` error frame (stdio.py line 1454). TUI MUST tolerate.
- **Citizen interrupts mid-chain** (Esc during the verify step): The TUI must abort the IPC future, surface "취소되었습니다" to the citizen, and emit a `cancelled` ledger entry rather than leaving an orphan delegation token.
- **Translation layer receives a nonexistent `tool_id`** (typo by LLM): Per US3 AC2, surface a structured error.
- **Two concurrent tool_calls in the same LLM turn** (e.g. multi-tool batch): The TUI must dispatch them in parallel (CC's query-engine contract) and aggregate their tool_results; any one timeout/error must not block the others.
- **Receipt id has fewer than 5 chars in the random suffix** (mock-adapter regression): Acceptance regex is strict — `\d\d-RX-[A-Z0-9]{5}` — so a regression here fails the smoke at keyframe Read.

## Requirements *(mandatory)*

### Functional Requirements

#### Phase 0 — TUI primitive call() wiring (P1)

- **FR-001**: The TUI primitive `LookupPrimitive.call()` (currently `tui/src/tools/LookupPrimitive/LookupPrimitive.ts:319-330`) MUST replace its `{status: 'stub'}` body with a real dispatcher that (a) constructs an IPC `tool_call` frame from the LLM-supplied input, (b) registers a TUI-side future keyed by the frame's `call_id`, (c) awaits the matching `tool_result` frame on the IPC ingress stream, and (d) returns the resolved frame's payload as the `ToolDef` output (success envelope `{data: {ok: true, result: …}}` or error envelope `{data: {ok: false, error: …}}`).
- **FR-002**: The TUI primitive `VerifyPrimitive.call()` (currently `tui/src/tools/VerifyPrimitive/VerifyPrimitive.ts:248-263`) MUST replace its stub identically per FR-001, with the additional translation step in FR-008.
- **FR-003**: The TUI primitive `SubmitPrimitive.call()` (currently `tui/src/tools/SubmitPrimitive/SubmitPrimitive.ts:255-265`) MUST replace its stub identically per FR-001.
- **FR-004**: The TUI primitive `SubscribePrimitive.call()` (currently `tui/src/tools/SubscribePrimitive/SubscribePrimitive.ts`, line range to verify during implementation) MUST replace its stub identically per FR-001, with the additional caveat that subscribe returns a session-lifetime `SubscriptionHandle` and the TUI must keep the underlying IPC subscription open until the LLM emits an explicit unsubscribe or the session ends.
- **FR-005**: The four `call()` bodies MUST share a single dispatcher helper (e.g. `tui/src/tools/_shared/dispatchPrimitive.ts`) that encapsulates the IPC frame round-trip + future registration + timeout handling, so the four primitives differ only by their argument-shape massaging and result-typing.
- **FR-006**: The shared dispatcher MUST honour an explicit timeout (default 30s, citizen-facing message: "응답 시간이 초과되었습니다") and MUST emit an OTEL span attribute `ummaya.tui.primitive.timeout=true` on timeout. The 30s default may be overridden via `UMMAYA_TUI_PRIMITIVE_TIMEOUT_MS` env var.
- **FR-007**: The shared dispatcher MUST surface backend-emitted `error` frames to the citizen as the existing TUI error envelope (`renderToolResultMessage` rendering a "오류 / Error: …" line) and MUST NOT crash the TUI process.
- **FR-008**: The system MUST resolve the verify-arm `tool_id ↔ family_hint` translation at the backend boundary so that the LLM-emitted shape `verify(tool_id="mock_verify_module_<family>", params={"scope_list": [...], "purpose_ko": "...", "purpose_en": "..."})` (as taught by `prompts/system_v1.md` v2 `<verify_chain_pattern>`) is accepted without LLM-visible signature change. **Decision: Option B (backend-side translation in `_VerifyInputForLLM`).** Plan-Phase-0 code reading (2026-04-30) confirmed the actual blocker: `src/ummaya/tools/mvp_surface.py` `_VerifyInputForLLM` declares `family_hint: str` + `session_context: dict[...]`, but `prompts/system_v1.md` v2 (η-shipped, manifest hash bda67fb…, FR-022 immutable) teaches the LLM to call `verify(tool_id=..., params=...)`. The actual citizen-facing failure is that `_dispatch_primitive` (`src/ummaya/ipc/stdio.py:993`) reads `args_obj.get("family_hint") or args_obj.get("family")`, gets `""`, and the verify primitive fails with empty family. The fix MUST translate `tool_id` → `family_hint` and `params` → `session_context` at exactly one layer. Option B is chosen because the LLM emits args directly to the backend dispatcher (TUI primitive `call()` runs in parallel with — and races against — backend `_dispatch_primitive`; backend always wins for in-memory mocks). Translating at the TUI layer is therefore architecturally moot for the citizen-blocker. (Option A — TUI-side translation — would still be useful as defensive correctness for the TUI dispatcher path covered by FR-001–FR-007, but is not the citizen-blocker fix.)
- **FR-008a**: The backend `_VerifyInputForLLM` schema (`src/ummaya/tools/mvp_surface.py:243`) MUST accept the LLM-emitted shape `{tool_id, params}` AND the legacy shape `{family_hint, session_context}`. A `@model_validator(mode="before")` pre-validator MUST detect the LLM shape, derive `family_hint` from `tool_id` via the canonical 10-row map (extracted from `prompts/system_v1.md` `<verify_families>` block at process boot — never duplicated in code), pack `params` into `session_context`, and rebuild the validated dict so the rest of the schema sees the legacy field names. The mapping MUST cover all 10 active verify families plus reject unknowns with a typed `ValueError("unknown verify tool_id: ...")`.
- **FR-008b**: The canonical 10-row `tool_id ↔ family_hint` map MUST be sourced from `prompts/system_v1.md` `<verify_families>` block at backend process boot (read-once, in-memory), NOT hardcoded in Python. A regression test MUST parse the markdown block and assert the parsed map is non-empty and contains the 10 canonical families. Drift between markdown and code MUST be impossible by construction (single source-of-truth = the markdown; code reads it).
- **FR-009**: The TUI-side `VerifyPrimitive.call()` (when dispatching via tool_call IPC per FR-002) MUST NOT translate `tool_id`. It forwards the LLM-emitted shape unchanged so the backend's `_VerifyInputForLLM` pre-validator owns the translation. Symmetric tests MUST assert the IPC `tool_call` frame's `arguments` object preserves `tool_id` and `params` field names verbatim.
- **FR-010**: An unknown `tool_id` (one not present in the canonical map) MUST produce a structured error envelope at the backend dispatcher (the `_VerifyInputForLLM` validator raises `ValueError("unknown verify tool_id: <value>")`, surfaced to the TUI as a `tool_result` envelope `{kind: "verify", error: "unknown verify tool_id: <value>", tool_id: <value>}`); the TUI renders the error as the existing "오류 / Error: 알 수 없는 인증 모듈입니다 (<value>)" envelope. The error MUST NOT crash the agentic loop — the LLM continuation receives the error as a `role="tool"` message and may retry with a corrected `tool_id`.

#### Phase 1 — E2E smoke + docs (P1 / P2 / P3)

- **FR-011**: The Layer 2 PTY scenario `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.expect` MUST drive `bun run tui` from a clean state, send `종합소득세 신고해줘`, wait for the chain to complete (timeout 90s), and capture the full pty session to `specs/2297-zeta-e2e-smoke/smoke-citizen-taxreturn-pty.txt`.
- **FR-012**: The Layer 4 vhs scenario `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.tape` MUST emit BOTH the animated `Output smoke-citizen-taxreturn.gif` AND **at least 3 named `Screenshot` PNG keyframes** at the canonical scenario stages: keyframe-1 (boot+branding), keyframe-2 (input-accepted with active spinner showing first tool dispatched), keyframe-3 (post-submit response with receipt id visible). Lead Opus uses the Read tool on each PNG to verify the rendered UI before push.
- **FR-013**: The captured PTY log MUST contain the literal string `CHECKPOINTreceipt token observed` exactly once. The smoke harness inserts this string when it parses the receipt arm from a backend `tool_result` payload — this is the LLM-readable convergence marker.
- **FR-014**: The captured PTY log MUST show ≥3 `tool_call` frames and ≥3 `tool_result` frames in interleaved order — not just stub sentinels.
- **FR-015**: The captured PTY log MUST show the citizen-facing receipt id rendered in the assistant's final message, matching the regex `접수번호: hometax-2026-\d\d-\d\d-RX-[A-Z0-9]{5}`.
- **FR-016**: The new integration test `tests/integration/test_tui_primitive_dispatch_e2e.py` MUST drive a TUI-mediated chain in a pytest fixture (using stdin/stdout pipes against a spawned `bun run tui` subprocess, ≤80 LOC), assert FR-014 + FR-015, and join 3 ledger lines on the same `delegation_token` value.
- **FR-017**: The doc `docs/research/policy-mapping.md` MUST be authored bilingually (Korean primary, English fallback per AGENTS.md § Source Code Language for Korean domain data), include exactly one mapping table with 4 foreign-spec columns (Singapore APEX / Estonia X-Road / EU EUDI Wallet / Japan マイナポータル) and ≥10 UMMAYA-adapter rows, and cite each foreign spec by stable canonical URL.
- **FR-018**: The 5 OPAQUE scenario docs `docs/scenarios/{hometax-tax-filing,gov24-minwon-submit,mobile-id-issuance,kec-yessign-signing,mydata-live}.md` MUST each contain a Korean-primary title, a "Why no adapter" thesis paragraph, a numbered citizen narrative (≥5 steps with citizen action / TUI message / hand-off URL / return path / confirmation), and a footer `## Hand-off URL` section listing the canonical agency UI URL.
- **FR-019**: The 10-fixture verify-family battery `tests/fixtures/citizen_chains/<family>.json` (one file per active verify family in the canonical map) MUST exist; each fixture pairs a citizen prompt with the expected first tool_call + expected `family_hint` translation.
- **FR-020**: A test `tests/integration/test_all_15_mocks_invoked.py` MUST run the 10-fixture battery + appropriate lookup/submit/subscribe extensions and assert all 15 mock adapters appear at least once in the captured tool_call sequences.
- **FR-021**: The acceptance regex check (FR-015) MUST be a non-flaky CI gate. The smoke harness uses a deterministic seed for the receipt-id random suffix when running under `CI=true` so the regex is stable across reruns. (The mock-adapter receipt suffix retains its production randomness when not in CI.)

#### Quality + invariants

- **FR-022 [LIFTED 2026-04-30 mid-PR per user authorization]**: Originally stated "MUST NOT modify any file under `prompts/**`". Lifted after live smoke evidence demonstrated K-EXAONE was not following the chain pattern from η v2; user explicitly authorized prompt rewrite within this PR. New `prompts/system_v1.md` v4 (SHA-256 `7bf22c42…`) adds a `<critical_first_directive>` block above `<role>` with: (a) trigger-word list (`신고/신청/발급/접수/제출/납부/위임/마이데이터`), (b) mandatory `verify(...)` first-call directive, (c) explicit forbidden-phrase list ("공공서비스 어댑터가 등록되어 있지 않습니다" etc.), (d) worked example. `<core_rules>` reorganised — chain TRIGGER promoted to top-level "규칙 1". `<verify_chain_pattern>` table extended with submit-class trigger → adapter mapping. `prompts/manifest.yaml` recomputed accordingly. `session_guidance_v1` / `compact_v1` SHA unchanged.
- **FR-023**: No new Python or TypeScript runtime dependencies (AGENTS.md hard rule). Build-time / test-time deps may be added under `[dev]` extras only with explicit justification in `plan.md`.
- **FR-024**: All `tui/src/**` changes MUST pass `bun typecheck` (UMMAYA scope) + `bun test` + `bun run tui` boot smoke before push.
- **FR-025**: All Python changes MUST pass `uv run ruff format --check` + `uv run ruff check` + `uv run mypy src/ummaya` + `uv run pytest` before push.
- **FR-026**: Sub-issue #2481 ("verify dispatcher tool_id↔family_hint translation (Codex P1)") MUST close on merge, with the PR body's `Closes` line referencing the parent Epic only (#2297) per AGENTS.md § PR closing rule; the sub-issue closes via the `subIssues` graph after merge.

### Key Entities

- **TUI Primitive Call Envelope** — the `(tool_id, params)` LLM-emitted shape that the TUI primitive `call()` receives; for `verify` arms this contains `tool_id="mock_verify_module_<family>"` which the FR-008 translation layer maps to `family_hint`.
- **IPC Tool Call Frame** — schema already defined per Epic #1978 N4 (`tool_call` arm of the `IPCFrame` discriminated union); contains `call_id` (UUIDv7), `name` (primitive name), `arguments` (the tool_id-aware dict for verify, the bare params dict for the other three).
- **IPC Tool Result Frame** — same schema family; contains `call_id` (must match a pending call), `result` (success envelope) or `error` (error envelope with `code` + `message`).
- **TUI Pending Call Registry** — TS-side analog of the Python `_pending_calls` future registry; keyed by `call_id`, valued by a `Promise<ToolResult>` that the IPC ingress handler resolves.
- **Family Map** — a static 10-row TS-side map (`mock_verify_module_<family>` → `family_hint`) byte-equal to the `<verify_families>` block in `prompts/system_v1.md`.
- **DelegationToken** — Spec ε payload carried in `result.delegation_context` for verify; consumed by lookup/submit downstream calls; bound to `scope_list` (verify-issued) ∩ `consumer_scope` (consumer-required).
- **PTY Log Artefact** — `specs/2297-zeta-e2e-smoke/smoke-citizen-taxreturn-pty.txt`, the LLM-grep-friendly text capture used to validate FR-013/FR-014/FR-015.
- **PNG Keyframe Artefacts** — three `.png` files under `specs/2297-zeta-e2e-smoke/scripts/` named `smoke-keyframe-{1-boot,2-dispatch,3-receipt}.png`, used for Lead Opus visual verification per AGENTS.md § Layer 4.
- **Policy Mapping Doc** — `docs/research/policy-mapping.md`, the bilingual reference doc; not a runtime artefact.
- **OPAQUE Scenario Doc** — 5 narrative files under `docs/scenarios/`; not runtime artefacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 [BLOCKED → #2516 — model-level limitation, not spec gap]**: A citizen running the canonical PTY scenario sees a hometax receipt id (matching `접수번호: hometax-2026-\d\d-\d\d-RX-[A-Z0-9]{5}`) in the assistant's final response within 90 seconds of typing `종합소득세 신고해줘`. **Verification**: PTY log contains the receipt-id regex exactly once + `CHECKPOINTreceipt token observed` exactly once. **Status (2026-04-30, post FR-022 lift)**: BLOCKED — K-EXAONE on FriendliAI Tier 1 demonstrably ignores even maximally-strong prompt directives. Three prompt iterations attempted in this PR: (v1, η baseline) chain pattern in `<verify_chain_pattern>` only — LLM emits no `tool_call`. (v3, "규칙 1" promotion) chain TRIGGER moved to top of `<core_rules>` with explicit `lookup search 금지` directive — LLM still emits `lookup(mode="search")` first. (v4, `<critical_first_directive>`) imperative block added ABOVE `<role>` with worked example and forbidden-phrase list — LLM STILL emits `lookup(mode="search")` and outputs the exact forbidden phrases ("검색 결과가 없습니다", "어댑터가 없습니다", direct hometax.go.kr URL). Conclusion: this is a **K-EXAONE instruction-following capability ceiling**, not a prompt-engineering gap. Tracked as #2516. Resolution paths: (a) FriendliAI Tier 2/3 + larger K-EXAONE variant, (b) K-EXAONE finetune on chain-following examples, (c) backend-side post-processing that detects "lookup(mode='search')" with submit-class trigger words and rewrites the call to `verify(...)`. Wiring scaffolding from this PR (Phase 0a + 0b + 1a + path B) provides the substrate for any of those follow-ups.
- **SC-002 [BLOCKED → #2516 — model-level limitation, not spec gap]**: Lead Opus visually confirms keyframe-3 of the vhs capture shows the receipt id rendered. **Verification**: Read tool on `specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-3-receipt.png`. **Status (2026-04-30 post FR-022 lift)**: BLOCKED — same root cause as SC-001. Keyframe-3 captured shows the LLM's fallback prose (hometax navigation guide + "https://www.hometax.go.kr" URL output, the exact pattern `<critical_first_directive>` forbids). Documents that the model-level gap survives even the strongest prompt-engineering pass.
- **SC-003**: The verify-family battery exercises all 10 active verify families with first-tool-call accuracy ≥9/10 (the LLM may legitimately disambiguate one family edge case). **Verification**: `pytest tests/integration/test_tool_id_to_family_hint_translation.py -v` reports ≥9 PASS.
- **SC-004**: All 15 mock adapters log ≥1 invocation across the full scenario battery. **Verification**: `pytest tests/integration/test_all_15_mocks_invoked.py` PASS.
- **SC-005**: The TUI-mediated chain logs exactly 3 ledger lines per chain run, all sharing the same `delegation_token` value. **Verification**: `pytest tests/integration/test_tui_primitive_dispatch_e2e.py` PASS.
- **SC-006 [REVISED 2026-04-30 — FR-022 lifted]**: `prompts/manifest.yaml` `system_v1` entry SHA changes intentionally to `7bf22c42889fff165fc8b484697f901403759eddcb07e8b235ce51c78ed3a082` (v4 with `<critical_first_directive>` block); `session_guidance_v1` / `compact_v1` SHA entries unchanged. **Verification**: `grep -A1 system_v1 prompts/manifest.yaml | grep '7bf22c42'` returns 1 match.
- **SC-007**: No new runtime dependencies. **Verification**: `git diff main -- pyproject.toml tui/package.json` shows no additions to `[project.dependencies]` or `dependencies` keys (only `[dev]` / `devDependencies` if any).
- **SC-008**: `bun test` + `uv run pytest` no regression vs `main`. **Verification**: CI green on the PR's `main` comparison runs.
- **SC-009**: The policy mapping doc cites Singapore APEX, Estonia X-Road, EU EUDI Wallet, and Japan マイナポータル by stable canonical URL; all URLs resolve to 2xx/3xx within 5s during a one-time link probe. **Verification**: link probe script (committed to `specs/2297-zeta-e2e-smoke/scripts/probe_policy_links.sh`) returns 0.
- **SC-010**: All 5 OPAQUE scenario docs exist with the prescribed structure (FR-018). **Verification**: `python specs/2297-zeta-e2e-smoke/scripts/check_scenario_docs.py` returns 0.
- **SC-011**: Sub-issue #2481 closes within 10 seconds of the merge commit landing on `main`. **Verification**: GraphQL `repository.issue(number: 2481).state` reads `CLOSED`.
- **SC-012**: Layer 2 PTY + Layer 4 vhs artefacts are committed BEFORE push (AGENTS.md § TUI verification methodology hard rule). **Verification**: pre-push git hook (or PR description checklist enforced by Lead) lists the four artefacts (`smoke-citizen-taxreturn.expect` / `smoke-citizen-taxreturn-pty.txt` / `smoke-citizen-taxreturn.tape` / `smoke-keyframe-{1,2,3}-*.png`) before the head commit.

## Assumptions

- The Epic η commit `1321f77` is on `main` and contains the registered 5-tool surface in `mvp_surface.py` (verified via `git log --oneline | grep 1321f77`).
- The backend `_dispatch_primitive` server-side execution path (stdio.py line ~1496) continues to fire as a background task; the new TUI primitive `call()` dispatcher does NOT replace it but coordinates with it via the shared `_pending_calls` future-registry pattern. (The exact coordination — whether TUI awaits the same future or a parallel TUI-side future driven by the `tool_result` frame — is decided in `plan.md`.)
- The 10-row canonical `tool_id ↔ family_hint` map in `prompts/system_v1.md` `<verify_families>` block is stable; this Epic does not modify it.
- FriendliAI Tier 1 (60 RPM) capacity holds across the 10-fixture verify-family battery + the 3-attempt resilience runs (10 + 3 + buffer ≈ 20 LLM turns per CI).
- The mock submit adapter `mock_submit_module_hometax_taxreturn` already deterministically generates the `hometax-YYYY-MM-DD-RX-XXXXX` receipt format under `CI=true` (or this Epic adds the deterministic-seed flag — verified during plan).
- `bun run tui` starts cleanly on a fresh worktree without manual env setup beyond `UMMAYA_FRIENDLI_TOKEN` (existing convention).

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **Real `data.go.kr` API calls in CI tests** — AGENTS.md § Hard rules forbids this; smoke uses Mock adapters only.
- **Live K-EXAONE quality regressions** — this Epic gates on "the chain runs and produces a receipt", not on prompt-quality A/B testing. Quality regressions belong to the shadow-eval workflow already established by Spec 026.
- **Adding new verify families or new mock adapters** — out of scope. The 10 verify families + 5 non-verify mocks (15 total) are the η-shipped surface and remain frozen for this Epic.
- **Modifying `prompts/**`** — explicitly forbidden by FR-022; if the canonical map needs amendment that work belongs to a future Epic that touches the prompt + recomputes manifest hash + clears shadow-eval.
- **Replacing backend server-side `_dispatch_primitive`** — the existing path stays; this Epic adds the TUI-mediated dispatcher coordinated with it. Removing the server-side path is its own architectural Epic.
- **Mobile native UI** — UMMAYA is a terminal-based platform.

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| Multi-turn delegation reuse (one verify, N citizen turns) | Architectural — requires session-lifetime token storage + UX for token expiry/refresh | Phase 2 — multi-turn delegation | #2511 |
| Real Live submit adapters (post-Mock to real hometax) | Requires real-world agency credential + production data permissions | Phase 2 — Live submit gateways | #2512 |
| Subscribe primitive E2E demonstration with a real CBS event source | The current `mock_subscribe_*` is sufficient for FR-020 invocation count; a real time-progressing demo needs a CBS-mock harness | Phase 2 — subscribe demo | #2513 |
| OTEL span coverage for the TUI dispatcher (beyond the FR-006 timeout attribute) | Spec 021 OTEL span coverage exists for backend; full TUI-side span instrumentation (per-call name/duration/result_class) is broader than this Epic's wiring goal | Spec 021 follow-up | #2514 |
| `policy-mapping.md` translation to additional languages (English-only secondary, Japanese tertiary) | Bilingual ko/en is the AGENTS.md baseline; further languages are scope creep | Phase 6+ docs | #2515 |
| **LLM prompt fidelity — K-EXAONE citizen chain emission rate <100%** (discovered 2026-04-30 during T018 live smoke) | Live smoke confirmed K-EXAONE on FriendliAI Tier 1 emits **0** `tool_call` frames for the citizen "종합소득세 신고해줘" prompt despite all 19 tools being registered + visible in the OpenAI-compat schema. The chain pattern in `prompts/system_v1.md` v2 `<verify_chain_pattern>` is not forceful enough. **Fixing this requires editing `prompts/**`** which Epic ζ FR-022 explicitly forbids (manifest hash + shadow-eval gate). | New prompt-engineering Epic (or η #2298 follow-up) | #2516 |
| Property-based testing of the family-map drift detector (FR-009) | Unit test with the 10 canonical entries is sufficient gate; property-based generation of malformed inputs is over-engineering for the closed catalog | Out of scope | (none) |
| Promote any of η's 5 deferred sub-issues (#2475–#2479) into this Epic | Each is a distinct concern with its own scope; not load-bearing for the P1 demo | Per sub-issue triage | #2475 / #2476 / #2477 / #2478 / #2479 |
