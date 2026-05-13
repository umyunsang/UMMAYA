---
tool_id: mock_welfare_application_submit_v1
primitive: send
tier: mock
permission_tier: 2
---

# mock_welfare_application_submit_v1

## Overview

Submits a welfare benefit application on behalf of a citizen and returns a deterministic application receipt confirming the benefit code, application type, and household record.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 보건복지부 마이데이터 복지 서비스 신청 API (KFTC MyData v240930 / 마이데이터 기본 API) — shape-mirrored (OOS) from the MyData standard welfare-application surface |
| Primitive | `send` |
| Module | `src/ummaya/tools/mock/mydata/welfare_application.py` |

## Envelope

**Input model**: `WelfareApplicationParams` defined at `src/ummaya/tools/mock/mydata/welfare_application.py:45–72`.

| Field | Type | Required | Description |
|---|---|---|---|
| `applicant_id` | `str` (1–64 chars) | yes | MyData-scoped pseudonymous applicant identifier (DI code) |
| `benefit_code` | `str` (1–32 chars) | yes | Welfare benefit type code, e.g. `기초생활수급`, `장애인지원` |
| `application_type` | `Literal["new", "renewal", "modification"]` | yes | Whether this is a new application, a renewal, or a modification of an existing application |
| `household_size` | `int` (1–50) | yes | Number of household members |

**Output model**: `SubmitOutput` (from `ummaya.primitives.submit`) — `adapter_receipt` block shown below.

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | `str` | yes | Deterministic UMMAYA transaction UUID derived from input params + adapter nonce |
| `status` | `SubmitStatus` (`"succeeded"`) | yes | Final application status |
| `adapter_receipt.application_ref` | `str` | yes | `MOCK-WA-<sha256[:12]>` — deterministic application receipt number |
| `adapter_receipt.benefit_code` | `str` | yes | Echo of the submitted benefit code |
| `adapter_receipt.application_type` | `str` | yes | Echo of the submitted application type |
| `adapter_receipt.household_size` | `int` | yes | Echo of the submitted household size |
| `adapter_receipt.mock` | `bool` | yes | Always `true` in fixture mode |

## Search hints

- 한국어: `복지`, `급여신청`, `마이데이터`, `기초생활`, `장애인`
- English: `welfare`, `benefit application`, `mydata`, `social assistance`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 보건복지부 마이데이터 복지 서비스 API — KFTC MyData 기본 API 명세서 v240930 (https://www.mydatacenter.or.kr/) and 정부24 복지급여 신청 흐름 (https://www.gov.kr/portal/service/serviceList/01). Adapter shape mirrors the standard welfare-application submission surface documented in the MyData welfare guide (OOS, source_mode=OOS).
- **Fixture path**: `tests/fixtures/mydata/welfare_application/` (recorded from public spec shape)

## Permission tier rationale

This adapter sits at permission tier 2 (orange ⓶) because it sends an application that creates an official government welfare record and processes sensitive personal data including household composition and applicant identity (PIPA class `personal_standard`). Spec 033 defines tier 2 for consequential, authenticated actions where the side effect persists in a government registry but is reversible through official withdrawal procedures outside UMMAYA. The adapter declares `is_irreversible=True` per the V1 invariant (`primitive=send` ∧ `pipa_class=personal_standard` → `is_irreversible=True`), requires OAuth AAL2 (`mydata_individual_aal2`), and enforces `requires_auth=True`. Citizens are prompted in the permission gauntlet before the dispatcher forwards the call.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_welfare_application_submit_v1",
  "params": {
    "applicant_id": "DI-AB12CD34EF56GH78",
    "benefit_code": "기초생활수급",
    "application_type": "new",
    "household_size": 3
  }
}
```

### Output envelope (success)

```json
{
  "transaction_id": "01HZXKQ4P5NR9S8QLME67T3UAF",
  "status": "succeeded",
  "adapter_receipt": {
    "application_ref": "MOCK-WA-7d3f9c1e2a4b",
    "benefit_code": "기초생활수급",
    "application_type": "new",
    "household_size": 3,
    "mock": true
  }
}
```

### Conversation snippet

```text
Citizen: 기초생활수급 신규 신청을 하고 싶어요. 가구원 수는 3명이에요.
UMMAYA: 기초생활수급 신규 신청이 완료되었습니다. 접수 번호는 MOCK-WA-7d3f9c1e2a4b이며, 담당 기관에서 추가 안내 연락을 드릴 예정입니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute: 5` (client-side); N/A for fixture mode (no upstream call).
- **Freshness window**: N/A — fixture returns deterministic mock receipts.
- **Fixture coverage gaps**: Only the `succeeded` status path is covered; rejection paths (e.g., duplicate application, missing documentation) and `modification` type scenarios are not represented in fixtures.
- **Error envelope examples**:
  - Tier-1 fail (validation): `{"kind": "error", "reason": "validation", "message": "household_size: ge=1 violated"}` — raised by `WelfareApplicationParams.model_validate` on zero or negative household size.
  - Tier-2 / Tier-3 (auth) fail: `{"kind": "error", "reason": "permission_denied", "message": "AAL2 MyData authentication required for mock_welfare_application_submit_v1"}` — raised when the citizen lacks a valid MyData OAuth2 token at the required assurance level.
  - Network timeout: N/A in fixture mode; in live mode would surface as `{"kind": "error", "reason": "timeout", "message": "MyData welfare API did not respond within 10s"}`.
