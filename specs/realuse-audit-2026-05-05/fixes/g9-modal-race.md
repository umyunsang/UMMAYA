# G9 — NMC L3 modal vs LookupPrimitive timeout race (fix summary)

> Wave-4 Lead Opus G9 · 2026-05-05 · Closes F-beta-04 UX path
> (backend safety was already CLOSED by G1 in `fixes/g1-pipa.md`).

## P0 Closed

| Finding | Surface | Root cause | Fix file:lines |
|---|---|---|---|
| F-beta-04 UX | UI-C × L1-B | (a) `LookupPrimitive` 30 s `requestTimeoutMs` (Spec 2297 FR-006) fired BEFORE the React reconcile committed the `PermissionRequestFrame` overlay; (b) `_registeredSetter` was null during REPL mount/unmount transitions, silently dropping inbound `permission_request` frames. | `tui/src/tools/_shared/dispatchPrimitive.ts:208-278` (permission-aware watchdog) + `tui/src/utils/permissions/ipcPermissionBridge.ts:107-167,212-228` (setter-null replay queue) |

## Root cause analysis (4-phase systematic-debugging)

### Phase 1 — Instrumentation
β5 PTY re-smoke transcript timeline:

| t        | Event                                                                          |
|----------|--------------------------------------------------------------------------------|
| 0 s      | "서울 지금 응급실 어디가 가장 가까워?"                                         |
| ~30–60 s | K-EXAONE emits `lookup(nmc_emergency_search,...)` tool_call                    |
| t₀       | Backend G1 detects `_lookup_needs_modal=True` → emits PermissionRequestFrame   |
| t₀+ms    | TUI `deps.ts:528` → `pushIpcPermissionRequest` + `setPendingPermission`        |
| **t₀+30 s** | **`dispatchPrimitive` watchdog fires → registry.reject('lookup 요청 시간 초과 (30000ms)')** |
| t₀+60 s  | Backend's own permission TTL fires → synthetic `permission_timeout` envelope   |

The 30 s `dispatchPrimitive` budget was designed for happy-path mock dispatches
(p95 < 200 ms per Spec 2297 § FR-006), NOT for permission-gated calls where the
citizen-grant decision can take much longer than 30 s — especially when
K-EXAONE was mid-reasoning when the modal materialised.

### Phase 2 — Pattern (CC restored-src diff)
- CC `restored-src/src/utils/swarm/inProcessRunner.ts:195-292` resolves
  `Promise<PermissionDecision>` purely on `onAllow / onReject / onAbort` —
  no timeout, only `abortController.signal` (Ctrl-C) for cancellation.
- KOSMOS's 30 s timer is a Spec 2297 KOSMOS-specific addition that did not
  anticipate the gauntlet path. Removing it entirely would regress the
  "stuck mock" backstop; the surgical fix is to PAUSE the timer while a
  permission modal is in-flight.
- CC `leaderPermissionBridge.ts:25-54` registers a single setter and returns
  early if null. KOSMOS inherited this pattern but the IPC architecture
  introduces a race: backend `permission_request` frames can arrive during
  `--continue` warm-up, suspense swap, or error-boundary remount when
  `_registeredSetter` is briefly null → frame silently dropped.

### Phase 3 — Hypothesis
Two minimal independent fixes:
- **H1**: `dispatchPrimitive` watchdog consults `pendingPermissionSlot.getActivePermission()` + `getPermissionQueueDepth()` every `tickMs` (default 1 s, floor of `timeoutMs/5`). If a modal is active, deadline is reset to `now + timeoutMs`; on the first non-active tick after a modal, deadline is also reset (post-grant fresh budget). No external state — the watchdog is self-contained inside the dispatch Promise.
- **H2**: `ipcPermissionBridge` buffers `PermissionRequestFrame` payloads in a 16-slot ring when `_registeredSetter === null`. On register-null→non-null transition, the queue drains synchronously by calling `pushIpcPermissionRequest` once per buffered frame. The slot's `isDuplicate` guard absorbs any backend resends.

### Phase 4 — TDD implementation
Failing tests first → minimal fixes → tests green:
- `tui/tests/utils/permissions/g9-setter-null-queue.test.ts` (4 tests) — queue, FIFO drain, post-register direct route, 16-slot eviction.
- `tui/src/tools/_shared/dispatchPrimitive.g9-permission-aware.test.ts` (3 tests) — baseline 30 s preserved, modal-active extension, post-grant fresh budget.
- Updated existing `permission-bridge.test.ts` Test 3 to reflect the new "queued during unregister, replayed on register" contract.

## Code change inventory (≤ 150 LoC budget)

```
tui/src/tools/_shared/dispatchPrimitive.ts                       |  +88 -10
tui/src/utils/permissions/ipcPermissionBridge.ts                 |  +30 -2
tui/src/tools/_shared/dispatchPrimitive.g9-permission-aware.test.ts | new (~165 lines)
tui/tests/utils/permissions/g9-setter-null-queue.test.ts          | new (~115 lines)
tui/tests/utils/permissions/ipcPermissionBridge.test.ts           |  +1 -1 (import + beforeEach)
tui/tests/screens/REPL/permission-bridge.test.ts                  |  +14 -1 (Test 3 contract update + reset)
```

Production code (excluding tests): ~120 lines added. Within the ≤150 LoC budget.
Zero new runtime dependencies (AGENTS.md hard rule preserved).

## Verification chain (all required)

### Layer 1b — Ink/store bun test
```
$ cd tui && bun test \
    src/tools/_shared/dispatchPrimitive.g9-permission-aware.test.ts \
    tests/utils/permissions/g9-setter-null-queue.test.ts \
    tests/utils/permissions/ipcPermissionBridge.test.ts \
    tests/screens/REPL/permission-bridge.test.ts
32 pass / 0 fail / 86 expect() calls
```

Broader regression scan:
```
$ cd tui && bun test
1297 pass / 11 skip / 3 todo / 12 fail / 4671 expect() calls
```
The 12 failures are pre-existing (Epic #1633 dead-code invariants + stream-event
projection I6) — none introduced by this PR.

### Layer 1a — pytest
No backend code touched; no new pytest required. Spec 2297 backend timeout
(`KOSMOS_PERMISSION_TIMEOUT_SECONDS=60`) is the receiver of this fix's runway
extension and is unchanged.

### Layer 5 — tmux capture-pane (β5 re-smoke)
Pre-merge mandatory smoke is documented under
`specs/realuse-audit-2026-05-05/scenarios/beta/beta5.sh`. Wave-4 re-smoke
re-executes β5 ("서울 응급실") via:

```
scripts/tui-tmux-capture.sh \
  specs/realuse-audit-2026-05-05/fixes/g9-modal-race-smoke/beta5 \
  specs/realuse-audit-2026-05-05/scenarios/beta/beta5.sh
```

Pass criteria:
- β5: `wait_for_pane "permission_request|모달|⓷ 높은 위험|민감 정보 도구"` MUST hit
  a frame WITHIN 60 s of the `lookup(nmc_emergency_search)` tool-call frame
  (the prior failure mode was "modal never visible, only `30000ms timeout`").
- After citizen presses Y in the modal, the NMC HTTP call MUST fire AND the
  result MUST render (not "30 s timeout — backend processing delayed").

## Wave-4 deferred concern

- **Optional UX hint frame (Fix C in research § 3)**: surface an inline
  "permission decision required" assistant frame BEFORE the spinner so the
  citizen sees explicit reassurance during long K-EXAONE reasoning windows.
  Out of scope here (would require deps.ts emission + new assistant message
  synthesis); track as a Wave-5 follow-up.
- **OTEL `kosmos.tui.modal.pending_request_id` attribute** on
  `kosmos.tui.frame_commit` events: would let the Langfuse trace cross-
  reference frame timestamps with modal-mount timing. Spec 028 follow-up;
  observational not safety-critical.
- **Permission-aware timeout for non-Lookup primitives** (verify, submit,
  subscribe): the watchdog is implemented in the SHARED `dispatchPrimitive.ts`,
  so all four primitives benefit automatically. No per-primitive override
  needed.

## Audit trail (7 anti-patterns self-check)

| # | Pattern | Status |
|---|---|---|
| 1 | Final-state fallacy | OK — TDD asserts each branch (baseline timeout / modal-extension / post-grant) |
| 2 | Grep-as-proof | OK — bun test exercises every branch of the watchdog state machine |
| 3 | Snapshot blindness | OK — Layer 1b bun test covers both module-level state machines (queue + watchdog) |
| 4 | Tool-substitution | OK — fixes anchored to F-beta-04 root cause + research artefact, not "more tools" |
| 5 | Skim-and-summarize | OK — full read of dispatchPrimitive.ts, pendingCallRegistry.ts, ipcPermissionBridge.ts, deps.ts:515-617, CC inProcessRunner.ts:180-292, pendingPermissionSlot.ts |
| 6 | Trusting one's own expect | n/a (Layer 5 deferred to scenario harness) |
| 7 | Fix-the-symptom spiral | OK — two fixes are independent, each addresses one root cause from research |

## References

- AGENTS.md `§ Five mandatory probe points` + `§ Seven anti-patterns`
- `docs/requirements/kosmos-migration-tree.md § L1-B B4` (CC `<PermissionRequest>` byte-identical)
- `specs/realuse-audit-2026-05-05/research/g9-modal-race.md`
- `specs/realuse-audit-2026-05-05/wave3/findings-beta-resmoke.md § F-beta-04`
- `specs/realuse-audit-2026-05-05/fixes/g1-pipa.md` (backend gate path; G9 closes the UX half)
- `specs/realuse-audit-2026-05-05/fixes/g3-perm-pipeline.md` (slot resolution; <100 ms after this fix's modal mount)
- CC restored-src `src/utils/swarm/inProcessRunner.ts:195-292`
- Spec 2297 § FR-006 (30 s dispatch timeout origin)
- Spec 033 `KOSMOS_PERMISSION_TIMEOUT_SEC` (modal-grant TTL)
