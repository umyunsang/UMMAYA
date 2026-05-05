# Implementation Plan: Permission Gauntlet Wire 완성

**Spec**: [`spec.md`](./spec.md)
**Branch**: `spec-035-permission-gauntlet-wire-completion`
**Created**: 2026-05-04
**Status**: Phase 0 complete (research finished inline below); Phase 1 design ready; Phase 2 task generation ready.

---

## Constitution alignment

- **CC byte-identical 우선** — 신규 모달 컴포넌트 작성 금지. CC `PermissionRequest.tsx` + `PermissionDialog.tsx` 패턴을 KOSMOS dispatcher 한 층 (`KosmosPermissionRequest.tsx`) 로 thin-wrap. (`AGENTS.md § CORE THESIS`)
- **Zero new runtime dependencies** — `react`, `ink`, `zod`, `zustand` 만 사용. `tui/package.json` + `pyproject.toml` diff 0. (`AGENTS.md § Hard rules`)
- **Backend permission service 변경 X** — Spec 033 영역. 본 plan 은 TUI side IPC consumer + state owner 만 다룸. (`AGENTS.md § L1-B B4`)
- **권한 정책 발명 금지** — KOSMOS 는 어댑터 metadata 의 `auth_level` + `is_irreversible` 를 backend 결정과 함께 표시할 뿐, 새 정책 분류 추가 X. (`AGENTS.md § Tool wrapping is the work`)
- **TUI 5-layer 검증 + tmux capture-pane** — Layer 5 frame 캡처는 `scripts/tui-tmux-capture.sh` + `wait_for_pane <regex> <deadline>` 사용. asciinema-in-asciinema 금지, 하드코딩 Sleep 금지 (K-EXAONE reasoning latency 30-90s). (`MEMORY.md feedback_debug_infra_rebuild`)

---

## Phase 0 — Research (✅ complete)

### R-1: backend IPC frame `permission_request` alive 확인

**Question**: backend (Spec 033 권한 서비스) 가 어댑터 호출 시 `permission_request` IPC frame 을 emit 하는가?

**Investigation**:
- `tui/src/ipc/codec.ts:158,168` — `permission_request` (kind) + `permission_response` (kind) frame 정의 확인.
- `tui/src/ipc/frames.generated.ts:412,468` — Kind8/Kind9 type 정의 + ULID round-trip 주석 확인.
- `tui/src/ipc/schema/frame.schema.json:1475-1621` — JSON Schema definition 확인 (PermissionRequestFrame + PermissionResponseFrame, discriminated union 의 arm 8/9).
- `src/kosmos/plugins/consent_bridge.py:176` — backend emit path 확인: `kind="permission_request"` 가 plugin consent bridge 에서 emit.

**Verdict**: ✅ backend IPC frame alive. **R1 risk 해소**. 단, `consent_bridge.py` 가 plugin path 만 커버 — Spec 033 의 verify/submit/subscribe primitive 호출 시 backend 가 동일 frame 을 emit 하는지 Phase 1 에서 backend module 추가 grep 필요. dead arm 발견 시 별도 sub-issue (Spec 033 영역) 발행.

### R-2: `/consent` 명령 핸들러 wire 상태

**Question**: `/consent list` 와 `/consent revoke` 명령이 이미 wired 인가?

**Investigation**:
- `tui/src/commands/consent.ts:1-100` — list + revoke 핸들러 alive, FR-019/020/021 주석 확인.
- `tui/src/commands/catalog.ts:33,41` — slash command catalog 등록 확인.
- `tui/src/components/consent/ConsentListView.tsx:42` — Layer 색 매핑 사용하는 view 컴포넌트 alive.

**Verdict**: ✅ **R4 risk 해소**. 명령 핸들러 + view 컴포넌트 alive. 본 spec 은 wire 가 _도달_ 함만 검증 (receipt 가 `addReceipt` 호출되어 list 에 표시되는지).

### R-3: CC `PermissionRequest.tsx` dispatcher 패턴 + KOSMOS 적응 표면

**Question**: KOSMOS 는 어떤 component 를 추가해야 CC reference 와 ≥ 90% structural fidelity 를 유지할 수 있는가?

**Investigation**:
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionRequest.tsx:47-80` — `permissionComponentForTool(tool)` switch dispatcher 가 13종 도구 (FileEditTool / BashTool / WebFetchTool 등) 를 component 에 매핑.
- KOSMOS 에는 도구 = 4 primitive (lookup/verify/submit/subscribe) — switch 가 4-arm 으로 축소.
- CC `PermissionDialog.tsx` — 모달 골격 (Y/A/N + 메시지), CC import 가능하지만 KOSMOS-specific 본문 (한국어 + 어댑터 metadata) 를 prop drilling 으로 전달.

**Verdict**: 추가 컴포넌트 = 1개 (`KosmosPermissionRequest.tsx`, ≤ 80 LOC switch dispatcher). CC `PermissionDialog.tsx` 는 직접 import 하여 child 로 사용 (CC byte-identical). 신규 LOC 총 약 200줄 (dispatcher + AAL 매핑 + i18n).

### R-4: `bypassPermissions` mode + `BypassReinforcementModal` 부활

**Question**: REPL.tsx 의 주석에서 "BypassReinforcementModal removed" 명시 — 부활 vs CC import?

**Investigation**:
- `.references/claude-code-sourcemap/restored-src/src/components/permissions/PermissionExplanation.tsx` — CC reinforcement 패턴 alive, KOSMOS 측에서는 dead.
- 부활 비용: ≤ 50 LOC, dependency 0 (이미 React + Ink 사용).

**Verdict**: 부활 (FR-014). `tui/src/components/permissions/KosmosBypassReinforcement.tsx` 추가 (CC `PermissionExplanation.tsx` 패턴 thin-port + 한국어 본문).

### R-5: state ownership — `setToolUseConfirmQueue` location

**Question**: `useCanUseTool` 의 default export 가 사용할 `setToolUseConfirmQueue` state 가 어디 owned 되어야 하는가?

**Investigation**:
- `tui/src/screens/REPL.tsx:5121` — `toolUseConfirmQueue` state 가 _아직 변수로 alive_ (CC inheritance), `[0]` indexing 으로 modal mount path 가 작동하던 흔적.
- `tui/src/screens/REPL.tsx:5534-5536` 주석 — KosmosActivePermissionGate / PermissionGauntletModal × 2 / BypassReinforcementModal 만 제거됨, queue state 자체는 alive.

**Verdict**: state ownership 변경 불필요. `toolUseConfirmQueue` state + `setToolUseConfirmQueue` setter 가 REPL.tsx 에 alive — `useCanUseTool` default export 가 setter 를 이용해 enqueue 후 promise 대기. **R2 risk 해소**.

### R-6: K-EXAONE reasoning latency 시나리오 검증

**Question**: 자연어 "내 카카오 인증으로 본인확인" → LLM 이 verify 호출까지 reasoning 30-90s 소요 가능. Layer 5 smoke 가 wait_for_pane 사용해야 함.

**Investigation**: `MEMORY.md feedback_debug_infra_rebuild` (2026-05-02 Spec 2521 lesson) — `wait_for_pane <regex> <deadline_seconds>` 가 reasoning_content stream 수렴까지 polling. Sleep 금지.

**Verdict**: scenario script 는 `wait_for_pane "Layer [123]" 90` 로 모달 mount 까지 대기. Phase 2 task 의 smoke script 에 invariant 명시.

---

## Phase 1 — Design

### Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│ REPL.tsx                                                         │
│  ├─ <PermissionReceiptProvider>                  (already alive) │
│  │    ├─ toolUseConfirmQueue state              (already alive) │
│  │    ├─ <KosmosPermissionRequest>              (NEW - thin)    │
│  │    │    ├─ aalToLayer(primitive, auth_level, is_irreversible)│
│  │    │    ├─ <KosmosBypassReinforcement>       (NEW if bypass) │
│  │    │    └─ <PermissionDialog>                (CC import)     │
│  │    │         └─ on Y/A: addReceipt + sendFrame(response)     │
│  │    └─ <ConsentListView>                       (already alive) │
└──────────────────────────────────────────────────────────────────┘
              ▲                              │
              │  permission_receipt          │ permission_response
              │  IPC frame                   │ IPC frame
              ▼                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Backend (Spec 033 service)                                       │
│  emits permission_request → mounts modal                         │
│  receives permission_response → emits permission_receipt         │
└──────────────────────────────────────────────────────────────────┘
```

### Module additions (NEW)

1. **`tui/src/utils/permissions/aalToLayer.ts`** (~ 60 LOC, FR-005/006)
   - Pure function `aalToLayer(primitive, authLevel?, isIrreversible?): PermissionLayerT | null` (null = bypass modal).
   - Single source-of-truth 8-row mapping table (spec FR-005 표).
   - Unit testable in isolation.

2. **`tui/src/components/permissions/KosmosPermissionRequest.tsx`** (~ 80 LOC, FR-004)
   - 4-arm switch over `primitive` ('lookup' | 'verify' | 'submit' | 'subscribe').
   - lookup → returns null (no modal — User Story 4).
   - verify/submit/subscribe → 호출 `aalToLayer` → 호출 `LAYER_VISUAL[layer]` → mount `<PermissionDialog>` (CC import).
   - Props: `permissionRequest: PermissionRequestFrame`, `onApprove`, `onDeny`, `sendFrame`, `bypassMode: boolean`.
   - Y/A 응답 시 `addReceipt({receipt_id: ..., layer, tool_name, decision, decided_at, session_id, revoked_at: null})` 호출.

3. **`tui/src/components/permissions/KosmosBypassReinforcement.tsx`** (~ 50 LOC, FR-014)
   - CC `PermissionExplanation.tsx` 패턴 thin-port + 한국어 본문 ("⚠️ bypass 모드 — 권한 검증이 비활성화되어도 시민 책임 영역").
   - Y 응답 시 추가 확인 모달 + dual-confirm 후 `onApprove` 호출.

4. **`tui/src/i18n/permission.ko.ts`** + **`permission.en.ts`** (~ 30 LOC each, FR-015)
   - 모달 본문 한국어 primary / English fallback string catalog.
   - Hardcoded literal 금지.

### Module modifications

5. **`tui/src/hooks/useCanUseTool.ts`** (FR-001/002)
   - 라인 48-54 의 하드코딩 `behavior: 'allow'` 제거.
   - CC signature 복원: `(setToolUseConfirmQueue, setToolPermissionContext) → ToolUseConfirmFn`.
   - ToolUseConfirmFn 내부에서 primitive 추출 → lookup 이면 즉시 allow / 그 외는 enqueue 후 promise 대기.

6. **`tui/src/screens/REPL.tsx`** (FR-003/008)
   - 주석 라인 5534-5536 의 dead 모달 placeholder 제거.
   - `<KosmosPermissionRequest>` mount logic 추가 (FullscreenLayout `bottom` slot, CC `toolPermissionOverlay` 패턴 따라).
   - `permission_receipt` IPC frame 수신 핸들러 추가 → `addReceipt` 호출.
   - bypassMode state 를 `<KosmosPermissionRequest bypassMode={...}>` 로 prop drilling.

### State flow (timeline)

```
[T+0s]   citizen 자연어 입력  "내 카카오 인증으로 본인확인"
[T+1s]   REPL → IPC chat_request → backend
[T+30s]  backend → IPC assistant_chunk (reasoning_content stream)
[T+45s]  backend → IPC tool_call (verify, kakao_pass_simple_verify)
[T+45.5s] backend (Spec 033) → IPC permission_request (request_id=ULID, primitive=verify, auth_level=AAL2, is_irreversible=false)
[T+45.5s] TUI receives permission_request → enqueue toolUseConfirmQueue
[T+45.6s] React reconcile → <KosmosPermissionRequest> mounts → aalToLayer('verify', 'AAL2', false) → 1 → <PermissionDialog> with Layer 1 green ⓵ glyph
[T+50s]  citizen presses Y
[T+50.1s] sendFrame(permission_response, request_id, decision=allow_once)
[T+50.5s] backend → IPC permission_receipt (receipt_id=rcpt-abc123)
[T+50.5s] TUI calls addReceipt({receipt_id, layer:1, tool_name:'kakao_pass_simple_verify', decision:'allow_once', ...})
[T+50.6s] toast "rcpt-abc123 발급됨"
[T+50.7s] modal dismiss → toolUseConfirmQueue.shift()
[T+51s]  backend dispatches verify adapter → IPC tool_result
```

### Edge case handling

| Case | Handler | FR |
|---|---|---|
| backend 가 `permission_request` 보내지 않고 `tool_result` 직접 emit | TUI fail-closed: ToolResult error envelope "권한 검증 우회 감지" | FR-012 |
| modal mount 중 IPC drop | 30s timeout → `timeout_denied` decision → backend 재연결 시 send | FR-013 |
| bypass mode + Y | `<KosmosBypassReinforcement>` dual-confirm → 후 approve | FR-014 |
| receipt revoke 후 동일 receipt 다시 revoke | `revokeReceipt` 가 `'already_revoked'` 반환 → 토스트 | FR-011 |
| lookup 호출 | aalToLayer 가 null 반환 → modal mount X | User Story 4 |

---

## Phase 2 — Task generation guidance

Tasks 는 `tasks.md` 에 12개로 분할. Lead Opus = 1, Sonnet teammates = 3 (T003-T005, T006-T008, T009-T010 각 1 teammate).

### Dispatch tree

```text
Phase 1 Foundational (T001-T002): Lead solo
  ├─ T001 aalToLayer.ts module (NEW, ~60 LOC) + unit test (8-row matrix)
  └─ T002 i18n permission.ko/en.ts (NEW, ~60 LOC each) + smoke

Phase 2 Hook + Components (T003-T005): sonnet-hook-components
  ├─ T003 useCanUseTool.ts wire 복구 (delete stub + restore CC signature)
  ├─ T004 KosmosPermissionRequest.tsx (NEW, ~80 LOC) + unit test
  └─ T005 KosmosBypassReinforcement.tsx (NEW, ~50 LOC) + unit test

Phase 3 REPL wire + addReceipt (T006-T008): sonnet-repl-wire
  ├─ T006 REPL.tsx delete dead modal placeholder + mount KosmosPermissionRequest
  ├─ T007 REPL.tsx permission_receipt IPC frame handler + addReceipt 호출 wire (≥ 3 callsites)
  └─ T008 fail-closed backstop (FR-012/013) + bypass mode wire (FR-014)

Phase 4 Integration tests (T009-T010): sonnet-integration
  ├─ T009 ink-testing-library snapshot test — verify/submit/subscribe modal mount + lookup negative test
  └─ T010 frameSequence (Layer 5c) test — full Y/A/N response loop + receipt 발급 + dismiss

Phase 5 Smoke + verification (T011-T012): Lead solo
  ├─ T011 Layer 5 tmux capture-pane smoke (4 frame: boot / 입력 / 모달 / receipt 토스트) + wait_for_pane
  └─ T012 vhs .tape (3 PNG keyframe + .txt + .ascii + .gif) + PR description
```

### Reference baseline per task

각 task body 에 reference baseline 명시 (memory `feedback_cc_source_migration_pattern`):
- T003 → `.references/claude-code-sourcemap/restored-src/src/hooks/useCanUseTool.tsx`
- T004 → `.references/.../components/permissions/PermissionRequest.tsx:47-80`
- T005 → `.references/.../components/permissions/PermissionExplanation.tsx`
- T006 → `.references/.../components/permissions/PermissionDialog.tsx`
- T009-T010 → `tui/src/test-utils/{waitForFrame,frameStreamSnapshot}.ts` + memory `feedback_debug_infra_rebuild`

### Test plan summary

- **Layer 1b (bun test + ink-testing-library)**: T001 (aalToLayer 8-row), T004 (modal switch), T005 (bypass dual-confirm), T009 (mount + dismiss).
- **Layer 5c (frame sequence hash)**: T010 — full timeline assertion with `assertFrameSequence`.
- **Layer 5 (tmux capture-pane)**: T011 — 4-frame scenario with `wait_for_pane`.
- **Layer 4 (vhs .tape + PNG keyframe)**: T012 — 3 PNG (modal-shown, y-pressed, receipt-toast) + .txt + .ascii + .gif.
- **Backend regression (pytest)**: zero — backend 변경 없음, but smoke 시 backend 가 mock 으로 `permission_request` emit 해주는 fixture 필요 (T009 가 fake LLM/mock fixture 사용).

### File change budget (per task)

- Each Sonnet teammate task ≤ 5 file 변경 (AGENTS.md hard rule).
- Total file changes:
  - NEW: 6 files (aalToLayer.ts, KosmosPermissionRequest.tsx, KosmosBypassReinforcement.tsx, permission.ko.ts, permission.en.ts, smoke scripts)
  - MODIFIED: 2 files (useCanUseTool.ts, REPL.tsx)
  - TEST: 4 files (unit + snapshot + integration + frame sequence)
  - SMOKE: 2 files (.tape + tmux script)
  - **Total**: 14 file changes — Lead solo 합산 4 + 3 sonnet × ≤ 5 = ≤ 19 budget.

---

## Risks 추적

| ID | Status | Mitigation |
|---|---|---|
| R1 backend permission_request alive | ✅ R-1 에서 해소 | `consent_bridge.py:176` alive 확인 |
| R2 setToolUseConfirmQueue ownership | ✅ R-5 에서 해소 | REPL.tsx:5121 alive 확인 |
| R3 BypassReinforcementModal 부활 | ✅ R-4 에서 design 결정 | `KosmosBypassReinforcement.tsx` 신규 (CC pattern thin-port) |
| R4 /consent 명령 wire | ✅ R-2 에서 해소 | `consent.ts` + `catalog.ts` alive 확인 |
| R5 verify/submit/subscribe primitive backend emit | ⚠️ Phase 1 grep 필요 | T009 의 mock fixture 가 cover, 실 backend dead arm 발견 시 별도 sub-issue |
| R6 K-EXAONE reasoning latency | ✅ R-6 에서 design 반영 | `wait_for_pane <regex> 90` invariant T011 명시 |

---

## Success criteria mapping (spec → plan deliverable)

| Spec SC | Plan deliverable |
|---|---|
| SC-001 verify modal Layer 1 표시 | T011 smoke frame `snap-002-modal.txt` + T009 unit test |
| SC-002 submit modal Layer 2 + dispatch | T012 vhs `smoke-keyframe-modal-shown.png` + T010 frameSequence |
| SC-003 lookup no modal | T009 negative test |
| SC-004 addReceipt ≥ 3 callsite | T007 wire + grep verification in PR description |
| SC-005 ccCompatDefault stub 제거 | T003 |
| SC-006 aalToLayer 8-row 단위 test | T001 |
| SC-007 bun test ≥ 969 + pytest 회귀 0 | T009-T010 + backend touch 0 |
| SC-008 zero new dep | T001-T012 의 package.json/pyproject.toml diff 0 |
| SC-009 Layer 5 ≥ 4 frame | T011 |
| SC-010 PIPA §22-2 modal ≤ 2s mount | T011 timeline + T012 keyframe timestamp |
