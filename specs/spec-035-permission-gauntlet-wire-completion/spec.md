# Feature Specification: Permission Gauntlet Wire 완성 (Spec 035 P5 deferred)

**Feature Branch**: `spec-035-permission-gauntlet-wire-completion`
**Created**: 2026-05-04
**Status**: Draft
**Input**: User description: "Spec 035 P5 — Permission Gauntlet wire completion. 시민이 verify/submit/subscribe 호출 시 Permission Gauntlet UX (Layer 색 모달 + Y/A/N + receipt 발급) 표시. 현 상태: useCanUseTool ccCompatDefault 가 항상 'allow' 반환 → Gauntlet 우회. addReceipt() 호출처 0. AAL → Layer 매핑 모듈 부재. PIPA §22-2 위반 (시민 권한 위임 시각적 확인 불가)."

**Epic**: TBD — Lead Opus session에서 GitHub Epic 이슈 발행 보류 (시간 사유). 본 spec 으로 작업 단위 박제.
**Parent Initiative**: [#2290 — KOSMOS DX→AX 마이그레이션](https://github.com/umyunsang/KOSMOS/issues/2290)
**Supersedes**: Spec 035 P5 (Permission Gauntlet wire) deferred 분량 — Spec 1635 PR commit 기준 미완.

**Primary upstream sources**:
- `tui/src/hooks/useCanUseTool.ts:1-55` — 현 ccCompatDefault stub (라인 48-54 하드코딩 'allow')
- `tui/src/context/PermissionReceiptContext.tsx:37-83` — `addReceipt`/`revokeReceipt` definition (caller 0개)
- `tui/src/screens/REPL.tsx:5534-5536` — "PermissionGauntletModal × 2, BypassReinforcementModal, KosmosActivePermissionGate removed. fall back to CC's canonical PermissionRequest pipeline" 주석
- `tui/src/schemas/ui-l2/permission.ts:43-51` — `LAYER_VISUAL` Layer→glyph/colorToken 매핑 (이미 존재)
- `tui/src/tools/{VerifyPrimitive,SubmitPrimitive,SubscribePrimitive,LookupPrimitive}/prompt.ts` — primitive 별 Layer 명시 (verify=Layer 1, submit/subscribe=Layer 2)
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionRequest.tsx:47-80` — CC `permissionComponentForTool(tool)` dispatcher 패턴
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionDialog.tsx` — CC 모달 골격 (Y/A/N + 메시지)
- `.references/claude-code-sourcemap/restored-src/src/hooks/useCanUseTool.tsx` — CC `(setToolUseConfirmQueue, setToolPermissionContext) → ToolUseConfirmFn` signature
- `docs/requirements/kosmos-migration-tree.md § UI-C` — Layer 색 (1=green ⓵ / 2=orange ⓶ / 3=red ⓷), `[Y / A / N]` 모달, receipt ID 표시, `/consent list`/`/consent revoke` 명령
- `specs/033-permission-v2-spectrum/spec.md` — backend permission service contract (TUI 가 invent 하지 않고 citation)
- `specs/035-onboarding-brand-port/spec.md` — Spec 1635 P4 citizen-port 의 P5 wire 가 본 spec 의 deferred 영역
- 메모리 `feedback_pr_pre_merge_interactive_test` + `feedback_vhs_tui_smoke` (TUI 변경 PR 의 5-layer 검증 필수)

**PIPA 근거 (시민 안전 invariant)**:
- 개인정보 보호법 제22조의2 (개인정보 처리방침의 평가 및 개선) — 시민이 권한 위임을 **시각적으로 확인**하지 못하면 처리방침 운영의 적정성 위반.
- 개인정보 보호법 제26조 (업무위탁에 따른 개인정보의 처리 제한) — KOSMOS 가 수탁자로서 위탁 사실을 시민에게 명시적 동의 흐름으로 전달해야 함.
- 본 spec 은 **권한 정책을 발명하지 않음** (AGENTS.md hard rule + B4 결정). 각 어댑터가 cite 하는 기관 자체 정책 + Spec 033 backend service decision 만 표시.

**Constitution constraint (non-negotiable)**:
- **Zero new runtime dependencies** (AGENTS.md hard rule). 본 spec 은 기존 `react`, `ink`, `zod`, `zustand` 만 사용.
- **CC byte-identical 우선** (CORE THESIS). 새 모달 컴포넌트 작성 금지 — CC `PermissionRequest.tsx` + `PermissionDialog.tsx` 패턴을 Layer 색 mapping 만 KOSMOS 적응.
- **Backend permission service 변경 금지** (Spec 033 영역). 본 spec 은 TUI wire-up 만 다룸.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 시민이 verify (간편인증) 호출 시 Layer 1 green 모달을 본다 (Priority: P1)

KOSMOS 사용 중 시민이 자연어로 "내 운전면허 정보 확인" 요청 → LLM 이 `verify(tool_id="kakao_pass_simple_verify")` 호출 → 어댑터의 `auth_family=simple_auth` (간편인증) → AAL2 → Permission Gauntlet 모달이 표시됨. 모달은 Layer 1 green ⓵ glyph (verify primitive 는 read-only 이므로 prompt.ts 가 Layer 1 명시) + 한국어 본문 ("간편인증 자격증명 검증을 위해 KOSMOS 가 카카오인증서로 위임 호출합니다") + `[Y 한번만 / A 세션 자동 / N 거부]` 셀렉터. 시민이 Y 또는 A 입력 시 backend permission service 가 receipt 발급 → TUI 가 `addReceipt({receipt_id, layer:1, tool_name, decision, decided_at, session_id, revoked_at:null})` 호출 → 시민에게 `rcpt-<id>` 토스트로 receipt 표시. N 입력 시 IPC 로 deny 전달, 도구 호출 차단.

**Why this priority**: verify 는 KOSMOS 의 4 primitive 중 가장 자주 호출되는 인증 primitive (간편인증·공인인증서·모바일신분증). 본 path 가 작동하지 않으면 어떤 submit/subscribe 호출도 안전하게 게이팅 불가. PIPA §22-2 의 시민 시각 확인 권리는 verify 모달 이 첫 번째 surface.

**Independent Test**: KOSMOS TUI 부팅 → 자연어 "내 카카오 인증으로 본인확인" 입력 → LLM 이 verify 호출 → (a) Layer 1 green ⓵ glyph 표시 확인, (b) 한국어 본문에 어댑터 명 + 위임 사실 명시 확인, (c) Y 입력 후 receipt ID 토스트 표시 확인, (d) `/consent list` 실행 시 해당 receipt 가 reverse-chronological 첫 번째로 표시 확인.

**Acceptance Scenarios**:

1. **Given** KOSMOS 가 부팅된 상태, **When** LLM 이 `verify(tool_id="kakao_pass_simple_verify")` 호출하고 backend permission service 가 prompt 응답 요청, **Then** Permission Gauntlet 모달이 mount 되어 Layer 1 green ⓵ glyph + 한국어 본문 + `[Y / A / N]` 셀렉터가 표시된다.
2. **Given** 모달이 표시된 상태, **When** 시민이 Y (한 번만 허용) 입력, **Then** PERMISSION_RESPONSE IPC 가 backend 로 전송되고 backend 가 `receipt_id` 반환 → TUI 가 `addReceipt({layer:1, decision:'allow_once', ...})` 호출 → `rcpt-<id>` 토스트가 표시된다.
3. **Given** 모달이 표시된 상태, **When** 시민이 A (세션 자동 허용) 입력, **Then** decision 이 `allow_session` 으로 receipt 가 발급되고 동일 세션 내 동일 `tool_name` 의 후속 verify 호출 시 모달이 다시 mount 되지 않는다 (CC `permissionContext` cache 패턴 보존).
4. **Given** 모달이 표시된 상태, **When** 시민이 N (거부) 입력, **Then** decision 이 `deny` 로 receipt 가 발급되고 LLM tool_call 결과로 권한 거부 에러가 반환되어 LLM 이 다른 경로 (수동 안내 등) 로 응답한다.
5. **Given** 모달이 표시된 상태, **When** 시민이 30초간 입력하지 않음, **Then** decision 이 `timeout_denied` 로 receipt 가 발급되고 도구 호출이 fail-closed 차단된다.

---

### User Story 2 — 시민이 submit (정부24 민원 제출) 호출 시 Layer 2 orange 모달을 본다 (Priority: P1)

시민이 "내 주민등록등본 PDF 발급" 자연어 요청 → LLM 이 `submit(tool_id="gov24_resident_registration_submit")` 호출 → 어댑터의 `pipa_class=personal_data` + `is_irreversible=true` → Layer 2 (medium-risk citizen-personal lookup, OPAQUE submit 도메인은 시나리오 핸드오프 영역이지만 Mock 어댑터의 경우 Layer 2 게이팅 표시) → orange ⓶ glyph + 본문 ("정부24 에 본인 명의로 등본 발급 요청을 제출합니다. 결제·발급 결과는 정부24 채널에서 확인됩니다") + `[Y / A / N]` 셀렉터. Y 시 receipt 발급 + 도구 dispatch.

**Why this priority**: submit primitive 는 시민 명의로 외부 기관에 변경/제출 행위를 위임하므로 Layer 2 게이팅이 PIPA §26 수탁자 책임 invariant 의 핵심. verify 와 함께 P1.

**Independent Test**: 자연어 "주민등록등본 발급" → LLM 이 submit 호출 → (a) Layer 2 orange ⓶ glyph, (b) 본문에 "본인 명의 위탁 제출" 문구, (c) Y 후 receipt + 도구 dispatch, (d) `/consent list` 에 layer=2 항목 표시.

**Acceptance Scenarios**:

1. **Given** verify 가 완료된 상태 (AAL2 보유), **When** LLM 이 submit 호출, **Then** Layer 2 orange ⓶ glyph 모달이 표시된다.
2. **Given** 모달 표시, **When** 시민이 Y 입력, **Then** receipt 가 layer=2 로 발급되고 도구가 dispatch 되어 backend 가 어댑터 호출 결과를 IPC 로 반환한다.
3. **Given** 시민이 같은 세션에서 동일 submit 어댑터를 두 번 호출, **When** 첫 호출에 A (세션 자동) 응답, **Then** 두 번째 호출은 모달 mount 없이 자동 dispatch 되고 두 번째 receipt 도 ledger 에 append 된다 (audit trail 무결성).

---

### User Story 3 — 시민이 subscribe (CBS 재난 구독) 호출 시 Layer 2 orange 모달을 본다 (Priority: P2)

자연어 "내 위치에 재난 알림 구독" → LLM 이 `subscribe(tool_id="cbs_disaster_alert")` 호출 → Layer 2 (citizen-personal location data) → orange ⓶ + 본문 ("위치 정보 기반 CBS 재난 알림 구독을 활성화합니다") + Y/A/N. 구독은 세션-수명 SubscriptionHandle 이므로 receipt 가 active subscription 의 lifetime 을 표시.

**Why this priority**: subscribe 는 verify/submit 보다 상대적 호출 빈도 낮음 (재난 알림 등 한정). P2 로 유지하되 P1 와 동일 코드 path 재사용.

**Independent Test**: 자연어 "재난 알림 구독" → subscribe 호출 → Layer 2 모달 표시 → A 응답 → SubscriptionHandle 가 receipt 와 함께 `/consent list` 에 표시.

**Acceptance Scenarios**:

1. **Given** subscribe 호출, **When** 모달 표시, **Then** Layer 2 orange ⓶ glyph + "구독 활성화" 본문이 표시된다.
2. **Given** 시민이 Y 응답, **When** SubscriptionHandle 이 backend 에서 생성, **Then** receipt 가 layer=2 로 발급되고 handle id 가 receipt 와 cross-reference 된다.

---

### User Story 4 — 시민이 lookup 호출 시 Permission Gauntlet 모달이 표시되지 않는다 (Priority: P1, negative test)

자연어 "오늘 서울 날씨" → LLM 이 `lookup(mode="fetch", tool_id="kma_short_term_forecast")` 호출 → public-data lookup (PIPA 비대상) → Permission Gauntlet 모달 mount 안 됨, 결과 즉시 표시. (CC 의 read-only tool 모달 우회 패턴 보존)

**Why this priority**: 시민이 매 lookup 호출마다 모달 보면 UX 망가짐. lookup 은 OPAQUE 어댑터 호출 시에도 backend 가 자체 게이팅 (시나리오 핸드오프 메시지) 를 사용하므로 TUI Gauntlet path 가 lookup 호출에 mount 되지 않아야 함.

**Independent Test**: 자연어 "오늘 날씨" → lookup 호출 → 모달 없음, 응답 직접 표시 → `/consent list` 비어있음 (해당 lookup 호출 receipt 없음).

**Acceptance Scenarios**:

1. **Given** LLM 이 lookup 호출, **When** backend 가 결과 반환, **Then** Permission Gauntlet 모달이 mount 되지 않고 결과가 직접 표시된다.

---

### User Story 5 — 시민이 `/consent list` 와 `/consent revoke rcpt-<id>` 를 사용할 수 있다 (Priority: P1)

시민이 receipt 발급 이력을 검토하고 특정 위임을 철회. `/consent list` → 세션 내 receipt 들이 reverse-chronological 표시 (`PermissionReceiptProvider` 의 `listReceipts()` 가 source-of-truth). `/consent revoke rcpt-abc123` → 확인 모달 → Y 시 `revokeReceipt()` 호출 → revoked_at timestamp 기록 (ledger 는 backend Spec 033 가 관리, TUI 는 read model).

**Why this priority**: 시민의 사후 통제권은 PIPA §38 (열람 등의 제한) 의 카운터파트. `/consent list` 가 receipt 목록을 보여주는 것이 본 spec User Story 1-3 의 receipt 발급의 의미를 닫음.

**Independent Test**: User Story 1-3 시나리오 후 `/consent list` 실행 → 발급된 receipt 들이 표시 → `/consent revoke rcpt-<id>` → 확인 → `revoked_at` 표시.

**Acceptance Scenarios**:

1. **Given** 세션에서 receipt 3개 발급된 상태, **When** `/consent list` 실행, **Then** receipt 3개가 reverse-chronological (newest first) 로 표시되고 각 항목에 layer glyph + tool_name + decision + decided_at 가 표시된다.
2. **Given** receipt 가 표시된 상태, **When** `/consent revoke rcpt-<id>` 실행, **Then** 확인 모달이 표시되고 Y 응답 시 `revokeReceipt()` 가 호출되어 revoked_at 이 표시된다.
3. **Given** 이미 revoked 된 receipt, **When** 동일 receipt_id 로 다시 revoke 실행, **Then** "이미 철회됨" 토스트 표시 (FR-021 idempotent, `revokeReceipt` 가 `'already_revoked'` 반환).

---

## Functional Requirements

### Wire 복구 (P1)
- **FR-001**: `tui/src/hooks/useCanUseTool.ts` 의 `ccCompatDefault` (라인 48-54) 의 하드코딩 `behavior: 'allow'` 를 제거하고 CC `(setToolUseConfirmQueue, setToolPermissionContext) → ToolUseConfirmFn` signature 로 복원한다. ToolUseConfirmFn 은 (a) primitive 가 lookup 이면 즉시 `{behavior:'allow'}` 반환 (User Story 4), (b) primitive 가 verify/submit/subscribe 이면 `setToolUseConfirmQueue` 에 enqueue 후 promise pending → 시민 응답 시 resolve.
- **FR-002**: `useCanUseTool` 의 named export `useCanUseTool()` (라인 28-40) 는 기존 store-driven path 를 유지하되 새 default export 와 일관성 검증 (단일 source-of-truth). store 의 `pending_permission` 이 set 되는 시점은 backend 의 `permission_request` IPC frame 수신 시.
- **FR-003**: `tui/src/context/PermissionReceiptContext.tsx` 의 `addReceipt` 호출 site 를 최소 1곳 (Permission Gauntlet 모달 의 Y/A 응답 핸들러) 에 wire-up 한다. 호출 인자는 backend 가 IPC 로 반환한 `receipt_id` + frontend 가 매핑한 `layer` + 도구 metadata 에서 추출한 `tool_name` + 시민 응답 `decision`.
- **FR-004**: Permission Gauntlet 모달 컴포넌트는 신규 작성 금지 — CC `PermissionRequest.tsx` 의 `permissionComponentForTool(tool)` switch 패턴을 KOSMOS primitive 4종 (lookup/verify/submit/subscribe) 으로 매핑하는 KOSMOS-side dispatcher 모듈 (`tui/src/components/permissions/KosmosPermissionRequest.tsx`) 을 추가한다. 각 primitive 의 모달 본문은 한국어 primary, 어댑터 metadata (tool_name + auth_family + 기관명) 를 표시.

### AAL → Layer 매핑 (P1)
- **FR-005**: 새 모듈 `tui/src/utils/permissions/aalToLayer.ts` 가 단일 source-of-truth 매핑 함수 `aalToLayer(primitive: 'lookup'|'verify'|'submit'|'subscribe', authLevel?: 'AAL1'|'AAL2'|'AAL3', isIrreversible?: boolean): PermissionLayerT` 를 export 한다. 매핑 표:

  | primitive | auth_level | is_irreversible | Layer |
  |---|---|---|---|
  | lookup | * | * | (no modal — bypass) |
  | verify | AAL1/AAL2/AAL3 | false (verify 는 read-only) | 1 (green ⓵) |
  | submit | AAL1 | false | 2 (orange ⓶) |
  | submit | AAL1 | true | 3 (red ⓷) |
  | submit | AAL2/AAL3 | false | 2 (orange ⓶) |
  | submit | AAL2/AAL3 | true | 3 (red ⓷) |
  | subscribe | AAL1 | * | 2 (orange ⓶) |
  | subscribe | AAL2/AAL3 | * | 2 (orange ⓶) |

- **FR-006**: `aalToLayer` 는 backend 에서 IPC 로 전달된 `auth_level` + `is_irreversible` 를 input 으로 받음. KOSMOS 는 primitive 별 default 매핑만 가지고 있고 backend 가 어댑터 metadata 의 published policy citation 을 cross-reference 함 (KOSMOS 가 권한 정책 invent 하지 않음 — AGENTS.md B4).
- **FR-007**: `LAYER_VISUAL` (`tui/src/schemas/ui-l2/permission.ts:43-47`) 매핑은 변경하지 않고 import 하여 재사용. 새 색상 토큰 추가 금지.

### Receipt 발급 + 표시 (P1)
- **FR-008**: 시민의 Y/A 응답 시 backend 의 `permission_response` IPC frame 송신 → backend 가 `permission_receipt` IPC frame 으로 `receipt_id` 반환 → TUI 가 `addReceipt({receipt_id, layer, tool_name, decision, decided_at, session_id, revoked_at:null})` 호출.
- **FR-009**: receipt ID 토스트는 모달 dismiss 직후 표시. 토스트 컴포넌트는 기존 `useNotifyAfterTimeout` 훅 + 기존 토스트 surface 재사용 (신규 컴포넌트 금지).
- **FR-010**: `/consent list` 명령 핸들러는 `usePermissionReceipts().listReceipts()` 호출 결과를 `ConsentListView` 컴포넌트 (`tui/src/components/consent/ConsentListView.tsx`, 이미 존재) 에 전달. 본 spec 은 이 wire 가 작동하는지만 검증하고 컴포넌트 내부 변경 없음.
- **FR-011**: `/consent revoke rcpt-<id>` 명령 핸들러는 (a) 확인 모달 표시, (b) Y 시 `revokeReceipt(id)` 호출, (c) 반환값 (`'revoked'` / `'already_revoked'` / `'not_found'`) 에 맞는 토스트 표시.

### Edge cases + fail-closed (P1)
- **FR-012**: backend 가 `permission_request` IPC frame 을 보내지 않은 채 도구 결과를 반환하면, TUI 는 fail-closed 로 LLM 에 "권한 검증 우회 감지" 에러 메시지 (구조화된 ToolResult error envelope) 를 emit 한다. 이는 backend bug 를 시민이 모르게 우회당하지 않게 하는 backstop.
- **FR-013**: 모달이 mount 된 채 IPC connection 이 dropped 되면, TUI 는 30초 timeout 후 `timeout_denied` 응답을 backend 에 send (재연결 시) + 시민에게 "권한 응답이 백엔드로 전달되지 않아 거부 처리됨" 토스트 표시.
- **FR-014**: Shift+Tab 으로 `bypassPermissions` mode 전환 시 (REPL 의 기존 mode-switch 핸들러 보존), Permission Gauntlet 모달은 여전히 mount 되지만 본문 상단에 강화된 경고 ("⚠️ bypass 모드 — 권한 검증이 비활성화되어도 시민 책임 영역") 가 표시되고 Y 입력 시 추가 확인 모달 (CC `BypassReinforcementModal` 패턴 부활) 이 표시된다. 이 fall-back 모달 컴포넌트는 CC `restored-src/src/components/permissions/PermissionExplanation.tsx` 패턴 재사용.

### 접근성 + i18n (P2)
- **FR-015**: 모달 본문은 한국어 primary, English fallback (시민 locale 이 `ko` 가 아닐 때만 fallback). 본문은 hardcoded string literal 금지 — `tui/src/i18n/permission.ko.ts` + `permission.en.ts` 에서 import.
- **FR-016**: 스크린리더 지원 — `LAYER_VISUAL[layer].ariaLabel` (이미 정의됨) 를 모달 wrapper 의 aria-label 로 출력. NO_COLOR=1 환경에서는 색 토큰 대신 `Layer N` 텍스트 prefix 표시.

### Out of scope (명시적)
- ❌ Backend permission service (Spec 033) 의 receipt 발급 로직 변경 — 본 spec 은 TUI wire-up 만 담당.
- ❌ 새 permission 정책 발명 — KOSMOS 가 권한 정책 결정 X, 어댑터 citation + Spec 033 결정 만 표시 (B4).
- ❌ Audit ledger 직접 쓰기 — TUI 는 read model only, 모든 ledger write 는 backend IPC 경유.
- ❌ ConsentListView 컴포넌트 내부 UI 변경 — 본 spec 은 wire 가 도달함만 검증.
- ❌ Onboarding 흐름의 PIPA consent step (Spec 035 P2 이미 ship 됨) 변경.

---

## Success Criteria *(measurable)*

- **SC-001**: User Story 1 시나리오 (verify 호출) 실행 시 Permission Gauntlet 모달이 Layer 1 green ⓵ glyph 와 함께 표시되고, Y 응답 후 `/consent list` 가 새 receipt 1개를 표시한다. PR 의 PTY 캡처 (`smoke-verify-modal-pty.txt`) 에서 확인.
- **SC-002**: User Story 2 시나리오 (submit 호출) 실행 시 Layer 2 orange ⓶ glyph 모달 표시, Y 응답 후 도구 dispatch 진행. PR 의 PTY 캡처 + Layer 4 vhs PNG keyframe 3종 (`smoke-keyframe-modal-shown.png`, `smoke-keyframe-y-pressed.png`, `smoke-keyframe-receipt-toast.png`) 으로 확인.
- **SC-003**: User Story 4 negative test — lookup 호출 시 모달 mount 되지 않음 확인. PTY 캡처에서 "permission_request" IPC frame 부재 + 결과 즉시 표시 확인.
- **SC-004**: `addReceipt` 호출처 ≥ 3 (verify/submit/subscribe path 각 1) — `grep -rn "\.addReceipt(" tui/src/` 로 검증.
- **SC-005**: `useCanUseTool.ts` 의 `ccCompatDefault` 의 `behavior: 'allow'` 하드코딩 제거 확인 — `grep "behavior: 'allow' as const, updatedInput: {}" tui/src/hooks/useCanUseTool.ts` 가 0 hit.
- **SC-006**: AAL→Layer 매핑 단일 모듈 (`aalToLayer.ts`) 존재 확인 + 매핑 표 8행 모두 unit test 로 검증.
- **SC-007**: `bun test` 통과 (기존 957 + 신규 ≥ 12 test = ≥ 969 pass) + `pytest` 회귀 0 (backend 변경 없음).
- **SC-008**: Zero new runtime dependencies — `tui/package.json` + `pyproject.toml` diff 0 line 추가.
- **SC-009**: Layer 5 tmux capture-pane snapshot ≥ 4 frame 캡처 (boot / 자연어 입력 / 모달 표시 / Y 응답 후 toast). `scripts/tui-tmux-capture.sh` + `wait_for_pane <regex> <deadline>` 패턴 (asciinema-in-asciinema 금지).
- **SC-010**: PIPA §22-2 시민 시각 확인 invariant — verify/submit/subscribe 호출 시나리오에서 모달이 PTY 의 첫 frame ≤ 2초 내에 mount 됨 확인 (Layer 5 frame timeline).

---

## Risks + Open Questions

- **R1**: backend (Spec 033) 의 `permission_request` IPC frame 이 현재 emit 되지 않을 수 있음. 본 spec 은 TUI side 만 다루지만 backend emit path 가 끊어져 있다면 SC-001 검증 시 모달 mount 안 됨. → Phase 0 research 에서 backend IPC frame catalog (Spec 032 monomerge frame schema) 를 확인하여 `permission_request` arm 이 alive 인지 검증 필수. dead 면 Spec 033 추가 sub-issue 발행 (별도 Epic) 필요.
- **R2**: `setToolUseConfirmQueue` 의 React state ownership 위치 — REPL.tsx 가 owner 이지만 state 가 currently dead (`toolUseConfirmQueue` 변수는 `REPL.tsx:5121` 에 남아있음). state 보존된 채 useCanUseTool wire 만 복구 가능한지 또는 state 도 다시 fully wire 필요한지 Phase 1 design 에서 결정.
- **R3**: bypass 모드 (`bypassPermissions`) 의 강화 확인 모달 (FR-014) 은 CC `BypassReinforcementModal` 이 KOSMOS 측에서 이미 제거되었음. 부활 vs CC reference 컴포넌트 그대로 import 결정 — Phase 0 research 에서 CC 코드 라인수 + KOSMOS 측 dependency 영향 확인.
- **R4**: `/consent list` 와 `/consent revoke` 명령 핸들러 위치 — `tui/src/commands/` 디렉토리에 이미 등록되어 있는지 또는 신규 등록 필요한지 Phase 0 grep 으로 확인.

---

## Dependencies

- **Spec 033** (Permission v2 spectrum) — backend permission service contract. 본 spec 은 backend 변경 X, 단지 IPC frame consumer.
- **Spec 035** (Onboarding + brand port) — PIPA consent step 이 이미 onboarding 에서 발급한 consent 가 본 spec 의 Permission Gauntlet 모달 호출 시 backend 가 cross-reference 하는 baseline.
- **Spec 1635** (UI L2 citizen port) — `PermissionReceiptContext` + `LAYER_VISUAL` + `ConsentListView` 가 이미 ship 됨. 본 spec 은 그 위에 wire 만 추가.
- **Spec 032** (IPC stdio hardening) — `permission_request` / `permission_response` / `permission_receipt` IPC frame 이 envelope 에 정의되어 있음 (확인 필요).

---

## Reference materials cross-walk

| Decision | Reference |
|---|---|
| Permission 모달 dispatcher 패턴 | `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionRequest.tsx:47-80` |
| useCanUseTool signature | `.references/claude-code-sourcemap/restored-src/src/hooks/useCanUseTool.tsx` |
| Layer 색 토큰 | `tui/src/schemas/ui-l2/permission.ts:43-47` (이미 존재) |
| PIPA §26 수탁자 책임 | `MEMORY.md project_pipa_role` + `docs/plugins/security-review.md` |
| 권한 정책 발명 금지 invariant | `AGENTS.md § L1-B B4` + `feedback_path_b_policy_derivation` |
| TUI 5-layer 검증 | `AGENTS.md § TUI verification` + `docs/testing.md § TUI verification methodology` |
| K-EXAONE reasoning latency 30-90s | `MEMORY.md feedback_debug_infra_rebuild` (Layer 5 wait_for_pane 패턴 필수) |
