# Contract — Transaction Dedup & Backpressure Signaling

**Spec**: 032-ipc-stdio-hardening
**Scope**: FR-011..017 (backpressure) + FR-026..033 (tx dedup) · US2 (P1, 부처 429 가시화) · US3 (P1, 민원 중복 제출 차단)
**Related entities**: `BackpressureSignalFrame`, `TransactionLRU`, `SessionRingBuffer`
**References**: Node.js Streams `highWaterMark` · Stripe idempotency 3-step · Claude Agent SDK stdio strictness · PIPA §35 (정정·삭제 청구)

---

## 1. Backpressure signaling contract (FR-011..017)

### 1.1 Threshold triangle

```
              hwm = 64       (pause threshold)
              ───────
              depth
              ───────
              hwm/2 = 32     (resume threshold)
```

- Queue at depth ≥ 64 → writer emits `backpressure {signal: "pause"}`.
- Queue at depth ≤ 32 → writer emits `backpressure {signal: "resume"}`.
- No-op when depth in (32, 64) — hysteresis prevents flap.

### 1.2 Sources (normative enum)

| `source`           | Meaning                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| `tui_reader`       | TUI cannot render fast enough; backend should pause.                    |
| `backend_writer`   | Backend ring buffer or outbound pipe congested; TUI should slow input.  |
| `upstream_429`     | External 부처 API returned 429/Retry-After; tool execution is throttled. |

### 1.3 `upstream_429` specifics

When an adapter catches a 429 from `data.go.kr` or a ministry API:

1. Extract `Retry-After` (seconds or HTTP-date); clamp to `[1, 900]`.
2. Emit:
   ```
   BackpressureSignalFrame {
     signal: "throttle",
     source: "upstream_429",
     queue_depth: <current>,
     hwm: 64,
     retry_after_ms: <parsed * 1000>,
     hud_copy_ko: "부처 API가 혼잡합니다. {retry_after}초 후 자동 재시도합니다.",
     hud_copy_en: "Ministry API rate-limited. Retrying in {retry_after}s."
   }
   ```
3. TUI renders the Korean copy as a non-blocking HUD banner with a live countdown.
4. No `pause` signal is emitted for `upstream_429` — only `throttle`. The IPC channel itself remains open.

### 1.4 Pause/resume pairing invariant

Every emitted `pause` MUST be matched by a later `resume` within the same session. On session teardown with an outstanding `pause`, backend emits a final `resume` before terminal `error` / `resume_rejected`.

### 1.5 HUD copy discipline (FR-015, Principle I)

- Korean copy is civic-facing; must be grade-appropriate (시민 독자).
- English copy is developer-facing (OTEL logs, devtools).
- Both MUST be present — dual-locale is a hard invariant.
- Placeholder interpolation: `{retry_after}`, `{queue_depth}`; no arbitrary format strings.

---

## 2. Transaction dedup contract (FR-026..033)

### 2.1 When `transaction_id` is required

The backend assigns a `transaction_id` (UUIDv7) to the envelope exactly when BOTH of these hold:

1. The frame kind is one of: `tool_call`, `permission_response`, or `payload_end` of a tool streaming response.
2. The target tool's `AdapterRegistration.is_irreversible == true` (Spec 024 metadata).

For every other frame the envelope has `transaction_id: null`.

### 2.2 Dedup lookup flow (Stripe 3-step)

```
(1) Request arrives at ToolExecutor with (session_id, transaction_id, tool_id, params)
    ├─ if tool.is_irreversible == false:
    │    └─ execute normally, no cache interaction
    └─ if tool.is_irreversible == true:
         ├─ hit = TransactionLRU.get((session_id, transaction_id))
         ├─ if hit != None:
         │    ├─ span attribute: ummaya.ipc.tx.cache_state = "hit"
         │    ├─ return hit.cached_response immediately
         │    └─ audit: ToolCallAuditRecord(status="dedup_hit", ...)
         └─ if hit == None:
              ├─ span attribute: ummaya.ipc.tx.cache_state = "miss"
              ├─ execute tool
              ├─ TransactionLRU.record(TxEntry(
              │    session_id, transaction_id, tool_id,
              │    is_irreversible=True, first_seen_ts=now,
              │    cached_response=response, correlation_id
              │  ))
              ├─ pin (auto)
              └─ audit: ToolCallAuditRecord(status="ok" | "error", ...)
```

### 2.3 Cache sizing & eviction

- Capacity: 512 entries (`UMMAYA_IPC_TX_CACHE_CAPACITY`, `ge=1`).
- Structure: `collections.OrderedDict`; insertion order = eviction order (FIFO).
- Pinned entries (`is_irreversible=true`) NEVER evicted regardless of LRU pressure.
- Non-pinned overflow → oldest non-pinned evicted first.
- Implication: in the worst case, all 512 slots are pinned irreversible civic submissions → eviction stops; operator must rotate sessions to reclaim (deferred feature in spec).

### 2.4 Key composition

Key = `(session_id: str, transaction_id: str)`.

- `session_id` scopes dedup to the originating conversation.
- `transaction_id` is globally unique (UUIDv7) but scoping by session prevents cross-user replay of valid-looking IDs.
- Constitution Principle II (Fail-Closed): empty strings on either element → raise `ValueError`, never accept.

### 2.5 Cached response serialization

`TxEntry.cached_response` stores the serialized `ToolCallResponse` Pydantic model:

```python
entry.cached_response = response.model_dump(mode="json")
```

On replay, the executor rebuilds the response via `ToolCallResponse.model_validate(entry.cached_response)`. This keeps the cache value JSON-safe and safe against pydantic schema evolution (validate-on-read catches drift).

### 2.6 Duplicate detection from client side

When a TUI client submits the SAME `transaction_id` twice (e.g., user double-clicks "제출"):

1. First send: generates `transaction_id` client-side as a UUIDv7, sends `tool_call` frame.
2. Second submit (if client re-emits same `transaction_id`): backend dedup hits cache → returns first response.
3. User sees "이미 제출되었습니다. 접수번호: ..." HUD (generated from `cached_response.receipt_id` when present).

If the client DOES NOT reuse the `transaction_id` (fresh UUIDv7 each time), dedup does not trigger — this is the correct behavior for "intentional retry with new intent". Discipline is on the client side.

### 2.7 Coupling with Spec 024 audit

Every irreversible tool call — cache hit OR miss — writes exactly one `ToolCallAuditRecord`:

| Scenario       | `status` field        | Audit body                                               |
| -------------- | --------------------- | -------------------------------------------------------- |
| First call     | `"ok"` or `"error"`   | Full response / error                                    |
| Duplicate hit  | `"dedup_hit"`         | Reference to original `correlation_id` + `transaction_id` |

The audit log is therefore a true record of intent (one row per request), separated from the effect (one row per first execution).

### 2.8 Span attributes (Spec 021 OTEL promotion)

All tool-call spans gain:

- `ummaya.ipc.correlation_id` (always)
- `ummaya.ipc.transaction_id` (when present)
- `ummaya.ipc.tx.cache_state` = `"hit" | "miss" | "bypass"` (for `is_irreversible=false`)

---

## 3. Coupling between backpressure + tx dedup

### 3.1 During backpressure, irreversible tools still enqueue

A civic submit triggered during a `pause` window MUST still register its `transaction_id` in the LRU before queuing. Rationale: the user sees their click "land", and any duplicate click during the pause window hits the cache. Even if the actual API call is delayed until `resume`, the dedup semantics hold.

### 3.2 Retry-after and cached responses

If `upstream_429` causes a throttle, and the first call eventually succeeds after the retry window, the LRU records the success response. A subsequent duplicate submit during the window returns a "처리 중" placeholder:

- Optional: LRU stores a `pending` marker → second submit returns HUD copy "이전 요청을 처리 중입니다" rather than executing twice.
- Deferred: true in-flight coalescing (spec.md deferred item).

---

## 4. Validation checklist

| Check                                                                               | Enforced in                     |
| ----------------------------------------------------------------------------------- | ------------------------------- |
| HWM default = 64, resume threshold = 32, hysteresis never inverts                   | `BackpressureController.tick()` |
| Every `pause` paired with later `resume` (or synthetic `resume` at teardown)        | session teardown hook           |
| `throttle` frames never arrive without `retry_after_ms`                              | pydantic `@model_validator`     |
| HUD copy both `ko` and `en` non-empty                                                | pydantic `min_length=1`         |
| `transaction_id` present ⇔ tool is irreversible AND kind ∈ allow-list               | pydantic `@model_validator` on `_BaseFrame` |
| LRU capacity enforced via `OrderedDict` size + pinned carve-out                      | `TransactionLRU.record()`       |
| Cached response round-trips through pydantic validate                                | executor replay path            |
| Audit log written for both cache-hit and miss                                        | `ToolExecutor` + test           |

---

## 5. Test matrix (normative for WS2 + WS3)

### 5.1 Backpressure

| Scenario                                                 | Expected                                                  |
| -------------------------------------------------------- | --------------------------------------------------------- |
| Queue depth crosses 64                                   | Exactly one `pause` emitted                               |
| Queue drains to 31                                       | Exactly one `resume` emitted                              |
| Queue oscillates 60↔64 repeatedly                         | At most one `pause` (hysteresis holds)                    |
| Upstream 429 during idle queue                           | `throttle` emitted with `retry_after_ms`, no `pause`     |
| Session teardown with outstanding `pause`                | Synthetic `resume` emitted before final error             |
| HUD copy interpolation with `retry_after=15`              | Korean: "부처 API가 혼잡합니다. 15초 후 자동 재시도합니다." |

### 5.2 Tx dedup

| Scenario                                                 | Expected                                                   |
| -------------------------------------------------------- | ---------------------------------------------------------- |
| First irreversible submit                                | cache miss, execute, record, pin                           |
| Duplicate submit (same tx_id)                            | cache hit, return cached, no execution, audit `dedup_hit`  |
| Submit with different tx_id                              | cache miss, execute again (intended behavior)             |
| Reversible tool (is_irreversible=false)                  | `transaction_id=null`, bypass cache                       |
| LRU overflow with 513 non-pinned entries                 | Oldest non-pinned evicted                                  |
| LRU overflow with 513 pinned entries                     | No eviction; test documents operational implication        |
| Cache survives session-drop → resume replay              | Replayed tool_call hits cache                              |
| `cached_response` rebuilds via Pydantic validate         | Round-trip successful                                      |

---

## 6. Out of scope

- In-flight coalescing of concurrent identical tx_ids (deferred).
- Cross-session dedup (keyed by session — intentional; cross-session dedup deferred).
- Cache persistence across process restart (deferred — in-memory only).
- Proactive cache eviction of stale pinned entries (deferred — operator-initiated purge).

All tracked in spec.md § Deferred to Future Work.
