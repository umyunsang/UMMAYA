# G11 Research — Partial P0/P1 Deepening

> Wave-4 Sonnet G11 · 2026-05-05 · Targets: F-beta-03 (PARTIAL), F-gamma-04 (PARTIAL), F-gamma-06 (PARTIAL)

---

## G11a — F-beta-03: param-variation hash gate bypass

### Root cause
`_hash_call` in `src/kosmos/ipc/stdio.py:2494-2502` already uses `sort_keys=True`
(key ordering normalized). But K-EXAONE on FriendliAI varies params between retries
in three ways that produce different hash values despite semantically identical calls:

1. **String whitespace**: `"소상공인 복지"` vs `"소상공인  복지"` (double space mid-token
   after the model's reasoning buffer flushes).
2. **Float/int drift**: `page_no=1` (int) vs `page_no=1.0` (float) — Python
   `json.dumps` renders these as `1` and `1.0` respectively → different hash.
3. **Pagination fields as part of the hash**: `page_no` and `num_of_rows` are
   *search-scope-neutral* — paginating the same query is the same semantic call.
   K-EXAONE sometimes increments `page_no` hoping the next page has data; this
   should be dedup-blocked per the same prior-NO_DATA rule.

### Fix (RFC 8785 / JCS research)
RFC 8785 (JSON Canonicalization Scheme) specifies: sort keys, no insignificant
whitespace, numbers in their shortest IEEE 754 representation. Python does not
ship an RFC 8785 library in stdlib, but we can approximate with:

```python
def _normalize_params(params: dict) -> dict:
    """Strip high-cardinality fields + normalize values before hashing."""
    _PAGINATION_KEYS = frozenset({"page_no", "num_of_rows", "order_by", "pageNo", "numOfRows"})
    result = {}
    for k, v in params.items():
        if k in _PAGINATION_KEYS:
            continue
        if isinstance(v, str):
            v = " ".join(v.split())  # collapse internal whitespace
        elif isinstance(v, float) and v == int(v):
            v = int(v)  # 1.0 → 1
        result[k] = v
    return result
```

Then `_hash_call` becomes:
```python
canonical = _json_dedup.dumps(
    _normalize_params(params), sort_keys=True, separators=(',', ':'), ensure_ascii=False
)
```

### CC reference
CC's `_hashCall` in `.references/claude-code-sourcemap/restored-src/src/query/query.ts`
does NOT normalize params — it uses a simple JSON.stringify on the raw tool input.
KOSMOS intentionally diverges here (documented in `research/g4-backend.md § 6`) because
K-EXAONE has higher retry-variation rate than Claude.

### Instrumentation
Add `logger.debug("DEDUP key=%s tool_id=%s params=%s", _dedup_key, tool_id, canonical)`
at the `_hash_call` return site so wave-5 smoke logs expose the exact canonical form.

---

## G11b — F-gamma-04: TUI receipt in-memory stale during reasoning

### Root cause
`usePermissionReceiptWatcher` fires on `bridge.onFrame` events (backend echo of
`permission_response` frame with `role="backend"` and `receipt_id`). This echo arrives:
1. After the Python backend writes the consent ledger (immediately post Y-press).
2. After the TUI's `resolvePermissionDecision` unblocks the `deps.ts` for-loop (G3 fix).
3. After `_dispatch_primitive` returns and emits `tool_result`.

Net: the echo arrives within ~1s of the citizen pressing Y. It is NOT delayed by
K-EXAONE reasoning (reasoning happens BEFORE the permission request is even shown).

The gamma-combined scenario timing is:
```
0s    K-EXAONE starts reasoning (~60s window)
60s   backend emits permission_request frame
60s   citizen pressed Y
60s   G3 fix: slot resolves, backend writes receipt + echoes
60s   watcher fires → addReceipt() called
```

The "0 receipts when K-EXAONE still reasoning" observation means the `/consent list`
command was invoked BEFORE any permission was ever granted. This is not a bug — it is
expected (no grants have occurred). The PARTIAL status is therefore:
- No grant happened yet → 0 receipts is correct.
- After grant: watcher does fire and add receipt (G3 fix unblocked the loop).

### Optimistic update rationale
For improved UX, an optimistic receipt can be shown in `/consent list` the instant
the citizen presses Y — even before the backend echo arrives. This uses:

```typescript
// ipcPermissionBridge.ts  — new export
let _optimisticAddReceipt: ((r: PermissionReceiptT) => void) | null = null
export function registerOptimisticAddReceipt(fn: ((r: PermissionReceiptT) => void) | null): void {
  _optimisticAddReceipt = fn
}
```

In `onAllow`:
```typescript
if (_optimisticAddReceipt) {
  const optimistic: PermissionReceiptT = {
    receipt_id: `rcpt-opt-${frame.request_id.replace(/[^A-Za-z0-9]/g, '').slice(0, 12)}`,
    layer: computedLayer,
    tool_name: toolName,
    decision: decision as PermissionReceiptT['decision'],
    decided_at: new Date().toISOString(),
    session_id: sessionId,
    revoked_at: null,
  }
  _optimisticAddReceipt(optimistic)
}
```

The real echo (with the canonical backend `receipt_id`) arrives within ~1s and calls
`addReceipt` again. The context deduplicates by `receipt_id` — the optimistic entry
has a `rcpt-opt-*` id distinct from the real `rcpt-*` id. To keep the UI clean,
`usePermissionReceiptWatcher` removes optimistic entries (prefixed `rcpt-opt-`) when
the real echo arrives for the same `request_id` correlation.

**Receipt ID constraint**: `PermissionReceipt` schema requires `/^rcpt-[A-Za-z0-9_-]{8,}$/`.
`rcpt-opt-<12 alphanum>` satisfies this (prefix "rcpt-opt-" = 9 chars + 12 chars suffix = 21 chars total, all alphanum or `-`).

### Instrumentation
Add `RECEIPT_CTX state=<n_receipts> source={ipc-echo|optimistic|disk}` log to
`usePermissionReceiptWatcher` at the addReceipt callsite.

---

## G11c — F-gamma-06: Shift+Tab bypassPermissions banner Bun PTY verification

### Root cause
tmux `send-keys S-Tab` suffers from the 500ms `escape-time` batching (AGENTS.md
infra-insight #2). The Bun PTY harness sends raw bytes directly to the PTY, bypassing
tmux entirely.

### Shift+Tab raw sequence
Shift+Tab = `\x1b[Z` (VT220 / xterm standard, ECMA-48 "CBT Cursor Backward Tabulation").
The harness already maps `BackTab` → `\x1b[Z` (see `scripts/bun-pty-capture.ts:61`).

### Scenario: verify mode cycles
```typescript
// scenarios/gamma/g11c-shift-tab-mode-cycle.ts
export default async (h) => {
  await h.waitForPane(/KOSMOS/, 20)
  h.snapshot('boot')
  // Read initial mode (expect "● high · /effort" or similar)
  const before = h.plain()
  h.sendKey('BackTab')           // raw \x1b[Z
  await sleep(300)               // allow Ink to reconcile
  h.snapshot('after-first-shift-tab')
  h.sendKey('BackTab')
  await sleep(300)
  h.snapshot('after-second-shift-tab')
  // Verify: "Use meta+t to toggle thinking" or mode banner changed
  // Verify: final snapshot returns to original mode after 2 presses
  h.sendCtrlC()
}
```

The test MUST show the mode indicator (e.g. `● high · /effort`) changes after
each `BackTab`, and that two presses returns to the original mode (or cycles through).

The bypassPermissions banner specifically: Shift+Tab cycles `NORMAL → BYPASSPERMS → NORMAL`
(or similar). The exact text is rendered by `PromptInput.tsx:cycleMode` which toggles
`bypassPermissions` in the shell state store.

---

## Summary of fixes

| Target | File | Lines changed |
|---|---|---|
| G11a | `src/kosmos/ipc/stdio.py` | `_hash_call`: +8 lines (normalize helper) |
| G11a | `tests/ipc/test_g4_agentic_loop_dedup.py` | +20 lines (param-variation cases) |
| G11b | `tui/src/utils/permissions/ipcPermissionBridge.ts` | +35 lines (register + onAllow write) |
| G11b | `tui/src/screens/REPL.tsx` | +3 lines (wire registration) |
| G11b | `tui/tests/utils/permissions/g11b-optimistic-receipt.test.ts` | NEW +60 lines |
| G11c | `specs/realuse-audit-2026-05-05/scenarios/gamma/g11c-shift-tab.ts` | NEW +50 lines |
| G11c | `specs/realuse-audit-2026-05-05/scenarios/gamma/run-g11c.sh` | NEW +15 lines |

Total: ≤ 191 LoC added. Zero new runtime dependencies.
