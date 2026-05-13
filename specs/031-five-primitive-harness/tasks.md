---
description: "Task list — Spec 031 Five-Primitive Harness Redesign (Epic #1052)"
---

# Tasks: Five-Primitive Harness Redesign

**Input**: Design documents from `/specs/031-five-primitive-harness/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Epic**: #1052 — public record Discussion #1051

**Tests**: INCLUDED — the spec declares explicit Independent Test + Acceptance Scenarios per US and Success Criteria SC-001–SC-010. Tests are therefore mandatory, not optional, for this feature.

**Organization**: Tasks are grouped by user story (US1..US6) in spec priority order so each story ships as an independent increment.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User-story label (US1..US6). Setup / Foundational / Polish phases have no story label.
- Every task carries an exact file path.

## Path Conventions

Single Python package layout per `plan.md § Project Structure`:
- `src/ummaya/primitives/` — NEW main-surface package (exports the 5 primitives)
- `src/ummaya/tools/registry.py` — EXISTING, extended with `AdapterPrimitive` + dual-axis fields
- `src/ummaya/tools/<ministry>/` — EXISTING Spec 022 adapters (preserved)
- `src/ummaya/tools/mock/<ministry>/` — NEW mock adapter tree
- `src/ummaya/security/v12_dual_axis.py` — NEW v1.2 backstop
- `tests/` — unit + integration + lint
- `docs/mock/`, `docs/scenarios/` — NEW doc trees (6 mirror-able + 3 OPAQUE)
- `docs/security/tool-template-security-spec-v1.md` — EXISTING, v1.2 bump in US6

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the net-new directory scaffolding + lint guardrails so all later phases have a stable surface to write into.

- [ ] T001 Create `src/ummaya/primitives/__init__.py` scaffold exporting placeholder symbols `lookup`, `resolve_location`, `submit`, `subscribe`, `verify` (actual bodies land in later phases)
- [ ] T002 [P] Create `src/ummaya/tools/mock/__init__.py` + six empty `src/ummaya/tools/mock/{data_go_kr,omnione,barocert,mydata,npki_crypto,cbs}/__init__.py` sub-packages (mock adapter tree roots — `__init__.py` only; adapter bodies deferred per Deferred Items)
- [ ] T003 [P] Create `docs/mock/{data_go_kr,omnione,barocert,mydata,npki_crypto,cbs}/` six empty directories (content build-out deferred per spec §Deferred Items)
- [ ] T004 [P] Create `docs/scenarios/` root with three stub files `gov24_submission.md`, `kec_xml_signature.md`, `npki_portal_session.md` — each containing only the H1 title + a `## UMMAYA ↔ real system handoff point` heading (content authoring deferred)
- [ ] T005 [P] Copy `specs/031-five-primitive-harness/contracts/` JSON Schemas into the feature dir (already written in Phase 1 of `/speckit-plan`) — verify `ls specs/031-five-primitive-harness/contracts/` returns 7 files (`README.md` + 6 `*.schema.json`)
- [ ] T006 [P] Add `specs/031-five-primitive-harness/contracts/README.md` cross-link to `specs/022-mvp-main-tool/contracts/` so `lookup` / `resolve_location` JSON Schemas are not duplicated (FR-016/FR-017 byte-identical preservation)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the registry + shared type aliases + error envelope so every user-story phase has a consistent enforcement surface. No user story begins until Phase 2 is green.

**⚠️ CRITICAL**: Every US in Phase 3+ depends on these.

- [X] T007 Extend `src/ummaya/tools/registry.py` with `AdapterPrimitive` StrEnum (`lookup`, `resolve_location`, `submit`, `subscribe`, `verify`) matching `data-model.md § 4`
- [X] T008 Extend `src/ummaya/tools/registry.py` with module-level type aliases `PublishedTier` (18-label `Literal[...]` enum) + `NistAalHint` (`Literal["AAL1","AAL2","AAL3"]`) matching `data-model.md § 2` and `research.md § 3.1`
- [X] T009 Extend `src/ummaya/tools/registry.py::AdapterRegistration` with `primitive: AdapterPrimitive`, `source_mode: AdapterSourceMode`, `published_tier_minimum: PublishedTier | None = None`, `nist_aal_hint: NistAalHint | None = None`; preserve Spec 024 / 025 V1–V6 invariants verbatim
- [X] T010 Extend `src/ummaya/tools/registry.py::ToolRegistry.register()` backstop to reject `tool_id` collisions with a structured `AdapterIdCollisionError` (FR-020) — first-wins
- [X] T011 Create `src/ummaya/primitives/_errors.py` with Pydantic models `AdapterNotFoundError`, `AdapterInvocationError`, and `SubscriptionBackpressureDrop` matching `data-model.md § 7`
- [X] T012 [P] Create `src/ummaya/security/v12_dual_axis.py` post-init backstop that enforces FR-030 (both `published_tier_minimum` and `nist_aal_hint` required on/after v1.2 GA) — gated by a module-level constant `V12_GA_ACTIVE: bool = False` so pre-v1.2 compatibility window (FR-028) remains open
- [X] T013 [P] Re-export Spec 022's existing `lookup` + `resolve_location` from `src/ummaya/primitives/__init__.py` without modifying their source modules (FR-016/FR-017 byte-identical preservation)
- [X] T014 [P] Unit test `tests/unit/registry/test_adapter_primitive_field.py` — asserts `AdapterRegistration` accepts new `primitive` + dual-axis fields and rejects unknown primitive strings
- [X] T015 [P] Unit test `tests/unit/registry/test_tool_id_collision.py` — asserts FR-020: second registration with an existing `tool_id` raises `AdapterIdCollisionError`

**Checkpoint**: Registry schema + error envelope + primitive scaffolding ready. US1–US6 can now begin in parallel.

---

## Phase 3: User Story 1 — `submit` absorbs every write-transaction verb (Priority: P1) 🎯 MVP

**Goal**: Ship the `submit` primitive with a purely domain-agnostic envelope `{tool_id, params}` → `{transaction_id, status, adapter_receipt}`. Two mock adapters from different ministries route through the same envelope, proving the 5-verb absorption.

**Independent Test**: Build `src/ummaya/tools/mock/data_go_kr/fines_pay.py` + `src/ummaya/tools/mock/mydata/welfare_application.py`. Invoke each via `ummaya.submit(tool_id=..., params=...)` and verify the main envelope never carries a domain-specific field. `SC-002` ripgrep lint (10 banned strings) comes back clean.

### Tests for User Story 1

> Write these first; they MUST fail before implementation lands (FR-001..005 + SC-001, SC-002).

- [X] T016 [P] [US1] Contract test `tests/unit/primitives/submit/test_contract_shape.py` — loads `contracts/submit.input.schema.json` + `submit.output.schema.json`, validates against fixture payloads, and asserts no domain fields appear in either schema
- [X] T017 [P] [US1] Lint test `tests/lint/test_submit_banned_words.py` — ripgreps `src/ummaya/primitives/submit.py` against the 10 banned strings from SC-002 (`check_eligibility`, `reserve_slot`, `subscribe_alert`, `pay`, `issue_certificate`, `submit_application`, `declared_income_krw`, `certificate_type`, `family_register`, `resident_register`). Zero matches required.
- [X] T018 [P] [US1] Unit test `tests/unit/primitives/submit/test_dispatch.py` — asserts envelope purity + `AdapterNotFoundError` path for unregistered `tool_id`
- [X] T019 [P] [US1] Unit test `tests/unit/primitives/submit/test_transaction_id_determinism.py` — FR-004: same `(tool_id, params)` produces same `transaction_id`
- [X] T020 [P] [US1] Integration test `tests/integration/test_submit_published_tier_gate.py` — registers a mock `submit` adapter with `published_tier_minimum="ganpyeon_injeung_kakao_aal2"`, invokes with a mismatched `AuthContext`, and asserts structured rejection (SC-005)

### Implementation for User Story 1

- [X] T021 [US1] Create `src/ummaya/primitives/submit.py` with `SubmitInput`, `SubmitStatus` StrEnum, `SubmitOutput` Pydantic models matching `data-model.md § 1`
- [X] T022 [US1] Implement `submit(tool_id, params) -> SubmitOutput | AdapterNotFoundError | AdapterInvocationError` dispatcher in `src/ummaya/primitives/submit.py` — resolves registry entry, validates `params` against adapter's typed model, awaits `invoke()`, emits Spec 024 `ToolCallAuditRecord` (delegated to existing audit sink) + Spec 021 OTEL span `gen_ai.tool_loop.iteration`
- [X] T023 [US1] Implement deterministic `transaction_id` derivation — SHA-256 over `canonical_json(tool_id, params, adapter_nonce)` + `urn:ummaya:send:` prefix
- [X] T024 [US1] Update `src/ummaya/primitives/__init__.py` to export real `submit` symbol (replacing Phase 1 placeholder)
- [X] T025 [P] [US1] Create first mock adapter `src/ummaya/tools/mock/data_go_kr/fines_pay.py` — `FinesPayParams` Pydantic model + `async def invoke()` + `AdapterRegistration` with `tool_id="mock_traffic_fine_pay_v1"`, matching the worked example in `quickstart.md § 3`
- [X] T026 [P] [US1] Create second mock adapter `src/ummaya/tools/mock/mydata/welfare_application.py` (different ministry, shared envelope) — `tool_id="mock_welfare_application_submit_v1"` — to prove Acceptance Scenario 2
- [X] T027 [US1] Register both mock adapters in `src/ummaya/tools/mock/__init__.py` on import so they are discoverable at registry boot

**Checkpoint**: `submit` is fully functional and testable. The 5→1 verb collapse is provable via SC-002 ripgrep.

---

## Phase 4: User Story 4 — `lookup` / `resolve_location` preserved from Spec 022 (Priority: P1)

**Goal**: Prove that Spec 022's 4 adapters + envelope shapes survive the 5-primitive migration byte-identically. This phase is placed before US2 because a regression here cascades.

**Independent Test**: Re-run Spec 022's full pytest suite against the new branch. All green. (SC-003)

### Tests for User Story 4

- [X] T028 [P] [US4] Regression test `tests/integration/test_spec_022_regression.py` — invokes `uv run pytest specs/022-mvp-main-tool/tests/ -q` as a subprocess + asserts exit code 0 (SC-003)
- [X] T029 [P] [US4] Contract byte-identity test `tests/unit/primitives/test_lookup_envelope_identity.py` — loads Spec 022's `contracts/lookup.input.schema.json` + `lookup.output.schema.json` and asserts that Spec 031's re-exported `lookup` emits the same shapes (FR-016)
- [X] T030 [P] [US4] Contract byte-identity test `tests/unit/primitives/test_resolve_location_envelope_identity.py` — same for `resolve_location` (FR-017)

### Implementation for User Story 4

- [X] T031 [US4] Verify `src/ummaya/primitives/__init__.py` re-export (T013) does not introduce any attribute / signature change on `lookup` or `resolve_location`
- [X] T032 [US4] Back-fill `AdapterPrimitive` + `published_tier_minimum=None, nist_aal_hint=None` on the 4 existing Spec 022 registrations (`koroad_accident_hazard_search`, `kma_forecast_fetch`, `hira_hospital_search`, `nmc_emergency_search`) during pre-v1.2 compatibility window (FR-028) — `None` is the legal default pre-v1.2
- [X] T033 [US4] Update the 4 Spec 022 adapter registrations to set `primitive=AdapterPrimitive.lookup` or `AdapterPrimitive.resolve_location` as appropriate; no other field changes

**Checkpoint**: Spec 022 test suite green; envelope shapes confirmed byte-identical. US1 + US4 are now the MVP surface.

---

## Phase 5: User Story 2 — `verify` publishes Korean tiers primary, NIST AAL advisory (Priority: P1)

**Goal**: Ship `verify` with a 6-family discriminated union + 18 `published_tier` labels + advisory `nist_aal_hint`. Delegation-only — no CA / HSM / VC issuer in UMMAYA.

**Independent Test**: For each of the 6 families, construct a mock `verify` call and confirm the returned `AuthContext` carries the correct `published_tier` + `nist_aal_hint`. A downstream `submit` adapter branches on `published_tier` (not `nist_aal_hint`) to gate access (SC-005).

### Tests for User Story 2

- [X] T034 [P] [US2] Contract test `tests/unit/primitives/verify/test_contract_shape.py` — loads `contracts/verify.input.schema.json` + `verify.output.schema.json`, validates 6 family variants + `VerifyMismatchError` against fixtures
- [X] T035 [P] [US2] Unit test `tests/unit/primitives/verify/test_discriminator.py` — 6-family coercion-free dispatch; `family_hint` mismatch returns `VerifyMismatchError`, never coerces (FR-010)
- [X] T036 [P] [US2] Unit test `tests/unit/primitives/verify/test_published_tier_narrowing.py` — each family variant rejects a `published_tier` outside its subset per `data-model.md § 2.1`
- [X] T037 [P] [US2] Unit test `tests/unit/primitives/verify/test_no_signing_keys.py` — grep-style assertion over `src/ummaya/primitives/verify.py` for `sign`, `BEGIN PRIVATE KEY`, `issue_credential`; zero matches (FR-009 harness-not-reimplementation)
- [X] T038 [P] [US2] Lint test `tests/lint/test_no_ca_material.py` — greps `src/` + `docs/` for forbidden extensions (`.pem` private halves, `.p12`, `.pfx`) outside `docs/mock/npki_crypto/fixtures/*` (SC-006)

### Implementation for User Story 2

- [X] T039 [US2] Create `src/ummaya/primitives/verify.py` with `VerifyInput`, `_AuthContextBase`, 6 family context classes (`GongdongInjeungseoContext`, `GeumyungInjeungseoContext`, `GanpyeonInjeungContext`, `DigitalOnepassContext`, `MobileIdContext`, `MyDataContext`), `AuthContext` Annotated union, `VerifyMismatchError`, `VerifyOutput` — all matching `data-model.md § 2`
- [X] T040 [US2] Implement `@model_validator(mode="after")` on each family variant enforcing per-family `published_tier` narrowing per the table in `data-model.md § 2.1`
- [X] T041 [US2] Implement `verify(family_hint, session_context) -> AuthContext | VerifyMismatchError` dispatcher — delegates to the registered adapter for the `family_hint`; returns `VerifyMismatchError` if the session context evidence disagrees with `family_hint` (FR-010, no coercion)
- [X] T042 [US2] Update `src/ummaya/primitives/__init__.py` to export real `verify` symbol (replacing placeholder)
- [X] T043 [US2] Register 6 mock verify adapters — one per family — under `src/ummaya/tools/mock/verify_<family>.py` (each fixture-backed, no real external calls); these back the acceptance scenarios and SC-005

**Checkpoint**: `verify` is fully functional. Dual-axis schema in effect. SC-005 + SC-006 demonstrable.

---

## Phase 6: User Story 3 — `subscribe` unifies CBS / REST pull / RSS 2.0 without webhook (Priority: P2)

**Goal**: Ship `subscribe` with a single `AsyncIterator[Event]` surface covering 3GPP CBS broadcast + REST polling + RSS 2.0 tailing. Bounded lifetime, back-pressure, no inbound webhook.

**Independent Test**: Register one mock adapter per modality (`mock_cbs_disaster_v1`, `mock_rest_pull_tick_v1`, `mock_rss_public_notices_v1`). Subscribe to each, iterate, confirm discriminated `kind` field, bounded lifetime expiry, back-pressure emission.

### Tests for User Story 3

- [X] T044 [P] [US3] Contract test `tests/unit/primitives/subscribe/test_contract_shape.py` — loads `contracts/subscribe.input.schema.json` + `subscribe.output.schema.json`, validates 4-variant event union
- [X] T045 [P] [US3] Unit test `tests/unit/primitives/subscribe/test_no_webhook_field.py` — introspects `SubscribeInput` model and asserts no field accepts a URL that could act as inbound receiver (FR-013)
- [X] T046 [P] [US3] Unit test `tests/unit/primitives/subscribe/test_muxer.py` — registers the 3 mock adapters and asserts events from all 3 modalities flow through the same iterator with discriminated `kind`
- [X] T047 [P] [US3] Unit test `tests/unit/primitives/subscribe/test_lifetime_bound.py` — `SubscribeInput` rejects `lifetime_seconds > 31536000` (365 days ceiling, FR-011)
- [X] T048 [P] [US3] Integration test `tests/integration/test_subscribe_lifetime_expiry.py` — FR-014: subscribe with lifetime=1s, iterate; after expiry the iterator terminates cleanly and a final audit marker is emitted
- [X] T049 [P] [US3] Integration test `tests/integration/test_subscribe_backpressure.py` — mock CBS feed emits 100 events in 1s with 64-event pending-buffer cap; assert at least one `SubscriptionBackpressureDrop` event (FR-015)
- [X] T050 [P] [US3] Unit test `tests/unit/primitives/subscribe/test_rss_guid_dedup.py` — duplicate `guid` values are suppressed; reset `guid` on publisher side surfaces as new item (Edge Case + research.md §4)

### Implementation for User Story 3

- [X] T051 [US3] Create `src/ummaya/primitives/subscribe.py` with `SubscribeInput`, `SubscriptionHandle`, `CbsBroadcastEvent`, `RestPullTickEvent`, `RssItemEvent`, `SubscriptionBackpressureDrop`, `SubscriptionEvent` union matching `data-model.md § 3`
- [X] T052 [US3] Implement the modality muxer — dispatches to one of 3 internal drivers based on `AdapterRegistration.source_mode` + adapter-declared modality flag; yields `SubscriptionEvent` through a shared `asyncio.Queue` with `maxsize=64` for back-pressure
- [X] T053 [US3] Implement CBS broadcast driver — consumes mock `3GPP TS 23.041` fixture producing events with `cbs_message_id ∈ {4370..4385}` + SHA-256 `payload_hash`
- [X] T054 [US3] Implement REST-pull driver — `httpx.AsyncClient` with adapter-declared `polling_interval`; harness enforces minimum 10s interval; emits `RestPullTickEvent` per tick
- [X] T055 [US3] Implement RSS 2.0 driver — tracks `guid` set per-handle; de-dupes; reset `guid` treated as new item; emits `RssItemEvent`
- [X] T056 [US3] Implement `lifetime_seconds` enforcement — `asyncio.wait_for` on the iterator wrapper; on expiry, releases network resources and emits a final `SubscriptionBackpressureDrop` only if unflushed events remain (FR-014)
- [X] T057 [US3] Update `src/ummaya/primitives/__init__.py` to export real `subscribe` symbol
- [X] T058 [P] [US3] Create mock adapter `src/ummaya/tools/mock/cbs/disaster_feed.py` — `tool_id="mock_cbs_disaster_v1"`
- [X] T059 [P] [US3] Create mock adapter `src/ummaya/tools/mock/data_go_kr/rest_pull_tick.py` — `tool_id="mock_rest_pull_tick_v1"`
- [X] T060 [P] [US3] Create mock adapter `src/ummaya/tools/mock/data_go_kr/rss_notices.py` — `tool_id="mock_rss_public_notices_v1"`

**Checkpoint**: `subscribe` is functional. 3-modality unification proven. No webhook field anywhere.

---

## Phase 7: User Story 5 — Mock design scope = 6 mirror-able systems only (Priority: P2)

**Goal**: Enforce that `docs/mock/` contains exactly 6 system directories and `docs/scenarios/` contains exactly 3 OPAQUE journey files (SC-004). Guard against silent drift.

**Independent Test**: `ls docs/mock/` returns 6 entries; `ls docs/scenarios/*.md` returns 3 entries; no adapter under `src/ummaya/tools/mock/` implements an OPAQUE system (FR-026).

### Tests for User Story 5

- [X] T061 [P] [US5] Docs-lint test `tests/test_mock_scenario_split.py` — asserts (a) `docs/mock/` subdirectory count == 6, (b) exact names are `{data_go_kr, omnione, barocert, mydata, npki_crypto, cbs}`, (c) `docs/scenarios/*.md` count == 3, (d) each scenario file contains the handoff heading `## UMMAYA ↔ real system handoff point` (FR-024, SC-004)
- [X] T062 [P] [US5] Docs-lint test `tests/test_no_opaque_mock_adapter.py` — walks `src/ummaya/tools/mock/` and asserts no adapter module imports or references `gov24`, `kec`, or `npki_portal_session` — `docs/scenarios/` content MUST NOT have a code sibling (FR-026)

### Implementation for User Story 5

- [X] T063 [P] [US5] Write `docs/mock/data_go_kr/README.md` — public-spec URL (`openapi.data.go.kr`), mirror axis (`byte`), license, fixture-recording approach
- [X] T064 [P] [US5] Write `docs/mock/omnione/README.md` — OpenDID reference stack URL, mirror axis (`byte`), Apache-2.0 license
- [X] T065 [P] [US5] Write `docs/mock/barocert/README.md` — developers.barocert.com URL, mirror axis (`shape`), SDK-docs basis
- [X] T066 [P] [US5] Write `docs/mock/mydata/README.md` — KFTC 마이데이터 v240930 standard URL, mirror axis (`shape`), mTLS + OAuth 2.0 profile
- [X] T067 [P] [US5] Write `docs/mock/npki_crypto/README.md` — PyPinkSign reference URL, crypto-layer-only scope (PKCS#7 / #12), explicit NOTE: NPKI portal session is OPAQUE and lives in scenarios (not mock)
- [X] T068 [P] [US5] Write `docs/mock/cbs/README.md` — 3GPP TS 23.041 URL, Message ID 4370–4385, mirror axis (`byte`)
- [X] T069 [P] [US5] Fill `docs/scenarios/gov24_submission.md` — journey narrative + "Submission API withheld from public disclosure" rationale + explicit handoff heading
- [X] T070 [P] [US5] Fill `docs/scenarios/kec_xml_signature.md` — journey narrative + "XSD + public signing key not disclosed" rationale + handoff heading
- [X] T071 [P] [US5] Fill `docs/scenarios/npki_portal_session.md` — journey narrative + "Portal-proprietary session handshake" rationale + handoff heading
- [X] T072 [US5] Document the scenario→mock promotion path in a new `docs/scenarios/README.md` (FR-025) — include the "Promoted to mock on <date>, tracked by #<issue>" footer template

**Checkpoint**: Mock scope + scenario scope both enforced. SC-004 green.

---

## Phase 8: User Story 6 — Security Spec v1.2 replaces TOOL_MIN_AAL with dual-axis schema (Priority: P3)

**Goal**: Bump `docs/security/tool-template-security-spec-v1.md` to v1.2. Replace `TOOL_MIN_AAL` single-axis table with `(published_tier_minimum, nist_aal_hint)` dual-axis. Preserve Spec 024 V1–V4 + Spec 025 V6 invariants verbatim.

**Independent Test**: Diff the doc pre/post — `TOOL_MIN_AAL` absent, dual-axis table present, v1.1→v1.2 migration note explicit, Spec 024/025 invariants preserved.

### Tests for User Story 6

- [X] T073 [P] [US6] Docs-lint test `tests/lint/test_security_spec_v12.py` — asserts `docs/security/tool-template-security-spec-v1.md` contains `## Version 1.2`, contains a migration note section, does NOT contain `TOOL_MIN_AAL` single-axis table, contains the `(published_tier_minimum, nist_aal_hint)` dual-axis table
- [X] T074 [P] [US6] Unit test `tests/unit/security/test_v12_dual_axis.py` — toggles `v12_dual_axis.V12_GA_ACTIVE = True` in a fixture and asserts registrations without both dual-axis fields raise `DualAxisMissingError` (FR-030, SC-007)
- [X] T075 [P] [US6] Registry-regression test `tests/unit/security/test_spec_024_025_preserved.py` — asserts V1 (irreversible rule), V3 (auth-level mapping), V6 (auth-type↔auth-level allow-list) still fire on/after v1.2 GA toggle (FR-028)

### Implementation for User Story 6

- [X] T076 [US6] Bump `docs/security/tool-template-security-spec-v1.md` metadata header to `Version: 1.2` + `Status: Draft` + `Supersedes: v1.1`
- [X] T077 [US6] Replace the `TOOL_MIN_AAL` table in the doc with the `(published_tier_minimum, nist_aal_hint)` dual-axis table — covering the 4 Spec 022 adapters + the new mock adapter landings from US1/US2/US3
- [X] T078 [US6] Write the v1.1→v1.2 migration note section in the doc — explicit list of which invariants re-stated (V1–V6 verbatim) vs superseded (`TOOL_MIN_AAL` → dual-axis)
- [X] T079 [US6] Flip `src/ummaya/security/v12_dual_axis.py::V12_GA_ACTIVE` from `False` to `True` — activates FR-030 enforcement
- [X] T080 [US6] Delete the legacy 8-verb entries from `src/ummaya/security/audit.py::TOOL_MIN_AAL` (confirmed present per research.md §6); migrate the 4 Spec 022 adapters + 2 Phase-2 entries to dual-axis

**Checkpoint**: Security spec is v1.2; dual-axis enforced at registration time; legacy 8-verb AAL-only artifacts removed.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Enforce SC-001 / SC-008 / SC-009 / SC-010, run the full quickstart smoke-test, update the agent-context file, and leave the feature ship-ready.

- [X] T081 [P] Unit test `tests/unit/primitives/test_registry_count.py` — asserts exactly 5 primitives are registered on the main surface (SC-001)
- [X] T082 [P] Lint test `tests/lint/test_no_legacy_verbs.py` — regex-scans `src/ummaya/primitives/` + `src/ummaya/tools/` + adapter registrations for any of the 6 banned legacy top-level verb names (`check_eligibility`, `reserve_slot`, `subscribe_alert`, `pay`, `issue_certificate`, `submit_application`). Zero top-level registrations may match (SC-010)
- [X] T083 [P] Dependency-diff test `tests/lint/test_no_new_runtime_deps.py` — uses `git diff main -- pyproject.toml` subprocess; asserts zero new entries under `[project].dependencies` (SC-008)
- [X] T084 [P] Onboarding checklist — add `docs/onboarding/five-primitive-harness.md` pointing at `specs/031-five-primitive-harness/quickstart.md` + the `docs/vision.md § Claude Code` analog table (SC-009)
- [X] T085 [P] OTEL span parity test `tests/integration/test_otel_span_emission.py` — asserts `submit`, `subscribe`, `verify` emit `gen_ai.tool_loop.iteration` spans with the same attribute shape as Spec 022's `lookup` / `resolve_location` (FR-031)
- [X] T086 Run `uv run pytest` locally; fix any failures; then run the full quickstart smoke-test (`quickstart.md § 5`) and confirm every SC-00X pytest invocation returns exit code 0
- [X] T087 Run `.specify/scripts/bash/update-agent-context.sh claude` — now that plan.md is fully populated, re-populate `CLAUDE.md` Active Technologies block correctly
- [X] T088 [P] Update `docs/vision.md § Reference materials` with a single line: "Spec 031 ratifies the 5-primitive surface; see `specs/031-five-primitive-harness/research.md § 1` for the CC primitive-mapping table."

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup (T001–T006)**: No dependencies — start immediately.
- **Phase 2 Foundational (T007–T015)**: Depends on Phase 1. **BLOCKS all user stories**.
- **Phase 3 US1 `submit` (P1, MVP) (T016–T027)**: Depends on Phase 2.
- **Phase 4 US4 `lookup`/`resolve_location` preservation (P1) (T028–T033)**: Depends on Phase 2. Independent of US1.
- **Phase 5 US2 `verify` (P1) (T034–T043)**: Depends on Phase 2. Independent of US1/US4; consumed by US1 (SC-005 integration test T020 references `AuthContext` from US2 — cross-story integration optional but preferred).
- **Phase 6 US3 `subscribe` (P2) (T044–T060)**: Depends on Phase 2. Independent.
- **Phase 7 US5 Mock scope (P2) (T061–T072)**: Depends on Phase 1 only (docs-layer). Can run in parallel with any other phase.
- **Phase 8 US6 Security v1.2 (P3) (T073–T080)**: Depends on Phase 2 (registry shape) + US1/US2/US3 implementations (v1.2 table enumerates them). Lands last in implementation order.
- **Phase 9 Polish (T081–T088)**: Depends on all desired user stories.

### User Story Dependencies

- **US1**: Self-contained after Phase 2. MVP candidate.
- **US4**: Self-contained after Phase 2. Second MVP candidate (preservation proof).
- **US2**: Self-contained after Phase 2. Third P1 candidate.
- **US3**: Self-contained after Phase 2.
- **US5**: Docs-layer only; no runtime dependency on other stories. Fully parallel.
- **US6**: Consumes the registrations from US1/US2/US3 when populating the dual-axis table (T077); therefore sequenced after those three user stories land.

### Within Each User Story

- Contract / unit tests (marked `tests/unit/` or `tests/lint/`) written first; must FAIL before implementation.
- Models (Pydantic classes) before dispatchers.
- Dispatchers before mock adapter landings.
- Mock adapter landings before integration tests in that story.

### Parallel Opportunities

- Phase 1 tasks T002 / T003 / T004 / T005 / T006 all `[P]` — five parallel scaffolding jobs.
- Phase 2 tasks T012 / T013 / T014 / T015 all `[P]` — four parallel backstop + test jobs after T007–T011 land sequentially.
- **All 4 P1/P2 user stories (US1, US4, US2, US3)** can run in parallel once Phase 2 completes — four independent Teammates.
- **US5 (docs-only)** can run in parallel with anything from day one (after Phase 1).
- Within US3 the three modality drivers (T053 / T054 / T055) are sequential (single file `subscribe.py`), but the three mock adapter landings (T058 / T059 / T060) are `[P]`.
- Within US5 all 9 `README.md` / scenario `.md` writes (T063–T071) are `[P]`.
- Polish phase tests T081 / T082 / T083 / T084 / T085 / T088 all `[P]`.

---

## Parallel Example: After Phase 2 Checkpoint

```bash
# Four Teammates kick off simultaneously once T007–T015 are complete:
Teammate A (Backend Architect): US1 submit — T016..T027
Teammate B (Backend Architect): US4 lookup/resolve_location preservation — T028..T033
Teammate C (Security Engineer): US2 verify — T034..T043
Teammate D (Backend Architect): US3 subscribe — T044..T060

# Concurrently (from day one, no Phase 2 dep beyond file-system writes):
Teammate E (Technical Writer): US5 docs/mock + docs/scenarios — T061..T072
```

---

## Implementation Strategy

### MVP (P1 Stories)

1. Phase 1 + Phase 2 serial.
2. US1 + US4 + US2 in parallel (3 P1 stories).
3. **STOP + VALIDATE** — `SC-001, SC-002, SC-003, SC-005, SC-006, SC-008, SC-009, SC-010` must all pass.
4. Demo-able MVP: `submit` shipped, Spec 022 regression-free, `verify` dual-axis live.

### Incremental Delivery

5. US3 `subscribe` — lands after MVP, demo-able independently.
6. US5 docs — parallel with any of the above; lands anywhere in the cycle.
7. US6 Security v1.2 — final; cutover flips `V12_GA_ACTIVE` → `True`.

### Parallel Team Strategy

Four Teammates can operate concurrently after Phase 2. US5 Teammate is purely docs-bound and never blocks code work. Lead (Opus) owns Phase 2 (registry backstop) + Phase 9 polish + US6 cutover review.

---

## Notes

- `[P]` = different files, no dependency on incomplete tasks.
- `[Story]` = traceability only; test files are grouped by story but live under `tests/unit/primitives/<primitive>/` / `tests/integration/` / `tests/lint/` per the plan.md layout.
- Every task has an exact file path + test identity.
- No new runtime dependencies (SC-008 hard gate).
- Commit after each task or logical group; respect the `feedback_no_co_author` rule (no `Co-Authored-By: Claude`).
- At any checkpoint, stop and validate the relevant SC before advancing.

---

## Summary

| Metric | Count |
|---|---|
| Total tasks | 88 |
| Setup (Phase 1) | 6 |
| Foundational (Phase 2) | 9 |
| US1 `submit` (P1 MVP) | 12 |
| US4 `lookup`/`resolve_location` preservation (P1) | 6 |
| US2 `verify` (P1) | 10 |
| US3 `subscribe` (P2) | 17 |
| US5 Mock scope (P2) | 12 |
| US6 Security v1.2 (P3) | 8 |
| Polish (Phase 9) | 8 |
| Parallel-eligible (`[P]`) tasks | 48 |

**MVP scope** = Phase 1 + Phase 2 + US1 (P1) + US4 (P1) + US2 (P1) = 43 tasks.
