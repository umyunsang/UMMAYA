# Implementation Plan: /consent revoke 확인 모달 + consentBridge.ts IPC 라운드트립

**Feature**: `2767-consent-revoke-modal`
**Branch**: `feat/2767-consent-revoke-modal`
**Created**: 2026-05-04
**Spec**: [`spec.md`](./spec.md)

## Reference Materials Phase 0 — required reads

AGENTS.md `/speckit-plan` 룰: Phase 0 마다 `.specify/memory/constitution.md` + `docs/vision.md § Reference materials` 확인. 본 Epic 의 design decision → reference 매핑:

| Design Decision | Reference | Reason |
|---|---|---|
| `ConsentRevokeConfirmDialog` shell 구조 | `.references/claude-code-sourcemap/restored-src/src/components/PermissionRequest.tsx` (research-use, line-cited only) | CC 2.1.88 의 모달 dialog 패턴 — KOSMOS UI L2 의 직접 baseline (AGENTS.md CORE THESIS "CC harness 1:1 보존") |
| `consentBridge.ts` IPC singleton 패턴 | `tui/src/bridge/replBridgeHandle.ts` (Spec 1978 ChatRequestFrame) | KOSMOS 내 기존 IPC bridge 모듈의 transport singleton 패턴 — 동일 구조 재사용 |
| ToolJSX overlay mount 룰 | `tui/src/components/ExportPdfDialog.tsx` (Spec 035 P4 port) + AGENTS.md "Infrastructure insights" #3 | `isLocalJSXCommand: false` + 자체 `useInput` Esc fallback (검증된 KOSMOS 패턴) |
| IPC frame arm 추가 절차 | `specs/032-ipc-stdio-hardening/spec.md` § E3 role allow-list, § ring-buffer registration | Spec 032 invariant — 모든 신규 arm 은 role allow-list + correlation_id + ring-buffer 통과 필수 |
| Ledger append `action="withdraw"` 구조 | `src/kosmos/permissions/ledger.py:1-100` + `specs/033-permission-v2-spectrum/data-model.md § 2.1 L1-L5` | Spec 033 의 backend 면 byte-identical 재사용 — 본 Epic 은 caller 만 추가, ledger logic 재구현 X |
| Receipt 파일 atomic 업데이트 | `src/kosmos/ipc/stdio.py:1471-1487` (기존 receipt write 패턴) | atomic temp+rename, 0o600 mode preservation |
| TUI verification chain | AGENTS.md "TUI verification methodology" Layer 1b/4/5 + Spec debug-infra-rebuild RFC | tmux capture-pane (NOT asciinema), waitForFrame (NOT Sleep), vhs `.txt` golden file (NOT GIF only) |
| Korean-primary i18n | `tui/src/i18n/uiL2.ts` (기존) | 모달 텍스트는 한국어 primary + English fallback (`getUiL2I18n(locale)`) |

**Constitution check**:
- §I (Korean public service domain) — 모달 텍스트 한국어 primary, PIPA §36 근거 표시. PASS.
- §II (Fail-closed) — backend HMAC 키 부재 시 ledger append 거부 + in-memory rollback. PASS.
- §III (Spec-driven) — 본 plan 자체가 절차 준수. PASS.
- §IV (Single-fixed LLM provider) — 본 Epic 은 LLM 비-수정. PASS.
- §V (PIPA compliance) — §36 정정·삭제권 명시 안내 + ledger `action=withdraw` 추적. PASS.
- §VI (Deferred sub-issue tracking) — OOS 5건 모두 deferred sub-issue 후보 명시. PASS.

## Phase 1 — Design

### 1.1 Component layout — `ConsentRevokeConfirmDialog.tsx`

```text
┌──────────────────────────────────────────────────────────────────┐
│  ✻ KOSMOS · 권한 영수증 철회 / Revoke consent receipt           │
├──────────────────────────────────────────────────────────────────┤
│  영수증 ID: rcpt-01HX2K3M4N5P6Q7R8S9T                            │
│  도구:      hira_hospital_search                                  │
│  결정:      allow_session                                         │
│  발급:      2026-05-04 14:23:11                                  │
│                                                                   │
│  PIPA §36 정정·삭제권 행사로 본 영수증을 철회합니다.            │
│  Right to correction & deletion under PIPA §36.                  │
│                                                                   │
│  [Y] 한번만 철회   [A] 영구 철회   [N] 취소                      │
└──────────────────────────────────────────────────────────────────┘
```

CC analog: `PermissionRequest.tsx` 의 box-bordered dialog shell + 3-key footer + Esc dismiss. KOSMOS-only 차이: receipt metadata 4 필드 + PIPA §36 명시 안내.

### 1.2 IPC envelope — 신규 2 arm

```typescript
// arm 22: TUI -> backend
{
  kind: 'consent_revoke_request',
  request_id: '01HX...',  // ULID, matched in response
  receipt_id: 'rcpt-01HX...',
  scope: 'once' | 'session-all',
  // _BaseFrame inherited: correlation_id, sender, timestamp
}

// arm 23: backend -> TUI
{
  kind: 'consent_revoke_response',
  request_id: '01HX...',  // matches request
  ok: boolean,
  revoked_at: string | null,    // ISO8601 UTC, null if !ok
  record_hash: string | null,   // SHA-256 hex, null if !ok
  error: 'ledger_key_missing' | 'not_found' | 'already_revoked' | 'unknown' | null,
}
```

Ring-buffer registration: 두 arm 모두 Spec 032 의 `SessionRingBuffer` (256-frame deque) 에 정상 적재.

### 1.3 Backend handler dispatch sketch

`src/kosmos/ipc/stdio.py` 의 `_handle_consent_revoke_request(frame, transport, ...)` 신규 함수:

```python
# 1. HMAC key check (fail-closed)
try:
    load_or_generate_key(...)
except (HMACKeyFileModeError, FileNotFoundError):
    await transport.send(ConsentRevokeResponseFrame(
        request_id=frame.request_id, ok=False,
        revoked_at=None, record_hash=None,
        error="ledger_key_missing",
    ))
    return

# 2. Receipt file existence
receipt_path = _Path.home() / ".kosmos" / "memdir" / "user" / "consent" / f"{frame.receipt_id}.json"
if not receipt_path.exists():
    await transport.send(ConsentRevokeResponseFrame(
        request_id=frame.request_id, ok=False,
        error="not_found", ...,
    ))
    return

# 3. Already-revoked idempotent check (FR-021)
receipt_data = json.loads(receipt_path.read_text())
if receipt_data.get("revoked_at") is not None:
    await transport.send(ConsentRevokeResponseFrame(
        request_id=frame.request_id, ok=False,
        error="already_revoked", ...,
    ))
    return

# 4. Ledger append (action="withdraw")
revoked_at = datetime.now(UTC).isoformat()
record = ledger.append({
    "action": "withdraw",
    "scope": frame.receipt_id,
    "decision": "denied",
    "withdrawn_at": revoked_at,
    "consent_receipt_id": str(uuid7()),
}, ...)

# 5. Receipt file atomic update
receipt_data["revoked_at"] = revoked_at
tmp_path = receipt_path.with_suffix(".tmp")
tmp_path.write_text(json.dumps(receipt_data))
os.chmod(tmp_path, 0o600)
os.rename(tmp_path, receipt_path)

# 6. Send response
await transport.send(ConsentRevokeResponseFrame(
    request_id=frame.request_id, ok=True,
    revoked_at=revoked_at,
    record_hash=record.record_hash,
    error=None,
))
```

### 1.4 TUI bridge module — `consentBridge.ts`

```typescript
// Module-level singleton (replBridgeHandle.ts pattern)
const _pending = new Map<string, {
  resolve: (r: RevokeBridgeResult) => void;
  timer: NodeJS.Timeout;
}>();

export async function requestRevoke(
  receiptId: string,
  options: { scope?: 'once' | 'session-all'; timeoutMs?: number } = {},
): Promise<RevokeBridgeResult> {
  const requestId = ulid();
  const scope = options.scope ?? 'once';
  const timeoutMs = options.timeoutMs ?? 5000;

  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      _pending.delete(requestId);
      resolve({ ok: false, error: 'timeout' });
    }, timeoutMs);

    _pending.set(requestId, { resolve, timer });

    void getReplBridge().send({
      kind: 'consent_revoke_request',
      request_id: requestId,
      receipt_id: receiptId,
      scope,
    });
  });
}

// Wired by REPL.tsx mount-time subscriber:
export function _handleConsentRevokeResponse(frame: ConsentRevokeResponseFrame): void {
  const pending = _pending.get(frame.request_id);
  if (!pending) return;
  clearTimeout(pending.timer);
  _pending.delete(frame.request_id);
  pending.resolve(
    frame.ok
      ? { ok: true, revoked_at: frame.revoked_at!, record_hash: frame.record_hash! }
      : { ok: false, error: frame.error ?? 'unknown' },
  );
}
```

### 1.5 REPL.tsx wire-up diff (sketch)

`tui/src/screens/REPL.tsx:3685-3691` 교체:

```typescript
} else if (subCmd === 'revoke') {
  const parsed = parseConsentArgs(_kosmosArgs);
  if (parsed.sub !== 'revoke') {
    addNotification({ key: 'kosmos-consent-revoke-usage',
      text: '사용법: /consent revoke <receipt-id>', priority: 'immediate' });
    return;
  }
  const target = permissionReceiptsRef.current.find(
    (r) => r.receipt_id === parsed.receiptId);
  if (!target) {
    addNotification({ key: 'kosmos-consent-revoke-not-found',
      text: `영수증을 찾을 수 없음: ${parsed.receiptId}`, priority: 'immediate' });
    return;
  }
  if (isReceiptRevoked(target)) {
    addNotification({ key: 'kosmos-consent-revoke-already',
      text: `이미 철회된 영수증: ${parsed.receiptId}`, priority: 'immediate' });
    return;
  }
  setToolJSX({
    jsx: React.createElement(ConsentRevokeConfirmDialog, {
      receipt: target,
      onConfirm: async (decision) => {
        const result = await consentBridge.requestRevoke(
          parsed.receiptId, { scope: decision === 'session-all' ? 'session-all' : 'once' });
        if (result.ok) {
          permissionReceiptsCtx.revokeReceipt(parsed.receiptId);
          addNotification({ key: 'kosmos-consent-revoke-done',
            text: `철회 완료: ${parsed.receiptId}`, priority: 'immediate' });
        } else {
          const errMsg = result.error === 'ledger_key_missing'
            ? 'HMAC 키 부재 — ledger 키 초기화 필요'
            : result.error === 'timeout'
            ? '응답 시간 초과'
            : `철회 실패: ${result.error}`;
          addNotification({ key: 'kosmos-consent-revoke-error',
            text: errMsg, priority: 'immediate' });
        }
        _kosmosCloseJSX();
      },
      onCancel: () => _kosmosCloseJSX(),
    }),
    shouldHidePromptInput: false,
    isLocalJSXCommand: false,
  });
}
```

## Phase 2 — Tasks (preview, finalised in `tasks.md`)

총 8 task, 5 user-story phase 매핑:

- **T001 [P] Phase Foundational**: `ConsentRevokeConfirmDialog.tsx` 컴포넌트 + ko/en i18n + `useInput` 핸들러 (FR-A01..A05).
- **T002 Phase Foundational**: `tui/src/components/consent/__tests__/ConsentRevokeConfirmDialog.test.tsx` (FR-F01).
- **T003 [P] Phase US1**: `src/kosmos/ipc/frame_schema.py` 신규 arm 2종 + role allow-list 갱신 (FR-C01, FR-C02). `tui/src/ipc/frames.generated.ts` 재생성 (FR-C03).
- **T004 Phase US1**: `src/kosmos/ipc/stdio.py` `_handle_consent_revoke_request` 핸들러 + ledger append + atomic receipt 갱신 (FR-D01..D05).
- **T005 Phase US1**: `src/kosmos/ipc/tests/test_consent_revoke_dispatch.py` (FR-F03) + `tui/src/services/ipc/__tests__/consentBridge.test.ts` (FR-F02).
- **T006 [P] Phase US1**: `tui/src/services/ipc/consentBridge.ts` 신규 + replBridge subscriber wire (FR-B01..B05).
- **T007 Phase US2 + US3**: `tui/src/screens/REPL.tsx` `subCmd === 'revoke'` 분기 재작성 + dangling comment 정리 (FR-E01..E04). `tui/src/screens/__tests__/REPL.consent-revoke.test.tsx` (FR-F04).
- **T008 Phase Polish**: `specs/2767-consent-revoke-modal/scripts/smoke-revoke.sh` (tmux) + `smoke-revoke.tape` (vhs, 3 PNG keyframes + .txt golden) + 5-layer verification chain 캡처 (FR-F05). `closure-2767.md` Spec 1635 P4 US2 마감 노트 + 본 Epic PR 의 Codex 리뷰 응답.

User-story phase mapping:
- T001-T002 → Foundational (모든 phase 의존, 컴포넌트 단위 격리)
- T003-T006 → US1 (happy path; IPC + backend + bridge + REPL wire 통합)
- T007 → US2 + US3 (invalid input fail-soft + backend fail-closed; REPL 분기 통합)
- T008 → Polish (smoke + closure)

`[P]` 마킹 기준: T001/T003/T006 은 서로 다른 파일 트리 (TS component / Python schema / TS service) 로 file overlap 0 → 병렬 디스패치 안전. T002 는 T001 의존, T004 는 T003 의존, T005 는 T003+T004 의존, T007 은 T001+T006 의존, T008 은 T007 의존.

Lead Opus dispatch tree (`dispatch-tree.md` 에 commit):

```text
Phase Foundational (T001-T002): sonnet-component (≤2 task / ≤3 file)
Phase US1 (T003-T006): sonnet-ipc (T003+T004+T005, ≤3 task / ≤5 file) + sonnet-bridge (T006, ≤1 task / ≤2 file) ── 병렬
Phase US2+US3 (T007): sonnet-repl-wire (≤1 task / ≤3 file)
Phase Polish (T008): Lead Opus solo (smoke + closure 작성 + PR 본문)
```

## Phase 3 — Risks & Open Questions

- **R-01 (Spec 032 invariant)**: 신규 arm 2종 추가가 Spec 032 의 SC-008 (zero new runtime deps) + ring-buffer 256-frame 한도 압박. 검증: T003 의 `frames.generated.ts` 재생성 후 `bun test` 의 envelope discrimination test PASS 필수.
- **R-02 (Bridge promise leak)**: timeout 후 backend 응답이 늦게 도착하면 `_pending` map 에서 이미 삭제된 요청에 대해 응답 처리 시도. 검증: T005 의 bridge test 에 "late response after timeout" 케이스 추가.
- **R-03 (Ledger append race)**: 동일 receipt 에 대한 동시 revoke 요청 2건. Spec 033 의 `fcntl.LOCK_EX` 가 이미 보장하므로 추가 가드 불필요. 검증 노트만 plan 에 남김.
- **R-04 (i18n drift)**: `uiL2.ts` 의 `consentRevoked` / `consentAlreadyRevoked` 메시지가 본 Epic 의 새 토스트 텍스트와 정합되지 않을 가능성. 검증: T001 에서 i18n bundle 재사용 가능성 확인 + 부족 시 추가 키 등록.
- **OQ-01**: `A` 키 (영구 철회) 의 backend 의미 — 본 Epic 에서는 P1 범위로 `Y` 와 동일 처리하되 ledger record 의 `scope` 만 `once_via_a_key` 로 마킹. 향후 Spec 에서 "동일 tool 미사용 영수증 일괄 철회" 로 확장 시 backend 핸들러만 변경하면 frame schema 무수정 가능. → Out of Scope OOS-03 으로 명시.
- **OQ-02**: receipt 파일이 `~/.kosmos/memdir/user/consent/` 에 없고 ledger 에만 존재하는 케이스 — Spec 033 의 reconciliation logic 영역이므로 본 Epic 은 receipt 파일을 source of truth 로 간주. `not_found` 응답 후 사용자가 `kosmos-permissions reconcile` 실행 (별도 spec).

## Phase 4 — Success Criteria Mapping

| SC | Phase | Verification Method |
|---|---|---|
| SC-01 | T007, T008 | PTY frame snapshot (Layer 5 tmux capture-pane) — `snap-001-prompt-revoke.txt`, `snap-002-modal-mounted.txt`, `snap-003-confirm-y.txt`, `snap-004-toast.txt`, `snap-005-list-revoked.txt` 5단계 |
| SC-02 | T002, T007 | `bun test ConsentRevokeConfirmDialog.test.tsx` + `REPL.consent-revoke.test.tsx` Esc/N 케이스 |
| SC-03 | T002, T007 | `bun test` 4 케이스 + Layer 5 `snap-006-invalid-format.txt` 등 |
| SC-04 | T005, T008 | `pytest test_consent_revoke_dispatch.py::test_fail_closed_no_hmac` + Layer 5 mock backend 시나리오 |
| SC-05 | T005 | `pytest test_consent_revoke_dispatch.py::test_idempotent_double_revoke` |
| SC-06 | T003 | `pytest src/kosmos/ipc/tests/test_frame_schema_role_allowlist.py` (Spec 032 기존 테스트에 신규 arm 추가 검증) |
| SC-07 | T008 | `git diff main...HEAD pyproject.toml tui/package.json` empty deps 변경 확인 |
| SC-08 | T008 | `specs/2767-consent-revoke-modal/scripts/` + `smoke-keyframe-*.png` 3+ 개 commit |
| SC-09 | T007 | `grep -rn "consentBridge.ts" tui/src` exit 0 + `grep -rn "P5 연동 예정" tui/src` exit 1 (no match) |
| SC-10 | T008 | `specs/1635-ui-l2-citizen-port/closure-2767.md` 작성 |

## Phase 5 — Test Plan

전 layer 적용:
1. **Layer 1a (pytest)**: `test_consent_revoke_dispatch.py` 5 케이스.
2. **Layer 1b (bun test + ink-testing-library)**: `ConsentRevokeConfirmDialog.test.tsx` (component) + `consentBridge.test.ts` (service) + `REPL.consent-revoke.test.tsx` (integration).
3. **Layer 2 (stdio JSONL probe)**: `python -m kosmos.ipc.demo.consent_revoke_probe` (신규 — 본 Epic 의 demo 스크립트) — TUI 우회로 backend 단독 검증.
4. **Layer 3 (interactive PTY)**: `expect` 기반 `smoke-revoke.expect` 시나리오.
5. **Layer 4 (vhs `.tape`)**: `smoke-revoke.tape` — 3+ PNG keyframes + `.txt` golden + `.gif` 보조.
6. **Layer 5 (tmux capture-pane)**: `scripts/tui-tmux-capture.sh` 기반 `smoke-revoke.sh` — `wait_for_pane` deadline-based polling.
7. **Layer 5c (frame sequence hash)**: `assertFrameSequence` 로 modal mount → confirm → toast 의 frame hash 시퀀스 deterministic 검증.

## Phase 6 — Rollout

본 Epic 은 단일 통합 PR (메모리 `feedback_integrated_pr_only`):
- 모든 task 통합 후 `bun test` + `pytest` PASS + Layer 1-5 smoke 캡처.
- PR body: `Closes #<Epic-issue>` 만 (Task sub-issues 미포함, 메모리 `feedback_pr_closing_refs`).
- Codex P1 review 즉시 응답.
- merge 후: 8개 Task sub-issue close + Spec 1635 closure note commit + `MEMORY.md` 의 `feedback_consent_revoke_completed` (또는 등가) 메모 업데이트.
