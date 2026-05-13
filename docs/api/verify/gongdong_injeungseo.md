---
tool_id: mock_verify_gongdong_injeungseo
primitive: check
tier: mock
permission_tier: 3
---

# mock_verify_gongdong_injeungseo

## Overview

Verifies a citizen's 공동인증서 (Joint Certificate, formerly 공인인증서) session issued by a licensed Korean Certificate Authority and returns a typed `GongdongInjeungseoContext` envelope including the issuing CA name.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 3 |
| Source | 한국정보인증/공동인증서 — KFTC/NPKI API docs (OOS shape-mirror via PyPinkSign) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_gongdong_injeungseo.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["gongdong_injeungseo"]` | yes | Must be `"gongdong_injeungseo"`; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence. Pass `{"_fixture_override": {"certificate_issuer": "TradeSign"}}` in tests to vary the issuing CA. |

**Output model**: `GongdongInjeungseoContext` defined at `src/ummaya/primitives/verify.py:119–135`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["gongdong_injeungseo"]` | yes | Discriminator field; always `"gongdong_injeungseo"`. |
| `published_tier` | `str` | yes | One of `gongdong_injeungseo_personal_aal3`, `gongdong_injeungseo_corporate_aal3`, `gongdong_injeungseo_bank_only_aal2`. |
| `nist_aal_hint` | `str` | yes | NIST AAL shorthand (`"AAL2"` for bank-only tier; `"AAL3"` for personal and corporate). |
| `verified_at` | `datetime` | yes | UTC timestamp when the external certificate session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the CA/NPKI infrastructure. |
| `certificate_issuer` | `str` | yes | Issuing CA name, e.g. `"KICA"`, `"KFTC"`, `"TradeSign"`, `"CrossCert"`. |

## Search hints

- 한국어: `공동인증서`, `공인인증서`, `KICA`, `KOSCOM`
- English: `joint certificate`, `NPKI`, `gongdong injeungseo`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 한국정보인증/공동인증서 (KISA NPKI specification); shape-mirrored from PyPinkSign open-source library (MIT, https://github.com/bandoche/PyPinkSign) and KFTC API documentation. Canonical authority: https://www.rootca.or.kr/ (금융결제원 공동인증 정책).
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `GongdongInjeungseoContext(certificate_issuer="KICA", published_tier="gongdong_injeungseo_personal_aal3", nist_aal_hint="AAL3", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-gongdong-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL3"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL3 maps to **permission tier 3** (red ⓷ in UI-C). 공동인증서 involves a unique personal identifier bound to a hardware token or encrypted certificate file (`pipa_class="personal_unique_id"`). AAL3 represents the highest assurance level in the Korean public-sector PKI (NPKI), covering cryptographic proof of possession. The TUI permission gauntlet must display the red ⓷ modal with explicit `[Y 한번만 / A 세션 자동 / N 거부]` prompts and record a consent receipt in the audit ledger before any invocation. Session-auto grants are still subject to Spec 033 AAL downgrade blocking.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_gongdong_injeungseo",
  "params": {
    "family_hint": "gongdong_injeungseo",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_gongdong_injeungseo",
  "result": {
    "family": "gongdong_injeungseo",
    "published_tier": "gongdong_injeungseo_personal_aal3",
    "nist_aal_hint": "AAL3",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-gongdong-ref-001",
    "certificate_issuer": "KICA"
  }
}
```

### Conversation snippet

```text
시민: 공동인증서로 본인인증 해줘.
UMMAYA: 공동인증서 (발급기관: KICA, AAL3) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-gongdong-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). `rate_limit_per_minute=10` is a soft advisory for live deployments.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp.
- **Network egress**: 0. No external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: Corporate tier (`gongdong_injeungseo_corporate_aal3`) and bank-only AAL2 tier (`gongdong_injeungseo_bank_only_aal2`) are not included in the default fixture. Pass `{"_fixture_override": {"published_tier": "gongdong_injeungseo_corporate_aal3", "certificate_issuer": "TradeSign"}}` in `session_context` to exercise those variants. Note that the bank-only tier changes `nist_aal_hint` to `"AAL2"` and therefore resolves to permission tier 2.
- **Error envelope examples**:
  - Tier-3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 3, "message": "Consent required for is_personal_data adapter at tier 3. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "gongdong_injeungseo", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'gongdong_injeungseo'."}
    ```
  - Malformed input (wrong family_hint):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "family_hint: Input should be 'gongdong_injeungseo'"}}
    ```
