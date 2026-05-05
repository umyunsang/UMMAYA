# Tasks: /consent revoke 확인 모달 + consentBridge.ts IPC 라운드트립

**Feature**: `2767-consent-revoke-modal`
**Spec**: [`spec.md`](./spec.md) · **Plan**: [`plan.md`](./plan.md)
**Total Tasks**: 8 (User-story phase 단위 5: Foundational / US1 / US2+US3 / Polish)
**Dispatch Tree**: [`dispatch-tree.md`](./dispatch-tree.md) (Lead Opus 가 `/speckit-implement` 시점에 commit)

본 tasks.md 는 `/speckit-tasks` 출력. `/speckit-taskstoissues` 가 8개 sub-issue 로 변환하여 Epic 의 sub-issue 로 link.

---

## Phase Foundational — UI 컴포넌트 + 단위 테스트

### T001 [P] [Foundational] `ConsentRevokeConfirmDialog.tsx` 컴포넌트 신규 작성

**Files**:
- `tui/src/components/consent/ConsentRevokeConfirmDialog.tsx` (신규)

**Reference baseline** (메모리 `feedback_cc_source_migration_pattern`):
- `.references/claude-code-sourcemap/restored-src/src/components/PermissionRequest.tsx` — CC 2.1.88 모달 dialog shell (research-use)
- `tui/src/components/consent/ConsentListView.tsx` — KOSMOS 측 consent UI 패턴 (i18n + theme 사용 + Esc fallback)
- `tui/src/components/ExportPdfDialog.tsx` — Spec 035 P4 dialog ported 형식 (3-key footer)

**Implementation**:
- Props: `{receipt: PermissionReceiptT, onConfirm: (decision: 'once' | 'session-all') => void, onCancel: () => void, locale?: 'ko' | 'en'}`.
- 4 필드 메타데이터 표시: `receipt_id` / `tool_name` / `decision` / `decided_at`.
- PIPA §36 정정·삭제권 안내 한 줄 (ko + en, `getUiL2I18n(locale)` 사용).
- 3-key footer: `[Y] 한번만 철회 · [A] 영구 철회 · [N] 취소`.
- `useInput` 핸들러: `y/Y` → `onConfirm('once')`, `a/A` → `onConfirm('session-all')`, `n/N` 또는 `key.escape` → `onCancel()`.
- AGENTS.md "Infrastructure insights" #4 — `useKeybinding` 미사용, `useInput` 직접 fallback.
- box-bordered + theme 토큰 (`theme.kosmosCore`, `theme.error`, `theme.text`, `theme.subtle`).

**Acceptance** (FR-A01..A05):
- 컴포넌트가 props 4 필드 + PIPA 안내 + 3-key footer 모두 렌더.
- `Y` / `A` / `N` / `Esc` 키 각각 정확한 callback 호출.
- ko/en locale 분기 PIPA 안내 텍스트 정상.

**Dependencies**: 없음 (Foundational).

---

### T002 [Foundational] `ConsentRevokeConfirmDialog` 단위 테스트

**Files**:
- `tui/src/components/consent/__tests__/ConsentRevokeConfirmDialog.test.tsx` (신규)

**Implementation** (Layer 1b — `ink-testing-library`):
- Test 1: 4 필드 메타데이터 표시 — `lastFrame()` snapshot에 `receipt_id`, `tool_name`, `decision`, `decided_at` 포함.
- Test 2: `Y` 입력 → `onConfirm` callback 이 `'once'` 인자로 호출됨.
- Test 3: `A` 입력 → `onConfirm` callback 이 `'session-all'` 인자로 호출됨.
- Test 4: `N` 입력 → `onCancel` callback 호출 + `onConfirm` 미호출.
- Test 5: `Esc` (`\x1b`) 입력 → `onCancel` callback 호출.
- Test 6: locale='en' 시 PIPA 안내 영문 ("PIPA §36" 또는 "right to correction") 포함.
- Test 7: 유효하지 않은 키 (예: `x`) 입력 시 두 callback 모두 미호출.

**Acceptance** (FR-F01):
- `bun test ConsentRevokeConfirmDialog.test.tsx` 7 case PASS.

**Dependencies**: T001.

---

## Phase US1 — Happy path: IPC + backend + bridge + REPL wire

### T003 [P] [US1] IPC frame schema arm 추가 (consent_revoke_request / consent_revoke_response)

**Files**:
- `src/kosmos/ipc/frame_schema.py` (수정)
- `tui/src/ipc/frames.generated.ts` (재생성)

**Reference baseline**:
- `src/kosmos/ipc/frame_schema.py:462-509` — `PermissionRequestFrame` / `PermissionResponseFrame` 패턴
- `specs/032-ipc-stdio-hardening/spec.md` § E3 role allow-list

**Implementation**:
- `ConsentRevokeRequestFrame` 클래스 추가:
  - `kind: Literal["consent_revoke_request"]`
  - `request_id: str` (ULID)
  - `receipt_id: str` (`rcpt-` 접두사 검증 `@field_validator`)
  - `scope: Literal["once", "session-all"]`
- `ConsentRevokeResponseFrame` 클래스 추가:
  - `kind: Literal["consent_revoke_response"]`
  - `request_id: str` (matches request)
  - `ok: bool`
  - `revoked_at: str | None`
  - `record_hash: str | None` (SHA-256 hex)
  - `error: Literal["ledger_key_missing", "not_found", "already_revoked", "unknown"] | None`
  - `@model_validator(mode="after")`: `ok=True` ↔ `revoked_at != None and record_hash != None and error == None` 정합성.
- `KIND_TO_ROLE_ALLOWLIST` 갱신:
  - `"consent_revoke_request": frozenset({"tui"})`
  - `"consent_revoke_response": frozenset({"backend"})`
- `IPCFrame` discriminated union 에 두 arm 추가.
- `__all__` 갱신 — 신규 클래스 2종 export.
- TS 측: `bun run codegen:ipc` (또는 동급 build script) 로 `frames.generated.ts` 재생성. 수동 편집 금지.

**Acceptance** (FR-C01..C04):
- `pytest src/kosmos/ipc/tests/test_frame_schema.py` PASS (기존 테스트 + 신규 arm 검증).
- `pytest src/kosmos/ipc/tests/test_frame_schema_role_allowlist.py` PASS (Spec 032 invariant).
- `tui/src/ipc/frames.generated.ts` 의 arm count 가 21 → 23 으로 증가.

**Dependencies**: 없음 ([P] mark — T001/T006 과 병렬 dispatch 가능).

---

### T004 [US1] backend handler `_handle_consent_revoke_request` 구현

**Files**:
- `src/kosmos/ipc/stdio.py` (수정 — 새 dispatcher 추가)

**Reference baseline**:
- `src/kosmos/ipc/stdio.py:1320-1490` — 기존 permission_response 핸들러 (consent receipt write 패턴)
- `src/kosmos/permissions/ledger.py:append()` — Spec 033 ledger append 함수
- `src/kosmos/permissions/hmac_key.py:load_or_generate_key` — fail-closed key check

**Implementation**: plan.md § 1.3 의 6단계 sketch 구현:
1. HMAC 키 검증 → 부재 시 `ledger_key_missing` 응답.
2. Receipt 파일 (`~/.kosmos/memdir/user/consent/<receipt_id>.json`) 존재 검증 → 부재 시 `not_found`.
3. `revoked_at` 필드 idempotent 검증 → 이미 set 시 `already_revoked` (FR-021).
4. `kosmos.permissions.ledger.append()` 호출 — `action="withdraw"`, `scope=<receipt_id>`, `decision="denied"`, `withdrawn_at=<ISO8601 UTC>`, `consent_receipt_id=<UUIDv7>`.
5. Receipt 파일 atomic 갱신 — `revoked_at` 추가, temp+rename, 0o600 mode.
6. `ConsentRevokeResponseFrame{ok=True, revoked_at, record_hash}` 송출.
- OTEL span: `kosmos.consent.revoke` with attributes `kosmos.consent.receipt_id`, `kosmos.permission.decision="revoked"`.
- Dispatcher 등록: `_kind_dispatch_table` (또는 등가) 에 `"consent_revoke_request": _handle_consent_revoke_request` 추가.

**Acceptance** (FR-D01..D05):
- handler 가 6단계 모두 정상 실행.
- HMAC 키 부재 시 ledger.append 호출 없이 fail-closed 응답.
- 동일 receipt 2회 revoke 시 ledger 에 record 1개만 추가.

**Dependencies**: T003.

---

### T005 [US1] backend dispatcher 테스트 + bridge 단위 테스트

**Files**:
- `src/kosmos/ipc/tests/test_consent_revoke_dispatch.py` (신규)
- `tui/src/services/ipc/__tests__/consentBridge.test.ts` (신규)

**Implementation**:

Python (`pytest-asyncio`):
- Test 1 `test_happy_path`: receipt 파일 + HMAC 키 mock setup → request 송출 → response `ok=True` + ledger 마지막 record `action=withdraw` + receipt 파일 `revoked_at` set.
- Test 2 `test_fail_closed_no_hmac`: HMAC 키 파일 삭제 → request 송출 → response `ok=False, error="ledger_key_missing"` + ledger.append 호출 0회.
- Test 3 `test_not_found`: 존재하지 않는 receipt_id → response `ok=False, error="not_found"`.
- Test 4 `test_idempotent_double_revoke`: 동일 receipt 2회 revoke → 첫 응답 `ok=True`, 두번째 `ok=False, error="already_revoked"` + ledger record 정확히 1개.
- Test 5 `test_otel_span_emitted`: span exporter mock 으로 `kosmos.consent.revoke` span 1건 capture.

TS (`bun:test` + mock transport):
- Test 1 `test_request_response_match`: mock backend 가 동일 `request_id` 로 응답 → promise resolve `ok=True`.
- Test 2 `test_timeout`: 5초 후 응답 없음 → promise resolve `ok=false, error="timeout"`.
- Test 3 `test_late_response_ignored`: timeout 후 backend 응답 도착 → 두번째 promise 호출 없음 (R-02 risk).
- Test 4 `test_error_routing`: backend `error="not_found"` 응답 → promise `ok=false, error="not_found"`.

**Acceptance** (FR-F02, FR-F03):
- `pytest test_consent_revoke_dispatch.py` 5 case PASS.
- `bun test consentBridge.test.ts` 4 case PASS.

**Dependencies**: T003 + T004 + T006.

---

### T006 [P] [US1] `consentBridge.ts` 신규 모듈 + replBridge subscriber wire

**Files**:
- `tui/src/services/ipc/consentBridge.ts` (신규)
- `tui/src/bridge/initReplBridge.ts` 또는 등가 (수정 — `consent_revoke_response` arm subscriber 등록)

**Reference baseline**:
- `tui/src/bridge/replBridgeHandle.ts` — Spec 1978 ChatRequestFrame singleton transport 패턴
- `tui/src/bridge/replBridge.ts` — frame send/dispatch 패턴

**Implementation**: plan.md § 1.4 sketch 그대로:
- Module-level `_pending: Map<string, {resolve, timer}>`.
- `requestRevoke(receiptId, options): Promise<RevokeBridgeResult>` — ULID 생성 + timeout setTimeout + frame send.
- `_handleConsentRevokeResponse(frame)` — `_pending.get(request_id)` 매칭 + clearTimeout + resolve.
- `RevokeBridgeResult` 타입 export.
- `initReplBridge` (또는 등가 mount-time wire-up) 에 `consent_revoke_response` arm subscriber 로 `_handleConsentRevokeResponse` 등록.

**Acceptance** (FR-B01..B05):
- `requestRevoke` 가 promise 반환 + timeout 동작.
- subscriber wire 가 mount 시점에 등록.
- `_pending` map cleanup 정상 (no leak).

**Dependencies**: T003 ([P] — T001 과 병렬 가능, frame schema 만 선행 필요).

---

## Phase US2+US3 — Invalid input fail-soft + backend fail-closed + REPL 분기

### T007 [US2+US3] REPL.tsx `subCmd === 'revoke'` 분기 재작성 + dangling reference 정리 + 통합 테스트

**Files**:
- `tui/src/screens/REPL.tsx` (수정 — `:3685-3691` 교체)
- `tui/src/commands/consent.ts` (수정 — `:10`, `:83` 코멘트의 `consentBridge.ts` → `consentBridge.js` 경로 정정)
- `tui/src/screens/__tests__/REPL.consent-revoke.test.tsx` (신규)

**Reference baseline**:
- `tui/src/screens/REPL.tsx:3664-3693` — 기존 `_kosmosCmd === 'consent'` 분기
- `tui/src/screens/REPL.tsx:3623-3644` — `/export` ToolJSX mount 패턴 (`isLocalJSXCommand: false` 정답 사례)

**Implementation**: plan.md § 1.5 sketch 그대로:
- `parseConsentArgs(_kosmosArgs)` 호출 + 4 분기 (`unknown` / `not found` / `already revoked` / 모달 mount).
- `consentBridge.requestRevoke()` 호출 + 성공 시 `permissionReceiptsCtx.revokeReceipt()` + 토스트.
- 실패 시 error code 별 토스트 (FR-E02).
- 기존 placeholder `addNotification({key: 'kosmos-consent-revoke', text: '... (P5 연동 예정)', ...})` 라인 완전 삭제 (FR-E03).
- `tui/src/commands/consent.ts:10` 의 `consentBridge.ts` 코멘트 → `consentBridge.js` 로 (TS extension is `.ts`, but Bun import resolves `.js`); `:83` 동일 정정.

통합 테스트:
- Test 1 `test_revoke_modal_mounts_on_valid_id`: receipt 1건 setup → `/consent revoke <id>` → `lastFrame()` 에 모달 마크 (`철회` 단어 등).
- Test 2 `test_invalid_format_no_modal`: `/consent revoke abc` → 모달 미표시 + notification 토스트 "유효하지 않은 형식".
- Test 3 `test_not_found_no_modal`: 빈 receipt 상태 + `/consent revoke rcpt-XXX` → notification "찾을 수 없음".
- Test 4 `test_already_revoked_no_modal`: receipt 1건 + 미리 `revokeReceipt` mutation → `/consent revoke <id>` → notification "이미 철회됨".
- Test 5 `test_confirm_y_calls_bridge`: mock `requestRevoke` resolve `ok=True` → `permissionReceiptsCtx.revokeReceipt` 호출 + 토스트 "철회 완료".
- Test 6 `test_cancel_n_no_bridge_call`: `N` 누름 → mock `requestRevoke` 호출 0회 + ledger 변경 0.
- Test 7 `test_bridge_error_no_state_mutation`: mock `requestRevoke` resolve `ok=false, error="ledger_key_missing"` → `revokeReceipt` 호출 0회 + 에러 토스트.

**Acceptance** (FR-E01..E04, FR-F04):
- `REPL.tsx:3686-3690` placeholder 라인 삭제 확인 (`grep -n "P5 연동 예정" REPL.tsx` 결과 0).
- `bun test REPL.consent-revoke.test.tsx` 7 case PASS.
- `tui/src/commands/consent.ts` 의 dangling reference 정정 확인.

**Dependencies**: T001 + T006.

---

## Phase Polish — Smoke + Closure + PR

### T008 [Polish] Layer 4/5 smoke + Spec 1635 closure + PR 본문 작성

**Files**:
- `specs/2767-consent-revoke-modal/scripts/smoke-revoke.sh` (신규 — tmux capture-pane)
- `specs/2767-consent-revoke-modal/smoke-revoke.tape` (신규 — vhs)
- `specs/2767-consent-revoke-modal/smoke-keyframe-{1-prompt,2-modal,3-confirm,4-toast,5-list}.png` (신규 — 5 PNG keyframes)
- `specs/2767-consent-revoke-modal/smoke-revoke.txt` (신규 — vhs `.txt` golden file)
- `specs/2767-consent-revoke-modal/smoke-revoke.gif` (신규 — vhs `.gif` 보조)
- `specs/2767-consent-revoke-modal/frames/snap-{001-006}-*.txt` (신규 — tmux 시나리오 snapshot)
- `specs/1635-ui-l2-citizen-port/closure-2767.md` (신규 — Spec 1635 P4 US2 마감 노트)
- `specs/2767-consent-revoke-modal/dispatch-tree.md` (신규 — Layer 1/2 parallelism 기록)
- `specs/2767-consent-revoke-modal/pr-description.md` (신규 — PR body draft)

**Reference baseline**:
- `scripts/tui-tmux-capture.sh` — KOSMOS tmux 시나리오 harness (Spec debug-infra-rebuild)
- `tui/src/test-utils/waitForFrame.ts` — Bubble Tea `teatest.WaitFor` 패턴 포팅
- `specs/2521-llm-swap-cc-rebuild/scripts/text-debug-smoke.sh` — vhs `.tape` 패턴 참고
- AGENTS.md "TUI verification methodology" Layer 4/5

**Implementation**:

`smoke-revoke.sh` (Layer 5 tmux):
```bash
# 6단계 시나리오:
# 1. boot → wait_for_pane "tool_registry: \\d+ entries verified"
# 2. send "/consent list\r" → wait_for_pane "권한 영수증" → snap-001
# 3. (테스트 setup: 1건 mock receipt 사전 주입)
# 4. send "/consent revoke rcpt-TEST01\r" → wait_for_pane "한번만 철회" → snap-002
# 5. send "Y" → wait_for_pane "철회 완료" → snap-003 + snap-004
# 6. send "/consent list\r" → wait_for_pane "\\[REVOKED\\]" → snap-005
```

`smoke-revoke.tape` (Layer 4 vhs):
```
Output specs/2767-consent-revoke-modal/smoke-revoke.gif
Output specs/2767-consent-revoke-modal/smoke-revoke.txt   # Golden file (LLM-readable)
Output specs/2767-consent-revoke-modal/smoke-revoke.ascii # Plain ASCII fallback

Set Width 120
Set Height 40

# 3+ named PNG keyframes (FR-F05 + AGENTS.md Layer 4)
Type "/consent list" Enter
Sleep 1s
Screenshot specs/2767-consent-revoke-modal/smoke-keyframe-1-list.png
Type "/consent revoke rcpt-TEST01" Enter
Sleep 1s
Screenshot specs/2767-consent-revoke-modal/smoke-keyframe-2-modal.png
Type "Y"
Sleep 1s
Screenshot specs/2767-consent-revoke-modal/smoke-keyframe-3-toast.png
Type "/consent list" Enter
Sleep 1s
Screenshot specs/2767-consent-revoke-modal/smoke-keyframe-4-revoked.png
```

`closure-2767.md` (Spec 1635 closure note):
- Spec 1635 P4 US2 의 FR-019 (`/consent list`) 는 이미 PASS 상태.
- FR-020 (`/consent revoke` 확인 모달) — 본 Epic merge 로 PASS 전환.
- FR-021 (idempotent revoke) — 본 Epic FR-D04 + T005 test 4 로 PASS 전환.
- 변경 미발생 항목 명시 (`PermissionReceiptContext.revokeReceipt` API 시그니처 무수정).
- Spec 1635 의 deferred sub-issue 상태 갱신 instruction.

`dispatch-tree.md` (메모리 `feedback_dispatch_unit_is_task_group` 준수):
- Layer 1: 본 Epic 단일 Lead Opus.
- Layer 2: Phase Foundational sonnet-component, Phase US1 sonnet-ipc + sonnet-bridge 병렬, Phase US2+US3 sonnet-repl-wire, Phase Polish Lead solo.

`pr-description.md` (PR body draft):
- Summary (3 bullets): 모달 + IPC bridge + Spec 1635 P4 closure.
- Changes (Group A/B/C/D/E/F 매핑).
- Verification (Layer 1-5 캡처 link).
- Closes: `Closes #<Epic-issue>` only (메모리 `feedback_pr_closing_refs`).

**Acceptance** (FR-F05, SC-08, SC-09, SC-10):
- 5+ PNG keyframes commit.
- `smoke-revoke.txt` golden file commit.
- `frames/snap-{001-006}-*.txt` 6+ tmux snapshot commit.
- `closure-2767.md` 작성 + Spec 1635 sub-issue 상태 변경 instruction.
- `dispatch-tree.md` commit.
- `pr-description.md` 작성.

**Dependencies**: T001-T007 모두.

---

## Dependency Graph

```
T001 ─┐
      ├─ T002 (Foundational complete)
      │
T003 ─┼─ T004 ─┐
      │        ├─ T005 (US1 IPC test complete)
      ├─ T006 ─┘
      │
T001 ─┴─ T006 ──┬─ T007 (US2+US3 wire complete)
                │
T001-T007 ───── T008 (Polish complete)
```

## Parallelism Markers

- **[P] T001 + T003 + T006**: 서로 다른 파일 트리 (TS component / Python schema / TS service) — 병렬 dispatch 안전.
- **순차**: T002 → T001, T004 → T003, T005 → T003+T004+T006, T007 → T001+T006, T008 → all.

## File-Change Budget Check (메모리 `feedback_dispatch_unit_is_task_group`)

각 sonnet teammate ≤ 5 task / ≤ 10 file:
- sonnet-component (T001+T002): 2 file (1 component + 1 test). PASS.
- sonnet-ipc (T003+T004+T005-py): 3 file (frame_schema.py + stdio.py + test_consent_revoke_dispatch.py). PASS.
- sonnet-bridge (T006+T005-ts): 3 file (consentBridge.ts + initReplBridge.ts wire + consentBridge.test.ts). PASS.
- sonnet-repl-wire (T007): 3 file (REPL.tsx + consent.ts + REPL.consent-revoke.test.tsx). PASS.
- Lead Opus (T008): 9 file (smoke + closure + dispatch-tree + pr-description). PASS.

총 file change: ~20. Spec scope 적정.

## Out-of-Tasks Items (메모리 `feedback_deferred_sub_issues`)

본 Epic 의 OOS 항목은 별도 sub-issue 로 추적 (Constitution §VI):
- OOS-01: Persistent rule-level revoke → Spec 033 의 별도 sub-issue.
- OOS-02: Ledger 검증 CLI → Spec 033 의 별도 sub-issue.
- OOS-03: `/consent revoke --all` → 본 Epic merge 후 신규 spec.
- OOS-04: `/consent show rcpt-<id>` → Spec 1635 의 별도 sub-issue.
- OOS-05: 일본어 모달 텍스트 → 다국어 Initiative 의 별도 sub-issue.
