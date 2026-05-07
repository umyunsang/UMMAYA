<!-- SPDX-License-Identifier: Apache-2.0 -->
# Tool Template Security Spec v1.2 — Five-Primitive Dual-Axis Hardening

**Feature**: 031-five-primitive-harness  
**Status**: Draft  
**Date**: 2026-04-19  
**Spec branch**: `031-five-primitive-harness`  
**Supersedes**: v1.1 (2026-04-17, feature 024-tool-security-v1)

---

## 1. Purpose & Audience

This document is the normative specification for the KOSMOS Tool Template security posture at the v1 baseline. It is written for two audiences: (1) a ministry security reviewer (부처 정보보호 담당관 or KISA 평가위원) evaluating KOSMOS as a candidate system for a public-service pilot, and (2) a KOSMOS adapter-lane contributor implementing or reviewing a new `GovAPITool` adapter.

All requirements in this document use RFC 2119 normative language: **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, **OPTIONAL**.

This document is authoritative and supersedes any informally described controls in earlier internal drafts. It references two companion artifacts:

1. **JSON Schema** — `docs/security/tool-call-audit-record.schema.json` (JSON Schema Draft 2020-12): the machine-readable contract for `ToolCallAuditRecord`.
2. **OpenAPI skeleton** — see §Delegation protocol (added in US2) for a forward reference to `docs/security/agent-delegation.openapi.yaml`, which documents the `/agent-delegation` endpoint family (OpenAPI 3.0). That artifact is added in the US2 delivery and is not required for the ministry self-serve questions addressed by this document.

The Korean statutory artifacts cited here are: PIPA (개인정보 보호법), 전자정부법 (Electronic Government Act), 전자서명법 (Electronic Signature Act), and K-ISMS-P (정보보호 및 개인정보보호 관리체계 인증기준). Every control cites at least one of these statutory artifacts or an international standard.

---

## 2. Dual-Axis Auth Contract (v1.2 GA)

### Why dual-axis

Starting with v1.2, KOSMOS replaces the single-axis `TOOL_MIN_AAL` table (8 legacy verbs, NIST AAL only) with a two-field dual-axis contract on every `AdapterRegistration`. The **primary axis** is `published_tier_minimum`: one of 18 labels drawn from the `PublishedTier` closed enum in `src/kosmos/tools/registry.py`, each encoding a specific Korean identity program (e.g., `gongdong_injeungseo_personal_aal3`, `ganpyeon_injeung_kakao_aal2`). This axis is the authoritative gate used by the dispatcher and enforced by the registry backstop. The **secondary axis** is `nist_aal_hint`: an advisory `Literal["AAL1", "AAL2", "AAL3"]` field intended solely for external consumers (e.g., international interop auditors, SIEM tools) who need a normalized NIST view of the credential requirement. The `nist_aal_hint` is logged and surfaced in OpenAPI schemas but is NOT the branching axis for access control decisions. The single-axis `TOOL_MIN_AAL` map from v1.1 is retired for all adapters except the 4 Spec 022 residual entries that remain in `src/kosmos/security/audit.py` during the pre-GA migration window — see §14 for the full invariant list. The dual-axis contract is enforced by `kosmos.security.v12_dual_axis.enforce()` wired as a `@model_validator(mode="after")` on `AdapterRegistration` once `V12_GA_ACTIVE` is flipped to `True` (T079).

> **Citation**: NIST SP 800-63-4 "Digital Identity Guidelines" (2024). SP 800-63-3 was withdrawn in 2024; all AAL citations use SP 800-63-4 exclusively. AAL definitions: §4.1 (AAL1 — single-factor), §4.2 (AAL2 — multi-factor), §4.3 (AAL3 — phishing-resistant hardware-bound key). "public" = no authentication required (below AAL1 baseline). Spec 031 FR-030.

### Dual-axis adapter table

Footnote (†): Spec 022 adapters (`lookup`, `resolve_location`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search`) are registered as `GovAPITool` objects via the legacy path; they do not construct `AdapterRegistration` directly and therefore carry `null` for `published_tier_minimum` during the pre-v1.2 GA migration window. Their `auth_level` values (referenced by V3) are authoritative until T080 completes the dual-axis migration.

| Tool ID | Primitive | `published_tier_minimum` | `nist_aal_hint` | Korean Description | English Description |
|---|---|---|---|---|---|
| `lookup` | `lookup` | `null` †  | `AAL1` | 공공정보 검색 — 개인정보 없음 | Public catalog search; no PII in inputs or outputs |
| `resolve_location` | `resolve_location` | `null` † | `AAL1` | 공간 좌표 조회 — 공공 지오코딩 | Public geospatial geocoding query |
| `nfa_emergency_info_service` | `lookup` | `null` † | `AAL1` | 소방청 구급통계 조회 — 익명화 집계 | NFA emergency statistics; anonymized aggregate, no PII |
| `mohw_welfare_eligibility_search` | `lookup` | `null` † | `AAL2` | 복지 서비스 목록 조회 — 개인정보 포함 | MOHW/SSIS welfare service list; personal data scope |
| `mock_traffic_fine_pay_v1` | `submit` | `ganpyeon_injeung_kakao_aal2` | `AAL2` | 교통 과태료 납부 — 간편인증 카카오 AAL2 | Traffic fine payment; irreversible; 간편인증 (Kakao) minimum |
| `mock_welfare_application_submit_v1` | `submit` | `mydata_individual_aal2` | `AAL2` | 복지급여 신청 — 마이데이터 개인 AAL2 | Welfare benefit application; irreversible; MyData individual minimum |
| `mock_verify_gongdong_injeungseo` | `verify` | `gongdong_injeungseo_personal_aal3` | `AAL3` | 공동인증서 본인확인 — NPKI 개인 AAL3 | Joint certificate identity verify; KICA/KOSCOM PKI |
| `mock_verify_geumyung_injeungseo` | `verify` | `geumyung_injeungseo_personal_aal2` | `AAL2` | 금융인증서 본인확인 — 금결원 개인 AAL2 | Financial certificate identity verify; KFTC |
| `mock_verify_ganpyeon_injeung` | `verify` | `ganpyeon_injeung_kakao_aal2` | `AAL2` | 간편인증 — 카카오 기본 AAL2 | Simple auth (Kakao default); Barocert |
| `mock_verify_digital_onepass` | `verify` | `digital_onepass_level2_aal2` | `AAL2` | 디지털원패스 Level 2 — 행정안전부 AAL2 | Digital Onepass Level 2; MOIS public auth |
| `mock_verify_mobile_id` | `verify` | `mobile_id_mdl_aal2` | `AAL2` | 모바일 운전면허 신분확인 — AAL2 | Mobile driver license identity verify; MOIS |
| `mock_verify_mydata` | `verify` | `mydata_individual_aal2` | `AAL2` | 마이데이터 OAuth 인증 — 금결원 개인 AAL2 | MyData OAuth identity verify; KFTC |

**Authoritative sources**: `published_tier_minimum` values are enforced by `src/kosmos/tools/registry.py::AdapterRegistration.published_tier_minimum` (the `PublishedTier` closed enum, 18 labels across 6 families). The registration-time backstop is `src/kosmos/security/v12_dual_axis.py::enforce` (a `@model_validator(mode="after")` on `AdapterRegistration`).

### 2.1 Legacy `check_eligibility` Public Path (archived in v1.2)

The 8 legacy top-level verbs (`check_eligibility`, `subscribe_alert`, `reserve_slot`, `issue_certificate`, `submit_application`, `pay`, `lookup`, `resolve_location`) were the main tool surface in the v1 design. The first six were retired in the five-primitive refactor (Spec 031 SC-010): their ministry semantics are now encapsulated in adapter-layer modules under `src/kosmos/tools/<ministry>/`, routed through the `submit` primitive envelope. `lookup` and `resolve_location` are retained as read-only Spec 022 primitives.

The `check_eligibility` public-path AAL1 carve-out — which permitted rules-only welfare eligibility evaluation without PII — was specific to the `check_eligibility` verb. That verb no longer exists as a first-class tool registration; the carve-out therefore has no live code backing in v1.2. The historical invariant (public-path calls MUST set `public_path_marker=True`, `auth_level_presented="AAL1"`, `pipa_class="non_personal"`, `dpa_reference=null`) is preserved in archived audit records and in the I2 invariant on `ToolCallAuditRecord`, but it cannot be triggered by any currently registered adapter.

Cross-reference: Spec 031 `spec.md § Scope Boundaries`; `src/kosmos/security/audit.py::TOOL_MIN_AAL` (which retains only `lookup`, `resolve_location`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search` after T080).

---

## 3. `check_eligibility` Public Path Conditions

The `check_eligibility` tool MUST default to AAL2. The AAL1 public-path exception is strictly bounded to the following conditions, all of which MUST hold simultaneously (FR-002):

1. **Rules-only evaluation**: the tool invocation runs a pure, deterministic eligibility rules engine against the supplied inputs. No database look-up of citizen-specific data is performed.
2. **Public inputs only**: every field in the request payload is drawn exclusively from public eligibility criteria (e.g., income bracket thresholds, household composition categories publicly defined in statute). No citizen-specific attribute (name, resident registration number, address, biometric, etc.) is present in the request.
3. **No PII in response**: the response contains only a boolean eligibility decision and/or publicly defined eligibility rules text. No personal attribute of the querying session is reflected back.

When all three conditions hold, `pipa_class` MUST be set to `"non_personal"`, `auth_level_presented` MUST be `"AAL1"`, and `public_path_marker` MUST be `True` in the resulting `ToolCallAuditRecord`. The record MUST NOT carry a `dpa_reference` (it will be `None`) because there is no PII processing scope to document.

Any `check_eligibility` invocation that does not satisfy all three conditions MUST be treated as an AAL2-gated call regardless of the presented credential level. An insufficient-AAL call MUST be rejected and an audit record MUST be emitted with `permission_decision="deny_aal"`.

> **Citation**: FR-002; OWASP ASVS V4.1.5 (fail-secure default); NIST SP 800-63-4 §4.1/§4.2.

---

## 4. `GovAPITool` Field Contract

Every `GovAPITool` registration MUST populate four new mandatory fields introduced by this spec. These fields are **required with no defaults** — a registration that omits, passes `None` for, or supplies an inconsistent value for any of these fields MUST fail at load time with a `ValueError` (FR-003, FR-004, FR-005).

> **Citation**: FR-003, FR-004, FR-005; OWASP ASVS V4.1.5 (fail-secure); PIPA §26; NIST SP 800-63-4 §4.

### 4.1 New Field Definitions

| Field | Type (Literal domain) | Semantics |
|---|---|---|
| `auth_level` | `Literal["public", "AAL1", "AAL2", "AAL3"]` | Minimum NIST SP 800-63-4 AAL required to invoke this tool. MUST equal the tool's row in `TOOL_MIN_AAL`. |
| `pipa_class` | `Literal["non_personal", "personal", "sensitive", "identifier"]` | PIPA data classification of the tool's input-or-output payload. `"personal"` = 개인정보 (PIPA §2.1); `"sensitive"` = 민감정보 (PIPA §23); `"identifier"` = 고유식별정보 (PIPA §24); `"non_personal"` = no PIPA-covered data. |
| `is_irreversible` | `bool` | `True` when invocation produces a side effect the citizen cannot undo via a second tool call (e.g., `pay`, `submit_application`, `issue_certificate`). Drives the FR-007 live-introspection requirement. |
| `dpa_reference` | `Optional[str]` | Identifier of the DPA (Data Processing Agreement) template governing the PIPA §26 processor chain for this tool's scope. MUST be non-null whenever `pipa_class != "non_personal"`. |

### 4.2 Cross-Field Validators

The following validators are enforced at `ToolRegistry.register()` via pydantic v2 `model_validator(mode="after")`. All violations raise `ValueError` with a message referencing the relevant FR. Silent defaults and silent coercions are forbidden.

| Validator | Condition | Error trigger | FR Reference |
|---|---|---|---|
| V1 | `pipa_class != "non_personal"` → `auth_level != "public"` | Any PII-class tool declared as `public` | FR-004 (extends FR-038) |
| V2 | `pipa_class != "non_personal"` → `dpa_reference is not None` | PII-class tool missing DPA documentation | FR-014 (closes PIPA §26 gap) |
| V3 | `auth_level` MUST equal the tool's row in `TOOL_MIN_AAL` | Drift between field and table | FR-001, FR-005 |
| V4 | `is_irreversible = True` → `auth_level != "public"` | Irreversible action declared public | FR-004 extension |

---

## 5. Permission Pipeline

The KOSMOS permission pipeline is deny-by-default: in the absence of a matching positive authorization, a tool call MUST be rejected (FR-008). This invariant maps directly to OWASP ASVS V4.1.5 ("Verify that the application denies all access by default, requiring explicit grants to specific roles for access to every function").

> **Citation**: FR-006, FR-007, FR-008; OWASP ASVS V4.1.5; NIST SP 800-207 §4 (Zero Trust policy decision point); PIPA §17 (목적 외 이용 금지); PIPA §28-2.

The pipeline MUST execute in the following 5-stage sequence:

### Stage 1 — AAL Gate (FR-006)

The presented credential AAL is compared against `TOOL_MIN_AAL[tool_id]`. If the presented AAL is below the minimum, the call MUST be rejected. The pipeline MUST emit a `ToolCallAuditRecord` with `permission_decision="deny_aal"` at the same evidentiary level as a successful call — rejected calls carry full audit records.

> **Citation**: FR-006; NIST SP 800-63-4 §4; ISO 27001 A.9.4.1.

### Stage 2 — Scope Gate (FR-003, FR-008)

The delegation token's declared scope (if any) MUST be validated against the requested `tool_id` and operation. If the scope does not cover the requested operation, the call MUST be rejected with `permission_decision="deny_scope"`.

> **Citation**: RFC 6749 §3.3 (OAuth scope); RFC 9068 §4 (`aal_asserted` claim); OWASP ASVS V4.1.3.

### Stage 3 — Irreversible-Action Introspection (FR-007)

If `GovAPITool.is_irreversible == True`, the pipeline MUST perform a live token introspection per RFC 7662 before executing the adapter body, regardless of local cache state. If the token is not currently active (expired, revoked, or otherwise invalid), the call MUST be rejected with `permission_decision="deny_irreversible_introspect_failed"`.

This stage applies even when the local cache indicates the token is valid. The introspection MUST be a fresh network call to the `introspection_endpoint` declared in the delegation token.

> **Citation**: FR-007; RFC 7662 §2.1; NIST SP 800-63-4 §4.3.

### Stage 4 — Deny-by-Default (FR-008)

Any call that has not been explicitly authorized by Stages 1–3 MUST be rejected with `permission_decision="deny_deny_by_default"`. This includes calls where scope matching returns a zero-length result, tool IDs not in the registry, and any other ambiguous or unrecognized authorization state.

> **Citation**: FR-008; OWASP ASVS V4.1.5; NIST SP 800-207 §4 (ZTA policy decision point).

### Stage 5 — Allow

A call that passes all four preceding stages MUST be allowed. The pipeline MUST emit a `ToolCallAuditRecord` with `permission_decision="allow"` and forward execution to the adapter's `handle()` body.

> **Citation**: FR-006; ISO 27001 A.9.4.2.

---

## 6. Audit Trail

Every KOSMOS tool call — successful or rejected — MUST produce an immutable `ToolCallAuditRecord` evidence artifact. Mock and live adapters MUST produce records with identical schema shape; the only permitted shape-differing field is `adapter_mode` (FR-012).

> **Citation**: FR-009, FR-010, FR-011, FR-012; PIPA 안전조치 고시 §8; 전자정부법 시행령 §33; ISO 27001 A.12.4.1; K-ISMS-P 2.11.2.

The `ToolCallAuditRecord` pydantic v2 model is defined in `src/kosmos/security/audit.py`. The authoritative JSON Schema (Draft 2020-12) is `docs/security/tool-call-audit-record.schema.json`. Both define the same contract and MUST stay in sync.

### 6.1 Field Catalog

The following 18 fields are defined. All are required unless marked "Conditional" or "Optional".

| # | Field | Type | Required | Semantics |
|---|---|---|---|---|
| 1 | `record_version` | `Literal["v1"]` | Yes | Schema version lock. Increment triggers a new JSON Schema version. |
| 2 | `tool_id` | `str` | Yes | Matches `GovAPITool.id`. Pattern: `^[a-z][a-z0-9_]*$`. |
| 3 | `adapter_mode` | `Literal["mock", "live"]` | Yes | The only permitted shape-differing field between mock and live records (FR-012). |
| 4 | `session_id` | `str` (minLength 1) | Yes | Opaque session identifier. UUIDv7 is RECOMMENDED (IETF draft-ietf-uuidrev-rfc4122bis). |
| 5 | `caller_identity` | `str` (minLength 1) | Yes | Opaque identity token. MUST NOT be a resident registration number (주민등록번호); PIPA §24 (고유식별정보 처리 제한). |
| 6 | `permission_decision` | `Literal["allow", "deny_aal", "deny_scope", "deny_irreversible_introspect_failed", "deny_deny_by_default"]` | Yes | Deny variants are first-class to satisfy FR-006 evidentiary parity. |
| 7 | `auth_level_presented` | `Literal["public", "AAL1", "AAL2", "AAL3"]` | Yes | The AAL the caller proved at call time — not what the tool required. |
| 8 | `pipa_class` | `Literal["non_personal", "personal", "sensitive", "identifier"]` | Yes | Classification of THIS call's payload, not the adapter default. |
| 9 | `dpa_reference` | `Optional[str]` | Conditional | Non-null whenever `pipa_class != "non_personal"`. Closes PIPA §26 위탁 documentation gap (FR-014). |
| 10 | `input_hash` | `str` (`^[0-9a-f]{64}$`) | Yes | Hex-encoded lowercase SHA-256 of the canonicalized input payload. |
| 11 | `output_hash` | `str` (`^[0-9a-f]{64}$`) | Yes | Hex-encoded lowercase SHA-256 of the raw output payload. |
| 12 | `sanitized_output_hash` | `Optional[str]` (`^[0-9a-f]{64}$` when non-null) | Optional | Hex-encoded SHA-256 of the sanitized output, when sanitization ran. |
| 13 | `merkle_covered_hash` | `Literal["sanitized_output_hash", "output_hash"]` | Yes | Declares which hash the Merkle leaf binds. MUST be `"sanitized_output_hash"` iff `sanitized_output_hash` is non-null; `"output_hash"` otherwise (FR-010). |
| 14 | `merkle_leaf_id` | `Optional[str]` | Optional | Leaf identifier in the external Merkle chain. Chain construction is deferred to a future epic. |
| 15 | `timestamp` | `datetime` (RFC 3339, timezone-aware) | Yes | Timezone MUST be present; naïve timestamps are rejected (I4). |
| 16 | `cost_tokens` | `int` (≥ 0) | Yes | LLM token cost if applicable; `0` for pure-tool calls with no LLM invocation. |
| 17 | `rate_limit_bucket` | `str` (minLength 1) | Yes | Bucket identifier for per-provider/per-key quota accounting. |
| 18 | `public_path_marker` | `bool` | Yes | `True` ONLY for `check_eligibility` AAL1 rules-only evaluations. See §3 and invariant I2. |

### 6.2 Model Invariants

The following invariants are enforced by the pydantic `model_validator(mode="after")` in `ToolCallAuditRecord`. Violations raise `ValidationError` at construction time.

- **I1**: `sanitized_output_hash is not None` ↔ `merkle_covered_hash == "sanitized_output_hash"`. Precisely: if `sanitized_output_hash` is set, `merkle_covered_hash` MUST be `"sanitized_output_hash"`; if `sanitized_output_hash` is `None`, `merkle_covered_hash` MUST be `"output_hash"`.
- **I2**: `public_path_marker = True` → `tool_id == "check_eligibility"` AND `auth_level_presented == "AAL1"` AND `pipa_class == "non_personal"`. All three conjuncts MUST hold.
- **I3**: `pipa_class != "non_personal"` → `dpa_reference is not None`. Non-empty string required (minLength 1) — an empty string is not a valid reference.
- **I4**: `timestamp.tzinfo is not None`. RFC 3339 naïve timestamps (those without a timezone offset) are rejected at construction time.

> **Citation**: FR-010; FR-002; IETF RFC 3339 §5.6 (Internet Date/Time Format); 개인정보 보호법 §26; OWASP ASVS v5.0 V4.1.5.

### 6.3 Audit Record Retention

Records MUST be retained for the binding maximum of 5 years, reconciling PIPA 안전조치 고시 §8 (2년 최소 보관) and 전자정부법 시행령 §33 (5년 최소 보관). The longer duty governs.

> **Citation**: FR-011; PIPA 안전조치 고시 §8; 전자정부법 시행령 §33; ISO 27001 A.12.4.1; K-ISMS-P 2.11.2.

Both statutes mandate retention floors (not ceilings). Selecting the maximum simultaneously satisfies both obligations without requiring per-tool retention branching. Over-retention does not harm audit integrity. The backing store for the retention policy (append-only log, Merkle chain, etc.) is deferred to a future epic.

### 6.4 Worked Examples

The following three worked examples MUST each validate against `docs/security/tool-call-audit-record.schema.json` under JSON Schema Draft 2020-12 validation. CI verifies this via `tests/unit/test_tool_call_audit_record.py` (SC-004).

---

#### Example 1 — Authenticated Allow (AAL3, `identifier` class, DPA referenced)

A citizen requests a 주민등록등본 (resident registration certificate). The tool `issue_certificate` is classified `pipa_class="identifier"` (고유식별정보, PIPA §24), requires AAL3, and is irreversible. The caller presents an AAL3 credential, the pipeline grants the call, and sanitized output (with direct identifier data redacted) is produced alongside the raw output. The Merkle leaf binds the sanitized form.

```json
{
  "record_version": "v1",
  "tool_id": "issue_certificate",
  "adapter_mode": "live",
  "session_id": "01jb8zk3v0000000deadbeefcafe0001",
  "caller_identity": "citizen:abc123",
  "permission_decision": "allow",
  "auth_level_presented": "AAL3",
  "pipa_class": "identifier",
  "dpa_reference": "DPA-MOIS-2026-01",
  "input_hash": "a3f1c2e4b5d6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  "output_hash": "b4e2d3f5c6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
  "sanitized_output_hash": "c5f3e4a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4",
  "merkle_covered_hash": "sanitized_output_hash",
  "merkle_leaf_id": null,
  "timestamp": "2026-04-17T10:30:00+09:00",
  "cost_tokens": 0,
  "rate_limit_bucket": "per-session",
  "public_path_marker": false
}
```

---

#### Example 2 — Deny on AAL Insufficiency (`deny_aal`)

A caller attempts to invoke `issue_certificate` but presents only an AAL1 credential. The AAL gate (Stage 1 of the permission pipeline) rejects the call immediately. The rejection is recorded at full evidentiary parity with a successful call — there is no reduced-detail mode for denied records (FR-006). No output is produced, so `output_hash` is the SHA-256 of an empty payload, and `sanitized_output_hash` is `null`.

```json
{
  "record_version": "v1",
  "tool_id": "issue_certificate",
  "adapter_mode": "live",
  "session_id": "01jb8zk3v0000000deadbeefcafe0002",
  "caller_identity": "citizen:def456",
  "permission_decision": "deny_aal",
  "auth_level_presented": "AAL1",
  "pipa_class": "identifier",
  "dpa_reference": "DPA-MOIS-2026-01",
  "input_hash": "d6e4f5a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
  "output_hash": "e7f5a6b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
  "sanitized_output_hash": null,
  "merkle_covered_hash": "output_hash",
  "merkle_leaf_id": null,
  "timestamp": "2026-04-17T10:31:00+09:00",
  "cost_tokens": 0,
  "rate_limit_bucket": "per-session",
  "public_path_marker": false
}
```

---

#### Example 3 — `check_eligibility` Public Path (AAL1, `non_personal`, public_path_marker=True)

A citizen asks "am I eligible for 긴급복지 지원?" with no PII in either direction — only publicly defined income bracket thresholds are evaluated. All three public-path conditions (§3) hold: rules-only evaluation, public inputs, no PII in response. The call is allowed at AAL1. No sanitization is needed since there is no PII to sanitize; the Merkle leaf binds the raw output hash directly.

```json
{
  "record_version": "v1",
  "tool_id": "check_eligibility",
  "adapter_mode": "mock",
  "session_id": "01jb8zk3v0000000deadbeefcafe0003",
  "caller_identity": "citizen:ghi789",
  "permission_decision": "allow",
  "auth_level_presented": "AAL1",
  "pipa_class": "non_personal",
  "dpa_reference": null,
  "input_hash": "f8a6b7c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
  "output_hash": "a9b7c8d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
  "sanitized_output_hash": null,
  "merkle_covered_hash": "output_hash",
  "merkle_leaf_id": null,
  "timestamp": "2026-04-17T10:32:00+09:00",
  "cost_tokens": 0,
  "rate_limit_bucket": "per-session",
  "public_path_marker": true
}
```

---

## 7. PIPA Role

> "KOSMOS defaults to the PIPA §26 수탁자 (processor) role for adapter-lane tool calls; the LLM synthesis step carries a controller-level carve-out documented inline. A PIPC 유권해석 query is pursued in a parallel track and is not blocking for this spec."

**Pre-synthesis tool calls**: When KOSMOS invokes a `GovAPITool` adapter on behalf of a citizen, KOSMOS acts as a 수탁자 (processor) under PIPA §26(4). The original purpose-decision belongs to the citizen (or the ministry whose data is accessed). KOSMOS has no independent purpose in collecting or processing the response; it acts as a pipe with evidentiary obligations. The `dpa_reference` field in every PII-bound record is the hook for the PIPA §26 위탁 documentation chain.

**LLM synthesis stage**: When KOSMOS's synthesis stage combines citizen PII (e.g., ministry API response text) with the LLM to produce a bespoke advisory artifact, KOSMOS independently determines the re-purposing of that PII. This constitutes controller-level processing (처리자). Consent records MUST therefore carry two distinct consent fields:
- `dpa_reference` — covers the §26 processor chain (forwarding the ministry response).
- `synthesis_consent: bool` — covers the controller-level carve-out (combining PII in LLM synthesis). These consents are separate; collecting `dpa_reference` without `synthesis_consent=True` does not authorize synthesis.

> **Citation**: SC-008; PIPA §26; PIPA §15(1) (처리 목적); PIPA §28-2 (LLM/AI 처리); FR-014, FR-015; research.md §3.5.

**Parallel legal track**: A PIPC (개인정보보호위원회) 유권해석 질의서 for this interpretation is tracked in the deferred items table (D4) and is not a blocker for v1 spec acceptance per the pre-decided product judgment documented in MEMORY.md.

---

## 8. Edge Case Disposition

The following 7 edge cases are drawn verbatim from `specs/024-tool-security-v1/spec.md § Edge Cases`. Each disposition is normative.

### EC-1 — Output Sanitization vs Audit Integrity

**Disposition: Allow (with mandatory hash fields).**  
The `ToolCallAuditRecord` carries both `output_hash` (always present, binds the raw payload) and `sanitized_output_hash` (nullable, binds the sanitized form). The `merkle_covered_hash` field explicitly declares which variant the Merkle leaf covers — `"sanitized_output_hash"` when sanitization ran, `"output_hash"` otherwise. Downstream verifiers MUST NOT infer which variant is authoritative from the record body; they MUST read `merkle_covered_hash` directly (FR-010). Invariant I1 ensures the two fields are always mutually consistent.

> **Citation**: FR-010; ISO/IEC 27001:2022 A.12.4.1 (Event logging integrity); OWASP ASVS v5.0 V10.3 (Data integrity).

### EC-2 — Delegation Revocation Race

**Disposition: Refer (to FR-007 introspection and future pipeline epic).**  
The current spec requires live token introspection per RFC 7662 before every `is_irreversible=True` call (Stage 3 of the permission pipeline, §5). For in-flight non-irreversible calls, the spec does not yet mandate a mid-execution abort mechanism; that behavior is deferred to the full pipeline implementation epic (#646). The audit record for a call that completes despite a mid-execution revocation SHOULD record the caller's revocation intent as a separate record field in future schema revisions; the v1 record does not carry this field. Any call completed after the revocation becomes detectable during the retention period via timeline cross-reference.

> **Citation**: RFC 7009 §2 (OAuth 2.0 Token Revocation); RFC 7662 §2.1 (Token Introspection response).

### EC-3 — AAL Downgrade Attempts

**Disposition: Deny.**  
Stage 1 of the permission pipeline (AAL gate) rejects any call whose presented AAL is below `TOOL_MIN_AAL[tool_id]`. The audit record for the rejected call MUST be retained at the same evidentiary level as successful calls — there is no reduced-detail mode for denied records (FR-006). This invariant is tested in `tests/unit/test_tool_call_audit_record.py` (the `deny_aal` example, §6.4 Example 2).

> **Citation**: FR-006; K-ISMS-P 2.11.2 (보안 모니터링); 개인정보의 안전성 확보조치 기준 §8 (접속기록 보관·점검).

### EC-4 — `check_eligibility` Public Path

**Disposition: Allow (under strict preconditions documented in §3).**  
The public-path exception is permitted only when all three conditions in §3 hold simultaneously. The audit record MUST set `public_path_marker=True`, `auth_level_presented="AAL1"`, `pipa_class="non_personal"`, and `dpa_reference=null`. Invariant I2 ensures this combination cannot be confused post-hoc with an authenticated call. Any attempt to set `public_path_marker=True` for any tool other than `check_eligibility` is rejected by invariant I2 at construction time.

> **Citation**: FR-002; NIST SP 800-63-4 §4.1 (AAL1); OWASP ASVS v5.0 V4.1.5 (Access control enforcement).

### EC-5 — LLM Synthesis Carve-Out

**Disposition: Allow (with explicit dual consent).**  
The synthesis stage carries a controller-level carve-out from the default §26 수탁자 posture (§7). The consent record MUST carry both `dpa_reference` and `synthesis_consent=True` to authorize synthesis. Forwarding a ministry response without synthesis requires only `dpa_reference`. The two consents are separate fields and MUST NOT be conflated. See FR-014, FR-015.

> **Citation**: FR-014; FR-015; 개인정보 보호법 §15(1) (처리 목적 구분); 개인정보 보호법 §26 (업무 위탁); 개인정보 보호법 §28-2 (가명정보 처리).

### EC-6 — SBOM Divergence

**Disposition: Deny (fail fast; signed regeneration required).**  
When a `.github/workflows/sbom.yml` run detects that the generated SBOM diverges from the last-signed artifact, the build MUST fail. The recovery path requires a signed regeneration with an explicit reviewer-authored note; silent override is not permitted (FR-019). This policy is scaffolded in the SBOM workflow epic (#647); the current spec records the normative requirement without landing the workflow (deferred T023).

> **Citation**: FR-019; 공공SW 보안관리요구사항; NIST SP 800-218 SSDF v1.1 PS.3 (Archive and Protect Each Software Release).

### EC-7 — Stale Token Reuse

**Disposition: Deny (for irreversible actions; allow-with-cache for reversible).**  
For `is_irreversible=True` tools, live introspection per RFC 7662 is MANDATORY at Stage 3 (§5), regardless of local cache state. A delegation token that is expired or revoked MUST cause the call to be rejected with `permission_decision="deny_irreversible_introspect_failed"`. For reversible tools, the local cache may be used for efficiency but MUST observe a minimum introspection cadence (exact window defined in the pipeline implementation epic #646). See FR-007.

> **Citation**: FR-007; RFC 7662 §2.1 (active-token introspection); NIST SP 800-63-4 §4.2 (AAL2 session management).

---

---

## 9. Delegation Protocol

> **Lint tooling note**: The companion OpenAPI 3.0 skeleton (`docs/security/agent-delegation.openapi.yaml`) was validated using `npx @redocly/cli lint docs/security/agent-delegation.openapi.yaml` (Redocly CLI v1.x, built-in recommended configuration). The run completed with zero errors and zero warnings after syntactic corrections described in §9.8 below and in the YAML comment block. SC-007 is satisfied.

The KOSMOS delegation protocol enables a citizen to grant a scoped, time-bounded, and revocable token to the KOSMOS agent to act on their behalf against Korean ministry APIs. The protocol is grounded exclusively in IETF RFCs, W3C recommendations, and Korean statutory artifacts. No KOSMOS-proprietary extensions are introduced; any ministry adopting OAuth 2.1 + mTLS can implement the companion OpenAPI skeleton (`docs/security/agent-delegation.openapi.yaml`) without depending on KOSMOS-internal artifacts.

> **Citation**: FR-013, FR-014, FR-015, FR-016; research.md §3.6; `.eval-artifacts/security-design-research/04-identity-delegation.md`.

### 9.1 OAuth 2.1 Baseline + PKCE Mandate (RFC 7636)

The authorization baseline is **OAuth 2.1** (consolidated in draft-ietf-oauth-v2-1-15), which mandates PKCE (Proof Key for Code Exchange) for all flows that involve a public client. KOSMOS CLI qualifies as a public client (no confidential client secret). Therefore:

- The Authorization Code grant + PKCE per **[RFC 7636](https://www.rfc-editor.org/rfc/rfc7636)** is the only permitted citizen-facing flow.
- `code_challenge_method=S256` (SHA-256) is REQUIRED; the `plain` method is PROHIBITED.
- The Implicit grant (removed in OAuth 2.1) and Resource Owner Password Credentials grant (also removed) are PROHIBITED.

PKCE defends the public-client flow against authorization code interception attacks (RFC 7636 §1). Because KOSMOS agents poll for tokens rather than receiving redirects, the citizen-facing confirmation-code hand-off MUST use the Device Authorization Grant per §9.2 below.

> **Citation**: RFC 7636 §4 (PKCE protocol); draft-ietf-oauth-v2-1-15 §4.1 (Auth Code + PKCE mandatory); RFC 9700 §2.1 (Security Best Current Practice — PKCE everywhere); FR-013.

### 9.2 Device Authorization Grant (RFC 8628)

The **Device Authorization Grant** per **[RFC 8628](https://www.rfc-editor.org/rfc/rfc8628)** is the primary grant type for all citizen-facing KOSMOS flows. It accommodates the architectural reality that the KOSMOS agent runs in a constrained context (server process or TUI) while the citizen must complete authentication on their own device using PASS 간편인증 or 공동인증서.

Flow summary:

1. KOSMOS agent posts the desired scopes and its `client_id` to `/agent-delegation/token` (Device Authorization Request, RFC 8628 §3.1). The server returns a `device_code`, a `user_code`, and a `verification_uri`.
2. The citizen navigates to `verification_uri` on their own device, authenticates with PASS or 공동인증서 (TEE-bound, on citizen's own hardware), and approves the requested scopes.
3. KOSMOS polls `/agent-delegation/token` (Device Access Token Request, RFC 8628 §3.3). Once the citizen completes the TEE challenge, polling returns the `DelegationToken`.

The citizen's TEE credential is **not bypassed** — it remains the authoritative authentication event. KOSMOS receives only a delegation token; the underlying TEE-bound credential never leaves the citizen's device. See §9.8 for TEE-binding constraints.

**Precondition**: Confirmation-code issuance endpoints MUST enforce the TEE-binding constraint documented in §9.8 before issuing a `device_code`.

> **Citation**: RFC 8628 §3.1, §3.3, §3.5; FR-013; research.md §3.6; `.eval-artifacts/security-design-research/04-identity-delegation.md` §3.

### 9.3 Token Exchange Flow (RFC 8693)

The **Token Exchange** grant per **[RFC 8693](https://www.rfc-editor.org/rfc/rfc8693)** handles ministry-to-ministry hand-off — specifically, the case where a single citizen delegation spans multiple ministry endpoints (e.g., a `submit_application` that triggers downstream calls to a welfare ministry and a housing ministry).

Contract for token exchange requests (grant type: `urn:ietf:params:oauth:grant-type:token-exchange`):

- `subject_token`: the original citizen-delegated `DelegationToken` access token.
- `subject_token_type`: `urn:ietf:params:oauth:token-type:access_token`.
- `requested_token_type`: `urn:ietf:params:oauth:token-type:access_token` (narrower-scoped derived token).
- `audience`: the target ministry resource server identifier.
- `scope`: MUST be a strict subset of the original token's scope.

**Critical invariant**: the `aal_asserted` claim MUST travel through the exchange unchanged. A derived token MUST NOT carry a higher `aal_asserted` value than the original token. The exchange server MUST reject any request where the derived token's requested scope would require a higher AAL than what was originally asserted. Cross-link: §2 (Dual-Axis Auth Contract).

> **Citation**: RFC 8693 §2.1 (Request parameters); RFC 8693 §4.1 (`may_act` claim); RFC 8693 §6 (Delegation semantics); FR-013; research.md §3.6.

### 9.4 JWT Profile (RFC 9068) — `aal_asserted` Claim

Every delegation token issued by the `/agent-delegation` endpoint MUST be a **JWT per [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068)** (JSON Web Token Profile for OAuth 2.0 Access Tokens).

The `aal_asserted` claim is **REQUIRED** on every access token. Its value MUST be one of `"AAL1"`, `"AAL2"`, `"AAL3"`, matching the NIST SP 800-63-4 AAL achieved by the citizen's authentication event. Tokens representing unauthenticated (public) requests MUST use an unsigned request mechanism and are out of scope for the delegation token JWT profile; the spec refers to these as "public markers" and they do not carry the `aal_asserted` claim.

The claim domain maps to `nist_aal_hint` values in the dual-axis table (§2):

| `aal_asserted` value | Permissible `nist_aal_hint` gate | Example adapters |
|---|---|---|
| `"AAL1"` | `AAL1` only | `lookup`, `resolve_location`, `nfa_emergency_info_service` |
| `"AAL2"` | `AAL1`, `AAL2` | `mock_traffic_fine_pay_v1`, `mock_welfare_application_submit_v1`, verify family adapters |
| `"AAL3"` | `AAL1`, `AAL2`, `AAL3` | `mock_verify_gongdong_injeungseo` |

Cross-link: §2 (Dual-Axis Auth Contract). A token presenting `aal_asserted="AAL1"` is rejected by Stage 1 of the permission pipeline (§5) for any adapter whose `nist_aal_hint` requires `AAL2` or higher.

> **Citation**: RFC 9068 §2 (JWT access token claims); RFC 9068 §2.2 (`scope` claim); RFC 9068 §2.3 (`act` claim); NIST SP 800-63-4 §4.1–§4.3; FR-013.

### 9.5 Introspection (RFC 7662) — Mandatory on Irreversible Calls

Token introspection per **[RFC 7662](https://www.rfc-editor.org/rfc/rfc7662)** is the mechanism by which the KOSMOS permission pipeline verifies that a delegation token is currently active.

**Normative requirement (FR-007)**: every tool where `is_irreversible=True` MUST call RFC 7662 introspection against the `introspection_endpoint` declared in the `DelegationToken` on **every invocation**, regardless of local cache state. A cached "active" result from a prior introspection MUST NOT be reused.

The introspection endpoint is `/agent-delegation/introspect` (documented in the OpenAPI skeleton). The response MUST follow the RFC 7662 §2.2 shape. A response with `"active": false` (token expired, revoked, or invalid for any reason) MUST cause the call to be rejected with `permission_decision="deny_irreversible_introspect_failed"`.

Cache constraint: the `exp` field in the introspection response indicates when the token expires. Caching of introspection results MUST NOT exceed the token's `exp`. For irreversible-action tools, no caching is permitted regardless of `exp`.

> **Citation**: RFC 7662 §2.1, §2.2; FR-007; §5 (Stage 3 — Irreversible-Action Introspection); EC-7.

### 9.6 Revocation (RFC 7009) — Maximum Cache Window

Token revocation per **[RFC 7009](https://www.rfc-editor.org/rfc/rfc7009)** enables a citizen to immediately cancel a prior delegation. A citizen revocation MUST be honored by all resource servers within a bounded propagation window.

**Normative requirement**: Resource servers MUST honor revocation within **60 seconds** of a successful HTTP 200 response from a POST to the revocation endpoint (`/agent-delegation/revoke`). This is a normative MUST. After a successful revocation POST:

1. The authorization server MUST mark the token as revoked in its token database immediately.
2. Resource servers that cache introspection results MUST flush the cached result for the revoked token within 60 seconds of the revocation event — via push notification, polling, or expiry of a hard-maximum cache TTL of 60 seconds, whichever the adopting implementation uses.
3. Any subsequent introspection call for a revoked token MUST return `"active": false`.

The 60-second window is a design choice that balances operational latency with citizen control assurance. It means a citizen who revokes mid-session may see up to one further tool call complete before propagation reaches all resource servers. The audit trail will reflect the revocation timeline; the post-revocation call is detectable during the retention period.

> **Citation**: RFC 7009 §2 (Revocation Request); RFC 7009 §2.2 (Error Response); RFC 7662 (Introspection, for verifying revocation state); EC-2 (Delegation revocation race).

### 9.7 Consent Record Fields

A consent record is a citizen-signed artifact linking a delegation event to one or more tool scopes. Every consent record issued through `/agent-delegation/consent` MUST carry the following fields:

| Field | Required? | Semantics |
|---|---|---|
| `subject` | REQUIRED | Opaque citizen identifier bound by PASS/공동인증서 at collection time (PIPA §22). |
| `agent_identifier` | REQUIRED | Identifier of the KOSMOS agent instance receiving the delegation. |
| `scope` | REQUIRED | Array of scope entries shaped as `<tool_id>:<verb>[:<resource>]`. |
| `dpa_reference` | Conditional — REQUIRED when any scope is PII-bound (FR-014) | Identifier of the DPA template governing the PIPA §26 위탁 chain for this consent. MUST be non-null when any scope covers a `pipa_class != "non_personal"` tool. Closes the PIPA §26 위탁 documentation gap. |
| `synthesis_consent` | REQUIRED | Separate boolean reflecting the LLM-synthesis controller-level carve-out (FR-015). `true` is REQUIRED for any call feeding LLM synthesis, per the PIPA §26 수탁자 default with controller-level carve-out (§7). |
| `issued_at` | REQUIRED | RFC 3339 timestamp with timezone at which the citizen signed. |
| `expires_at` | REQUIRED | RFC 3339 timestamp with timezone at which the consent expires. Maximum validity is defined by the token's `expires_in`; adopting implementations SHOULD limit to 24 hours for citizen-facing flows. |
| `revoked_at` | Optional | RFC 3339 timestamp with timezone at which the citizen revoked the consent. Non-null after revocation. |
| `proof_of_consent_hash` | REQUIRED | SHA-256 hash of the canonical serialization of the consent payload, binding the citizen's approval event to the record; hash algorithm: FIPS 180-4 §6.2 (SHA-256). |

`synthesis_consent=true` is REQUIRED when KOSMOS synthesizes a response from a ministry API payload that contains citizen PII. It is NOT implied by `dpa_reference` being non-null; the two fields cover distinct PIPA processing purposes. See §7 (PIPA role).

> **Citation**: FR-014 (`dpa_reference`); FR-015 (`synthesis_consent`); PIPA §17, §22, §26, §28-2; research.md §3.5; §7 (PIPA Role).

### 9.8 PASS / 공동인증서 TEE-Binding (FR-016)

PASS 간편인증 and 공동인증서 credentials are **TEE-bound**: their signing keys are held inside the citizen's device hardware security enclave (Samsung Knox Vault / Titan M / Android StrongBox on Android; Apple Secure Enclave on iOS) and cannot be programmatically exported. The KOSMOS delegation protocol intentionally does not attempt to bypass this constraint.

**Normative requirement (FR-016)**: the confirmation-code issuance endpoint (`/agent-delegation/token` when processing a Device Authorization Grant) MUST bind the resulting delegation token to a TEE-held key. This means:

1. The citizen completes the PASS or 공동인증서 authentication challenge on their own device (in the TEE-bound context).
2. The resulting delegation token MUST carry a **`cnf` (confirmation) claim** per one of the following standards, whichever the adopting ministry implements:
   - **[RFC 8705](https://www.rfc-editor.org/rfc/rfc8705)** — Mutual-TLS Client Authentication and Certificate-Bound Access Tokens: the token's `cnf` claim contains an `x5t#S256` (SHA-256 thumbprint of the client certificate), binding the token to the mutual-TLS channel.
   - **[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449)** — OAuth 2.0 Demonstrating Proof of Possession (DPoP): the token's `cnf` claim contains a `jkt` (JWK thumbprint), binding the token to a DPoP proof signed with the client's key pair.

KOSMOS does not hold the citizen's TEE-bound key. The delegation architecture preserves the TEE boundary: KOSMOS receives only the delegation token, and the `cnf` claim binds that token to the citizen's original authentication event. A resource server verifying the token can confirm the citizen's TEE involvement through the `cnf`-bound channel without requiring KOSMOS to re-possess the underlying credential.

> **Citation**: FR-016; RFC 8705 §3 (Certificate-Bound Access Tokens); RFC 9449 §4 (DPoP Proof); research.md §3.6; `.eval-artifacts/security-design-research/04-identity-delegation.md` §3 (PASS TEE-Bound Constraint).

---

### 9.9 W3C Verifiable Credentials + DID

The current KOSMOS delegation baseline (§9.1–§9.8) uses OAuth 2.1 + RFC 9068 JWTs as the primary token format. W3C Verifiable Credentials (VC) and Decentralized Identifiers (DID) are a forward-looking option that KOSMOS tracks but does not mandate in the v1 spec.

**Target credential format**: **[W3C VC Data Model v2.0](https://www.w3.org/TR/vc-data-model-2.0/)** (Candidate Recommendation, 15 May 2025) is the target format for agent-bound credentials when KOSMOS advances beyond the JWT baseline. VC v2.0 introduces mandatory `@context` with the `https://www.w3.org/ns/credentials/v2` URL, `validFrom`/`validUntil` replaces `issuanceDate`/`expirationDate`, and Data Integrity Proofs plus SD-JWT selective disclosure suites are first-class options.

**Target identifier format**: **[W3C DID Core v1.0](https://www.w3.org/TR/did-core/)** (W3C Recommendation, 19 July 2022) is the target identifier format for KOSMOS agent identities and ministry issuer identities. The `capabilityDelegation` verification method (DID Core §5.3.3) maps to scoped tool authorization in the KOSMOS context.

**Posture rationale**: KOSMOS deliberately ships OAuth 2.1 + RFC 9068 JWTs as the v1 baseline for two reasons documented in `.eval-artifacts/security-design-research/04-identity-delegation.md` §2 and research.md §3.6:

1. **Korean public-sector PKI coexistence is non-negotiable**. PASS and 공동인증서 interoperate with OAuth 2.1 device grant flows today; W3C DID/VC issuance by Korean government ministries is not yet available. The JWT baseline is deployable; the VC/DID path requires ministry infrastructure investment.
2. **Standards maturity**: W3C VC Data Model v2.0 was a Candidate Recommendation as of the spec date. RFC 9068 JWT profile is a finalized RFC. The VC/DID path is forward-looking but not yet stable enough to mandate.

**Extension point**: The `/agent-delegation` OpenAPI skeleton's `ConsentRecord` schema (`$ref: '#/components/schemas/ConsentRecord'`) and `DelegationToken` schema are designed to be extended. A `VerifiableCredential` extension point at the consent-record level (via an additional properties extension or a oneOf variant) is **deferred** in the v1 OpenAPI skeleton; the current ConsentRecord schema does not include a `verifiableCredential` field. Adopting implementers who wish to issue VC-based consent records SHOULD use the `allOf` extension mechanism against `ConsentRecord` and cite W3C VC Data Model v2.0 §4 in the extension schema.

> **Citation**: W3C VC-DATA-MODEL-2.0 (CR, 2025-05-15) §4 (Basic Concepts), §5 (Verifiable Credential), §6 (Verifiable Presentation); W3C DID-CORE-1.0 (Rec., 2022-07-19) §5.1 (DID Syntax), §5.3.3 (`capabilityDelegation`); research.md §3.6; `.eval-artifacts/security-design-research/04-identity-delegation.md` §2 (Protocol Reference Matrix), §5 (VC Design); FR-016.

---

---

## §10. Supply chain & provenance

This section is normative. It binds FR-017, FR-018, and FR-019 from `specs/024-tool-security-v1/spec.md` and is grounded in the supply-chain posture decisions recorded in `specs/024-tool-security-v1/research.md §3.7` ("Supply-chain posture — SLSA L3 gap + dual-format SBOM") and `§3.8` ("Fail-closed registration invariant"). Neither decision is re-litigated here; this section enforces the outcomes.

> **Citation**: FR-017, FR-018, FR-019, SC-005; research.md §3.7, §3.8; NIST SP 800-218 SSDF v1.1; SLSA v1.0.

---

### §10.1 SBOM — Dual-Format Generation (FR-017)

Every release and every push to `main` MUST generate a Software Bill of Materials (SBOM) in **both** of the following formats. The two formats are MANDATORY together — one format alone does not satisfy this requirement.

**Format 1 — SPDX 2.3**

Governed by the [SPDX 2.3 Specification](https://spdx.github.io/spdx-spec/v2.3/) and published as [ISO/IEC 5962:2021](https://www.iso.org/standard/81870.html). SPDX is the canonical format for Korean public-sector procurement tooling: Korean 공공SW 보안관리요구사항 and KISA tooling pipelines consume SPDX as the primary input for license and vulnerability tracking in procured software. Generating SPDX 2.3 specifically — rather than SPDX 2.2 or the emerging SPDX 3.0 draft — aligns with the ISO/IEC 5962:2021 published standard rather than a working draft, which is the appropriate basis for a ministry-pilot submission.

**Format 2 — CycloneDX 1.6**

Governed by the [CycloneDX 1.6 Specification](https://cyclonedx.org/docs/1.6/json/) (OWASP-governed). CycloneDX 1.6 is the canonical format for runtime VEX (Vulnerability Exploitability eXchange) and dependency-graph tooling. It is the preferred SBOM format for GitHub Dependency Review and Trivy-based supply-chain scanners, which KOSMOS CI uses for advisory analysis. CycloneDX 1.6 introduces first-class `vulnerabilities` and `declarations` components that align with the VEX workflow deferred to the dependency-scanning Epic.

**Source of truth**: Both SBOM files MUST be generated automatically by `.github/workflows/sbom.yml` from two and only two source inputs: `pyproject.toml` (package metadata and declared dependencies) and `uv.lock` (pinned transitive dependency graph). Hand-authored SBOMs are categorically a build-gate failure — any SBOM not produced by this workflow in a fresh environment from those two inputs MUST be rejected.

**Artifact retention**: Both generated files MUST be published as:

1. **GitHub release artifacts** — attached to every tagged release via the workflow's `softprops/action-gh-release` step, making them permanently addressable by release tag.
2. **GitHub Actions workflow artifacts** — retained for a minimum of **90 days** per workflow run, matching the CI evidence retention policy established in §6.3 (audit record retention) and the NIST SP 800-218 SSDF PS.3 evidence-archive requirement.

The 90-day floor is a minimum; adopters MAY retain longer. The floor ensures that any two consecutive builds within a typical sprint cycle are simultaneously available for divergence comparison (§10.3).

> **Citation**: FR-017, SC-005; [SPDX 2.3 Specification](https://spdx.github.io/spdx-spec/v2.3/); [ISO/IEC 5962:2021](https://www.iso.org/standard/81870.html); [CycloneDX 1.6 Specification](https://cyclonedx.org/docs/1.6/json/); [NIST SP 800-218 SSDF v1.1 PS.3](https://csrc.nist.gov/publications/detail/sp/800-218/final) (Archive and Protect Each Software Release); research.md §3.7.

---

### §10.2 Build Provenance & SLSA Maturity (FR-018)

KOSMOS commits to a documented SLSA maturity trajectory grounded in [SLSA v1.0](https://slsa.dev/spec/v1.0/). The current effective level, the target level, and the gaps between them are recorded in the table below. This table is normative: any gap-closing engineering work MUST reference this table as the authoritative acceptance criterion for the supply-chain improvement.

**Current effective level: SLSA L1.** This reflects the current state: source is version-controlled on GitHub, and all builds are scripted via `.github/workflows/`. SLSA L1 requires version-controlled source and a scripted build — both are met. SLSA L2 and L3 require signed provenance attestation and hermetic, isolated builds respectively — neither is fully met as of this spec.

**Target level: SLSA L3.** Once the signing infrastructure decision is resolved (see signing deferral below), the target is SLSA L3: signed provenance attestation from an isolated, ephemeral builder with no secret exposure to the build environment.

#### SLSA v1.0 Gap Analysis

| Criterion | SLSA v1.0 Requirement | Current | Target | Gap |
|-----------|----------------------|---------|--------|-----|
| Build.Source | Version-controlled source | Met (GitHub) | Met | None |
| Build.Provenance | Signed provenance attestation | Not met | L3 | Signing infra deferred (research.md §3.8) |
| Build.Isolation | Hermetic, isolated builder | Partial (GitHub-hosted runner) | L3 (ephemeral, no secret exposure) | Runner hardening backlog |
| Build.Parameterless | Build is not parameterised | Met | Met | None |

**Signing deferral and intended trust anchors**: As documented in `research.md §3.8`, full SLSA L3 signing is deferred pending a key-management posture decision tracked in Epic #647. The intended trust anchors are [sigstore/cosign](https://github.com/sigstore/cosign) for artifact signing and the [Rekor transparency log](https://rekor.sigstore.dev/) for public append-only attestation storage. The signing step in `.github/workflows/sbom.yml` currently emits a **stub** — a placeholder that will be replaced by a live `cosign sign` invocation once the key-management decision in Epic #647 is resolved. Adopters reviewing the workflow MUST NOT treat the stub as a valid provenance attestation; it is an explicit forward-reference marker only.

The NIST SSDF provides the broader framing: [NIST SP 800-218 SSDF v1.1](https://csrc.nist.gov/publications/detail/sp/800-218/final) Practice PO.3 ("Implement Supporting Toolchains") and Practice PS.3 ("Archive and Protect Each Software Release") are the primary NIST anchors for this section. [NIST SP 800-161 Rev. 1 C-SCRM](https://csrc.nist.gov/publications/detail/sp/800-161/rev-1/final) (Cybersecurity Supply Chain Risk Management Practices for Systems and Organizations) provides the broader C-SCRM policy context within which SLSA maturity progress is reported to ministry reviewers.

> **Citation**: FR-018; [SLSA v1.0](https://slsa.dev/spec/v1.0/) (Levels 1–3 requirements); [NIST SP 800-218 SSDF v1.1](https://csrc.nist.gov/publications/detail/sp/800-218/final) PO.3, PS.3; [NIST SP 800-161 Rev. 1 C-SCRM](https://csrc.nist.gov/publications/detail/sp/800-161/rev-1/final); research.md §3.7, §3.8.

---

### §10.3 Build-Gate on SBOM Divergence (FR-019)

The following rule is normative:

> **The build MUST fail when two back-to-back SBOM generations over the same commit SHA produce different content. Recovery requires a deliberate re-pin of the upstream dependency (PR-level evidence).**

This gate is implemented as a diff step in `.github/workflows/sbom.yml` that compares the freshly generated SBOM against the last artifact retained from the most recent successful run on the same branch. A non-zero diff output causes the workflow to exit with a non-zero status code, failing the build.

**Why this matters**: The gate protects against silent transitive dependency drift — the class of supply-chain mutation where the dependency graph silently changes between the lockfile resolve step and the artifact publish step due to upstream package index mutation, mirror inconsistency, or proxy cache poisoning. This threat is specifically relevant in the Korean public procurement context: Korean 공공SW 보안관리요구사항 requires that submitted software artifacts be reproducible from their declared sources, and K-ISMS-P Domain A.12 (Supplier Management) requires documented evidence that third-party supply inputs are controlled and verified.

**Recovery path**: Silent override is prohibited. When the divergence gate fires, the recovery MUST follow this path:

1. A human contributor identifies the changed dependency in the diff output.
2. The contributor authors a deliberate re-pin commit that explicitly updates `uv.lock` with a documented rationale (e.g., security advisory CVE-YYYY-NNNNN, upstream yanked release, approved version bump).
3. The re-pin commit MUST pass at least one reviewer's sign-off in a PR before merging. The SBOM regenerated from the re-pinned commit becomes the new reference artifact.

**Explicit prohibition**: A workflow configuration that skips the divergence check on any push (e.g., via `continue-on-error: true` or a force-push bypass) is a violation of FR-019 and MUST be flagged as a CRITICAL finding in any Copilot review gate run.

> **Citation**: FR-019; EC-6 (SBOM divergence edge case, §8); [K-ISMS-P A.12 (Supplier Management)](https://isms.kisa.or.kr/); [NIST SP 800-218 SSDF v1.1 PS.3](https://csrc.nist.gov/publications/detail/sp/800-218/final) (Archive and Protect Each Software Release); [NTIA Minimum Elements for an SBOM (2021)](https://www.ntia.gov/files/ntia/publications/sbom_minimum_elements_report.pdf) §3 (Baseline SBOM practice); 전자정부법 §49 (정보시스템의 유지·보수 — electronic government system maintenance obligations applying to software component integrity).

---

### §10.4 Out of Scope (Explicit)

The following items are explicitly outside the scope of this section and of the §10 normative requirements:

- **Runtime vulnerability scanning** — tracked separately as the dependency-scanning Epic. SBOM generation in this section provides the input artifact for that scanning pipeline; the scanning logic, advisory enrichment, and VEX workflow are deferred.
- **Binary reproducibility** — not in scope until SLSA L4 consideration. SLSA L4 mandates hermetic, reproducible builds from a source snapshot; KOSMOS targets L3 as documented in §10.2, and L4 requirements are not yet stabilized in SLSA v1.0.
- **SBOM signing** — deferred per `research.md §3.8` pending sigstore infrastructure decision (Epic #647). The signing stub in `.github/workflows/sbom.yml` is a forward-reference marker; production signing is out of scope for this spec.

---

## V6 — `auth_type` ↔ `auth_level` consistency

`GovAPITool.auth_type` and `GovAPITool.auth_level` MUST form a pair drawn from the canonical mapping defined by FR-039 and FR-040; any pairing outside that mapping is a misconfiguration that MUST be rejected at the earliest defensible point. This invariant is enforced at two independent layers: (1) a pydantic `@model_validator(mode="after")` on `GovAPITool` (Layer 1, FR-039) and (2) an independent re-check inside `ToolRegistry.register()` (Layer 2, FR-042). For the full FR text and precise error-message contracts, see [`../../specs/025-tool-security-v6/spec.md`](../../specs/025-tool-security-v6/spec.md) and [`../../specs/025-tool-security-v6/contracts/v6-error-contract.md`](../../specs/025-tool-security-v6/contracts/v6-error-contract.md).

### Canonical mapping matrix

The table below is the single source of truth for which `(auth_type, auth_level)` pairs are permitted. Everything not listed is rejected (FR-048 fail-closed). Eight pairs are allowed in total.

| `auth_type` | Allowed `auth_level` values |
|---|---|
| `public` | `public`, `AAL1` |
| `api_key` | `AAL1`, `AAL2`, `AAL3` |
| `oauth` | `AAL1`, `AAL2`, `AAL3` |

Allowed pairs in full: `(public, public)`, `(public, AAL1)`, `(api_key, AAL1)`, `(api_key, AAL2)`, `(api_key, AAL3)`, `(oauth, AAL1)`, `(oauth, AAL2)`, `(oauth, AAL3)`.

**FR-048 fail-closed** — if a new `auth_type` value is introduced without updating the canonical mapping, both layers refuse construction/registration with an "unknown auth_type" error. This forces every `auth_type` extension to be a coordinated PR that updates the mapping in the same change.

### Worked example — MVP meta-tools are an APPROVED combination, not an exception

`resolve_location` and `lookup` are declared with `auth_type="public"`, `auth_level="AAL1"`, and `requires_auth=True`. This combination is compliant under both V5 and V6 with no carve-out, no exemption, and no special-case code:

- **V5 check**: V5 enforces `auth_level == "public"` ⇔ `requires_auth == False`. Here `auth_level` is `"AAL1"` (not `"public"`), so V5 imposes no constraint — `requires_auth=True` is not only permitted but expected. Check passes.
- **V6 check**: `(public, AAL1)` is explicitly in the canonical allow-list. Check passes.

The orchestrator calls these meta-tools directly, not through `PermissionPipeline.dispatch()`. They require an authenticated session for rate-limit accounting and audit continuity, even though the upstream geocoder and BM25 index require no government-API credential. This session-auth requirement is precisely why `requires_auth=True` is set despite `auth_type="public"`. The pattern is fully endorsed by V5+V6.

Any future meta-tool that follows the same `(public, AAL1, requires_auth=True)` shape is automatically compliant; no per-tool exception machinery is involved.

### Rationale — why V6 exists

V5 enforces the biconditional `auth_level == "public"` ⇔ `requires_auth == False`. This closes one gap: a tool cannot claim no authentication is required while being classified at a non-`public` assurance level. However, the legacy `PermissionPipeline.dispatch()` runtime path derives its **access tier** from `auth_type`, not from `requires_auth`. Without V6, a future adapter declaring `auth_type="public"` + `auth_level="AAL2"` + `requires_auth=True` would:

1. Pass V1–V5 cleanly — `auth_level` is `"AAL2"` (not `"public"`), so V5's biconditional fires no violation; V1–V4 check PII class, DPA, irreversibility, and `TOOL_MIN_AAL` drift — none of those address the `auth_type`/`auth_level` cross-field pairing.
2. Be correctly auth-gated by `executor.invoke()`, which reads `requires_auth` and would require a session credential.
3. But be **anonymously callable through `dispatch()`**, which reads `auth_type="public"` as the access tier and concludes that no authentication is needed — bypassing the `requires_auth` gating entirely.

V6 closes this class of misconfiguration at the model layer, regardless of which runtime path dispatches the tool. The deeper `dispatch()` refactor (switching it to read `requires_auth` directly) is deferred to a separate Epic and is NOT covered by V6.

### Two-layer defense architecture

**Layer 1 — pydantic `@model_validator(mode="after")` on `GovAPITool`** (FR-039): checks the `(auth_type, auth_level)` pair against `_AUTH_TYPE_LEVEL_MAPPING` at the earliest point in the object lifecycle. Violations raise `ValueError` (wrapped by pydantic into `ValidationError`) with a message prefixed `V6 violation (FR-039/FR-040): ...` that names both offending fields and lists the allowed levels for the given `auth_type`. See `src/kosmos/tools/models.py`.

**Layer 2 — independent re-check inside `ToolRegistry.register()`** (FR-042): imports `_AUTH_TYPE_LEVEL_MAPPING` from `kosmos.tools.models` and re-runs the same check before accepting a tool into the registry. Violations raise `RegistrationError` with a message prefixed `V6 violation (FR-042): ...` and suffixed `(registry backstop — bypass of pydantic V6 detected)`. A structured log at `ERROR` level is emitted before the raise, mirroring the V3 FR-038 precedent at `src/kosmos/tools/registry.py`.

Layer 2 exists to defend against `GovAPITool.model_construct(...)` (which skips validators) and post-construction `object.__setattr__(tool, "auth_level", ...)` mutations. The two errors are distinguishable by type and message (FR-043), enabling observability tooling and debugging to identify which defense layer triggered.

---

---

## 14. v1.1 → v1.2 Migration Note

This section is normative. It records exactly which v1.1 contracts are preserved verbatim, which are superseded, and what new invariants take effect on v1.2 GA. Ministry reviewers and adapter contributors MUST read this section when upgrading from v1.1.

---

### Preserved verbatim (FR-028)

The following invariants are retained without modification. Their FR references, phrasing, and enforcement points are identical to v1.1. Any adapter that passed validation under v1.1 continues to pass under v1.2 for these invariants.

- **V1** (PIPA §26 / FR-004): `pipa_class != "non_personal"` → `auth_level != "public"`. A tool that processes personal data MUST NOT be declared at the `public` assurance level. Enforced by pydantic `@model_validator(mode="after")` on `GovAPITool`.
- **V2** (FR-014): `pipa_class != "non_personal"` → `dpa_reference is not None`. Every tool with a personal-data scope MUST carry a non-empty DPA reference to close the PIPA §26 위탁 documentation gap. Enforced alongside V1.
- **V3** (FR-001 / FR-005): `auth_level` MUST equal the tool's row in `TOOL_MIN_AAL` **for the 4 residual Spec 022 / Phase-2 entries** (`lookup`, `resolve_location`, `nfa_emergency_info_service`, `mohw_welfare_eligibility_search`). The legacy 8-verb rows (`check_eligibility`, `subscribe_alert`, `reserve_slot`, `issue_certificate`, `submit_application`, `pay`) were removed from `TOOL_MIN_AAL` in T080; V3 still fires for the 4 adapters that remain.
- **V4** (FR-004 extension): `is_irreversible=True` → `auth_level != "public"`. An irreversible action MUST NOT be declared at the `public` assurance level.
- **V5** (FR-004): `auth_level == "public"` ⇔ `requires_auth is False`. The biconditional is enforced symmetrically: a tool that requires no authentication MUST be at `public` level, and a tool at `public` level MUST NOT require authentication.
- **V6** (FR-039 / FR-040 / FR-042 / FR-048): `(auth_type, auth_level)` MUST form a pair drawn from the canonical allow-list `{public ⇒ {public, AAL1}, api_key ⇒ {AAL1, AAL2, AAL3}, oauth ⇒ {AAL1, AAL2, AAL3}}`. Enforced at two independent layers (pydantic `@model_validator` on `GovAPITool` and `ToolRegistry.register()` backstop). Pairs not in the allow-list are rejected at the earliest defensible point (FR-048 fail-closed).

---

### Superseded

The following v1.1 artifacts no longer represent the authoritative contract. They are retained here as a historical record for audit reviewers; no code relies on the superseded forms.

- **Old §2 `TOOL_MIN_AAL` 8-verb table** — the single-axis table covering 8 legacy top-level verbs (`check_eligibility`, `subscribe_alert`, `reserve_slot`, `issue_certificate`, `submit_application`, `pay`, `lookup`, `resolve_location`) is replaced by the dual-axis §2 table in v1.2. The new table covers 15 adapter entries (4 Spec 022 / Phase-2 adapters + 2 submit adapters + 6 verify adapters + 3 subscribe adapters). The 6 retired verbs no longer have live code backing in the five-primitive harness (Spec 031 SC-010); their rows are removed from `TOOL_MIN_AAL` in T080.
- **Single-axis `auth_level` field as the primary gate** — `auth_level` on `GovAPITool` is retained for V3 / V6 compatibility (and continues to fire for the 4 residual adapters above), but it is no longer the primary access-control axis for Spec 031 adapters. The primary axis is now `AdapterRegistration.published_tier_minimum` (18 `PublishedTier` labels). `auth_level` is the secondary axis for those adapters that carry an `AdapterRegistration`.

---

### New invariant (FR-030)

**FR-030 — dual-axis completeness on v1.2 GA**: every `AdapterRegistration` constructed **on or after v1.2 GA** MUST declare BOTH:

1. `published_tier_minimum` — non-null, one of the 18 `PublishedTier` literals defined in `src/kosmos/tools/registry.py::PublishedTier`.
2. `nist_aal_hint` — non-null, one of `"AAL1"` / `"AAL2"` / `"AAL3"`.

Enforcement mechanism: `kosmos.security.v12_dual_axis.enforce()` is wired as a `@model_validator(mode="after")` on `AdapterRegistration`. It raises `DualAxisMissingError` when either field is `None` and `V12_GA_ACTIVE` is `True`.

The toggle `V12_GA_ACTIVE` is flipped from `False` to `True` in T079. Until that flip, the pre-GA migration window allows `None` on either field (FR-028 compatibility window). After the flip, all new registrations must carry both fields.

Adapters registered before T079 (Spec 022 / Phase-2 adapters using the legacy `GovAPITool` path) are exempt from FR-030 until they are migrated to `AdapterRegistration` in T080.

---

### Out of scope for v1.2

The following items are explicitly not addressed in this version:

- **OPAQUE systems** — Government 24 민원 제출 (form submission), KEC XML 서명 (digital signature), and NPKI 포털 세션 핸드셰이크 (portal session handshake) cannot be byte/shape mirrored per the mock-evidence matrix (docs/mock/ criteria, FR-026). These systems are documented in `docs/scenarios/` only and do not appear in the dual-axis adapter table.
- **Subscribe security invariants on `AdapterRegistration`** — deferred. Subscribe is not an active CLI primitive; national alert/RSS delivery belongs to a future app/push runtime with its own registration and security contract.

> **Citation**: Spec 031 FR-028 (V1–V6 preservation); FR-030 (dual-axis completeness); SC-007 (no new runtime deps in security layer); SC-010 (legacy 8-verb surface retired).

---

## Changelog

| Version | Date | Summary |
|---|---|---|
| v1.2 | 2026-04-19 | Five-primitive dual-axis hardening: replaced single-axis `TOOL_MIN_AAL` with `(published_tier_minimum, nist_aal_hint)` dual-axis table over 15 adapters; added §14 migration note; V1–V6 preserved verbatim (FR-028); FR-030 new invariant. |
| v1.1 | 2026-04-17 | Added V6 invariant (Epic #654). No changes to V1–V5. |

---

*End of normative spec. For the unified adapter PR checklist, see `docs/tool-adapters.md § Security PR checklist (spec v1)` (US3).*
