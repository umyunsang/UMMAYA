---
tool_id: mock_traffic_fine_pay_v1
primitive: send
tier: mock
permission_tier: 2
---

# mock_traffic_fine_pay_v1

## Overview

Submits a traffic fine payment request on behalf of a citizen and returns a deterministic receipt confirming the payment channel and reference number.

| Field | Value |
|---|---|
| Classification | Mock · Permission tier 2 |
| Source | 경찰청 교통범칙금 납부 (eFine, https://www.efine.go.kr/) — shape-mirrored from public data.go.kr 교통 범칙금 REST API |
| Primitive | `send` |
| Module | `src/ummaya/tools/mock/data_go_kr/fines_pay.py` |

## Envelope

**Input model**: `FinesPayParams` defined at `src/ummaya/tools/mock/data_go_kr/fines_pay.py:47–67`.

| Field | Type | Required | Description |
|---|---|---|---|
| `fine_reference` | `str` (1–32 chars) | yes | Unique fine identifier — 이의신청번호 or 고지서번호 as printed on the notice |
| `payment_method` | `Literal["virtual_account", "card", "bank_transfer"]` | yes | Payment channel for the fine settlement |

**Output model**: `SubmitOutput` (from `ummaya.primitives.submit`) — `adapter_receipt` block shown below.

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | `str` | yes | Deterministic UMMAYA transaction UUID derived from input params + adapter nonce |
| `status` | `SubmitStatus` (`"succeeded"`) | yes | Final settlement status |
| `adapter_receipt.receipt_ref` | `str` | yes | `MOCK-FP-<sha256[:12]>` — deterministic receipt identifier |
| `adapter_receipt.fine_reference` | `str` | yes | Echo of the submitted fine reference |
| `adapter_receipt.payment_channel` | `str` | yes | Echo of the submitted payment method |
| `adapter_receipt.mock` | `bool` | yes | Always `true` in fixture mode |

## Search hints

- 한국어: `과태료`, `교통범칙금`, `납부`, `벌금`
- English: `traffic fine`, `payment`, `fine settlement`

## Endpoint

- **Mode**: Fixture-replay only
- **Public spec source**: 경찰청 교통범칙금 납부 포털 eFine (https://www.efine.go.kr/) and data.go.kr 교통 범칙금 조회·납부 API (https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15000588). Adapter shape mirrors the REST payment-submission surface documented in the eFine API guide (OOS, source_mode=OOS).
- **Fixture path**: `tests/fixtures/data_go_kr/fines_pay/` (recorded from public spec shape)

## Permission tier rationale

This adapter sits at permission tier 2 (orange ⓶) because it sends an irreversible financial transaction that processes personal payment data (PIPA class `personal_standard`). Spec 033 defines tier 2 as the layer for actions that are consequential and reversible only outside UMMAYA (e.g., via bank dispute). The adapter declares `is_irreversible=True` per the V1 data-model invariant (`primitive=send` ∧ `pipa_class=personal_standard` → `is_irreversible=True`), requires OAuth AAL2 (`ganpyeon_injeung_kakao_aal2`), and enforces `requires_auth=True`. A citizen must confirm the payment in the permission gauntlet modal (`[Y 한번만 / A 세션 자동 / N 거부]`) before the dispatcher forwards the call.

## Worked example

### Input envelope

```json
{
  "mode": "fetch",
  "tool_id": "mock_traffic_fine_pay_v1",
  "params": {
    "fine_reference": "2026-FINE-00123",
    "payment_method": "card"
  }
}
```

### Output envelope (success)

```json
{
  "transaction_id": "01HZXKQ3V2NM8R7FKWD95P4TGE",
  "status": "succeeded",
  "adapter_receipt": {
    "receipt_ref": "MOCK-FP-a1b2c3d4e5f6",
    "fine_reference": "2026-FINE-00123",
    "payment_channel": "card",
    "mock": true
  }
}
```

### Conversation snippet

```text
Citizen: 제 교통범칙금 2026-FINE-00123을 카드로 납부하고 싶어요.
UMMAYA: 교통범칙금 납부가 완료되었습니다. 영수증 번호는 MOCK-FP-a1b2c3d4e5f6이며, 카드 결제로 처리되었습니다.
```

## Constraints

- **Rate limit**: `rate_limit_per_minute: 10` (client-side); N/A for fixture mode (no upstream call).
- **Freshness window**: N/A — fixture returns deterministic mock receipts.
- **Fixture coverage gaps**: Only the `succeeded` status path is covered; `pending` and `failed` statuses (e.g., insufficient funds, expired card) are not represented in fixtures.
- **Error envelope examples**:
  - Tier-1 fail (validation): `{"kind": "error", "reason": "validation", "message": "fine_reference: min_length=1 violated"}` — raised by `FinesPayParams.model_validate` on empty reference.
  - Tier-2 / Tier-3 (auth) fail: `{"kind": "error", "reason": "permission_denied", "message": "AAL2 authentication required for mock_traffic_fine_pay_v1"}` — raised by permission gauntlet when citizen declines or session lacks OAuth token.
  - Network timeout: N/A in fixture mode; in live mode would surface as `{"kind": "error", "reason": "timeout", "message": "upstream eFine API did not respond within 10s"}`.
