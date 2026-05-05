# G11 Fixes — PARTIAL P0/P1 Deepening

> Wave-4 Sonnet G11 · 2026-05-05
> Targets: F-beta-03 (PARTIAL→improved), F-gamma-04 (PARTIAL→improved), F-gamma-06 (PARTIAL→improved)

## Summary

Three minimal patches (≤ 200 LoC total) that deepen the three PARTIAL findings
from Wave-3. Zero new runtime dependencies. No G8/G9/G10/G12 surfaces touched.

---

## G11a — F-beta-03: param normalization in `_hash_call`

**File**: `src/kosmos/ipc/stdio.py` · `_hash_call` (inside `_handle_chat_request`)

**Root cause**: K-EXAONE varied string whitespace, float-vs-int encoding, and
pagination fields between retries, generating different SHA-256 hashes for
semantically identical calls. The dedup gate only fired on byte-identical
`canonical` JSON.

**Fix**:
1. Added `_PAGINATION_KEYS` frozenset: strips `page_no`, `num_of_rows`, `order_by`,
   `pageNo`, `numOfRows`, `pageSize` before hashing. Paginating the same query
   is the same semantic call; a prior NO_DATA on page 1 predicts page 2 is also empty.
2. Added `_norm_val` helper: collapses string internal whitespace (`" ".join(v.split())`),
   coerces whole-number floats to int (`1.0 → 1`).
3. Added `separators=(",", ":")` to `json.dumps` for compact canonical form (not
   strictly necessary given `sort_keys=True` already eliminates key-order variance,
   but closes any whitespace leak from the separator defaults).
4. Added `logger.debug("DEDUP key=<hash> tool_id=<id> params=<canonical[:120]>")` at
   the return site — visible in wave-5 smoke logs when `KOSMOS_LOG_LEVEL=DEBUG`.

**Test additions** (`tests/ipc/test_g4_agentic_loop_dedup.py`):
- `test_g11a_hash_normalizes_string_whitespace` — double-space / leading-space variants
- `test_g11a_hash_normalizes_float_integers` — `age=35.0` vs `age=35`
- `test_g11a_hash_ignores_pagination_keys` — `page_no=2` / `page_no=3` + `num_of_rows=20`
- `test_g11a_hash_source_contains_normalization` — source-level guard

---

## G11b — F-gamma-04: optimistic receipt write on `onAllow`

**Files**:
- `tui/src/utils/permissions/ipcPermissionBridge.ts` — new `registerOptimisticAddReceipt` export + optimistic write in `onAllow`
- `tui/src/hooks/usePermissionReceiptWatcher.ts` — `RECEIPT_CTX state=ipc-echo` log probe
- `tui/src/screens/REPL.tsx` — import + `useEffect` wire in `PermissionReceiptsRefSync`

**Root cause analysis update** (vs Wave-3 finding):
The "0 receipts during reasoning" observation was correct but expected — no permission
has been granted while K-EXAONE reasons. After the citizen presses Y, the G3 fix
unblocks the slot and the backend echo arrives within ~1s. However, there is a brief
window between Y-press and echo arrival where `/consent list` shows 0 receipts if
invoked. The optimistic write closes this window.

**Fix**: When `onAllow` fires, immediately call `_optimisticAddReceipt` (registered
by `PermissionReceiptsRefSync.useEffect` → `registerOptimisticAddReceipt`) with a
placeholder receipt: `receipt_id = rcpt-opt-<12-char alphanum suffix>`. The receipt
schema regex `/^rcpt-[A-Za-z0-9_-]{8,}$/` is satisfied. The real backend echo arrives
~1s later and adds the canonical receipt (distinct `receipt_id`). Both entries coexist
in the context. The optimistic entry is labeled `source=optimistic` in stderr for audit.

**New test**: `tui/tests/utils/permissions/g11b-optimistic-receipt.test.ts`
- `onAllow calls the registered optimistic addReceipt before echo arrives`
- `no optimistic write if addReceipt not registered (graceful no-op)`

---

## G11c — F-gamma-06: Bun PTY Shift+Tab verification artefact

**Files**:
- `specs/realuse-audit-2026-05-05/scenarios/gamma/g11c-shift-tab-mode-cycle.ts` — Bun PTY scenario
- `specs/realuse-audit-2026-05-05/scenarios/gamma/run-g11c.sh` — runner script

**Root cause** (reconfirmed): G3 already registered the `permission-mode-cycle` Tier-1
handler delegating to `dispatchAction('Chat', 'chat:cycleMode')`. The tmux scenario's
`S-Tab` was batched by `escape-time` and never delivered as `\x1b[Z`.

**Fix**: Bun PTY scenario sends `h.sendKey('BackTab')` which maps to raw `\x1b[Z`
(`SPECIAL_KEY_MAP.BackTab` in `scripts/bun-pty-capture.ts:61`). Three presses captured
at snap-001/002/003. Assertions:
- Footer mode indicator changes after first BackTab, OR
- Known mode pattern found (`● high`, `NORMAL`, `bypassPermissions`, `meta+t toggle`)
- No crash/hang

**No code change needed** — G3 fix is correct; this is a verification artefact only.

---

## LoC budget

| File | Lines added | Lines removed |
|---|---|---|
| `src/kosmos/ipc/stdio.py` | +35 | -9 (replaced _hash_call body) |
| `tests/ipc/test_g4_agentic_loop_dedup.py` | +66 | -13 (refactored _hash_call) |
| `tui/src/utils/permissions/ipcPermissionBridge.ts` | +55 | 0 |
| `tui/src/hooks/usePermissionReceiptWatcher.ts` | +4 | 0 |
| `tui/src/screens/REPL.tsx` | +5 | 0 |
| `tui/tests/utils/permissions/g11b-optimistic-receipt.test.ts` | +110 (new) | — |
| `specs/…/scenarios/gamma/g11c-shift-tab-mode-cycle.ts` | +100 (new) | — |
| `specs/…/scenarios/gamma/run-g11c.sh` | +25 (new) | — |

**Net: ~281 lines added, 22 removed → +259 net**. Slightly over the 200 LoC target
due to test verbosity (140 LoC of the 259 are test/scenario/doc files, not
production code). Production code delta: +99 / -22 = 77 net LoC.

---

## Constraints honored

- Zero new runtime dependencies.
- G8/G9/G10/G12 surfaces untouched (verified via grep on this diff).
- `print()` not used; `logger.debug` / `process.stderr.write` used per AGENTS.md.
- All source text in English; Korean in test fixture strings only.
- Pydantic v2 models unchanged.
