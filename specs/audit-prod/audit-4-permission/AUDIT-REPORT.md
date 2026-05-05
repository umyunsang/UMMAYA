# Audit-4 — Permission Gauntlet + Consent lifecycle (PROD readiness)

> **VERDICT — PRODUCTION READY: NO.** 11 P0 blockers found.  Permission Gauntlet is rendered but not interactable; consent ledger is never written by production code; receipt-id format mismatch makes /consent revoke impossible from the citizen surface; raw IPC NDJSON leaks onto the citizen's screen during a revoke attempt.  PIPA §22-2 / §26 obligations cannot be discharged in the current build.
>
> Date: 2026-05-04 · Lead Opus · Scope: Permission Gauntlet + Consent lifecycle end-to-end.
> Run env: macOS Darwin 25.2.0, tmux 3.6a, bun 1.3.12, K-EXAONE on FriendliAI.
> Captures: `specs/audit-prod/audit-4-permission/` (43 tmux snaps + 12 bun-pty snaps + backend log `/tmp/audit-4-bun.log`).

---

## P0 findings (production blockers)

| # | Severity | Surface | Finding | Evidence |
|---|---|---|---|---|
| **P0-1** | CRITICAL | TUI modal | **Y/A/N selector functionally frozen** — modal mounts (snap-01) but Enter / Down keys delivered via raw PTY (`\r`, `\x1b[B`) never advance the Select component.  Cause: `useInput` hook competition between `PromptInput`, `PermissionDialog`, and `PermissionPrompt`; raw bytes land in PromptInput first.  Citizens cannot make any decision. | `audit-4-bun-pty/snap-001..snap-008` are byte-identical with `❯ 1. Y 한 번만 허용` focused; backend log shows no `permission_response` ever arriving. |
| **P0-2** | CRITICAL | Backend gate | **Allow path bypasses Spec 033 ledger entirely.** `_check_permission_gate` (stdio.py:1539-1559) writes a JSON receipt file but never calls `kosmos.permissions.ledger.append()`. No HMAC seal, no SHA-256 chain, no key_id, no fcntl lock, no WORM mode. PIPA §22-2 audit-trail obligation violated. | After full scenario: `~/.kosmos/consent_ledger.jsonl` does not exist; `~/.kosmos/keys/registry.json` does not exist; `~/.kosmos/permissions.json` does not exist; only the pre-existing 2026-04-22 onboarding receipt is on disk. |
| **P0-3** | CRITICAL | Backend revoke | **Revoke path uses ad-hoc hashlib SHA-256 instead of canonical ledger.** `_handle_consent_revoke_request` (stdio.py:3192-3221) writes to `~/.kosmos/memdir/user/consent/ledger.jsonl` (NOT the canonical Spec 033 path) with no HMAC seal, no prev_hash chain, no key_id, no fcntl lock — entries are forgeable in plain text. | stdio.py:3200 `record_hash = _hashlib.sha256(ledger_json.encode("utf-8")).hexdigest()` — no `kosmos.permissions.ledger` import in the entire file. |
| **P0-4** | CRITICAL | Schema mismatch | **Receipt-ID format mismatch: backend writes plain UUIDv4, TUI requires `^rcpt-[A-Za-z0-9_-]{8,}$`.** `executeConsentRevoke` in `commands/consent.ts:90` rejects every backend-generated receipt with `invalid_id`. | stdio.py:1528 `receipt_id = str(uuid.uuid4())` (no prefix); schemas/ui-l2/permission.ts:26 `regex(/^rcpt-[A-Za-z0-9_-]{8,}$/)`; the 2026-04-22 disk receipt has filename `2026-04-22T...uuid.json` — not `rcpt-` either. |
| **P0-5** | CRITICAL | Wire decision | **Allow-session caching is broken — Y vs A is collapsed to `'granted'` on the wire.** `pushIpcPermissionRequest._sendPermissionResponse` (`utils/permissions/ipcPermissionBridge.ts:178-200`) has only two branches: `'granted'` and `'denied'`. The KOSMOS adapter in `KosmosPermissionRequestAdapter.tsx:75-86` collapses both `allow_once` and `allow_session` into `toolUseConfirm.onAllow(...)` which always sends `'granted'`. Backend then maps `'granted' → 'allow_once'` (stdio.py:1505 `is_allow_session = raw_decision == "allow_session"`). | Code-level — verified by reading both call-sites; cannot be observed at runtime because P0-1 prevents any decision from being sent. |
| **P0-6** | CRITICAL | TUI render | **Layer is hardcoded to `1` for every receipt regardless of primitive.** `usePermissionReceiptWatcher.ts:102` sets `layer: 1 as const` because the `PermissionResponseFrame` schema has no `primitive_kind` field — the TUI cannot recompute the layer from the echo frame. UI-C-1 spec ("1=green ⓵ / 2=orange ⓶ / 3=red ⓷") is unmet for every submit / subscribe receipt. | usePermissionReceiptWatcher.ts:102 `layer: 1 as const, // conservative default`. |
| **P0-7** | CRITICAL | TUI render | **`tool_name` is hardcoded to `'unknown'`.** Same hook line 103 sets `tool_name: 'unknown'`. ConsentListView shows the placeholder for every receipt. | usePermissionReceiptWatcher.ts:103 `tool_name: 'unknown', // filled by the adapter context if available` (never filled). |
| **P0-8** | CRITICAL | UI corruption | **Raw IPC NDJSON spilled onto the citizen's terminal during /consent revoke.** During `/consent revoke <id>` the response frame `{"version":"1.0","session_id":"5f2defb9-...","correlation_id":"3e00fead-...","ts":"...","role":"tui",...}` was painted INSIDE the prompt box and the empty-receipt-list view, mid-screen. Citizen sees raw protocol bytes. Cause: `_sendPermissionResponse` writes via `process.stdout.write(encodeFrame(...))` — raw write to the same stdout the renderer drives. | `audit-4-permission/snap-013-13` line 22, snap-014 line 22, snap-017 line 20-22, snap-020 line 20-22 (the `correlation_id`/`session_id` JSON visible in the rendered pane). |
| **P0-9** | CRITICAL | Backend manifest | **All 5 Mock submit adapters are dropped from the AdapterManifestSyncFrame** because `policy_authority_url` is null. The TUI's `resolveAdapter` returns `undefined` for them, so `is_irreversible` always defaults to `false` (Layer 2 instead of Layer 3 for irreversible submits). PIPA §22-2 "high-risk visual signal" obligation cannot be met. | `/tmp/audit-4-bun.log` lines 61-90: 10 separate `manifest_emitter: skipping ... policy_authority_url is required` warnings on every boot. |
| **P0-10** | CRITICAL | Backend wire | **`tool_name` shown in modal is the literal string `"main"`** for every primitive call. Cause: `pushIpcPermissionRequest` (ipcPermissionBridge.ts:151) sets `input.tool_id = frame.worker_id || frame.primitive_kind` and the backend never sets a meaningful `worker_id` (it's hardcoded `"main"` in stdio.py:1451). The citizen reads "main 도구가 신원 확인을 수행하려 합니다" — meaningless. | `audit-4-bun-pty/snap-001-01-verify-modal.txt` line 613 `"main" 도구가 신원 확인을 수행하려 합니다`; `audit-4-bun-pty/snap-005-05-submit-modal-mounted.txt` shows the same `"main"` for the verify-before-submit chain. |
| **P0-11** | CRITICAL | Backend wire | **TUI generates a `receipt_id` in its `permission_response` frame that is silently discarded by the backend** (which generates its own UUID). Two receipt_ids exist transiently for every decision; only the backend's persists. The TUI-side generated ID may be retained in any logs/OTEL spans created on the TUI side, creating an audit-trail discrepancy. | ipcPermissionBridge.ts:194 `receipt_id: randomUUID()`; stdio.py:1528 `receipt_id = str(uuid.uuid4())` (overwrite). |

## P1 findings (high — fix before production)

| # | Severity | Surface | Finding |
|---|---|---|---|
| P1-1 | HIGH | Backend log | Backend gate code paths use `logger.debug` exclusively. With default INFO level the audit log shows ZERO permission events. PIPA §22-2 forensic discoverability is meaningless without log-at-INFO traces. |
| P1-2 | HIGH | Backend OTEL | `OTEL context detach` ValueError after every LLM stream (stack at `/tmp/audit-4-bun.log:95-108`). Spans may not flush correctly to Langfuse. |
| P1-3 | HIGH | TUI render | Modal's "main" placeholder, hardcoded layer, and hardcoded tool_name combine to produce a citizen view that violates the **brand intelligibility test** (citizen cannot tell which agency/module is being invoked, what its risk level is, or which receipt was just issued). |
| P1-4 | HIGH | Backend permission | `_session_grants` is a process-local dict (stdio.py:1404) — even if P0-5 were fixed, Allow-session would not survive a TUI restart, contradicting "세션 동안 자동" wording (citizens reasonably expect this to persist for the visible session). |
| P1-5 | HIGH | TUI overlay stack | ConsentListView stacks ON TOP of an unfinished permission modal (audit-4-permission/snap-017-17 lines 13-23) — multiple overlays render simultaneously without z-order discipline. Citizens cannot tell what the focused dialog is. |

## P2 findings (medium)

| # | Severity | Surface | Finding |
|---|---|---|---|
| P2-1 | MED | i18n | `permissionEn` strings exist but are unreachable from `KOSMOS_TUI_LOCALE` because the env var is read once at module load (KosmosPrimitivePermissionRequest.tsx:56) — locale switch requires a TUI restart. |
| P2-2 | MED | Schema | The PIPA citation in `submitModalBody(toolName, isIrreversible=true)` cites §26 (수탁자 의무) but a submit to a non-trustee chain (e.g. KMA pre-warning subscription) should not. Citation is hardcoded, not derived from adapter manifest. |
| P2-3 | MED | TUI render | The 2026-04-22 onboarding receipt JSON is in the consent dir but its filename does not match the expected `rcpt-<uuid>.json` glob (`receipt_id=<UUID without prefix>.json`). The revoke-by-`session-all` path scans `consent_dir.glob("rcpt-*.json")` (stdio.py:3141) which would skip every backend-issued receipt. |

## Backend ↔ Frontend wiring matrix

| Surface | Expected (per spec) | Observed | Status |
|---|---|---|---|
| permission_request emit | backend → TUI on first gated primitive | YES — modal mounts (snap-01 of bun-pty) | ✅ |
| permission_request → KosmosPrimitivePermissionRequest mount | via toolUseConfirmQueue | YES — visible | ✅ |
| Y/A/N selector responsive | citizen presses Enter/arrow keys → decision | NO — frozen (P0-1) | ❌ |
| permission_response decision wire vocab | `allow_once` / `allow_session` / `deny` | only `granted` / `denied` (P0-5) | ❌ |
| receipt_id generation | backend canonical (stdio.py:1528) | dual generation (P0-11) | ⚠ |
| receipt format | matches TUI regex `^rcpt-...` | UUIDv4 plain (P0-4) | ❌ |
| receipt JSON write | `~/.kosmos/memdir/user/consent/<id>.json` | YES (when allowed) | ✅ |
| ledger.append (allow path) | Spec 033 chained+sealed entry | NEVER CALLED (P0-2) | ❌ |
| ledger.append (deny path) | per FR-D01 | NEVER CALLED (P0-2) | ❌ |
| ledger.append (withdraw path) | Spec 033 with action="withdraw" | ad-hoc unsealed (P0-3) | ❌ |
| permission_response echo back | backend → TUI w/ receipt_id | code-present (stdio.py:1571) | ⚠ untested (modal blocks) |
| addReceipt → PermissionReceiptContext | usePermissionReceiptWatcher | hardcoded layer=1, tool=unknown (P0-6/7) | ⚠ |
| /consent list render | reverse chrono table w/ layer color | renders empty (no receipts due to P0-1) | ⚠ untested-with-data |
| /consent revoke confirm dialog | mounts on valid rcpt-<id> | rejects every backend ID (P0-4) | ❌ |
| consent_revoke_request → backend | TUI → backend | code-present | ⚠ unreachable in citizen flow |
| consent_revoke_response → revokeReceipt | backend → TUI in-memory | code-present | ⚠ unreachable |

## Y/A/N citizen wording — UI-C-2 spec compliance

| Spec text | Observed in build |
|---|---|
| `Y 한번만` | `Y  한 번만 허용` ✅ |
| `A 세션 자동` | `A  세션 동안 자동 허용` ✅ |
| `N 거부` | `N  거부` ✅ |

Wording is compliant.  Functional behavior is not (P0-5 silently downgrades A → Y).

## PIPA compliance — observable obligations

| Obligation | Source | Observed | Status |
|---|---|---|---|
| §22-2 시각 확인 의무 (citizen-visible processing notice) | bottom of modal: "개인정보보호법 제22조의2·제26조에 따라 고지합니다." | Present in every modal | ✅ |
| §22-2 forensic audit trail | requires append-only ledger with HMAC seal | ledger never written; not auditable (P0-2/3) | ❌ |
| §26 수탁자 위탁 처리 거부권 (citizen consent withdrawal) | /consent revoke flow | impossible from citizen surface (P0-1, P0-4) | ❌ |
| Receipt visibility (Kantara CR receipt analog) | rcpt-<id> shown to citizen on grant | not observable in modal (modal renders `receiptIdLabel` only when prop is non-null; backend never passes it back to TUI before the decision) | ❌ |
| Layer color coding (1 green / 2 orange / 3 red) | UI-C-1 | hardcoded layer=1 in /consent list (P0-6); modal does color the gauntlet correctly via `aalToLayer` | ⚠ partial |

## Citizen safety — denial fallback

The N (deny) path could not be tested because the modal is frozen (P0-1).  Code-level inspection of the deny path:

- `KosmosPermissionRequestAdapter.handleDecision('deny')` calls `toolUseConfirm.onReject()` then `onReject()` then `onDone()`.
- `_sendPermissionResponse(frame, 'denied')` writes a `permission_response` with `decision: 'denied'`.
- Backend `_check_permission_gate` (stdio.py:1503-1525) emits a synthetic `tool_result` envelope with `error: 'permission_denied', denied: true` and resolves the call's pending Future.
- LLM receives the tool_result with the error envelope and can decide whether to retry or present a fallback to the citizen.

Citizen-facing fallback wording would depend on the LLM's prompt; **no deterministic guidance is shown to the citizen by KOSMOS itself** (no toast, no banner, no "alternative options" panel).  Production should add a Korean wording fallback (e.g. "권한이 거부되어 작업을 중단했습니다. 다른 방법을 시도하려면 …") in the message timeline at deny-time, independent of the LLM.

## Summary verdict

**PRODUCTION READY: NO.**

The Permission Gauntlet is the **single most safety-critical surface** in KOSMOS — it is the boundary between a citizen's request and a side-effecting / irreversible call against a Korean public-service module.  The current build:

1. **Cannot collect a citizen decision.**  P0-1 alone halts every gated primitive at the modal.  Citizens see a frozen Y/A/N selector with no visible cause; the backend waits 60 s for a response that never arrives.
2. **Cannot prove the audit trail.**  P0-2 / P0-3 mean the canonical Spec 033 HMAC-sealed ledger is never written by production code.  PIPA §22-2 forensic audit is unmeetable.
3. **Cannot be revoked from the citizen surface.**  P0-4 (regex mismatch) makes `/consent revoke` reject every receipt.
4. **Leaks raw protocol bytes onto the citizen's screen.**  P0-8 — the citizen sees IPC frames mid-conversation, which is both a UX failure and an information-leak surface.

These are not polish issues — they are absolute blockers.  Before re-attempting production qualification, the following must be true (in order):

1. P0-1 fix (Y/A/N delivers).  Without this all downstream tests are observation-blind.
2. P0-2 + P0-3 fix (allow / deny / withdraw all flow through `kosmos.permissions.ledger.append`).
3. P0-4 fix (single canonical receipt-id format end-to-end).
4. P0-5 fix (extend wire vocab to allow_session and exercise `_session_grants` cache).
5. P0-6 + P0-7 fix (extend `PermissionResponseFrame` schema with `primitive_kind` + `tool_id`; rebuild layer + tool_name on the TUI side).
6. P0-8 fix (route IPC writes through a dedicated channel, NOT shared with the renderer's stdout).
7. P0-9 fix (backfill `policy_authority_url` on all 5 Mock submit adapters).
8. P0-10 fix (set `worker_id` to the resolving adapter's display name).
9. P0-11 fix (TUI sends `receipt_id: null`; backend remains source of truth).
10. P1-1 (raise gate-related logs to INFO so the audit trail is at-rest greppable).

Recommend re-running this audit after every fix to prevent regression.

---

## Reproducible commands

```bash
# Tmux scenario (full 8-stage Y/A/N + revoke + LLM-fallback)
KOSMOS_BACKEND_LOG_FILE=/tmp/audit-4.log \
  bash scripts/tui-tmux-capture.sh \
    specs/audit-prod/audit-4-permission \
    specs/audit-prod/scripts/audit-4-permission.sh

# Bun-PTY scenario (cleanly delivers raw bytes; bypasses tmux escape-time)
KOSMOS_BACKEND_LOG_FILE=/tmp/audit-4-bun.log \
  bun scripts/bun-pty-capture.ts \
    specs/audit-prod/audit-4-bun-pty \
    specs/audit-prod/scripts/audit-4-bun-pty.ts
```

Both runs were performed for this audit.  The Bun-PTY harness is the authoritative source for keystroke-timing claims (P0-1) per AGENTS.md "Infrastructure insights" #2.
