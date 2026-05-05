# Feature Specification: /consent revoke 확인 모달 + consentBridge.ts IPC 라운드트립

**Feature Branch**: `2767-consent-revoke-modal`
**Created**: 2026-05-04
**Status**: Draft
**Epic**: TBD (Initiative #2290 산하, P4 UI L2 잔여 결함)
**Input**: Lead-S5 audit (snap-006 ≡ snap-007 byte-identical) — `/consent revoke <rcpt-id>` 분기가 placeholder `addNotification` 토스트만 띄우고 모달 자체가 mount 되지 않음. Spec 1635 P4 US2 T032/T033 의 `parseConsentArgs()`, `executeConsentRevoke()`, `buildRevokeConfirmText()` 셋 다 callsite=0 로 cold-store 상태. `tui/src/commands/consent.ts:10,83` + `tui/src/screens/REPL.tsx:3688` 코멘트가 모두 dangling reference to 비존재 파일 `consentBridge.ts`.

## Methodology — what makes this Epic different

Spec 1635 P4 의 receipt-list 경로(US2 T031)는 byte-copy + IPC 우회로 출시되었지만, **revoke 경로는 in-memory `revokeReceipt()` mutation 만 도착하고 ledger append 까지 도달하지 못함**. 본 Epic 은 Spec 033 (PIPA Consent Ledger) 의 backend 면을 재사용하면서, TUI 측 누락 3 layer 를 한꺼번에 마감한다:

1. **Layer L1 — UI confirm modal**: `ConsentRevokeConfirmDialog` 컴포넌트 (Spec 035 `ExportPdfDialog` 패턴 기반). `[Y 한번만 / A 영구 철회 / N 취소]` 3-key 결정. `isLocalJSXCommand: false` + 자체 `useInput` Esc fallback (AGENTS.md "Infrastructure insights" #3, #4).

2. **Layer L2 — IPC bridge module**: `tui/src/services/ipc/consentBridge.ts` 신규. Spec 032 envelope 의 기존 `permission_response` arm 을 재사용하지 않고 (request/decision 짝은 prompt-driven), **신규 arm `consent_revoke_request` / `consent_revoke_response` (arm 22/23)** 를 추가하여 receipt revoke 라이프사이클을 모델링. backend 는 `kosmos.permissions.ledger.append(action="withdraw", ...)` 를 호출하고 응답에 `revoked_at` 타임스탬프 + ledger record_hash 를 포함.

3. **Layer L3 — REPL.tsx wire-up**: `_kosmosCmd === 'consent'` 분기의 `subCmd === 'revoke'` 가지에서 (a) `parseConsentArgs(_kosmosArgs)` 호출, (b) 검증 통과 시 `setToolJSX({jsx: <ConsentRevokeConfirmDialog .../>, isLocalJSXCommand: false})` mount, (c) confirm 시 `consentBridge.requestRevoke(receiptId)` 호출 → `revokeReceipt()` 로컬 mutation + 서버 응답으로 `revoked_at` 동기화.

CC 원본 등가물이 없는 KOSMOS-only 컴포넌트이므로 Spec 2521 § Step C ("KOSMOS-only file behavior-mirror phase") 절차 적용 — 가장 가까운 CC analog 인 `ExportPdfDialog` (Spec 035 P4 ported) 의 dialog shell + key-handling 구조를 line-cited 로 재사용한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 시민이 잘못 발급한 영수증을 철회한다 (Priority: P1)

시민이 `/consent list` 로 현재 세션 영수증 목록을 확인한 후, 의도치 않게 발급한 영수증 (`rcpt-01HX2K3M4N5P6Q7R8S9T`) 을 철회하기로 결정한다. `/consent revoke rcpt-01HX2K3M4N5P6Q7R8S9T` 입력 → 확인 모달이 표시된다. 모달은 (a) 영수증 ID, (b) 영수증의 `tool_name` + `decision` + `decided_at`, (c) 철회의 PIPA §36 (정정·삭제권) 근거 안내, (d) 3-key 옵션 (`Y 한번만 / A 영구 철회 / N 취소`) 을 보여준다. 시민이 `Y` 누름 → consentBridge 가 `consent_revoke_request` frame 송출 → backend 가 ledger 에 `action=withdraw` 레코드 append + receipt 의 `revoked_at` 갱신 → backend 가 `consent_revoke_response{revoked_at, record_hash}` 반환 → TUI 의 `PermissionReceiptContext.revokeReceipt()` 가 in-memory state 갱신 → 모달 dismiss + `addNotification` "영수증 철회 완료: rcpt-…" 토스트 표시 → `/consent list` 재실행 시 해당 영수증 row 가 `[REVOKED]` 마크와 빨강 색으로 표시.

**Why this priority**: Constitution §V (PIPA §36 정정·삭제권) 의 핵심. 철회 UI 가 없으면 KOSMOS 는 PIPA 위반 상태로 출시 불가. 동시에 Spec 1635 P4 US2 의 acceptance criterion (FR-020 + FR-021) 미충족 잔존 결함.

**Independent Test**: 세션에서 mock receipt 1건 발급 → `/consent list` → revoke 입력 → 모달 표시 확인 → `Y` confirm → IPC frame 페어 (`consent_revoke_request` → `consent_revoke_response`) 가 stdio JSONL 에 기록되는지 확인 → ledger JSONL 의 마지막 record `action=withdraw` 검증 → `/consent list` 재실행 시 `[REVOKED]` 표시 확인. 6단계 모두 PTY frames + Python pytest 로 검증 가능.

**Acceptance Scenarios**:

1. **Given** 세션에 1건 이상의 활성 영수증, **When** 시민이 `/consent revoke rcpt-<유효-id>` 입력, **Then** `ConsentRevokeConfirmDialog` 가 mount 되고 모달은 영수증 ID + `tool_name` + `decision` + `decided_at` + PIPA §36 근거 + 3-key 옵션 (`Y/A/N`) 을 표시.
2. **Given** revoke 모달 표시, **When** 시민이 `Y` 또는 `A` 누름, **Then** consentBridge 가 `consent_revoke_request` frame 송출 → backend 가 ledger 에 `action=withdraw, scope=previous_receipt_id, withdrawn_at=<ISO8601>` append → `consent_revoke_response{revoked_at, record_hash}` 반환 → 모달 dismiss + 토스트 표시.
3. **Given** revoke 모달 표시, **When** 시민이 `N` 또는 `Esc` 누름, **Then** 모달 dismiss + IPC frame 송출 없음 + ledger 변경 없음 + `revokeReceipt()` 호출 없음.
4. **Given** revoke 후 세션 유지, **When** 시민이 `/consent list` 재실행, **Then** 해당 영수증 row 가 `[REVOKED]` suffix + `theme.error` 색으로 표시되고 timestamp 가 revoked_at 으로 표시.

---

### User Story 2 — 잘못된 receipt ID 또는 이미 철회된 영수증 (Priority: P1)

시민이 형식이 잘못된 ID (`/consent revoke abc123`) 또는 존재하지 않는 ID (`rcpt-NONEXISTENT`) 또는 이미 철회된 ID (`rcpt-…` with `revoked_at != null`) 를 입력한다. 각 경우는 모달을 띄우지 않고 즉시 inline 토스트 메시지로 처리된다 (PIPA §36 의 idempotent 정정·삭제 의도 보존 — 실패 케이스에 추가 모달 부담을 지우지 않음).

**Why this priority**: FR-021 의 idempotent 보장 + edge-case fail-soft. P1 인 이유는 잘못된 입력이 모달을 띄운 채 무한 루프 가능성을 차단해야 하기 때문.

**Independent Test**: 4개 케이스 (형식 무효 / 존재하지 않음 / 이미 철회됨 / 빈 인자) 각각 입력 → 모달 미표시 + 케이스별 토스트 메시지 확인. PTY frame snapshot 으로 검증.

**Acceptance Scenarios**:

1. **Given** 임의 세션 상태, **When** 시민이 `/consent revoke abc123` (rcpt- 접두사 없음) 입력, **Then** 모달 미표시 + `addNotification`: "유효하지 않은 영수증 ID 형식: abc123" 토스트.
2. **Given** 세션에 receipt `rcpt-A` 만 존재, **When** 시민이 `/consent revoke rcpt-NONEXISTENT` 입력, **Then** 모달 미표시 + `addNotification`: "영수증을 찾을 수 없음: rcpt-NONEXISTENT" 토스트.
3. **Given** receipt `rcpt-A` 가 이미 revoked 상태, **When** 시민이 `/consent revoke rcpt-A` 입력, **Then** 모달 미표시 + `addNotification`: "이미 철회된 영수증: rcpt-A" (FR-021 idempotent — ledger 추가 entry 없음).
4. **Given** 임의 세션 상태, **When** 시민이 `/consent revoke ` (인자 빈 문자열) 입력, **Then** 모달 미표시 + `addNotification`: "사용법: /consent revoke <receipt-id>" 토스트.

---

### User Story 3 — Backend 응답 실패 시 fail-closed (Priority: P2)

backend 가 ledger 쓰기 실패 (HMAC 키 부재 / 디스크 가득 / 파일 권한 오류) 시 `consent_revoke_response{ok: false, error: <ErrorCode>}` 를 반환한다. TUI 는 in-memory `revokeReceipt()` 를 호출하지 **않고** (rollback), 모달을 닫고 에러 envelope 을 표시한다. 시민이 같은 ID 로 재시도 시 다시 모달이 정상 표시된다 (in-memory state 변경 없으므로).

**Why this priority**: Spec 033 §US2 시나리오 3 의 fail-closed 동작과 정합. P2 인 이유는 happy path 가 P1 으로 우선되며, 본 케이스는 운영 환경에서 드물게 발생.

**Independent Test**: backend mock 으로 `consent_revoke_response{ok: false, error: "ledger_key_missing"}` 강제 반환 → 모달 confirm → in-memory receipt 상태 unchanged 확인 + 에러 토스트 표시 + 같은 ID 로 재실행 시 모달 정상 mount.

**Acceptance Scenarios**:

1. **Given** backend 가 `ledger_key_missing` 에러 반환, **When** 시민이 모달에서 `Y` 누름, **Then** in-memory `revokeReceipt()` 호출 없음 + 모달 dismiss + `addNotification`: "철회 실패: HMAC 키 부재 — ledger 키 초기화 필요" 토스트 + 종료.
2. **Given** backend 응답이 timeout (5초 초과), **When** 시민이 모달에서 `Y` 누름, **Then** in-memory mutation rollback + 토스트 + 모달 dismiss.
3. **Given** 위 실패 후, **When** 시민이 같은 receipt ID 로 `/consent revoke` 재실행, **Then** receipt 가 in-memory state 에서 여전히 unrevoked 이므로 모달 정상 mount.

---

### Edge Cases

- **빈 receipts 상태에서 /consent revoke 입력**: US2 시나리오 2 분기 (not_found) 와 동일하게 처리.
- **모달 mount 중 새 IPC frame 도착**: ToolJSX overlay 는 frame 이벤트 차단하지 않음 (Spec 1635 패턴). 모달은 mount 시점의 receipt snapshot 을 사용.
- **모달 mount 중 세션 변경 (`/resume <id>` 등)**: ToolJSX overlay 가 active 인 동안 session swap 은 차단되지 않으나, 모달의 receiptId 가 새 세션에 존재하지 않으면 `Y` confirm 시 backend 가 `not_found` 반환 → US3 시나리오와 동일 처리.
- **i18n locale=en 시 모달 텍스트**: `getUiL2I18n('en')` 사용; `buildRevokeConfirmText(receiptId, 'en')` 의 `Revoke <id>? (Y/N)` 메시지 + 영문 PIPA §36 안내 ("Right to correction & deletion under PIPA §36").
- **A 옵션 (영구 철회) 의 의미**: 기본 `Y`(once) 와 backend 동작이 동일 (영수증 1건 철회는 본질적으로 단발 액션). `A` 는 향후 "동일 tool 의 모든 미사용 영수증 일괄 철회" 확장을 위한 예약. P1 범위에서는 `A == Y` 로 처리하되 ledger 의 `scope=once_via_a_key` 로 별도 마킹.

## Requirements *(mandatory)*

### Functional Requirements

#### Group A — UI Confirm Modal (US1, US2)

- **FR-A01**: `tui/src/components/consent/ConsentRevokeConfirmDialog.tsx` 신규 컴포넌트는 props `{receipt: PermissionReceiptT, onConfirm: (decision: 'once' | 'session-all') => void, onCancel: () => void, locale?: 'ko' | 'en'}` 을 받는다.
- **FR-A02**: 모달은 영수증 메타데이터 (`receipt_id`, `tool_name`, `decision`, `decided_at`) 4종 + PIPA §36 근거 한 줄 + 3-key 옵션 표시줄 (`[Y] 한번만 철회 · [A] 영구 철회 · [N] 취소`) 을 렌더한다.
- **FR-A03**: `useInput` 으로 `y/Y` → `onConfirm('once')`, `a/A` → `onConfirm('session-all')`, `n/N` 또는 `key.escape` → `onCancel()`. 기타 키는 무시.
- **FR-A04**: 모달 mount 시 `setToolJSX({..., isLocalJSXCommand: false, shouldHidePromptInput: false})` 를 사용하여 부모 `useInput` 훅을 비활성화하지 않음 (AGENTS.md "Infrastructure insights" #3).
- **FR-A05**: `ConsentRevokeConfirmDialog` 컴포넌트는 자체 `useInput((_, key) => key.escape && onCancel())` Esc fallback 을 보유 (AGENTS.md "Infrastructure insights" #4 — `defaultBindings.ts` 에 `consent:revoke:dismiss` 미등록).

#### Group B — IPC Bridge (US1, US3)

- **FR-B01**: `tui/src/services/ipc/consentBridge.ts` 신규 모듈은 `requestRevoke(receiptId: string, options?: {scope?: 'once' | 'session-all', timeoutMs?: number}): Promise<RevokeBridgeResult>` 함수를 export.
- **FR-B02**: `RevokeBridgeResult = {ok: true, revoked_at: string, record_hash: string} | {ok: false, error: 'ledger_key_missing' | 'not_found' | 'already_revoked' | 'timeout' | 'unknown'}`.
- **FR-B03**: `requestRevoke` 는 IPC envelope `consent_revoke_request{kind: 'consent_revoke_request', request_id: <ULID>, receipt_id, scope}` 송출 후 `consent_revoke_response{request_id: <matching>, ok, ...}` 응답 대기. 5초 타임아웃 시 `{ok: false, error: 'timeout'}`.
- **FR-B04**: `requestRevoke` 는 promise resolution 시점에 in-memory state mutation 호출하지 않음. mutation 책임은 caller (REPL.tsx) 에 위임.
- **FR-B05**: `consentBridge` 는 module-level singleton transport handle 을 사용 (Spec 1978 ChatRequestFrame 의 `replBridgeHandle.ts` 패턴 준용).

#### Group C — IPC Frame Schema (US1, US3)

- **FR-C01**: `src/kosmos/ipc/frame_schema.py` 에 신규 arm 2종 추가:
  - `ConsentRevokeRequestFrame` (TUI → backend, `kind="consent_revoke_request"`, `request_id: ULID`, `receipt_id: str`, `scope: Literal["once", "session-all"]`).
  - `ConsentRevokeResponseFrame` (backend → TUI, `kind="consent_revoke_response"`, `request_id: ULID`, `ok: bool`, `revoked_at: str | None`, `record_hash: str | None`, `error: Literal[...] | None`).
- **FR-C02**: `KIND_TO_ROLE_ALLOWLIST` 에 `consent_revoke_request: {tui}`, `consent_revoke_response: {backend}` 추가 (Spec 032 E3 invariant 준수).
- **FR-C03**: `tui/src/ipc/frames.generated.ts` 는 `bun run codegen:ipc` (또는 동급 build script) 로 재생성하여 22번/23번 arm 추가. 수동 편집 금지.
- **FR-C04**: `IPCFrame` discriminated union 갱신 + `__all__` export 갱신 (Python) / typegen 출력 (TS).

#### Group D — Backend Handler (US1, US3)

- **FR-D01**: `src/kosmos/ipc/stdio.py` 에 `consent_revoke_request` arm dispatcher 추가. handler 는 (a) receipt 디렉토리 (`~/.kosmos/memdir/user/consent/<receipt_id>.json`) 존재 확인, (b) `kosmos.permissions.ledger.append(action="withdraw", ...)` 호출, (c) receipt JSON 파일에 `revoked_at` 필드 갱신 (atomic temp+rename), (d) `consent_revoke_response{ok: true, revoked_at, record_hash}` 송출.
- **FR-D02**: HMAC 키 부재 시 `consent_revoke_response{ok: false, error: "ledger_key_missing"}` 즉시 반환 (ledger.append 호출 없음, fail-closed).
- **FR-D03**: receipt 파일 부재 시 `{ok: false, error: "not_found"}` 반환.
- **FR-D04**: receipt 의 `revoked_at` 이 이미 set 인 경우 `{ok: false, error: "already_revoked"}` 반환 + ledger 추가 entry 없음 (FR-021 idempotent).
- **FR-D05**: ledger record 의 `action="withdraw"`, `scope=<original receipt_id>`, `decision="denied"`, `withdrawn_at=<ISO8601 UTC>` 4 필드 필수 기록.

#### Group E — REPL Wire-up (US1, US2, US3)

- **FR-E01**: `tui/src/screens/REPL.tsx` 의 `_kosmosCmd === 'consent'` + `subCmd === 'revoke'` 분기를 `parseConsentArgs(_kosmosArgs)` 호출 기반으로 재작성. dispatch:
  - `parsed.sub === 'unknown'` → 토스트 "사용법: /consent revoke <receipt-id>" + 종료.
  - `parsed.sub === 'revoke'` + `permissionReceiptsRef.current` 에 receiptId 미존재 → 토스트 "영수증을 찾을 수 없음: ..." + 종료.
  - `parsed.sub === 'revoke'` + `isReceiptRevoked(target)` true → 토스트 "이미 철회된 영수증: ..." + 종료.
  - 그 외 → `setToolJSX({jsx: <ConsentRevokeConfirmDialog receipt={target} onConfirm={...} onCancel={...} />, isLocalJSXCommand: false})`.
- **FR-E02**: 모달 `onConfirm` 핸들러는 (a) `consentBridge.requestRevoke(receiptId, {scope})` 호출, (b) 응답 `ok: true` 시 `permissionReceiptsCtx.revokeReceipt(receiptId)` + "철회 완료" 토스트, (c) `ok: false` 시 error code 별 토스트, (d) 모달 dismiss.
- **FR-E03**: 기존 placeholder `addNotification({key: 'kosmos-consent-revoke', text: '... (P5 연동 예정)', ...})` 라인 (`REPL.tsx:3686-3690`) 완전 제거.
- **FR-E04**: dangling reference comment 정리 — `tui/src/commands/consent.ts:10` + `:83` 의 `consentBridge.ts` 참조를 실제 모듈 경로 (`../services/ipc/consentBridge.js`) 로 갱신.

#### Group F — Test Coverage (US1, US2, US3)

- **FR-F01**: `tui/src/components/consent/__tests__/ConsentRevokeConfirmDialog.test.tsx` 신규 — Ink snapshot test (Layer 1b) 로 (a) 4종 메타데이터 표시, (b) `Y/A/N/Esc` 키 처리, (c) i18n ko/en locale 분기 검증.
- **FR-F02**: `tui/src/services/ipc/__tests__/consentBridge.test.ts` 신규 — mock transport 로 (a) frame 송출 + 응답 매칭, (b) 5초 타임아웃, (c) error code 라우팅 검증.
- **FR-F03**: `src/kosmos/ipc/tests/test_consent_revoke_dispatch.py` 신규 — pytest-asyncio 로 (a) handler 가 ledger 에 `action=withdraw` append, (b) HMAC 키 부재 시 fail-closed, (c) idempotent 동작 검증.
- **FR-F04**: `tui/src/screens/__tests__/REPL.consent-revoke.test.tsx` 신규 — `ink-testing-library` 로 wire-up 통합 테스트 (모달 mount → confirm → 토스트).
- **FR-F05**: AGENTS.md TUI verification chain Layer 4 (vhs `.tape`) + Layer 5 (tmux capture-pane) 시나리오 신규 — `specs/2767-consent-revoke-modal/scripts/smoke-revoke.sh` (tmux) + `smoke-revoke.tape` (vhs, 3+ PNG keyframes: pre-modal / modal-mounted / post-confirm-toast) + `smoke-revoke.txt` (vhs golden file).

### Non-Functional Requirements

- **NFR-01**: backend handler 는 ledger append 까지 200ms 이내 응답 (p95). 5초 절대 한도.
- **NFR-02**: ConsentRevokeConfirmDialog mount → first frame paint 50ms 이내 (Spec 2297 ζ-E2E primitive timeout 대응).
- **NFR-03**: 신규 runtime dependency 0 (AGENTS.md hard rule). TS: 기존 `ink`, `react`, `@inkjs/ui` 활용. Python: 기존 `pydantic`, stdlib `fcntl`, `hashlib`, `hmac` 만 활용.

## Success Criteria *(mandatory)*

- **SC-01** (US1 P1 happy path): `/consent revoke rcpt-<유효-id>` 입력 → 모달 mount → `Y` confirm → ledger record 추가 → in-memory `revokeReceipt()` 호출 → `/consent list` 재실행 시 `[REVOKED]` 표시. PTY frame snapshot 으로 5단계 모두 검증 PASS.
- **SC-02** (US1 P1 cancel path): 모달에서 `N` 또는 `Esc` → 모달 dismiss + ledger 변경 없음 + IPC frame 송출 없음. `bun test` 검증 PASS.
- **SC-03** (US2 P1 invalid input): 4 케이스 (형식 무효 / not_found / already_revoked / 빈 인자) 모두 모달 미표시 + 케이스별 토스트. `bun test` + PTY frame 검증 PASS.
- **SC-04** (US3 P2 fail-closed): backend mock 으로 `ledger_key_missing` 강제 반환 → in-memory state unchanged + 에러 토스트 + 재시도 가능. pytest 검증 PASS.
- **SC-05** (FR-021 idempotent invariant): 같은 receipt 에 대한 revoke 호출 2회 → ledger 에 `action=withdraw` record 1개만 존재 (2번째는 `already_revoked` 응답). pytest 검증 PASS.
- **SC-06** (Spec 032 envelope invariant): 신규 arm `consent_revoke_request` / `consent_revoke_response` 가 `KIND_TO_ROLE_ALLOWLIST` allow-list 통과 + `correlation_id` 보존 + ring-buffer 등록 검증 (Spec 032 SC 재사용).
- **SC-07** (Zero new runtime dependencies): `pyproject.toml` + `tui/package.json` diff 에 신규 `dependencies` entry 0개. AGENTS.md hard rule 준수.
- **SC-08** (Layer 5 smoke parity): `tui/src/screens/REPL.tsx` 변경 PR 이므로 AGENTS.md "TUI verification" 5-layer 의무 충족 — vhs `.tape` 3+ PNG keyframes + tmux capture-pane snapshots + Layer 5c frame-sequence-hash assert 모두 commit.
- **SC-09** (Dangling reference cleanup): `grep -rn "consentBridge.ts" tui/src` 결과 0건 (`consentBridge.js` 또는 `services/ipc/consentBridge` 만 매치). `grep -rn "P5 연동 예정" tui/src` 결과 0건.
- **SC-10** (Spec 1635 P4 US2 closure): Spec 1635 의 FR-020 + FR-021 (revoke 확인 + idempotent) acceptance criterion 이 본 Epic merge 후 PASS 로 전환됨을 `specs/1635-ui-l2-citizen-port/closure-2767.md` 에 명시.

## Out of Scope

- **OOS-01**: Persistent rule store 의 영구 규칙 철회 (Spec 033 FR-D02 의 rule-level `withdraw`). 본 Epic 은 receipt-level revoke 만.
- **OOS-02**: Ledger 검증 CLI (`kosmos-permissions verify-chain`). Spec 033 의 별도 트랙.
- **OOS-03**: `/consent revoke --all` (세션 전체 영수증 일괄 철회) — 본 Epic 의 `A` 키 의미 확장 케이스이지만 P2 이후.
- **OOS-04**: receipt 의 read-only 상세 보기 (`/consent show rcpt-<id>`) — Spec 1635 의 별도 후속.
- **OOS-05**: 다국어 일본어 (jp) 모달 텍스트. 현재 ko + en 만.

## References

- **AGENTS.md** — § "Infrastructure insights" #3 (`isLocalJSXCommand: false`), #4 (`useInput` Esc fallback). § "Hard rules" — zero new runtime deps.
- **docs/vision.md** — § Layer 4 Permission UX, § Layer 6 Citizen Frontend.
- **docs/requirements/kosmos-migration-tree.md** — § UI-C (Permission Gauntlet) C.4 `/consent revoke rcpt-<id>` 확인 모달.
- **specs/033-permission-v2-spectrum/spec.md** — §US2 (FR-D01..FR-D05 ledger), §FR-B01..FR-B04 (killswitch), §Edge Cases (HMAC 키 부재 fail-closed).
- **specs/033-permission-v2-spectrum/data-model.md** — § 2.1 L1-L5 ledger invariants.
- **specs/1635-ui-l2-citizen-port/spec.md** — §FR-019 `/consent list` (이미 출시), §FR-020 `/consent revoke` 확인 모달, §FR-021 idempotent revoke.
- **specs/032-ipc-stdio-hardening/spec.md** — § envelope arm 추가 절차 (E3 role allow-list, ring-buffer 등록).
- **specs/2521-llm-swap-cc-rebuild/spec.md** — § Step C (KOSMOS-only file behavior-mirror phase).
- **specs/2297-zeta-e2e-smoke/spec.md** — § primitive timeout invariant (50ms first-paint).
- **.references/claude-code-sourcemap/restored-src/src/components/PermissionRequest.tsx** — CC 2.1.88 권한 모달 dialog shell + key-handling 패턴 (research-use, byte-citation only).
- **tui/src/commands/consent.ts:10,83** — dangling reference (본 Epic 으로 정정).
- **tui/src/screens/REPL.tsx:3685-3691** — placeholder revoke 분기 (본 Epic 으로 교체).
- **tui/src/components/consent/ConsentListView.tsx** — list view 패턴 (본 Epic 의 dialog shell 참조 baseline).
