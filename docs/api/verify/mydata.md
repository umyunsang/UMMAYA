---
tool_id: mock_verify_mydata
primitive: check
tier: mock
permission_tier: 2
---

# mock_verify_mydata

## Overview

Verifies a citizen's 마이데이터 (MyData) OAuth 2.0 + mTLS session with a licensed MyData operator and returns a typed `MyDataContext` envelope identifying the provider and assurance tier.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 마이데이터 표준 API 규격서 v240930 (금융위원회 / KFTC MyData, OOS shape-mirror) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_mydata.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["mydata"]` | yes | Must be `"mydata"`; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence. Pass `{"_fixture_override": {"provider_id": "MY_OP_999"}}` in tests to exercise alternate provider IDs. |

**Output model**: `MyDataContext` defined at `src/ummaya/primitives/verify.py:202–215`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["mydata"]` | yes | Discriminator field; always `"mydata"`. |
| `published_tier` | `str` | yes | Currently constrained to `mydata_individual_aal2`. |
| `nist_aal_hint` | `str` | yes | Always `"AAL2"` for the individual tier. |
| `verified_at` | `datetime` | yes | UTC timestamp when the external MyData OAuth session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the MyData operator. |
| `provider_id` | `str` | yes | 마이데이터 사업자 코드 (min length 1). In the default fixture this is the anonymised test code `"TEST_PROVIDER_001"`. |

## Search hints

- 한국어: `마이데이터`, `금융데이터`, `금결원`, `KFTC`, `개인신용정보`, `복지`, `복지신청`, `복지급여신청`, `사회보장`, `한부모가족`, `한부모`, `아동양육비`
- English: `mydata`, `open banking`, `KFTC mydata`, `personal credit data`, `welfare`, `welfare application`, `benefit application`, `social assistance`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 마이데이터 표준 API 규격서 v240930 (금융위원회 마이데이터 가이드, https://www.mydatacenter.or.kr/); shape-mirrored from KFTC MyData open-source schema. Additional legal basis: 신용정보의 이용 및 보호에 관한 법률 §33의2.
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `MyDataContext(provider_id="TEST_PROVIDER_001", published_tier="mydata_individual_aal2", nist_aal_hint="AAL2", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-mydata-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL2"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL2 maps to **permission tier 2** (orange ⓶ in UI-C). 마이데이터 provides access to aggregated personal credit and financial data across multiple institutions, classified as `pipa_class="personal_sensitive"` — the strictest PIPA sensitivity class present in any of the six verify adapters. The `dpa_reference` includes both PIPA §26 (수탁자 처리) and 신용정보법 §33의2, reflecting dual statutory obligations. The permission gauntlet must surface the orange ⓶ consent modal and record a consent receipt in the audit ledger before the first call. Because the data is sensitive, citizens should be informed via the consent prompt that MyData access aggregates records from multiple financial institutions.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_mydata",
  "params": {
    "family_hint": "mydata",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_mydata",
  "result": {
    "family": "mydata",
    "published_tier": "mydata_individual_aal2",
    "nist_aal_hint": "AAL2",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-mydata-ref-001",
    "provider_id": "TEST_PROVIDER_001"
  }
}
```

### Conversation snippet

```text
시민: 마이데이터 인증해줘.
UMMAYA: 마이데이터 (사업자: TEST_PROVIDER_001, AAL2) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-mydata-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). `rate_limit_per_minute=10` is a soft advisory for live deployments.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp; live MyData tokens have a 3-month validity window defined in the 마이데이터 표준 API 규격서.
- **Network egress**: 0. No external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: Only the `mydata_individual_aal2` tier is present in the fixture. No business/corporate MyData tier exists in the current published-tier set. The `provider_id` field is anonymised (`"TEST_PROVIDER_001"`); real operator codes are registered with 금융위원회 and must not be hard-coded in tests.
- **Error envelope examples**:
  - Tier-2/3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 2, "message": "Consent required for is_personal_data adapter. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "mydata", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'mydata'."}
    ```
  - Malformed input (empty provider_id in override):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "provider_id: String should have at least 1 character"}}
    ```
