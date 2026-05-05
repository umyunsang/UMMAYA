# G9 — NMC L3 modal vs LookupPrimitive timeout race (research)

> Wave-4 Lead Opus G9 · 2026-05-05 · F-beta-04 PARTIAL → CLOSED.
> Backend G1 fix holds (NMC HTTP not executed). Citizen UX path broken: modal
> never visible because `LookupPrimitive` 30 s `requestTimeoutMs` fires before
> the React reconcile commits the `PermissionRequestFrame` overlay.

## 1. Symptom timeline (β5 re-smoke 2026-05-05)

| t        | Event                                                              |
|----------|--------------------------------------------------------------------|
| 0 s      | Citizen sends "서울 지금 응급실 어디가 가장 가까워?"               |
| ~3 s     | K-EXAONE `enable_thinking=true` reasoning starts                   |
| ~30–60 s | Reasoning chain emits `tool_call lookup(nmc_emergency_search,...)` |
| t₀       | Backend: `_check_permission_gate` → `_lookup_needs_modal=True`     |
|          | (G1 fix path) → emits `PermissionRequestFrame` to TUI stdout       |
| t₀+~ms   | TUI `deps.ts:528` consumes frame → `pushIpcPermissionRequest(...)` |
|          | → `setter((prev) => [...prev, confirm])`                            |
| t₀+~ms   | `setPendingPermission(...)` returns Promise; for-loop suspends     |
| t₀+30 s  | **`dispatchPrimitive` setTimeout(30_000) fires** in TUI            |
|          | → `registry.reject(toolUseId, 'lookup 요청 시간 초과 (30000ms)')`   |
| t₀+30 s  | LookupPrimitive returns `{ok:false, error:{kind:'timeout'}}`       |
| t₀+30 s  | Citizen's screen: `⏺ lookup(nmc_emergency_search)` `⎿ 오류: ... 30000ms` |
| t₀+60 s  | Backend's `_PERM_TIMEOUT_S=60` fires → emits `tool_result`         |
|          | with `{error:'permission_timeout', denied:True}` envelope          |
| t₀+60 s  | Modal still not granted; `pendingPermissionSlot` `KOSMOS_PERMISSION_TIMEOUT_SEC=300` |
|          | continues to wait but the citizen has already seen the timeout     |

## 2. Root-cause decomposition

### R1 — Timeout mismatch by design (FR-006 Spec 2297)

`tui/src/tools/_shared/dispatchPrimitive.ts:34` defines
`DEFAULT_TIMEOUT_MS = 30_000`. Spec 2297 § FR-006 says this is for "genuinely
stuck dispatches" with mock adapters where p95 < 200 ms. It was NOT designed
to encompass:
- Backend permission-gate await (60 s default)
- `pendingPermissionSlot` modal-grant TTL (300 s default per Spec 033)
- Citizen think time
- React reconcile + setter mount (typically <100 ms but unbounded under load)

The 30 s default is correct for `lookup(read-only)` happy path; it is wrong
for `lookup(login-gated NMC/HIRA-L3)` paths that enter the permission gauntlet.

### R2 — `_registeredSetter` mount/unmount race

`ipcPermissionBridge.ts:51` holds `_registeredSetter: SetToolUseConfirmQueueFn | null`
as module-scoped state. `REPL.tsx:1377` registers via `useEffect` cleanup.
When a `permission_request` frame arrives DURING REPL re-render or unmount
(e.g., `--continue` session warm-up, suspense boundary swap), `setter === null`
→ early return at line 134-138, frame silently dropped. No retry, no queue.

CC restored-src `inProcessRunner.ts:195` has the same `getLeaderToolUseConfirmQueue()
?.( ... )` early-return, BUT CC's permission requests are in-process synchronous
(no IPC); the leader queue is registered on REPL boot before any teammate dispatch.
KOSMOS's IPC architecture means the backend can emit a `permission_request`
frame at ANY moment, including milliseconds after a teammate-driven REPL mount.

### R3 — Citizen does not know permission decision is required

When K-EXAONE reasoning takes 60 s+ (model-card default
`enable_thinking=True`), the citizen sees the spinner with no hint that a
permission gate is about to materialise. If the spinner times out at 30 s,
the citizen reads "도구 실패" and has no way to retry without re-sending the
request.

## 3. Fix taxonomy

| Fix                                                                        | LoC | Risk | Decision |
|----------------------------------------------------------------------------|-----|------|----------|
| (a) Extend `dispatchPrimitive` permission-aware timeout: pause the timer when `pendingPermissionSlot` activates a request for the same correlation; resume on grant/deny | ~50 | Med  | **CHOSEN** |
| (b) Queue frames in `ipcPermissionBridge` when `_registeredSetter === null`; replay on `registerIpcToolUseConfirmQueue(non-null)` | ~25 | Low  | **CHOSEN** |
| (c) Inline "permission decision required" assistant frame BEFORE the spinner (UX hint) | ~30 | Med  | Deferred — would require deps.ts emission + assistant-message synthesis |
| (d) Move 30 s timeout to a per-primitive override at LookupPrimitive call site | ~10 | Low  | Rejected — primitive-level patch leaks gate semantics into the wrong layer |
| (e) Disable the timeout entirely when an active permission slot exists | ~15 | Low  | Rejected — no fallback if the modal-pipeline is itself broken |

(a) + (b) chosen. (c) deferred to a separate UX-only follow-up.

## 4. Five mandatory probe points

Per AGENTS.md § Five mandatory probe points, this fix instruments:

1. **Input ingress** — N/A (no keypress change in this fix).
2. **IPC frame boundary** — `ipcPermissionBridge.ts` already logs warnings on
   setter-null; we extend with `MODAL ts=… correlation_id=… stage=queued|replayed`
   when frames are buffered/replayed.
3. **Tool dispatch boundary** — `dispatchPrimitive` adds a debug log
   `MODAL ts=… correlation_id=… stage=timer_paused|timer_resumed` when the
   permission-aware extension activates.
4. **Render commit** — `kosmos.tui.frame_commit` OTEL event already exists
   (Spec 032). We add an attribute `kosmos.tui.modal.pending_request_id` so
   the frame_commit timeline cross-references the modal mount.
5. **Snapshot trigger** — Layer 5 β5 re-run captures `frames/` directory.

## 5. CC restored-src diff

CC `restored-src/src/utils/swarm/inProcessRunner.ts:195-292` shows the
canonical permission-await: `setToolUseConfirmQueue(...)` is called once,
then `new Promise<PermissionDecision>(resolve => …)` resolves on
`onAllow/onReject/onAbort`. CC has NO timeout on the await — it relies on
`abortController.signal` (Ctrl-C) for cancellation. The 30 s timer is a
KOSMOS-specific addition from Spec 2297 FR-006 that did not anticipate the
gauntlet path.

The fix preserves Spec 2297 FR-006 default (30 s for genuinely-stuck mocks)
and ADDS a permission-pause hook so the timer extends ONLY when a permission
modal is in-flight for the same correlation_id.

## 6. Implementation surface

| File                                                                   | Lines added | Purpose                                                                                  |
|------------------------------------------------------------------------|-------------|------------------------------------------------------------------------------------------|
| `tui/src/tools/_shared/dispatchPrimitive.ts`                           | ~35         | Permission-aware timer pause/resume; reads `pendingPermissionSlot` for active request    |
| `tui/src/utils/permissions/ipcPermissionBridge.ts`                     | ~30         | `_pendingFrames` queue when setter null; replay on register; flush on null-register      |
| `tui/tests/utils/permissions/g9-setter-null-queue.test.ts` (NEW)       | ~75         | 4 tests: queue, replay, drain-on-null, idempotency                                       |
| `tui/tests/tools/_shared/g9-permission-aware-timeout.test.ts` (NEW)    | ~60         | 3 tests: timer paused on pending modal, resumed on resolve, baseline 30 s preserved       |

Total: ~200 LoC including tests; production code <80 LoC. Within ≤150 LoC budget.

## 7. References

- AGENTS.md § "Five mandatory probe points" + "Seven anti-patterns"
- `specs/2297-zeta-e2e-smoke/spec.md § FR-006` (30 s default rationale)
- `specs/realuse-audit-2026-05-05/wave3/findings-beta-resmoke.md § F-beta-04`
- `specs/realuse-audit-2026-05-05/fixes/g1-pipa.md` (backend gate path)
- `specs/realuse-audit-2026-05-05/fixes/g3-perm-pipeline.md` (slot unblock)
- CC restored-src `src/utils/swarm/inProcessRunner.ts:195-292` (await pattern)
- CC restored-src `src/utils/swarm/leaderPermissionBridge.ts:25-54` (setter registry)
- Spec 033 `KOSMOS_PERMISSION_TIMEOUT_SEC=300` (modal grant TTL)
- Backend `src/kosmos/ipc/stdio.py:1386` `KOSMOS_PERMISSION_TIMEOUT_SECONDS=60`
