# Data Model — Epic ε #2296

**Date**: 2026-04-29
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Research**: [research.md](./research.md)

This document specifies every new or modified data shape introduced by Epic ε. All Pydantic models are v2 frozen (`model_config = ConfigDict(frozen=True)`); the `Any` type is forbidden (Constitution § III). All field names are English; only domain-data values may be Korean.

---

## 1. `DelegationToken` *(NEW · `src/kosmos/primitives/delegation.py`)*

Opaque, scope-bound, time-bound, session-bound credential issued by a verify adapter and consumed by a subsequent submit or lookup adapter. Mirrors the OID4VP-style envelope the AX gateway is expected to issue when the policy mandate ships.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `vp_jwt` | `str` | non-empty, dot-separated JWS-shape (header.payload.signature) | Verifiable Presentation as JWS. In Mock mode, header is `{"alg":"none","typ":"vp+jwt"}`, payload is the issuance claims, signature is `"mock-signature-not-cryptographic"` |
| `delegation_token` | `str` | non-empty, prefix `del_`, 24+ chars after prefix | Opaque token consumed by submit/lookup |
| `scope` | `str` | non-empty, format `<verb>:<adapter_family>.<action>` | e.g., `submit:hometax.tax-return` or `lookup:hometax.simplified` |
| `issuer_did` | `str` | non-empty, DID method form `did:web:<host>` or `did:key:<multibase>` | e.g., `did:web:mobileid.go.kr` |
| `issued_at` | `datetime` | UTC tz-aware | Token mint time |
| `expires_at` | `datetime` | UTC tz-aware, must be > `issued_at` | 24h max in Mock mode |
| `_mode` | `Literal["mock"]` | always `"mock"` for Epic ε | Reserved for `Literal["mock", "live"]` post-Epic-ζ |

**Validators**:
- `@model_validator(mode="after")`: `expires_at > issued_at`; raise `ValueError` otherwise
- `@field_validator("scope")`: must match regex `^(lookup|submit|verify|subscribe):[a-z0-9_]+\.[a-z0-9_-]+$`
- `@field_validator("delegation_token")`: must start with `del_` and have ≥ 24 chars after prefix

**Lifecycle**:
- **Issued**: by a verify mock adapter (e.g., `mock_verify_module_modid`) on successful citizen-side ceremony simulation
- **Used**: by exactly one submit or lookup adapter per call; the token may be presented to multiple adapters within its `scope` and `expires_at` window
- **Revoked**: by `/consent revoke <token>` slash command; revocation appends a `delegation_revoked` ledger event and the token is added to a session-scoped revocation set (in-memory only — Spec 027 mailbox does not persist this set, by design, since the token expires anyway)

**Session binding**: Tokens are bound to the issuing session via the `session_id` (passed through call context, not stored on the token itself). The submit/lookup adapter compares the token's issuance-time `session_id` (looked up in the consent ledger by token value) against the consuming call's `session_id`; mismatch → reject.

---

## 2. `DelegationContext` *(NEW · `src/kosmos/primitives/delegation.py`)*

Wrapper that carries a `DelegationToken` plus the bilingual purpose strings shown in the permission UI to the citizen. Optional citizen DID for audit-anchoring.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `token` | `DelegationToken` | required | The opaque credential |
| `citizen_did` | `str \| None` | optional, DID method form when set | The citizen's DID if the verify ceremony surfaced one (e.g., from `did:web:mobileid.go.kr` issuance) |
| `purpose_ko` | `str` | non-empty, ≤ 200 chars | Korean purpose statement, e.g., `"2024년 귀속 종합소득세 신고"` |
| `purpose_en` | `str` | non-empty, ≤ 200 chars | English purpose statement, e.g., `"Filing 2024 comprehensive income tax return"` |

**Validators**: standard Pydantic v2 string-length validation.

**Construction**: typically built by the verify mock adapter when it returns the token; passed forward through the LLM's tool-call context to the next adapter.

---

## 3. `IdentityAssertion` *(NEW · `src/kosmos/primitives/delegation.py`)*

Returned **instead of** `DelegationContext` by the `mock_verify_module_any_id_sso` adapter. Per `delegation-flow-design.md § 2.2`, Any-ID is identity-SSO only — it does not produce a delegation grant. This shape exists to demonstrate the AX-gateway-spec gap fail-closed.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `assertion_jwt` | `str` | non-empty, JWS-shape | Identity assertion |
| `citizen_did` | `str \| None` | optional, DID method form when set | If Any-ID surfaces a citizen DID |
| `expires_at` | `datetime` | UTC tz-aware | Assertion validity window |
| `_mode` | `Literal["mock"]` | always `"mock"` | |

**Distinction from `DelegationContext`**: no `delegation_token`, no `scope`. A submit/lookup adapter that receives an `IdentityAssertion` (rather than a `DelegationContext`) MUST reject the call with `DelegationGrantMissing`. Fail-closed semantics preserved (Constitution § II).

---

## 4. `AdapterManifestEntry` *(NEW · `src/kosmos/ipc/frame_schema.py`)*

One record inside an `AdapterManifestSyncFrame.entries` array. Used by the TS-side cache to resolve `tool_id` and populate the citation slot in permission prompts.

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `tool_id` | `str` | non-empty, lowercase, snake-case | Globally unique within the registry; e.g., `nmc_emergency_search` |
| `name` | `str` | non-empty, ≤ 80 chars | Human-readable display name; bilingual permitted |
| `primitive` | `Literal["lookup", "submit", "subscribe", "verify", "resolve_location"]` | matches `AdapterPrimitive` enum | Primitive verb the adapter is registered under |
| `policy_authority_url` | `str \| None` | when set: URL form, ≤ 2048 chars | The agency-published policy URL the adapter cites; `None` only for KOSMOS-internal MVP-surface entries (`resolve_location`, `lookup`) which do not call agency APIs |
| `source_mode` | `Literal["live", "mock", "internal"]` | matches `AdapterSourceMode` | Tag for the citation-rendering surface |

**Validators**: `@field_validator("policy_authority_url")` requires HTTPS URL when `source_mode in ("live", "mock")`; `None` only allowed when `source_mode == "internal"`.

---

## 5. `AdapterManifestFrame` *(NEW · `src/kosmos/ipc/frame_schema.py`)*

The full IPC frame the backend emits on boot. Becomes the **21st arm** of the existing `IPCFrame` discriminated union (Spec 032).

| Field | Type | Constraint | Notes |
|---|---|---|---|
| inherited from `_BaseFrame` | — | — | `version`, `role`, `correlation_id`, `timestamp`, `trailer` |
| `kind` | `Literal["adapter_manifest_sync"]` | constant | Discriminator |
| `entries` | `list[AdapterManifestEntry]` | non-empty, no duplicate `tool_id` | The full registry snapshot |
| `manifest_hash` | `str` | 64-char hex (SHA-256) | Cheap change-detection: hash of canonical-JSON-serialised `entries` |
| `emitter_pid` | `int` | positive | The Python backend's PID at boot — useful for cross-correlating manifest version with backend lifetime in OTEL spans |

**Validators**:
- `@model_validator(mode="after")`: `entries` non-empty
- `@model_validator(mode="after")`: no two entries share the same `tool_id`
- `@model_validator(mode="after")`: `manifest_hash` matches `sha256(canonical_json(entries))` — fails closed at frame construction

**Role**: always `"backend"`. Emitted exactly once at successful boot. Future-epic hot-reload triggers (out of scope per spec § Deferred Items) would re-emit with a new `manifest_hash`.

---

## 6. `DelegationLedgerEvent` (union) *(NEW · `src/kosmos/memdir/consent_ledger.py`)*

Three new event kinds appended to the existing Spec 035 consent ledger discriminated union. Same JSONL append-only path: `~/.kosmos/memdir/user/consent/<YYYY-MM-DD>.jsonl`.

### 6.1 `DelegationIssuedEvent`

| Field | Type | Constraint |
|---|---|---|
| `kind` | `Literal["delegation_issued"]` | constant |
| `ts` | `datetime` | UTC tz-aware |
| `session_id` | `str` | non-empty UUID |
| `delegation_token` | `str` | matches `DelegationToken.delegation_token` constraint |
| `scope` | `str` | matches `DelegationToken.scope` constraint |
| `expires_at` | `datetime` | UTC tz-aware |
| `issuer_did` | `str` | matches `DelegationToken.issuer_did` constraint |
| `verify_tool_id` | `str` | the issuing adapter's `tool_id` |
| `_mode` | `Literal["mock"]` | always `"mock"` for Epic ε |

### 6.2 `DelegationUsedEvent`

| Field | Type | Constraint |
|---|---|---|
| `kind` | `Literal["delegation_used"]` | constant |
| `ts` | `datetime` | UTC tz-aware |
| `session_id` | `str` | non-empty UUID |
| `delegation_token` | `str` | references the earlier `DelegationIssuedEvent.delegation_token` |
| `consumer_tool_id` | `str` | the submit/lookup adapter's `tool_id` |
| `receipt_id` | `str \| None` | populated when consumer is a submit adapter and the call succeeded; the synthetic 접수번호 |
| `outcome` | `Literal["success", "scope_violation", "expired", "session_violation", "revoked"]` | the resolution |

### 6.3 `DelegationRevokedEvent`

| Field | Type | Constraint |
|---|---|---|
| `kind` | `Literal["delegation_revoked"]` | constant |
| `ts` | `datetime` | UTC tz-aware |
| `session_id` | `str` | non-empty UUID |
| `delegation_token` | `str` | references the earlier `DelegationIssuedEvent.delegation_token` |
| `reason` | `Literal["citizen_request", "expired", "admin_intervention"]` | the cause |

**Union form**: `DelegationLedgerEvent = Annotated[DelegationIssuedEvent | DelegationUsedEvent | DelegationRevokedEvent, Field(discriminator="kind")]`. Joins the existing `LedgerEvent` discriminated union as three new arms.

---

## 7. Mock Adapter Response Shape (six transparency fields)

Every Mock adapter response payload (returned from `invoke()` or `call()`) MUST contain six top-level fields plus the adapter's domain-specific data. Stamped by the shared helper `kosmos.tools.transparency.stamp_mock_response()` (research.md Decision 7).

| Field | Type | Allowed values |
|---|---|---|
| `_mode` | `Literal["mock"]` | always `"mock"` |
| `_reference_implementation` | `str` | non-empty; the AX-channel reference family this adapter mirrors. Recommended values: `"ax-infrastructure-callable-channel"` (Singapore-APEX-style verify/submit), `"public-mydata-action-extension"` (마이데이터 write extension), `"public-mydata-read-v240930"` (마이데이터 read existing) |
| `_actual_endpoint_when_live` | `str` | URL form; the URL the agency is expected to expose when the policy mandate ships. Format: `https://api.gateway.kosmos.gov.kr/v1/<verb>/<adapter_id>` for AX-gateway placeholder URLs; agency-specific URLs allowed when known |
| `_security_wrapping_pattern` | `str` | the security stack the channel is expected to use, e.g., `"OAuth2.1 + mTLS + scope-bound bearer"` or `"OID4VP + DID-resolved RP"` or `"마이데이터 표준동의서 OAuth2 + finAuth"` |
| `_policy_authority` | `str` | URL form; the agency-published policy URL. Examples: `"https://www.mois.go.kr/frt/bbs/.../public-mydata.do"`, `"https://www.kdca.go.kr/.../digital-id.html"` |
| `_international_reference` | `str` | non-empty; the closest international-analog system, e.g., `"Singapore APEX"`, `"Estonia X-Road"`, `"EU EUDI Wallet"`, `"Japan マイナポータル API"`, `"UK HMRC Making Tax Digital"` |
| `_mock_fidelity_grade` | `str \| None` | optional evidence-grade extension for institution-gated channels |
| `_mock_evidence` | `dict[str, object] \| None` | optional evidence object with source URLs, inference boundary, and live-swap requirements |

**Stamping point**: the Mock adapter's response builder calls `stamp_mock_response(domain_payload, reference_implementation=..., actual_endpoint_when_live=..., security_wrapping_pattern=..., policy_authority=..., international_reference=...)` to produce the final dict. The five non-mode values are typically per-adapter constants declared at module top-level (e.g., `_REFERENCE_IMPL = "ax-infrastructure-callable-channel"`).

**Evidence-grade rule**: For privileged domains where the channel exists but KOSMOS has no official credential, the adapter should pass `mock_fidelity_grade` and `mock_evidence` to the shared stamper. The evidence object MUST distinguish official facts from inferred private payload details and list the approvals or credentials needed for Live promotion.

**Retrofit applies to all 20 Mock adapters**: 5 existing verify (after `digital_onepass` deletion) + 5 new verify + 2 existing submit + 3 new submit + 3 existing subscribe + 2 new lookup.

---

## 8. Modifications to Existing Per-Primitive Context Types

The five existing verify mocks (after `digital_onepass` deletion) return per-family Pydantic context types (e.g., `MobileIdContext`, `KECInjeungseoContext`). These types currently lack the six transparency fields.

**Modification**: Each context type gains six optional fields with `Field(default=None)`. The Mock adapter implementations populate them via the `stamp_mock_response` helper at response construction time. Live adapters (when they ship in a future epic) leave them `None` — the contract is "Mock adapters MUST populate, Live adapters MUST NOT".

**Affected types** (all in `src/kosmos/primitives/verify.py`):
- `MobileIdContext` (used by `mock_verify_mobile_id`)
- `KECInjeungseoContext` (used by `mock_verify_gongdong_injeungseo`)
- `GeumyungInjeungseoContext` (used by `mock_verify_geumyung_injeungseo`)
- `GanpyeonInjeungContext` (used by `mock_verify_ganpyeon_injeung`)
- `MydataContext` (used by `mock_verify_mydata`)

Same retrofit applies to the existing submit context type(s) in `src/kosmos/primitives/submit.py` (used by `mock_traffic_fine_pay_v1`, `mock_welfare_application_submit_v1`) and the existing subscribe context type(s) in `src/kosmos/primitives/subscribe.py`.

**Why optional + default `None`**: Live and Mock adapters share the context types; making the fields required would break Live adapter construction. The regression test (FR-006) iterates only Mock adapter responses and asserts `value is not None and value != ""` for each of the six fields.

---

## 9. State Transitions

### 9.1 `DelegationToken` lifecycle

```
[absent] ──verify(modid|simple_auth|kec|geumyung)──► [issued]
[issued] ──submit/lookup with matching scope, before expiry──► [issued, used]
[issued] ──expires_at reached──► [expired]
[issued] ──/consent revoke <token>──► [revoked]
[issued, used] ──submit/lookup with matching scope, before expiry──► [issued, used] (idempotent within scope+window)
[expired | revoked] ──submit/lookup attempt──► REJECTED + audit ledger entry
```

**Token state is NOT stored** server-side as a model — it is reconstructed from the audit ledger (last `delegation_*` event for the token wins). The session-scoped in-memory revocation set is a performance optimisation, not the source of truth.

### 9.2 `AdapterManifestSyncFrame` lifecycle

```
[backend boot success] ──emit once──► [TUI cache populated]
[TUI cache populated] ──validateInput call──► [resolution attempts: cache → internal-tools fallback]
[backend hot-reload (future epic)] ──re-emit with new manifest_hash──► [TUI cache replaced]
[TUI restart] ──cache discarded──► [empty cache → cold-boot race window until next emit]
```

**Cold-boot race**: while the cache is empty (between TUI restart and the first `AdapterManifestSyncFrame` arriving), `validateInput` MUST fail closed with `ManifestNotYetSynced` (FR-019). Empty cache MUST NOT be silently treated as authoritative.

### 9.3 Audit ledger event ordering

For one citizen US1 chain (verify → lookup → submit), the ledger appends three events in order:

```
1. {kind:"delegation_issued",   ts:T0,    delegation_token:tok, scope:"submit:hometax.tax-return", verify_tool_id:"mock_verify_module_modid"}
2. {kind:"delegation_used",     ts:T0+5s, delegation_token:tok, consumer_tool_id:"mock_lookup_module_hometax_simplified", outcome:"success"}
3. {kind:"delegation_used",     ts:T0+12s,delegation_token:tok, consumer_tool_id:"mock_submit_module_hometax_taxreturn",  receipt_id:"hometax-2026-04-30-XXXX", outcome:"success"}
```

The scope-violation acceptance scenario (US1 acceptance scenario #3) appends a fourth event:

```
4. {kind:"delegation_used",     ts:T0+18s,delegation_token:tok, consumer_tool_id:"mock_submit_module_gov24_minwon", outcome:"scope_violation"}
```

---

## 10. Cross-Reference Summary

| Entity | File (after Epic ε) | First introduced by | Validators |
|---|---|---|---|
| `DelegationToken` | `src/kosmos/primitives/delegation.py` | this Epic (NEW) | `expires_at > issued_at`; scope regex; token prefix |
| `DelegationContext` | `src/kosmos/primitives/delegation.py` | this Epic (NEW) | string-length |
| `IdentityAssertion` | `src/kosmos/primitives/delegation.py` | this Epic (NEW) | `expires_at` UTC; JWS-shape |
| `AdapterManifestEntry` | `src/kosmos/ipc/frame_schema.py` | this Epic (NEW) | URL form when source_mode != internal |
| `AdapterManifestFrame` | `src/kosmos/ipc/frame_schema.py` | this Epic (NEW) | non-empty entries; no duplicate tool_id; SHA-256 hash matches |
| `DelegationIssuedEvent` | `src/kosmos/memdir/consent_ledger.py` | this Epic (NEW) | matches `DelegationToken` constraints on referenced fields |
| `DelegationUsedEvent` | `src/kosmos/memdir/consent_ledger.py` | this Epic (NEW) | outcome enum |
| `DelegationRevokedEvent` | `src/kosmos/memdir/consent_ledger.py` | this Epic (NEW) | reason enum |
| `MobileIdContext` and 4 siblings | `src/kosmos/primitives/verify.py` | Spec 031 (MODIFY) | retain existing + add six optional transparency fields |
