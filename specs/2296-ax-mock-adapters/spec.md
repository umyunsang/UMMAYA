# Feature Specification: AX-Infrastructure Mock Adapters & Adapter-Manifest IPC Sync

**Feature Branch**: `2296-ax-mock-adapters`
**Created**: 2026-04-29
**Status**: Draft
**Input**: User description: "Epic ε #2296 — AX-infrastructure mock adapters (Singapore APEX + 공공마이데이터). Ship 10 new mock adapters mirroring the AX-infrastructure callable-channel reference shape, plus the `DelegationToken` / `DelegationContext` schema. Piggyback Codex P1 #2395 (TS-side adapter manifest IPC sync) so primitive `validateInput` can resolve real backend adapter IDs."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Citizen end-to-end one-stop tax filing in Mock mode (Priority: P1)

A Korean citizen tells UMMAYA "내 종합소득세 신고해줘". The LLM recognises the request as an OPAQUE-domain submit class, chains `verify(modid)` → `lookup(hometax_simplified)` → `submit(hometax_taxreturn)`, and returns a 접수번호 to the citizen. Every adapter call carries a scope-bound `DelegationToken`; every response carries the six transparency fields proving the call ran in Mock mode against an AX-callable-channel reference shape (Singapore APEX style). Three append-only audit lines land in `~/.ummaya/memdir/user/consent/` (delegation_issued / delegation_used ×2).

**Why this priority**: This is the entire reason Epic ε exists. The chain is the canonical demonstration that UMMAYA's five-primitive client surface can drive the LLM-callable secure-wrapping channels the national AX policy stack will mandate. Without this user story, the new schema and adapters have no demonstrable value.

**Independent Test**: A scripted PTY scenario can execute the full chain end-to-end against the Mock backend and assert (a) three audit ledger entries with matching `delegation_token`, (b) a 접수번호 surfaced in the final assistant message, (c) every adapter response carries the six transparency fields.

**Acceptance Scenarios**:

1. **Given** the LLM has the new mock-verify and mock-submit adapters registered, **When** the citizen says "내 종합소득세 신고해줘", **Then** the LLM emits exactly one `verify` call with `scope` containing `send:hometax.tax-return`, exactly one `lookup` call carrying the returned delegation token, and exactly one `submit` call carrying the same token.
2. **Given** a `DelegationToken` has been issued by `mock_verify_module_modid` with a 24-hour `expires_at`, **When** `mock_submit_module_hometax_taxreturn` is invoked with that token, **Then** the submit succeeds with a synthetic 접수번호 and the audit ledger records `delegation_used` with the same `delegation_token` value as the earlier `delegation_issued` line.
3. **Given** the `DelegationToken` was issued with `scope=send:hometax.tax-return`, **When** the LLM attempts to invoke `mock_submit_module_gov24_minwon` with that same token, **Then** the submit fails closed with a scope-violation error and the audit ledger records the rejection.
4. **Given** any adapter response, **When** the consumer inspects the JSON payload, **Then** the six transparency fields (`_mode`, `_reference_implementation`, `_actual_endpoint_when_live`, `_security_wrapping_pattern`, `_policy_authority`, `_international_reference`) are all present and non-empty.

---

### User Story 2 — LLM can reach real backend adapters through primitives (Priority: P1)

When the LLM emits `lookup(mode='fetch', tool_id='nmc_emergency_search', params={...})`, the primitive's `validateInput` resolves `nmc_emergency_search` against a backend-synced adapter manifest, populates the citation slot from that adapter's published policy URL, and dispatches the call. The same path works for any backend-only adapter (KOROAD, KMA, HIRA, NMC, NFA119, MOHW, plus all new Mock adapters), not just the small set of TS-side internal tools (WebFetch, Calculator, etc.). The Codex P1 #2395 failure mode — `validateInput` returning `AdapterNotFound` for any backend adapter ID — no longer occurs.

**Why this priority**: P1 because today this path is broken: the `submit`, `verify`, `subscribe`, and `lookup-fetch` primitives are functionally unusable for any real adapter ID. Every Mock adapter shipped under US1 will fail at `validateInput` until this is fixed. US1 cannot deliver value without US2.

**Independent Test**: A bun test can stand up a synthetic backend that emits a manifest sync frame containing a synthetic adapter, then invoke `lookupPrimitive.validateInput` with that adapter's ID, and assert (a) `validateInput` returns success (not `AdapterNotFound`), (b) the citation slot is populated from the synthetic adapter's policy URL.

**Acceptance Scenarios**:

1. **Given** the backend has registered the `nmc_emergency_search` adapter and emitted a manifest sync frame at boot, **When** the TUI invokes `lookupPrimitive.validateInput({mode: 'fetch', tool_id: 'nmc_emergency_search', ...})`, **Then** validation succeeds without any `AdapterNotFound` and the resolved adapter's `real_domain_policy.policy_authority_url` appears in the citation slot.
2. **Given** the same boot, **When** the TUI invokes `lookupPrimitive.validateInput({mode: 'search', query: 'emergency hospital', ...})`, **Then** validation succeeds via the existing internal-tools path (no manifest lookup needed).
3. **Given** the backend restarts and re-emits the manifest with one added adapter, **When** the TUI receives the new manifest frame, **Then** the cached manifest reflects the addition without a TUI restart.
4. **Given** a tool_id that exists neither in the synced backend manifest nor in the TS-side internal tools list, **When** any primitive's `validateInput` is called with that ID, **Then** validation fails closed with a clear `AdapterNotFound` error naming the unknown ID.

---

### User Story 3 — Catalog observability and policy traceability (Priority: P2)

A reviewer (operator, auditor, policy stakeholder) can observe the full mock catalog through three signals: the four registry surfaces total **34 entries** (16 main `ToolRegistry` + 10 verify-family + 5 submit-family + 3 subscribe-family) — see SC-003 for the canonical breakdown; every Mock adapter (all 20 surfaces) exposes the six transparency fields when called; and the deletion of `mock_verify_digital_onepass` (서비스 종료 2025-12-30) is recorded so no stale tool surfaces in BM25 search results.

**Why this priority**: P2 because it is observability, not behavioural. The chain in US1 will work even if the count is off-by-one or the digital_onepass mock is still registered; the value here is auditability for policy reviewers, which is the whole point of the AX-reference-implementation framing.

**Independent Test**: A pytest fixture can boot the registry, count adapters by type, assert the deletion of `mock_verify_digital_onepass`, iterate every Mock adapter response payload through one happy-path call, and assert the six transparency fields are present.

**Acceptance Scenarios**:

1. **Given** a fresh UMMAYA backend boot, **When** the test enumerates the four registry surfaces (main `ToolRegistry` + the three per-primitive `_ADAPTER_REGISTRY` sub-registries), **Then** the totals match SC-003 exactly (16 + 10 + 5 + 3 = 34 entries) with no duplicate IDs anywhere.
2. **Given** the new mock catalog is registered, **When** any consumer searches BM25 for "디지털원패스", **Then** zero adapters match (deletion confirmed).
3. **Given** the citizen ran the US1 chain, **When** the auditor inspects the consent ledger, **Then** every `delegation_used` entry references a tool ID that resolves through the synced manifest to a citation URL belonging to the issuing agency (not a UMMAYA-invented URL).

---

### Edge Cases

- **Token replay across sessions**: A `DelegationToken` issued in session A is presented in session B. The mock submit adapter MUST reject it (scope-bound + session-bound, `_mode=mock` is not a security relaxation).
- **Token expiry mid-chain**: A token issued with a short `expires_at` lapses between `lookup` and `submit`. The submit MUST fail closed with `DelegationTokenExpired`; the chain MUST NOT silently re-issue.
- **Backend adapter manifest race**: A primitive `validateInput` is called before the first manifest frame arrives at boot. Validation MUST fail closed with a clear "manifest not yet synced" error rather than treating the empty manifest as authoritative.
- **Manifest size limit**: The backend has 28 adapters; if a future epic adds many more (~hundreds), the IPC frame MUST chunk or stream rather than block. (Out of scope for #2296: spec MUST note 28 as the immediate target and call out the chunking design as a deferred concern.)
- **Adapter removal mid-session**: Backend hot-reloads and removes an adapter that the LLM has already cached as an option. The next `validateInput` for that ID MUST fail with `AdapterNotFound`; the LLM is then expected to call `lookup(mode='search', ...)` to re-discover.
- **Citizen confirms via mobile but backend timeout**: `mock_verify_module_*` simulates a 3-second confirmation. If the simulated confirmation fires after the verify primitive's timeout, the result MUST be `VerifyTimeout`, not `VerifyFailure` (distinct so the LLM can retry).
- **Six transparency fields missing on one adapter**: A registry-wide pytest scan MUST fail if any Mock adapter response is missing any of the six transparency fields, so this contract cannot rot.

## Requirements *(mandatory)*

### Functional Requirements

#### Mock Adapter Catalog (US1, US3)

- **FR-001**: System MUST register five new mock verify adapters: `mock_verify_module_simple_auth` (간편인증), `mock_verify_module_modid` (모바일ID), `mock_verify_module_kec` (KEC 공동인증서), `mock_verify_module_geumyung` (금융인증서), `mock_verify_module_any_id_sso` (Any-ID SSO 후속, identity-only — no delegation token).
- **FR-002**: System MUST register three new mock submit adapters: `mock_submit_module_hometax_taxreturn` (홈택스 종합소득세), `mock_submit_module_gov24_minwon` (정부24 민원), `mock_submit_module_public_mydata_action` (공공마이데이터 action-scope extension).
- **FR-003**: System MUST register two new mock lookup adapters: `mock_lookup_module_hometax_simplified` (홈택스 간이장부), `mock_lookup_module_gov24_certificate` (정부24 증명서).
- **FR-004**: System MUST delete `mock_verify_digital_onepass` (서비스 종료 2025-12-30) and remove it from BM25 indices.
- **FR-005**: Every Mock adapter response payload MUST carry six transparency fields: `_mode` (always `"mock"`), `_reference_implementation` (e.g., `"ax-infrastructure-callable-channel"`), `_actual_endpoint_when_live` (the URL the agency would expose when the policy mandate ships, e.g., `"https://api.gateway.ummaya.gov.kr/v1/..."`), `_security_wrapping_pattern` (e.g., `"OAuth2.1 + mTLS + scope=..."`), `_policy_authority` (citation of the agency-published policy URL), `_international_reference` (e.g., `"Singapore APEX"`, `"Estonia X-Road"`, `"EU EUDI Wallet"`, `"Japan マイナポータル API"`).
- **FR-006**: A registry-wide test MUST iterate every Mock adapter through one happy-path invocation and assert the six transparency fields are present and non-empty; the test MUST fail closed if any single adapter omits any single field.

#### Delegation Schema (US1)

- **FR-007**: System MUST expose a `DelegationToken` data type with fields `vp_jwt`, `delegation_token`, `scope`, `issuer_did`, `issued_at`, `expires_at`, `_mode`. The type MUST be immutable.
- **FR-008**: System MUST expose a `DelegationContext` data type carrying a `DelegationToken` plus optional citizen DID and bilingual purpose strings (`purpose_ko`, `purpose_en`).
- **FR-009**: A `DelegationToken` MUST be scope-bound: any submit/lookup adapter that receives a token MUST reject the call if the requested action is outside the token's `scope` string.
- **FR-010**: A `DelegationToken` MUST be time-bound: any adapter receiving a token whose `expires_at` is in the past relative to the current time MUST reject the call with a distinct `DelegationTokenExpired` error.
- **FR-011**: A `DelegationToken` MUST be session-bound: tokens issued in session A presented in session B MUST be rejected (mock simulation enforces the same property).

#### Audit Ledger (US1)

- **FR-012**: When a verify adapter issues a `DelegationToken`, the system MUST append a `delegation_issued` event to `~/.ummaya/memdir/user/consent/` recording timestamp, opaque token value, scope, expiry, and issuer DID.
- **FR-013**: When a submit or lookup adapter consumes a `DelegationToken`, the system MUST append a `delegation_used` event recording the token value and the consuming `tool_id` (and `receipt_id` if a submit).
- **FR-014**: When a citizen revokes a token via the existing `/consent` UI surface, the system MUST append a `delegation_revoked` event. Subsequent token use MUST be rejected.

#### Adapter-Manifest IPC Sync (US2)

- **FR-015**: The backend MUST emit, on every successful boot, an `adapter_manifest_sync` IPC frame containing the full set of registered adapter IDs together with each adapter's name, primitive verb, and citation slot (the published `policy_authority_url` from the adapter's real-domain-policy declaration).
- **FR-016**: The TUI MUST cache the most-recent `adapter_manifest_sync` frame in memory; the cache MUST be replaced (not merged) when a new frame arrives.
- **FR-017**: Each primitive's `validateInput` (`lookup`, `submit`, `verify`, `subscribe`) MUST resolve `tool_id` against the cached backend manifest first; on miss, it MUST fall back to the existing TS-side internal-tools list (WebFetch, Calculator, etc.).
- **FR-018**: When `validateInput` resolves an ID through the cached backend manifest, it MUST populate the permission UI's citation slot from that adapter's `policy_authority_url` (no UMMAYA-invented citation).
- **FR-019**: When `validateInput` is invoked before the first manifest frame has arrived (cold boot race), it MUST fail closed with a distinct error indicating "manifest not yet synced", not silently treat the empty manifest as authoritative.
- **FR-020**: When `validateInput` cannot resolve `tool_id` in either source, it MUST fail closed with `AdapterNotFound` naming the unknown ID.

#### Smoke Verification (US1, US2)

- **FR-021**: System MUST provide a PTY smoke harness scenario that spawns a Mock-fixture backend (NOT `UMMAYA_BACKEND_CMD=sleep 60`), executes the full US1 chain, and asserts the three audit ledger entries plus the surfaced 접수번호. (The `sleep 60` placeholder used in prior smoke harnesses is the gap Codex P1 #2395 flagged as unable to catch the dispatch path.)
- **FR-022**: System MUST provide a vhs `.tape` scenario that emits an animated `.gif` plus three named `Screenshot` PNG keyframes (boot+branding, citizen-query-accepted, post-action-receipt) consistent with the AGENTS.md vhs Layer 4 mandate.

#### Hard-Rule Preservation

- **FR-023**: System MUST add zero new runtime dependencies (Python or TypeScript). The IPC frame variant MUST reuse the existing Spec 032 envelope and discriminated-union shape.
- **FR-024**: All new source text MUST be English; Korean is permitted only inside domain-data fields (`search_hint`, `llm_description`, transparency-field `_policy_authority` if the citation URL points to a Korean-language gov page).
- **FR-025**: Each Mock adapter MUST cite an agency-published policy URL in `_policy_authority`; no UMMAYA-invented permission classifications are permitted.

### Key Entities

- **DelegationToken**: An opaque, scope-bound, time-bound, session-bound credential issued by a verify adapter and consumed by a subsequent submit or lookup adapter. Mirrors the OID4VP-style envelope that the AX gateway is expected to issue when the policy mandate ships. Transparency-stamped (`_mode=mock`).
- **DelegationContext**: The wrapper that carries a `DelegationToken` plus the bilingual purpose strings shown in the permission UI to the citizen. Optional citizen DID for audit-anchoring.
- **AdapterManifestEntry**: The shape of one record inside an `adapter_manifest_sync` frame: tool ID, name, primitive verb, citation slot URL. Used by the TUI to resolve `tool_id` and populate citation in permission prompts.
- **AdapterManifestFrame**: The full IPC frame that the backend emits on boot, containing the array of all `AdapterManifestEntry` plus a manifest hash for cheap change-detection.
- **AuditLedgerEvent (delegation_*)**: Three append-only kinds — `delegation_issued`, `delegation_used`, `delegation_revoked` — added to the existing Spec 035 consent ledger schema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A citizen-facing PTY scenario chains `verify → lookup → submit` end-to-end and surfaces a synthetic 접수번호 in under 30 seconds wall-clock from the citizen query, on a developer machine, against the Mock backend.
- **SC-002**: After an end-to-end run, the consent ledger shows exactly three new entries (one `delegation_issued`, two `delegation_used`) all referencing the same opaque token value.
- **SC-003**: After a fresh boot, the four registry surfaces report the following counts (corrected during Phase 0 research — see `research.md § Decision 1` for why "15 Mock in ToolRegistry" was architecturally impossible):
  - Main `ToolRegistry`: 16 entries (12 Live agency tools + 2 MVP-surface tools `resolve_location` + `lookup` + 2 new lookup mock GovAPITools)
  - `ummaya.primitives.verify._ADAPTER_REGISTRY`: 10 families (5 existing after `mock_verify_digital_onepass` deletion + 5 new `mock_verify_module_*`)
  - `ummaya.primitives.submit._ADAPTER_REGISTRY`: 5 families (2 existing + 3 new `mock_submit_module_*`)
  - `ummaya.primitives.subscribe._ADAPTER_REGISTRY`: 3 families (unchanged)
  - **Total Mock surfaces across all registries**: 20 (10 verify + 5 submit + 3 subscribe + 2 lookup)
- **SC-004**: Zero `mock_verify_digital_onepass` matches when BM25 is searched for "디지털원패스" or "digital_onepass".
- **SC-005**: A registry-wide transparency scan invokes every Mock adapter once and reports zero missing transparency fields across all 20 Mock surfaces (10 verify + 5 submit + 3 subscribe + 2 lookup).
- **SC-006**: A direct primitive call `lookup(mode='fetch', tool_id='nmc_emergency_search', params={...})` from the TUI reaches the backend's `call()` method (verified via OTEL span attribute `ummaya.tool.id=nmc_emergency_search`), with zero `AdapterNotFound` errors.
- **SC-007**: A scope-violation regression test confirms that a token issued with `scope=send:hometax.tax-return` is rejected when presented to `mock_submit_module_gov24_minwon`, with the rejection logged in the consent ledger.
- **SC-008**: Zero new entries appear in `pyproject.toml` `[project.dependencies]` and zero new entries appear in `tui/package.json` `dependencies` after the merge.
- **SC-009**: The vhs Layer 4 tape produces three named PNG keyframes whose pixel content (visually verified via Read tool by Lead Opus) shows the citizen branding (boot), the typed citizen query (input), and the surfaced 접수번호 (action) respectively.

## Assumptions

- The Goal section of Epic #2296 says "9 new mock adapters" but the deliverable list enumerates 5+3+2 = 10. This spec adopts **10 new adapters**, treating the prose count as a typo. Phase 0 research (`research.md § Decision 1`) further corrected the spec's original "15 Mock in ToolRegistry" count — the existing per-primitive sub-registry architecture (Spec 031) means most mocks live in `ummaya.primitives.{verify,submit,subscribe}._ADAPTER_REGISTRY`, not in the main `ToolRegistry`. The corrected breakdown is enumerated in SC-003.
- `mock_verify_module_any_id_sso` is the Any-ID successor stub. Per the project's delegation-flow research (`specs/1979-plugin-dx-tui-integration/delegation-flow-design.md § 2.2`), Any-ID is identity-SSO only, not delegation-grant, so this adapter MUST return an identity assertion only — NOT a `DelegationToken`. It exists in the catalog as the fail-closed canonical for "the citizen authenticated, but the gateway has not yet defined a delegation channel for this ID family".
- The backend already exposes `real_domain_policy.policy_authority_url` on every adapter (Spec 022 + Spec 1636). This spec assumes that field is the source of truth for the citation slot synced over IPC. If a particular adapter is missing that field, the manifest-sync emitter MUST fail closed at boot rather than silently emit an empty citation.
- `_actual_endpoint_when_live` URLs are illustrative-only ("https://api.gateway.ummaya.gov.kr/v1/...") and do not imply that any such gateway exists today. The reference-implementation framing is documented in the transparency field's value itself.
- The IPC frame MUST be a NEW arm of the existing Spec 032 discriminated union (e.g., a new variant `adapter_manifest_sync`). Extending an existing arm risks correlation-id ambiguity and breaks the Spec 032 ring-buffer replay invariant. This spec assumes the new arm approach.
- The Mock backend used by the PTY smoke is a pure-Python process that imports `ummaya.tools.registry` and answers the JSONL frames the TUI sends — the same shape the production backend speaks. No new external dependency, no `UMMAYA_BACKEND_CMD=sleep 60` placeholder.
- All transparency fields are stamped at adapter-call time (in the response builder), not at registration time, so they are observable in OTEL spans and JSONL session logs.

## Scope Boundaries & Deferred Items *(mandatory)*

### Out of Scope (Permanent)

- **Live calls to any holders of the simulated channels** (홈택스 / 정부24 / KOMSCO 모바일ID / NPKI / 금융결제원 / 마이데이터 게이트웨이 — none of these expose an LLM-callable channel as of 2026-04). UMMAYA will never call them in this Epic; the Mock surface is the entire deliverable.
- **Browser-automation fallback** (Playwright / mobile-companion) — explicitly OPAQUE per `delegation-flow-design.md § 12.10`. UMMAYA as student-tier does not operate the citizen's browser.
- **Inventing a permission classification not cited from agency policy** — AGENTS.md hard rule + Spec 024/025 invariants. Every adapter cites an agency-published policy URL or it does not ship.
- **Writing back to or proposing changes to any agency's published API surface** — UMMAYA provides the client-side reference shape; the agency-side wrapping is policy-driven (`delegation-flow-design.md § 12 final canonical`).

### Deferred to Future Work

| Item | Reason for Deferral | Target Epic/Phase | Tracking Issue |
|------|---------------------|-------------------|----------------|
| End-to-end smoke transcript + UMMAYA-adapter ↔ Singapore APEX / Estonia X-Road / EU EUDI / Japan マイナポータル mapping doc | Belongs in Epic ζ which depends on the 10 mocks shipped here | Epic ζ #2297 (E2E smoke + policy mapping doc) | #2297 |
| System-prompt rewrite teaching K-EXAONE the 5-primitive citizen UX + OPAQUE hand-off rules + the new delegation-token vocabulary | Belongs in Epic η; optional, executed only if the LLM is observed using outdated tool guidance | Epic η #2298 (System prompt rewrite, optional) | #2298 |
| Manifest-frame chunking / streaming for adapter counts at scale (~hundreds) | Current target is 28-34 adapters; chunking is unnecessary at this scale and adds complexity. Add when adapter count crosses a measured size threshold | TBD — future scaling spec | #2441 |
| Hot-reload of adapter manifest mid-session (TUI receives a new frame after first one) | FR-016 requires cache replacement when a new frame arrives, but the trigger that causes the backend to re-emit (admin command, plugin install, etc.) is not designed in this Epic | Future plugin-DX or live-config spec | #2442 |
| Live-mode promotion: swap any Mock adapter to a Live adapter once the corresponding agency channel ships | Live adapters require agency credentials + a real channel that does not yet exist | Future post-Epic-ζ work; revisit when a national AX gateway publishes a spec | #2443 |
| Spec 035 ledger UI surface for the new `delegation_*` event kinds (`/consent list` rendering of token issuance vs. plain consent receipts) | UI-side rendering can ship after the backend ledger format is proven by US1 | Spec 035 follow-up or Epic ζ | #2444 |
| ~~Wire `mock_verify_module_*` into the Spec 031 `verify(family_hint=...)` dispatch path~~ — **RESOLVED in this PR** | The new verify mocks now return typed `AuthContext` variants (`SimpleAuthModuleContext`, `ModidContext`, `KECContext`, `GeumyungModuleContext`, `AnyIdSsoContext` — 5 new arms in the discriminated union). 5 new `PublishedTier` literals added to `src/ummaya/tools/registry.py`. Verified by `tests/integration/test_verify_module_dispatch.py` (6 tests covering all 5 families + unknown-family mismatch). | (Resolved in PR #2445 head) | #2446 (will close on merge) |
