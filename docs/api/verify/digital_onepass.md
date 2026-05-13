---
tool_id: mock_verify_digital_onepass
primitive: check
tier: mock
permission_tier: 2
---

# mock_verify_digital_onepass

## Overview

Verifies a citizen's Digital Onepass (디지털원패스) identity session at Level 1, 2, or 3 and returns a typed `DigitalOnepassContext` envelope with the observed NIST AAL tier.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 행정안전부 디지털원패스 (OmniOne OpenDID shape-mirror, OOS) |
| Primitive | `check` |
| Module | `src/ummaya/tools/mock/verify_digital_onepass.py` |

## Envelope

**Input model**: `VerifyInput` defined at `src/ummaya/primitives/verify.py:44–51`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family_hint` | `Literal["digital_onepass"]` | yes | Must be `"digital_onepass"` for this adapter; dispatcher rejects any other value (FR-010). |
| `session_context` | `dict[str, object]` | no | Opaque external evidence passed to the adapter. Pass `{"_fixture_override": {...}}` in tests to override fixture fields. |

**Output model**: `DigitalOnepassContext` defined at `src/ummaya/primitives/verify.py:170–183`.

| Field | Type | Required | Description |
|---|---|---|---|
| `family` | `Literal["digital_onepass"]` | yes | Discriminator field; always `"digital_onepass"`. |
| `published_tier` | `str` | yes | One of `digital_onepass_level1_aal1`, `digital_onepass_level2_aal2`, `digital_onepass_level3_aal3`. |
| `nist_aal_hint` | `str` | yes | NIST AAL shorthand matching the published tier (`"AAL1"`, `"AAL2"`, or `"AAL3"`). |
| `verified_at` | `datetime` | yes | UTC timestamp when the external session was established. |
| `external_session_ref` | `str \| None` | no | Opaque reference returned by the identity provider. |
| `level` | `Literal[1, 2, 3]` | yes | Numeric Digital Onepass assurance level. |

## Search hints

- 한국어: `디지털원패스`, `Digital Onepass`, `행정안전부`, `공공서비스 인증`
- English: `digital onepass`, `MOIS public auth`, `digital_onepass`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 행정안전부 디지털원패스 (https://www.onepass.go.kr/); shape-mirrored from the OmniOne OpenDID reference stack (Apache-2.0, https://github.com/OmniOneID/did-doc-architecture).
- **Fixture path**: Fixture data is hard-coded as constants inside the adapter module itself per the unit-test convention. Default fixture is `DigitalOnepassContext(level=2, published_tier="digital_onepass_level2_aal2", nist_aal_hint="AAL2", verified_at=2026-04-19T09:00:00Z, external_session_ref="mock-onepass-ref-001")`.

## Permission tier rationale

This adapter carries `auth_level="AAL2"` and `is_irreversible=False`. Per `src/ummaya/tools/permissions.py` `compute_permission_tier()` (Spec 033 FR-011), AAL2 maps to **permission tier 2** (orange ⓶ in UI-C). Identity-binding at AAL2 presents personally identifiable data (`is_personal_data=True`, `pipa_class="personal_standard"`), which means the TUI permission gauntlet must surface an explicit citizen consent prompt and record an audit receipt before the adapter executes. A tier-2 session consent is sufficient for repeated calls within the same session without re-prompting, unless the citizen revokes consent via `/consent revoke`.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_verify_digital_onepass",
  "params": {
    "family_hint": "digital_onepass",
    "session_context": {}
  }
}
```

### Output envelope (success)

```json
{
  "tool_id": "mock_verify_digital_onepass",
  "result": {
    "family": "digital_onepass",
    "published_tier": "digital_onepass_level2_aal2",
    "nist_aal_hint": "AAL2",
    "verified_at": "2026-04-19T09:00:00+00:00",
    "external_session_ref": "mock-onepass-ref-001",
    "level": 2
  }
}
```

### Conversation snippet

```text
시민: 디지털원패스로 본인인증 해줘.
UMMAYA: 디지털원패스 Level 2 (AAL2) 인증이 확인되었습니다. 인증 시각: 2026-04-19 09:00 UTC, 세션 참조: mock-onepass-ref-001.
```

## Constraints

- **Rate limit**: N/A (fixture). Live Digital Onepass sessions are subject to 행정안전부 policy; the mock adapter enforces `rate_limit_per_minute=10` as a soft advisory only.
- **Freshness window**: N/A. Fixture `verified_at` is a static recorded timestamp; it does not update at runtime.
- **Network egress**: 0. This is a fixture-replay adapter; no external HTTP connections are made under any circumstances.
- **Fixture coverage gaps**: Level 1 (AAL1) and Level 3 (AAL3) variants are not included in the default fixture. Pass `{"_fixture_override": {"level": 3, "published_tier": "digital_onepass_level3_aal3", "nist_aal_hint": "AAL3"}}` in `session_context` to exercise higher-assurance paths in tests.
- **Error envelope examples**:
  - Tier-2/3 unauthenticated (consent not granted):
    ```json
    {"error": {"code": "PERMISSION_DENIED", "tier": 2, "message": "Consent required for is_personal_data adapter. Run /consent to grant permission."}}
    ```
  - Fixture not found / adapter missing:
    ```json
    {"family": "mismatch_error", "reason": "family_mismatch", "expected_family": "digital_onepass", "observed_family": "<no_adapter>", "message": "No verify adapter registered for family 'digital_onepass'."}
    ```
  - Malformed input (wrong family_hint):
    ```json
    {"error": {"code": "VALIDATION_ERROR", "message": "family_hint: Input should be 'digital_onepass'"}}
    ```
