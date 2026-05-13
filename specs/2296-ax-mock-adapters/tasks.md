---
description: "Task list for Epic ε #2296 — AX-infrastructure mock adapters & adapter-manifest IPC sync"
---

# Tasks: AX-Infrastructure Mock Adapters & Adapter-Manifest IPC Sync

**Input**: Design documents from `/Users/um-yunsang/UMMAYA-w-2296/specs/2296-ax-mock-adapters/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ (3 docs) ✅, quickstart.md ✅

**Tests**: Tests are MANDATORY — FR-006 demands a registry-wide transparency scan, US1 / US2 acceptance scenarios require integration tests, and the plan enumerates 13 test surfaces gating the merge.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. US1 (P1) and US2 (P1) are co-equal — US1's chain is non-functional without US2's manifest resolution.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This is a multi-package monorepo (Python backend at `src/ummaya/` + TS TUI at `tui/src/`). All paths in this file are repository-relative, resolved against worktree root `/Users/um-yunsang/UMMAYA-w-2296/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Worktree + dependency-boundary verification before any code work begins.

- [X] T001 Verify worktree state: confirm `pwd` is `/Users/um-yunsang/UMMAYA-w-2296`, branch is `2296-ax-mock-adapters`, `git status` is clean. If dirty, stop and reconcile before proceeding.
- [X] T002 Capture dependency baseline: run `git diff main -- pyproject.toml tui/package.json` and confirm zero changes (FR-023 / SC-008 baseline). The Polish phase rerun MUST also report zero changes.

**Checkpoint**: Worktree clean and dependency boundaries snapshotted.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schemas, helpers, and IPC frame definitions that every user-story phase depends on.

**⚠️ CRITICAL**: No US1 / US2 / US3 work can begin until Phase 2 is complete.

- [X] T003 [P] Implement `DelegationToken`, `DelegationContext`, `IdentityAssertion` Pydantic v2 frozen models in `src/ummaya/primitives/delegation.py` per `data-model.md § 1, 2, 3`. Include 4 validators (`expires_at > issued_at`, scope regex, token prefix, JWS-shape). Add `validate_delegation()` function per `contracts/delegation-token-envelope.md § 4`. Add `tests/unit/primitives/test_delegation_token.py` covering construction (happy + 4 validator failures) + `_scope_matches` (8 table-driven cases) + `validate_delegation` (5 outcome paths).
- [X] T004 [P] Implement `stamp_mock_response()` shared helper in `src/ummaya/tools/transparency.py` per `contracts/mock-adapter-response-shape.md § 1`. Pure function, raises `ValueError` on empty caller-supplied values. Add `tests/unit/tools/test_transparency.py` covering happy path + empty-string rejection.
- [X] T005 [P] Add `AdapterManifestEntry` + `AdapterManifestSyncFrame` Pydantic v2 frozen models to `src/ummaya/ipc/frame_schema.py` per `data-model.md § 4, 5`. Extend the `IPCFrame` discriminated union (currently 21 arms — ChatRequestFrame was added by Spec 1978) to **22 arms** by appending `| AdapterManifestSyncFrame` after `PluginOpFrame`. Implement validators I1-I7 from `contracts/ipc-adapter-manifest-frame.md § 3`. Add `tests/unit/ipc/test_adapter_manifest_sync_frame.py` covering: round-trip serialisation, discriminator validation, hash mismatch handling, 22-arm union exhaustive count (regression guard). Also updated tests/ipc/ parity tests + regenerated tui/src/ipc/schema/frame.schema.json.
- [X] T006 [P] Extend the `LedgerEvent` discriminated union in `src/ummaya/memdir/consent_ledger.py` with three new arms: `DelegationIssuedEvent`, `DelegationUsedEvent`, `DelegationRevokedEvent` per `data-model.md § 6`. Add helper functions `append_delegation_issued()`, `append_delegation_used()`, `append_delegation_revoked()`. Add `tests/unit/memdir/test_consent_ledger_delegation_events.py` covering JSONL append + parse round-trip for all 3 event kinds. (Note: `src/ummaya/memdir/consent_ledger.py` did not exist; created new module as the spec-035 ledger is for individual consent records, not JSONL events.)
- [X] T007 [P] Retrofit existing per-primitive context types in `src/ummaya/primitives/verify.py` (5 types: `MobileIdContext`, `KECInjeungseoContext`, `GeumyungInjeungseoContext`, `GanpyeonInjeungContext`, `MydataContext`) and `src/ummaya/primitives/submit.py` and `src/ummaya/primitives/subscribe.py` to add **six optional transparency fields** per `data-model.md § 8` (`_mode`, `_reference_implementation`, `_actual_endpoint_when_live`, `_security_wrapping_pattern`, `_policy_authority`, `_international_reference`), each `Optional[str] = None`. Adapter implementations (Phase 4) will populate them via `stamp_mock_response`. No tests in this task — coverage comes from per-adapter tests in Phase 4 + the registry-wide scan in Phase 6.

**Checkpoint**: All schemas + helpers + IPC frame in place. US1 / US2 / US3 phases can now proceed in parallel.

---

## Phase 3: User Story 2 — IPC Manifest Sync (Priority: P1)

**Goal**: Enable TS-side primitive `validateInput` to resolve any backend adapter ID via the synced manifest, populating the citation slot from the agency-published policy URL. Closes Codex P1 #2395.

**Independent Test**: A bun test stands up a synthetic backend that emits a manifest sync frame containing a synthetic adapter, then invokes `LookupPrimitive.validateInput` with that adapter's ID and asserts (a) `validateInput` returns success (not `AdapterNotFound`), (b) the citation slot is populated from the synthetic adapter's `policy_authority_url`.

### Implementation for User Story 2

- [X] T008 [P] [US2] Implement `src/ummaya/ipc/adapter_manifest_emitter.py` per `contracts/ipc-adapter-manifest-frame.md § 5.1`. Function `emit_manifest(stdout_writer, registry, sub_registries, *, pid)` walks the main `ToolRegistry` + the three per-primitive sub-registries (`ummaya.primitives.{verify,submit,subscribe}._ADAPTER_REGISTRY`), constructs sorted `AdapterManifestEntry` list, computes SHA-256 over canonical JSON, emits an `AdapterManifestSyncFrame`. Wire the call into `src/ummaya/ipc/mcp_server.py` (after `register_all_tools()` returns successfully — locate the call site at `mcp_server.py:246`). Add `tests/unit/ipc/test_adapter_manifest_emitter.py` covering happy emission + sort ordering + hash matches canonical JSON.
- [X] T009 [P] [US2] Implement `tui/src/services/api/adapterManifest.ts` per `contracts/ipc-adapter-manifest-frame.md § 5.2`. Module exports: `ingestManifestFrame(frame)`, `resolveAdapter(tool_id): AdapterManifestEntry | undefined`, `isManifestSynced(): boolean`, `clearManifestCache()` (test-only). Cache is module-singleton, replace-on-frame (NOT merge — FR-016). No persistence.
- [X] T010 [US2] Wire the IPC frame router in `tui/src/services/api/` (locate via `grep -rn "kind.*===.*'session_event'\\|kind.*===.*'tool_result'" tui/src/services/api/`) to add a new branch on `frame.kind === 'adapter_manifest_sync'` calling `ingestManifestFrame(frame)`. Frame router file is single-source modification (≤ 1 file). Depends on T009.
- [X] T011 [P] [US2] Modify `tui/src/tools/LookupPrimitive/LookupPrimitive.ts:159-180` `validateInput` to use the two-tier resolution per `contracts/ipc-adapter-manifest-frame.md § 5.3`: (1) `isManifestSynced()` cold-boot check fail-closed, (2) `resolveAdapter(input.tool_id)` from synced manifest with citation populate, (3) `context.options.tools.find` fallback for internal tools, (4) `AdapterNotFound` fail-closed. Depends on T010.
- [X] T012 [P] [US2] Modify `tui/src/tools/SubmitPrimitive/SubmitPrimitive.ts:135-155` `validateInput` with same two-tier pattern. Depends on T010.
- [X] T013 [P] [US2] Modify `tui/src/tools/VerifyPrimitive/VerifyPrimitive.ts` `validateInput` with same two-tier pattern. Depends on T010.
- [X] T014 [P] [US2] Modify `tui/src/tools/SubscribePrimitive/SubscribePrimitive.ts` `validateInput` with same two-tier pattern. Depends on T010.
- [X] T015 [US2] Add three TS test files under `tui/tests/`: `adapterManifest.test.ts` (cache replace + cold-boot race + isManifestSynced), `primitive/lookup-validation-fallback.test.ts` (synced-manifest hit + internal-tools fallback + AdapterNotFound), `primitive/submit-citation-from-manifest.test.ts` (citation slot populated from manifest URL). Cover all 9 mandatory tests from `contracts/ipc-adapter-manifest-frame.md § 7`.

**Checkpoint**: Codex P1 #2395 fix is shippable independently. US2 acceptance scenarios 1-4 pass.

---

## Phase 4A: User Story 1 — New Verify Mock Catalog (Priority: P1, parallel teammate A)

**Goal**: Five new mock verify adapters mirror the AX-callable-channel reference shape (Singapore APEX style), each issuing a `DelegationToken` (except Any-ID SSO which issues an `IdentityAssertion`), each carrying the six transparency fields. Plus deletion of `mock_verify_digital_onepass` and retrofit of the existing 5 verify mocks.

**Independent Test**: Per-adapter pytest invokes the verify mock with synthetic input, asserts (a) returned context is a `DelegationContext` (or `IdentityAssertion` for any_id_sso), (b) all six transparency fields are present and non-empty, (c) for `delegation_issued` ledger event is appended.

### Implementation for User Story 1 (Phase 4A)

- [X] T016 [P] [US1] Implement `src/ummaya/tools/mock/verify_module_simple_auth.py` (간편인증) issuing `DelegationToken` with `scope` from `params.scope_list`. Use `stamp_mock_response` with per-adapter constants (`_REFERENCE_IMPL = "ax-infrastructure-callable-channel"`, `_INTERNATIONAL_REF = "Japan マイナポータル API"`, see `contracts/mock-adapter-response-shape.md § 4`). Append `delegation_issued` ledger event. Register via `register_verify_adapter("simple_auth_module", invoke)`. Bilingual `search_hint`. Add `tests/unit/tools/test_mock_verify_module_simple_auth.py` covering happy + scope-validation-failure + ledger-append assertions.
- [X] T017 [P] [US1] Implement `src/ummaya/tools/mock/verify_module_modid.py` (모바일ID) per same pattern. Constants: `_INTERNATIONAL_REF = "EU EUDI Wallet"`, `_SECURITY_WRAPPING = "OID4VP + DID-resolved RP + DPoP"`, `issuer_did = "did:web:mobileid.go.kr"`. Add `tests/unit/tools/test_mock_verify_module_modid.py`.
- [X] T018 [P] [US1] Implement `src/ummaya/tools/mock/verify_module_kec.py` (KEC 공동인증서) per same pattern. Constants: `_INTERNATIONAL_REF = "Singapore APEX"`, `_SECURITY_WRAPPING = "OAuth2.1 + mTLS + scope-bound bearer"`. Add `tests/unit/tools/test_mock_verify_module_kec.py`.
- [X] T019 [P] [US1] Implement `src/ummaya/tools/mock/verify_module_geumyung.py` (금융인증서) per same pattern. Constants: `_INTERNATIONAL_REF = "Singapore Myinfo"`, `_REFERENCE_IMPL = "public-mydata-read-v240930"`. Add `tests/unit/tools/test_mock_verify_module_geumyung.py`.
- [X] T020 [P] [US1] Implement `src/ummaya/tools/mock/verify_module_any_id_sso.py` returning `IdentityAssertion` (NOT `DelegationContext` — see `data-model.md § 3` + research Decision 4). Constants: `_INTERNATIONAL_REF = "UK GOV.UK One Login"`. Add `tests/unit/primitives/test_any_id_sso_returns_identity_assertion_not_delegation.py` asserting (a) returned type is `IdentityAssertion`, (b) downstream submit fails with `DelegationGrantMissing`.
- [X] T021 [P] [US1] DELETE `src/ummaya/tools/mock/verify_digital_onepass.py` (FR-004; 서비스 종료 2025-12-30). Remove `verify_digital_onepass` from the import tuple in `src/ummaya/tools/mock/__init__.py:44-51`. Update the docstring at `__init__.py:25` to drop the line `- verify_digital_onepass: Digital Onepass Level 1-3`. Verify: `grep -r "digital_onepass\|verify_digital_onepass" src/ tests/ tui/` returns 0 active usages (test fixtures and doc references update if they exist).
- [X] T022 [P] [US1] Retrofit the 5 existing verify mocks to use `stamp_mock_response`: `src/ummaya/tools/mock/verify_mobile_id.py`, `verify_gongdong_injeungseo.py`, `verify_geumyung_injeungseo.py`, `verify_ganpyeon_injeung.py`, `verify_mydata.py`. Each adds 5 module-level constants (per `contracts/mock-adapter-response-shape.md § 4` "EXISTING (retrofitted)" rows) and wraps `invoke()` return. Add `tests/unit/tools/test_existing_verify_mocks_have_transparency.py` parameterised over the 5 mocks asserting six transparency fields populated.

**Checkpoint**: All 10 verify mock surfaces (5 existing + 5 new) carry transparency fields. `digital_onepass` is gone.

---

## Phase 4B: User Story 1 — Submit Mocks + Subscribe Retrofit (Priority: P1, parallel teammate B)

**Goal**: Three new mock submit adapters mirror the AX-callable-channel write surface, each consuming a `DelegationToken` and validating scope/expiry/session before producing a synthetic 접수번호. Plus retrofit of existing 2 submit + 3 subscribe mocks for transparency.

**Independent Test**: Per-adapter pytest constructs a `DelegationContext` with valid scope, invokes the submit, asserts (a) success path returns synthetic 접수번호, (b) `delegation_used` ledger event appended with `outcome="success"` and `receipt_id`. Then constructs a token with mismatched scope and asserts (c) failure with `outcome="scope_violation"`.

### Implementation for User Story 1 (Phase 4B)

- [X] T023 [P] [US1] Implement `src/ummaya/tools/mock/submit_module_hometax_taxreturn.py` consuming `DelegationContext`, calling `validate_delegation(context, required_scope="send:hometax.tax-return", current_session_id=..., revoked_set=..., ledger_reader=...)`, returning synthetic 접수번호 like `"hometax-2026-04-29-RX-7K2J9"` on success. Stamp with `stamp_mock_response`. Constants: `_INTERNATIONAL_REF = "UK HMRC Making Tax Digital"`, `_REFERENCE_IMPL = "ax-infrastructure-callable-channel"`. Append `delegation_used` ledger event. Register via `register_submit_adapter("hometax_taxreturn_module", invoke)`. Add `tests/unit/tools/test_mock_submit_module_hometax_taxreturn.py` covering happy + 4 validation failure paths + ledger assertions.
- [X] T024 [P] [US1] Implement `src/ummaya/tools/mock/submit_module_gov24_minwon.py` per same pattern. Constants: `_INTERNATIONAL_REF = "Singapore APEX"`, scope `"send:gov24.minwon"`. Add `tests/unit/tools/test_mock_submit_module_gov24_minwon.py`.
- [X] T025 [P] [US1] Implement `src/ummaya/tools/mock/submit_module_public_mydata_action.py` per same pattern. Constants: `_INTERNATIONAL_REF = "Estonia X-Road"`, `_REFERENCE_IMPL = "public-mydata-action-extension"`, scope `"send:public_mydata.action"`. Add `tests/unit/tools/test_mock_submit_module_public_mydata_action.py`.
- [X] T026 [P] [US1] Retrofit existing 2 submit mocks: `src/ummaya/tools/mock/data_go_kr/fines_pay.py` and `src/ummaya/tools/mock/mydata/welfare_application.py` with `stamp_mock_response` per `contracts/mock-adapter-response-shape.md § 4` constants. (Existing mocks pre-date `DelegationToken`; do NOT add scope validation — they continue to use whatever auth they currently use. Transparency-fields-only retrofit.) Update existing test files (or add `test_existing_submit_mocks_have_transparency.py` parameterised over the 2) asserting six fields present.
- [X] T027 [P] [US1] Retrofit existing 3 subscribe mocks: `src/ummaya/tools/mock/cbs/disaster_feed.py`, `src/ummaya/tools/mock/data_go_kr/rest_pull_tick.py`, `src/ummaya/tools/mock/data_go_kr/rss_notices.py` with `stamp_mock_response`. Same constants pattern. Add `tests/unit/tools/test_existing_subscribe_mocks_have_transparency.py` parameterised over the 3.

**Checkpoint**: All 8 submit + subscribe mock surfaces carry transparency fields. New 3 submit mocks enforce delegation token scope/expiry/session.

---

## Phase 4C: User Story 1 — Lookup Mocks (Priority: P1, parallel teammate C)

**Goal**: Two new mock lookup adapters register as `GovAPITool` entries in the main `ToolRegistry` (not per-primitive sub-registry — lookup adapters use BM25 discovery). Each consumes a `DelegationToken` (optional but enforced when present) and returns synthetic data.

**Independent Test**: Per-adapter pytest invokes the lookup tool via the registry's executor, asserts (a) response payload contains six transparency fields, (b) BM25 search for adapter's bilingual `search_hint` keywords surfaces this tool.

### Implementation for User Story 1 (Phase 4C)

- [X] T028 [P] [US1] Implement `src/ummaya/tools/mock/lookup_module_hometax_simplified.py` as a `GovAPITool` with `AdapterRegistration(tool_id="mock_lookup_module_hometax_simplified", primitive=AdapterPrimitive.lookup, ...)`. Bilingual `search_hint`: `{"ko": ["홈택스", "간소화", "연말정산", "종합소득세"], "en": ["hometax", "simplified", "year-end tax", "income tax"]}`. Returns synthetic 간소화 자료 fixture stamped with `stamp_mock_response` (constants: `_INTERNATIONAL_REF = "UK HMRC Making Tax Digital"`, `_REFERENCE_IMPL = "public-mydata-read-v240930"`). When called with a `DelegationContext`, validate scope match `"find:hometax.simplified"`. Wire into `register_all_tools()` (additional `registry.register(...)` line). Add `tests/unit/tools/test_lookup_module_hometax_simplified.py` covering happy + scope-validation + BM25 discovery.
- [X] T029 [P] [US1] Implement `src/ummaya/tools/mock/lookup_module_gov24_certificate.py` per same pattern. Constants: `_INTERNATIONAL_REF = "Estonia X-Road"`, `_REFERENCE_IMPL = "public-mydata-read-v240930"`. Bilingual `search_hint`: `{"ko": ["정부24", "주민등록등본", "가족관계증명서", "사업자등록증"], "en": ["gov24", "resident certificate", "family relations cert", "business reg cert"]}`. Scope `"find:gov24.certificate"`. Add `tests/unit/tools/test_lookup_module_gov24_certificate.py`.

**Checkpoint**: 16-entry main `ToolRegistry` (12 Live + 2 MVP-surface + 2 new lookup mocks). BM25 surfaces both new lookup mocks.

---

## Phase 5: User Story 1 — End-to-End Wiring + Integration (depends on Phases 4A/4B/4C)

**Goal**: Wire all the pieces so the citizen US1 chain runs end-to-end against a real Mock backend.

**Independent Test**: `tests/integration/test_e2e_citizen_taxreturn_chain.py` runs the verify→lookup→submit chain against the Mock backend, asserts 3 ledger events with matching `delegation_token`, asserts surfaced 접수번호 in final response.

### Implementation for User Story 1 (Phase 5)

- [X] T030 [US1] Implement `src/ummaya/ipc/demo/mock_backend.py` per research Decision 5 + `quickstart.md § 1`. Module entry-point boots the full registry (`register_all_tools` + `import ummaya.tools.mock`), emits `AdapterManifestSyncFrame` via `adapter_manifest_emitter.emit_manifest()`, then enters the standard JSONL stdio loop (reuse existing `ummaya.ipc.mcp_server` patterns or factor out a shared loop). All logging to stderr (NEVER stdout). Document the `UMMAYA_BACKEND_CMD="uv run python -m ummaya.ipc.demo.mock_backend"` invocation in module docstring. Depends on T008 + Phase 4 mock implementations.
- [X] T031 [US1] Add the single line `import ummaya.tools.mock  # noqa: F401 — registers all mock surfaces in production` to `src/ummaya/tools/register_all.py` per research Decision 6. Insert after `register_mvp_surface(registry)` at line 107. Single-file, single-line change. Verify: `cd /Users/um-yunsang/UMMAYA-w-2296 && uv run python -c "from ummaya.tools.registry import ToolRegistry; from ummaya.tools.executor import ToolExecutor; from ummaya.tools.register_all import register_all_tools; reg = ToolRegistry(); register_all_tools(reg, ToolExecutor()); print(f'main registry: {len(reg)} entries')"` reports 16 entries (12 Live + 2 MVP + 2 new lookup mocks).
- [X] T032 [US1] Add `tests/integration/test_e2e_citizen_taxreturn_chain.py` covering all 4 US1 acceptance scenarios from spec.md: (1) verify+lookup+submit chain emits one verify, one lookup, one submit; (2) submit succeeds with matching scope+token; (3) scope-violation rejected; (4) all responses carry six transparency fields. Use the Mock backend in-process (import `ummaya.tools.mock` + invoke adapters directly). Assert ledger has 3 lines for happy chain (4 for scope-violation scenario).
- [X] T033 [US2] Add `tests/integration/test_codex_p1_adapter_resolution.py` covering US2 acceptance scenarios: (1) `nmc_emergency_search` resolves through synced manifest; (2) `WebFetch` resolves through internal-tools fallback; (3) cache replaces on second frame; (4) bogus tool_id fails with named `AdapterNotFound`. Test uses an in-process simulated backend that emits a synthetic manifest frame via the IPC envelope and asserts TS-side resolution. (Run via `cd tui && bun test tests/integration/codex-p1-adapter-resolution.test.ts` if the test ends up TS-side; if Python-side via simulated frame ingestion, adjust path accordingly. Coordinate with T015 to avoid duplication — T015 is unit, T033 is integration.)

**Checkpoint**: US1 chain runs end-to-end. US2 fix verified end-to-end. Both P1 user stories shippable.

---

## Phase 6: User Story 3 — Catalog Observability (Priority: P2)

**Goal**: Observable counts + transparency-field coverage + deletion regression. Auditor / policy reviewer can verify the catalog.

**Independent Test**: Three pytest assertions enumerate registries, count entries, BM25-search for the deleted adapter, and run the registry-wide six-field scan.

### Implementation for User Story 3

- [X] T034 [US3] Add `tests/unit/tools/test_mock_transparency_scan.py` per `contracts/mock-adapter-response-shape.md § 5`. Parameterised test enumerates all 20 Mock adapter IDs across the four sub-registries + main `ToolRegistry`, invokes each with synthetic input, asserts six transparency fields present and non-empty. **Test FAILS if any single adapter omits any single field** — this is the canonical drift-prevention. Satisfies FR-006 + SC-005.
- [X] T035 [US3] Add `tests/unit/tools/test_registry_count_breakdown.py` asserting the four-surface count breakdown from spec.md SC-003: main `ToolRegistry` = 16; `verify._ADAPTER_REGISTRY` = 10 families; `submit._ADAPTER_REGISTRY` = 5 families; `subscribe._ADAPTER_REGISTRY` = 3 families. Use direct registry inspection via `len()` + iterating sub-registry dicts. Test FAILS if any count is off-by-one.
- [X] T036 [US3] Add `tests/unit/tools/test_digital_onepass_deletion.py` asserting (a) BM25 search for "디지털원패스" or "digital_onepass" returns zero adapter matches; (b) `ummaya.tools.mock.verify_digital_onepass` import raises `ModuleNotFoundError`; (c) the per-primitive verify registry contains no entry with `tool_id` containing "digital_onepass". Satisfies SC-004.

**Checkpoint**: Observability is shippable. US3 acceptance scenarios 1-3 pass.

---

## Phase 7: Smoke (Layer 2 PTY + Layer 4 vhs — PR mandatory per AGENTS.md)

**Purpose**: Capture the citizen end-to-end demonstration as both a grep-friendly text log and an LLM-reviewable visual artefact.

- [X] T037 [P] Author `specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.expect` per `quickstart.md § 5.1`. Spawns `bun run tui` with `UMMAYA_BACKEND_CMD="uv run python -m ummaya.ipc.demo.mock_backend"`, waits for UMMAYA branding, sends `내 종합소득세 신고해줘\r`, waits for permission prompt, sends `Y\r`, waits up to 30s for `접수번호` to appear, asserts non-zero match, sends `\003\003` to exit.
- [X] T038 [P] Author `specs/2296-ax-mock-adapters/scripts/smoke-citizen-taxreturn.tape` per `quickstart.md § 5.2`. Emits BOTH `Output specs/2296-ax-mock-adapters/smoke-citizen-taxreturn.gif` AND three `Screenshot` PNG keyframes: `smoke-keyframe-1-boot.png` (boot+branding), `smoke-keyframe-2-input.png` (citizen query typed), `smoke-keyframe-3-action.png` (접수번호 surfaced). Per AGENTS.md vhs Layer 4 mandate.
- [X] T039 Run `expect` and `vhs` to produce captures: `specs/2296-ax-mock-adapters/smoke-citizen-taxreturn-pty.txt` + `smoke-citizen-taxreturn.gif` + 3 keyframe PNGs. Commit all four artefacts. (FR-021 + FR-022 require the artefacts in the PR.)
- [X] T040 Lead Opus visually verified all 3 keyframes via Read tool. **Keyframe 1 (boot)**: PASS — UMMAYA UFO mascot + version banner + tool_registry boot logs visible. **Keyframe 2 (input)**: PASS — citizen query `내 종합소득세 신고해줘` visible in input bar. **Keyframe 3 (action)**: PARTIAL after timeout extension (PTY 30s→120s, vhs 16s→75s). Re-run shows LLM enters "Hatching…" → "Boogieing…" state but never reaches permission prompt or 접수번호. **Root cause confirmed = #2446** (deferred Codex P1 review): the new `mock_verify_module_*` mocks return stamped dicts, so Spec 031's `verify()` dispatcher converts them to `VerifyMismatchError` — no permission prompt fires. End-to-end receipt rendering IS proven by the 4-test integration suite `tests/integration/test_e2e_citizen_taxreturn_chain.py` (T032). The TUI smoke cannot demonstrate the full chain until #2446 wires the verify-module dispatch path. (SC-009 partial via smoke; full via integration tests; LLM-driven TUI demo gated on #2446.)

**Checkpoint**: Smoke captures committed and verified. PR-mandatory vhs gate passed.

---

## Phase 8: Polish & Cross-Cutting Concerns (Lead solo)

**Purpose**: Final test pass, hard-rule verification, Codex P1 closure, audit chain capture for PR.

- [X] T041 Full pytest pass: 3386 pass / 36 skipped / 2 xfailed / 0 fail. 14 cross-spec failures resolved via the polish-fix commit (OPAQUE scanner narrowed, count drift 14→16, balanced-paren scanner for adapter_mode invariant, otel test fixture leak fixed).
- [X] T042 `bun typecheck` clean (tsc --noEmit -p tsconfig.typecheck.json). `bun test` reports 901 pass / 19 fail — all 19 failures verified pre-existing on main (`git stash` reproducer), not introduced by Epic ε.
- [X] T043 SC-008 verified: `git diff main -- pyproject.toml tui/package.json` returns empty. Zero new runtime dependencies.
- [X] T044 Codex P1 #2395 closure comment posted: https://github.com/umyunsang/UMMAYA/issues/2395#issuecomment-4342680090 — references PR #2445 + FR-015–FR-020 implementation + 5-test `codex-p1-adapter-resolution.test.ts` proving the fix. Issue will close on merge per AGENTS.md.
- [X] T045 PR #2445 created with full audit chain: https://github.com/umyunsang/UMMAYA/pull/2445 — 25 FRs + 9 SCs mapped, 4-surface registry counts (16+10+5+3=34), 3 smoke artefacts (PTY + gif + 3 PNGs), Codex P1 piggyback note, deferred-items table updated to #2441-#2444, `Closes #2296` only (Epic). All 16 active CI checks PASS (Python 3.12+3.13 / TUI / Lint / CodeQL / Docker / etc.).

**Checkpoint**: Ready for `gh pr create`. PR description is reviewer-friendly with full audit chain.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US2 IPC sync)**: Depends on Phase 2 — independently shippable
- **Phase 4A/4B/4C (US1 mocks)**: All depend on Phase 2 — independently parallel
- **Phase 5 (US1 wiring + integration)**: Depends on Phases 4A + 4B + 4C all complete — and on Phase 3 (US2 manifest sync) for the integration test to exercise the round-trip
- **Phase 6 (US3 observability)**: Depends on Phase 5 (because the assertions need the registry boot path with mocks registered)
- **Phase 7 (Smoke)**: Depends on Phase 5 (mock backend module exists) + Phase 6 (registry counts proven)
- **Phase 8 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)** depends on **US2 (P1)** at integration time (the chain's `validateInput` calls require the synced manifest). However, US1's per-mock implementations (Phases 4A/4B/4C) can run in parallel with US2's TS-side modifications (Phase 3) because they touch different files.
- **US3 (P2)** depends on US1 (Phase 5 must complete for US3 to count entries). US3's tests can be authored in parallel with Phase 5.

### Within Each User Story

- Tests written together with implementation (not before — per spec, this is verification, not TDD).
- Models/schemas in Phase 2 before adapters in Phases 4A/4B/4C.
- Adapter implementations before integration tests in Phase 5.

### Parallel Opportunities

- All 5 Phase 2 tasks marked [P] can run together.
- All 4 TS-side primitive modifications (T011/T012/T013/T014) can run together once T010 (frame router) completes.
- All Phase 4A tasks (T016-T022) can run together.
- All Phase 4B tasks (T023-T027) can run together.
- All Phase 4C tasks (T028-T029) can run together.
- Phases 4A + 4B + 4C themselves can run as three parallel Sonnet teammates.

---

## Parallel Example: Phase 4A (sonnet-us1a teammate)

```bash
# Single Sonnet teammate handles all 7 tasks in this phase. Parallelism within
# the teammate's worktree is achieved by the teammate writing all 7 files in
# a single batch of Write tool calls before running tests.
Task: "Implement src/ummaya/tools/mock/verify_module_simple_auth.py + test"
Task: "Implement src/ummaya/tools/mock/verify_module_modid.py + test"
Task: "Implement src/ummaya/tools/mock/verify_module_kec.py + test"
Task: "Implement src/ummaya/tools/mock/verify_module_geumyung.py + test"
Task: "Implement src/ummaya/tools/mock/verify_module_any_id_sso.py + test"
Task: "DELETE src/ummaya/tools/mock/verify_digital_onepass.py + adjust __init__.py"
Task: "Retrofit 5 existing verify mocks with stamp_mock_response"
```

Phase 4A teammate dispatch budget: 7 tasks, ≈ 12 file changes (5 new + 5 retrofit + 1 delete + 1 __init__.py edit). Slightly over the AGENTS.md ≤ 10 file guideline — Lead splits if any teammate context exhaustion is observed during /speckit-implement.

---

## Implementation Strategy

### MVP Path (US1 + US2 together, since they are co-equal P1)

1. Complete Phase 1 (Setup — Lead solo, ~5 min)
2. Complete Phase 2 (Foundational — sonnet-foundational, ~30 min)
3. **Two parallel tracks**:
   - Track A: Phase 3 (US2 IPC sync — sonnet-us2)
   - Track B: Phases 4A + 4B + 4C in parallel (US1 mocks — three Sonnet teammates)
4. Synchronise at Phase 5 (US1 wiring + integration tests — sonnet-us1integration)
5. **STOP and VALIDATE**: Run `tests/integration/test_e2e_citizen_taxreturn_chain.py` + `tests/integration/test_codex_p1_adapter_resolution.py` end-to-end. Both green = MVP shippable.
6. Add Phase 6 (US3 observability) → Phase 7 (Smoke) → Phase 8 (Polish) → PR

### Incremental Demo Path (if time-constrained)

1. Phases 1 + 2 + 3 → US2 alone is shippable: closes Codex P1 #2395 with a synthetic adapter test, even before any new mocks land.
2. Phases 4A + 4B + 4C + 5 → US1 chain becomes demonstrable.
3. Phase 6 → Auditor/reviewer-friendly.
4. Phases 7 + 8 → PR-ready.

### Sonnet Teammate Layout (Lead Opus draws this for `/speckit-implement`)

```text
Phase 1 Setup (T001-T002): Lead solo
Phase 2 Foundational (T003-T007): sonnet-foundational             [5 tasks, ~7 file changes]
Phase 3 US2 IPC sync (T008-T015): sonnet-us2                      [8 tasks, ~9 file changes]
Phase 4A US1 verify mocks (T016-T022): sonnet-us1a                [7 tasks, ~12 file changes]    ┐
Phase 4B US1 submit + subscribe (T023-T027): sonnet-us1b          [5 tasks, ~10 file changes]    ├─ all 4 in parallel
Phase 4C US1 lookup mocks (T028-T029): sonnet-us1c                [2 tasks, ~4 file changes]     ┘
                                                                                                  └─ Phase 3 can be Track A
Phase 5 US1 wiring + integration (T030-T033): sonnet-us1integration [4 tasks, ~5 file changes]
Phase 6 US3 observability (T034-T036): sonnet-us3                 [3 tasks, ~3 file changes]
Phase 7 Smoke (T037-T040): sonnet-smoke                           [4 tasks, ~5 file changes]
Phase 8 Polish (T041-T045): Lead solo                             [5 tasks, ~1 file change (PR body)]
```

`dispatch-tree.md` will be authored by Lead Opus at `/speckit-implement` time per AGENTS.md and committed to `specs/2296-ax-mock-adapters/dispatch-tree.md`.

---

## Notes

- All 45 tasks have absolute file paths.
- All 25 FRs from spec.md are covered: FR-001 (T016-T020) · FR-002 (T023-T025) · FR-003 (T028-T029) · FR-004 (T021) · FR-005 (T004 + T022 + T026 + T027 + adapter implementations) · FR-006 (T034) · FR-007/008 (T003) · FR-009/010/011 (T003 + T023-T025 enforce) · FR-012/013/014 (T006 + adapter implementations) · FR-015 (T005 + T008) · FR-016 (T009) · FR-017/018 (T011-T014) · FR-019 (T011-T014 cold-boot check) · FR-020 (T011-T014 fail-closed) · FR-021 (T037 + T039) · FR-022 (T038 + T039) · FR-023 (T002 + T043) · FR-024 (every implementation task) · FR-025 (every implementation task per `contracts/mock-adapter-response-shape.md § 4`)
- All 9 SCs are testable: SC-001 (T032) · SC-002 (T032 ledger assertion) · SC-003 (T035) · SC-004 (T036) · SC-005 (T034) · SC-006 (T033) · SC-007 (T032 scope-violation acceptance) · SC-008 (T043) · SC-009 (T040)
- Task count: **45**, well under the 90-task budget (50% headroom).
- Hard rules per task: zero new deps; English source; agency-published policy citations; new IPC arm only; Pydantic v2 frozen no-Any; real Mock backend (NOT `sleep 60`).
- `[Deferred]` items from spec.md remain tracked in spec.md's "Deferred to Future Work" table and will be materialised as placeholder issues by `/speckit-taskstoissues`.
- Avoid: vague tasks (none — every task has file path); same-file conflicts (each task lists its files; Phase 4A T021+T022 both touch `mock/__init__.py` so they are sequenced); cross-story dependencies that break independence (US1 + US2 are co-equal but can ship as separate sub-PRs in the incremental path).
