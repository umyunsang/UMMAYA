# Tasks: Permission Gauntlet Wire 완성

**Spec**: [`spec.md`](./spec.md)
**Plan**: [`plan.md`](./plan.md)
**Branch**: `spec-035-permission-gauntlet-wire-completion`
**Created**: 2026-05-04

> **Dispatch policy** (`AGENTS.md § Agent Teams`): Lead Opus solo for foundational + smoke (T001-T002, T011-T012). 3 Sonnet teammates parallel for Phase 2-4 (T003-T005, T006-T008, T009-T010). 각 task ≤ 5 file 변경. 각 Sonnet teammate prompt ≤ 30 LOC.

> **Reference baseline rule** (`MEMORY.md feedback_cc_source_migration_pattern`): 모든 task 가 CC restored-src 또는 KOSMOS 기존 모듈을 reference baseline 으로 명시. 새로 작성 X — 포팅 또는 wire 복구.

> **Zero new dependency** invariant: 모든 task 는 `tui/package.json` + `pyproject.toml` 변경 없이 완료. `bun add` / `uv add` 금지.

---

## Phase 1 — Foundational (Lead solo)

### T001 — `aalToLayer.ts` 모듈 + 8-row unit test [P] [Lead Opus]

**File**: `tui/src/utils/permissions/aalToLayer.ts` (NEW), `tui/test/utils/permissions/aalToLayer.test.ts` (NEW)

**Reference baseline**:
- `tui/src/schemas/ui-l2/permission.ts:43-47` (`LAYER_VISUAL` glyph + colorToken 매핑, import 하여 재사용)
- `tui/src/tools/{VerifyPrimitive,SubmitPrimitive,SubscribePrimitive}/prompt.ts` (primitive 별 Layer 명시)
- spec FR-005 매핑 표

**Deliverables**:
1. Pure function `aalToLayer(primitive: 'lookup'|'verify'|'submit'|'subscribe', authLevel?: 'AAL1'|'AAL2'|'AAL3', isIrreversible?: boolean): PermissionLayerT | null` export.
2. `null` 반환 = lookup (modal bypass).
3. `1` = verify (모든 AAL).
4. `2` = submit (irreversible=false) 또는 subscribe.
5. `3` = submit (irreversible=true).
6. Unit test 8 row 매핑 표 검증 (spec FR-005).

**Definition of done**: `bun test tui/test/utils/permissions/aalToLayer.test.ts` 통과 (8 case green) + lint clean.

---

### T002 — `permission.ko.ts` + `permission.en.ts` i18n 카탈로그 [P] [Lead Opus]

**File**: `tui/src/i18n/permission.ko.ts` (NEW), `tui/src/i18n/permission.en.ts` (NEW)

**Reference baseline**:
- `tui/src/i18n/onboarding.ko.ts` (Spec 035 P2 패턴)
- spec FR-015 (한국어 primary, English fallback)

**Deliverables**:
1. `PERMISSION_I18N_KO` 객체 — `modalTitle.verify`, `modalTitle.submit`, `modalTitle.subscribe`, `modalBody.verify(toolName, authFamily, agency)`, `modalBody.submit(...)`, `modalBody.subscribe(...)`, `selector.allowOnce`, `selector.allowSession`, `selector.deny`, `bypassWarning`, `bypassReinforce`, `receiptToast(receiptId)`, `timeoutDeniedToast`, `failClosedError`.
2. 동일 키의 English fallback 카탈로그.
3. 각 modalBody 함수는 한국어 primary 본문 (~ 50자) 반환.

**Definition of done**: `bun typecheck` 통과 (KOSMOS narrow `src/stubs/**`) + lint clean. (Smoke 는 본 task 에서 별도 X.)

---

## Phase 2 — Hook + Components (sonnet-hook-components)

> Sonnet teammate prompt 예시 (≤ 30 LOC):
> ```
> Spec: specs/spec-035-permission-gauntlet-wire-completion/
> Tasks: T003-T005 (3 tasks, max 5 files)
> Reference baselines: per task body. CC restored-src 우선.
> Constraint: zero new dependency, CC byte-identical 우선, 기존 LAYER_VISUAL/i18n 모듈 import.
> Definition of done: bun test + bun typecheck 통과 + grep "behavior: 'allow'" useCanUseTool.ts = 0 hit.
> ```

### T003 — `useCanUseTool.ts` wire 복구 [sonnet-hook-components]

**File**: `tui/src/hooks/useCanUseTool.ts` (MODIFY)

**Reference baseline**: `.references/claude-code-sourcemap/restored-src/src/hooks/useCanUseTool.tsx` (CC signature)

**Deliverables**:
1. 라인 48-54 의 하드코딩 `behavior: 'allow' as const, updatedInput: {}` 제거.
2. `ccCompatDefault` 를 CC signature `(setToolUseConfirmQueue, setToolPermissionContext) → ToolUseConfirmFn` 로 복원.
3. ToolUseConfirmFn 내부:
   - input args 에서 primitive 추출.
   - lookup → 즉시 `{behavior: 'allow', updatedInput}` resolve.
   - verify/submit/subscribe → `setToolUseConfirmQueue(prev => [...prev, request])` enqueue + Promise pending → grant/deny callback 으로 resolve.
4. 기존 named export `useCanUseTool()` (라인 28-40, store-driven path) 는 변경 없이 유지 (단일 source-of-truth: 둘 다 store 의 `pending_permission` 사용).

**Definition of done**: `grep "behavior: 'allow' as const, updatedInput: {}" tui/src/hooks/useCanUseTool.ts` = 0 hit + `bun test tui/test/hooks/useCanUseTool.test.ts` 통과 (기존 test alive 유지).

---

### T004 — `KosmosPermissionRequest.tsx` dispatcher [sonnet-hook-components]

**File**: `tui/src/components/permissions/KosmosPermissionRequest.tsx` (NEW), `tui/test/components/permissions/KosmosPermissionRequest.test.tsx` (NEW)

**Reference baseline**:
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionRequest.tsx:47-80` (`permissionComponentForTool` switch 패턴)
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionDialog.tsx` (모달 골격, child 로 import)
- `tui/src/utils/permissions/aalToLayer.ts` (T001)
- `tui/src/i18n/permission.ko.ts` (T002)
- `tui/src/schemas/ui-l2/permission.ts` (`LAYER_VISUAL`, `PermissionReceiptT`)

**Deliverables**:
1. Functional component `<KosmosPermissionRequest>` (~ 80 LOC).
2. Props: `permissionRequest` (Spec 032 IPC frame shape), `onApprove(decision: 'allow_once'|'allow_session')`, `onDeny`, `bypassMode: boolean`.
3. 4-arm switch on `primitive`:
   - lookup: return `null` (no modal).
   - verify/submit/subscribe: 호출 `aalToLayer` → `LAYER_VISUAL[layer]` → 본문 i18n 호출 → `<PermissionDialog>` mount.
4. bypassMode=true 시 `<KosmosBypassReinforcement>` (T005) 를 wrapper 로 mount.
5. Y/A 응답 시 `onApprove(decision)` 호출 — `addReceipt` 호출은 T007 (REPL wire) 에서 수행.
6. Unit test 4 case: lookup→null, verify→Layer 1 modal, submit (irreversible=false)→Layer 2, submit (irreversible=true)→Layer 3.

**Definition of done**: 4 unit test green + ink-testing-library snapshot 안정.

---

### T005 — `KosmosBypassReinforcement.tsx` dual-confirm [sonnet-hook-components]

**File**: `tui/src/components/permissions/KosmosBypassReinforcement.tsx` (NEW), `tui/test/components/permissions/KosmosBypassReinforcement.test.tsx` (NEW)

**Reference baseline**:
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionExplanation.tsx` (CC reinforce 패턴)
- `tui/src/i18n/permission.ko.ts` `bypassWarning` + `bypassReinforce` (T002)
- spec FR-014

**Deliverables**:
1. Functional component (~ 50 LOC) wrapper around its child.
2. 첫 번째 Y 응답 시 reinforcement 모달 mount → 두 번째 Y 입력 후에만 child 의 onApprove 호출.
3. N 또는 timeout 시 즉시 deny.
4. Unit test 3 case: dual-confirm 성공, 첫 번째 N 즉시 deny, reinforcement 단계 timeout deny.

**Definition of done**: 3 unit test green + spec FR-014 본문 ("⚠️ bypass 모드…") 매치.

---

## Phase 3 — REPL wire + addReceipt (sonnet-repl-wire)

### T006 — REPL.tsx dead placeholder 제거 + KosmosPermissionRequest mount [sonnet-repl-wire]

**File**: `tui/src/screens/REPL.tsx` (MODIFY)

**Reference baseline**:
- `.references/claude-code-sourcemap/restored-src/src/screens/REPL.tsx` 의 `toolPermissionOverlay` (CC line 5121 mount 패턴)
- 현 `tui/src/screens/REPL.tsx:5121-5536` (existing toolUseConfirmQueue state + 주석)

**Deliverables**:
1. 라인 5534-5536 의 dead 모달 placeholder 주석 제거 (또는 historical-note 한 줄로 축소).
2. `<KosmosPermissionRequest>` 를 FullscreenLayout `bottom` slot 또는 `toolPermissionOverlay` 위치에 mount.
3. `toolUseConfirmQueue[0]` 가 truthy 일 때만 mount (CC 패턴 보존).
4. Props 전달: `permissionRequest={toolUseConfirmQueue[0]}`, `onApprove`, `onDeny`, `bypassMode={mode === 'bypassPermissions'}`.

**Definition of done**: `grep "PermissionGauntletModal × 2" tui/src/screens/REPL.tsx` = 0 hit (또는 historical-note 한 줄로) + KosmosPermissionRequest import + mount 라인 alive + `bun test` 회귀 0.

---

### T007 — REPL.tsx `permission_receipt` IPC handler + addReceipt wire (≥ 3 callsites) [sonnet-repl-wire]

**File**: `tui/src/screens/REPL.tsx` (MODIFY)

**Reference baseline**:
- `tui/src/ipc/codec.ts:158,168` (`permission_request` + `permission_response` frame, `permission_receipt` frame 신규 정의 필요 여부 R-1 grep 으로 결정 — 본 task 에서는 `permission_response.receipt_id` 응답 또는 신규 `permission_receipt` arm 둘 중 하나로 emit 가정, backend 측 응답 shape 확인 후 wire)
- `tui/src/context/PermissionReceiptContext.tsx:81` (`addReceipt` API)
- `tui/src/utils/permissions/aalToLayer.ts` (T001, layer 매핑)

**Deliverables**:
1. IPC frame consumer 추가 — `permission_receipt` (또는 backend 가 응답으로 사용하는 frame) 수신 시 `addReceipt({receipt_id, layer, tool_name, decision, decided_at, session_id, revoked_at: null})` 호출.
2. Layer 는 `aalToLayer(primitive, auth_level, is_irreversible)` 로 계산 (backend 가 layer 를 직접 보내주면 그것 사용 우선, KOSMOS 측 fallback only).
3. `KosmosPermissionRequest` 의 `onApprove` 콜백에서 `sendFrame(permission_response, {request_id, decision})` 호출.
4. `addReceipt` 호출처 ≥ 3 (verify path / submit path / subscribe path 각 1 — primitive 분기는 frame.primitive 필드로 자동 분기되므로 단일 callsite 가 3 primitive 모두 cover 해도 SC-004 만족).

**Definition of done**: `grep -rn "\.addReceipt(" tui/src/` ≥ 3 (또는 ≥ 1 callsite + comment 명시 "covers verify/submit/subscribe via frame.primitive") + verify scenario smoke (T011) 시 `/consent list` 에 receipt 표시.

---

### T008 — fail-closed backstop + bypass mode wire [sonnet-repl-wire]

**File**: `tui/src/screens/REPL.tsx` (MODIFY), `tui/src/utils/permissions/failClosed.ts` (NEW, ~ 40 LOC)

**Reference baseline**:
- spec FR-012 (backend 우회 감지) + FR-013 (IPC drop timeout) + FR-014 (bypass reinforce)
- `tui/src/i18n/permission.ko.ts` `failClosedError` + `timeoutDeniedToast` (T002)

**Deliverables**:
1. `failClosed.ts` — pure function `detectBypass(toolCall, recentPermissionRequests): boolean` — `tool_call` 이 verify/submit/subscribe primitive 인데 매칭 `permission_request` 가 직전 5초 내에 없으면 true.
2. REPL.tsx 의 `tool_result` IPC consumer 에서 `detectBypass` 호출 → true 시 ToolResult 를 error envelope 로 교체 + 시민에게 fail-closed 토스트.
3. Modal mount 후 30초 timeout 핸들러 → `timeout_denied` IPC send + 토스트.
4. `mode === 'bypassPermissions'` 토글 시 KosmosPermissionRequest 에 prop drilling (T006 이미 wire).

**Definition of done**: `failClosed.test.ts` (3 case: 정상 / 우회 감지 / lookup 무시) green + 30s timeout test green.

---

## Phase 4 — Integration tests (sonnet-integration)

### T009 — ink-testing-library snapshot — verify/submit/subscribe + lookup negative [sonnet-integration]

**File**: `tui/test/integration/permission-gauntlet-wire.test.tsx` (NEW)

**Reference baseline**:
- `tui/src/test-utils/waitForFrame.ts` (Spec debug-infra-rebuild § P1, polling helper)
- `tui/test/integration/onboarding-flow.test.tsx` (Spec 035 P2 패턴)

**Deliverables**:
1. Mock IPC bridge fixture — `permission_request` frame emit 시뮬레이션.
2. 4 scenario:
   - verify 호출 → Layer 1 green ⓵ glyph 모달 mount.
   - submit (irreversible=false) → Layer 2 orange ⓶.
   - subscribe → Layer 2 orange ⓶.
   - lookup → 모달 mount X (negative test).
3. 각 시나리오 Y 응답 → `addReceipt` mock 호출 검증 (jest.spyOn).
4. `waitForFrame` 패턴 사용 (Sleep 금지).

**Definition of done**: 4 scenario green + `bun test` 957 → ≥ 961 (4 신규 test).

---

### T010 — frameSequence (Layer 5c) test — Y/A/N 응답 timeline [sonnet-integration]

**File**: `tui/test/integration/permission-gauntlet-frame-sequence.test.tsx` (NEW)

**Reference baseline**:
- `tui/src/test-utils/frameStreamSnapshot.ts` (Spec debug-infra-rebuild § P3/P4, `assertFrameSequence`)
- `MEMORY.md feedback_pty_log_full_inspection` (final-state fallacy 회피)

**Deliverables**:
1. 3 scenario × 3 응답 (Y, A, N) = 9 frame-sequence assertion.
2. Each assertion verifies full frame hash sequence (de-dup) — modal mount → highlight 전환 → response → toast → dismiss.
3. Y → `addReceipt` 1회 + dismiss / A → `addReceipt` 1회 + session-cache mark / N → `addReceipt` 1회 (decision='deny') + dismiss.

**Definition of done**: 9 frame-sequence green + `bun test` ≥ 970.

---

## Phase 5 — Smoke + verification (Lead solo)

### T011 — Layer 5 tmux capture-pane scenario [Lead Opus]

**File**: `specs/spec-035-permission-gauntlet-wire-completion/scripts/smoke-permission-gauntlet.sh` (NEW), `specs/spec-035-permission-gauntlet-wire-completion/snap-NNN-*.txt` (CAPTURED, 4+ frame)

**Reference baseline**:
- `scripts/tui-tmux-capture.sh` (RFC `specs/debug-infra-rebuild/RFC.md § P2`)
- `MEMORY.md feedback_debug_infra_rebuild` (`wait_for_pane <regex> <deadline>` 필수)

**Deliverables**:
1. `smoke-permission-gauntlet.sh` 시나리오:
   - `bun run tui` 부팅 → `wait_for_pane "tool_registry: \d+ entries verified" 30`
   - capture `snap-001-boot.txt`
   - `tmux send-keys "내 카카오 인증으로 본인확인" Enter`
   - `wait_for_pane "Layer 1" 90` (K-EXAONE reasoning 30-90s 대응)
   - capture `snap-002-modal.txt`
   - `tmux send-keys y`
   - `wait_for_pane "rcpt-" 10`
   - capture `snap-003-receipt.txt`
   - `tmux send-keys "/consent list" Enter`
   - `wait_for_pane "rcpt-" 5`
   - capture `snap-004-list.txt`
   - `tmux send-keys C-c C-c`
2. 4 snap 파일 commit.
3. PR 본문에 SC-001/SC-009/SC-010 cross-reference.

**Definition of done**: 4 frame 캡처 + `grep "Layer 1" snap-002-modal.txt` 1+ hit + `grep "rcpt-" snap-003-receipt.txt` 1+ hit + `grep "rcpt-" snap-004-list.txt` 1+ hit.

---

### T012 — vhs .tape + 3 PNG keyframe + .txt + .ascii + .gif [Lead Opus]

**File**: `specs/spec-035-permission-gauntlet-wire-completion/smoke.tape` (NEW), `smoke.gif` + `smoke.txt` + `smoke.ascii` + `smoke-keyframe-modal-shown.png` + `smoke-keyframe-y-pressed.png` + `smoke-keyframe-receipt-toast.png` (CAPTURED)

**Reference baseline**:
- `AGENTS.md § TUI verification` Layer 4 — `Output ....gif` + `Output ....txt` + `Output ....ascii` + 3+ `Screenshot <path>.png` 의무
- `MEMORY.md feedback_vhs_tui_smoke` (텍스트 로그 + GIF 보조)
- `specs/2521-llm-swap-cc-rebuild/smoke-thinking-fast.gif` 패턴

**Deliverables**:
1. `.tape` 파일 — 동일 시나리오 (T011) 의 vhs 버전.
2. `Output smoke.gif`, `Output smoke.txt`, `Output smoke.ascii` 모두 emit.
3. `Screenshot smoke-keyframe-modal-shown.png` (Layer 1 modal mounted 시점).
4. `Screenshot smoke-keyframe-y-pressed.png` (Y 입력 직후).
5. `Screenshot smoke-keyframe-receipt-toast.png` (receipt toast 표시).
6. PR description 에 SC-002 cross-reference + 3 PNG 시각 확인 보고.

**Definition of done**: 6 artefact 모두 commit + Lead Opus 가 Read tool 로 3 PNG 각각 시각 확인 (frame=first-page rendering, `feedback_pty_log_full_inspection` 무시 X) + .txt/.ascii grep 가능 확인.

---

## Acceptance gate (PR 머지 직전)

PR description 에 다음 5 항목 cross-reference:

1. **SC mapping table** — spec.md `## Success Criteria` 의 SC-001 ~ SC-010 모두 deliverable 위치 명시.
2. **5-layer verification chain** — Layer 1b (T001/T004/T005/T009 unit), Layer 5c (T010 frameSequence), Layer 5 (T011 tmux), Layer 4 (T012 vhs) 모두 captured 확인.
3. **Hard rule check** — `tui/package.json` + `pyproject.toml` diff 0 line / `grep "behavior: 'allow' as const, updatedInput: {}" tui/src/hooks/useCanUseTool.ts` = 0 hit / `grep -rn "\.addReceipt(" tui/src/` ≥ 3 hit / `grep "Layer 1" snap-002-modal.txt` 1+ hit.
4. **CC parity statement** — 신규 컴포넌트 3개 (`KosmosPermissionRequest`, `KosmosBypassReinforcement`, `aalToLayer`) 모두 CC reference 명시 + KOSMOS 적응 설명.
5. **Closes #EPIC** — Epic 이슈 발행 후 number 채워서 `Closes #N` (Lead Opus 가 PR 직전에 GitHub Epic 발행 — 본 spec 의 첫 PR 직전 단계).

---

## Estimate + critical path

- Phase 1 (T001-T002): Lead solo, ~ 30 min
- Phase 2 (T003-T005): Sonnet teammate, ~ 60 min (병렬)
- Phase 3 (T006-T008): Sonnet teammate, ~ 60 min (병렬, T006 가 T004/T005 완료 의존)
- Phase 4 (T009-T010): Sonnet teammate, ~ 45 min (T003-T008 완료 의존)
- Phase 5 (T011-T012): Lead solo, ~ 45 min (T009-T010 완료 의존)

Total wall-clock (병렬): ~ 3.5 hour. Critical path: T002 → T004 → T006 → T009 → T011.

Lead Opus push/PR/CI 별도 + Codex P1 응답 (estimated ~ 30 min).
