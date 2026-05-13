---
tool_id: mock_verify_geumyung_injeungseo
primitive: check
tier: mock
permission_tier: 2
---

# mock_verify_geumyung_injeungseo

## Overview

Verifies a citizen's 금융인증서 (Financial Certificate, KFTC) session stored in the KFTC cloud and returns a typed `GeumyungInjeungseoContext` envelope identifying the bank cluster.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 금융결제원 금융인증서 API specification (OOS shape-mirror) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_geumyung_injeungseo.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["geumyung_injeungseo"]` | yes | Must be `"geumyung_injeungseo"`; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence. Pass `{"_fixture_override": {"published_tier": "geumyung_injeungseo_business_aal3", "nist_aal_hint": "AAL3"}}` in tests to exercise the business AAL3 variant. |

**Output model**: `GeumyungInjeungseoContext` defined at `src/ummaya/primitives/verify.py:138–151`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["geumyung_injeungseo"]` | yes | Discriminator field; always `"geumyung_injeungseo"`. |
| `published_tier` | `str` | yes | One of `geumyung_injeungseo_personal_aal2`, `geumyung_injeungseo_business_aal3`. |
| `nist_aal_hint` | `str` | yes | NIST AAL shorthand (`"AAL2"` for personal; `"AAL3"` for business). |
| `verified_at` | `datetime` | yes | UTC timestamp when the external KFTC cloud session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the KFTC cloud infrastructure. |
| `bank_cluster` | `Literal["kftc"]` | yes | 금융결제원 cloud cluster identifier; currently fixed to `"kftc"`. |

## Search hints

- 한국어: `금융인증서`, `금결원`, `KFTC`, `은행인증`
- English: `financial certificate`, `KFTC`, `geumyung injeungseo`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 금융결제원 금융인증서 (https://www.yessign.or.kr/); shape-mirrored from KFTC 금융인증서 API specification document.
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `GeumyungInjeungseoContext(bank_cluster="kftc", published_tier="geumyung_injeungseo_personal_aal2", nist_aal_hint="AAL2", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-geumyung-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL2"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL2 maps to **permission tier 2** (orange ⓶ in UI-C). The 금융인증서 ties a citizen's financial identity to their bank account and exposes a unique personal identifier (`pipa_class="personal_unique_id"`), making the consent gate mandatory. The permission gauntlet records a consent receipt in the audit ledger before execution; session-auto (`A`) grant is permitted within a single session. Note that the `geumyung_injeungseo_business_aal3` published tier, if returned via `_fixture_override`, would logically correspond to permission tier 3, but the adapter registration declares `auth_level="AAL2"` (the default personal tier) — keep overriding tests aware of this distinction.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_geumyung_injeungseo",
  "params": {
    "family_hint": "geumyung_injeungseo",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_geumyung_injeungseo",
  "result": {
    "family": "geumyung_injeungseo",
    "published_tier": "geumyung_injeungseo_personal_aal2",
    "nist_aal_hint": "AAL2",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-geumyung-ref-001",
    "bank_cluster": "kftc"
  }
}
```

### Conversation snippet

```text
시민: 금융인증서로 본인인증 해줘.
UMMAYA: 금융인증서 (금결원 클러스터: kftc, AAL2) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-geumyung-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). `rate_limit_per_minute=10` is a soft advisory for live deployments.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp.
- **Network egress**: 0. No external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: The business AAL3 tier (`geumyung_injeungseo_business_aal3`) is not included in the default fixture. Use `_fixture_override` in tests to exercise that path. The `bank_cluster` field is currently constrained to `Literal["kftc"]`; future multi-cluster support would require a spec change.
- **Error envelope examples**:
  - Tier-2/3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 2, "message": "Consent required for is_personal_data adapter. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "geumyung_injeungseo", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'geumyung_injeungseo'."}
    ```
  - Malformed input (wrong family_hint):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "family_hint: Input should be 'geumyung_injeungseo'"}}
    ```
