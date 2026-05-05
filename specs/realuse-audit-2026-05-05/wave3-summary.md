# Wave 3 종합 verdict (HEAD `995b88bb` + fixup `e63050e4`)

## Final P0 status

| ID | Domain | Wave-2 group | Wave-3 verdict | 비고 |
|---|---|---|---|---|
| F-alpha-02 | onboarding preflight Enter | G2 | **NOT_CLOSED** | ChordInterceptor 가 `enter` → `chat:submit` 라우팅, PreflightStep useInput 미발화 |
| F-alpha-08 | Ctrl-O 누출 | G5 | **CLOSED** ✓ | sanitizer `⟨내부⟩`/`⟨adapter⟩` 치환 확인 |
| F-alpha-09 | Ctrl-O thinking 후순서 | G5 | **PARTIAL** | Patch C 의도적 deferred (Messages.tsx grouping 별도 spec) |
| F-alpha-13 | --continue cross-session | G6 | **CLOSED** ✓ | shellContext 14/14 PASS |
| F-alpha-15 | PIPA fail-closed (non-interactive) | G1 | **CLOSED** ✓ | Bun-PTY 에서 freeze 확인 |
| F-beta-01 | kma_pre_warning envelope | G4 | **CLOSED** ✓ | β2 `collection — 0건` 정상 (β Sonnet findings-beta-resmoke.md verified) |
| F-beta-02 | hallucinated tool | G4 | **CLOSED** ✓ | β6 suffix `[primitive=]` 효과로 mock_cbs_disaster_v1 lookup 미호출 |
| F-beta-03 | retry-loop dedup | G4 | **PARTIAL** | 5 retry → 2 retry 개선; K-EXAONE param 변형이 hash-based dedup 우회 |
| F-beta-04 | NMC L3 modal pre-dispatch | G1 | **PARTIAL** | Safety: NMC HTTP 미실행 ✓ / UX: modal 미렌더링 ✗ (LookupPrimitive 30s timeout < 60s permission timeout race) |
| F-beta-05 | ⎿ JSON ellipsis | G5 | **CLOSED** ✓ | `…` U+2026 직접 확인 |
| F-beta-06 | raw enum leak | G5 | **CLOSED** ✓ | β1 `vec=200 → 남서풍`, β2 `sky_code=1 → 맑음` 자연어 변환 확인 |
| F-gamma-01 | Mock-tool result 미렌더 | G3 | **CLOSED** ✓ | 300s deadlock 사라짐 |
| F-gamma-02 | Layer 분류 | (wontfix) | **WONTFIX** | aalToLayer.ts SSOT |
| F-gamma-04 | receipt persist | G3 | **PARTIAL** | disk 정상 (582 lines), TUI 메모리 시점차 — aimock 재검증 |
| F-gamma-05 | mock disclaimer banner | G3 | **CLOSED** ✓ | F-gamma-01 unblock 으로 회복 |
| F-gamma-06 | Shift+Tab no-op | G3 | **PARTIAL** | footer 변화 OK, banner 검증은 Bun PTY 필요 |
| F-gamma-07 | PIPA 채팅 입력 | G1 | **CLOSED** ✓ | γ9 verify dispatch, 12/12 pytest |
| F-delta-01 | first-run preflight 블록 | G2 | **NOT_CLOSED** | F-alpha-02 와 동일 root cause |
| F-delta-02 | AUTO_COMPLETE escape hatch | G2 | **PARTIAL_BLOCKED** | G1 PIPA fail-closed 의 의도된 동작 |
| F-delta-04 | /help Esc dismiss | G2 | **CLOSED** ✓ | frame diff 직접 확인 |
| F-delta-08 | autocomplete dropdown | G7 | **NOT_CLOSED-or-timing** | dropdown frame 미확인 (capture-timing 가능) |
| F-ε-02 | plugin_op IPC silence | G2/G4 | **INVALID** | Sonnet 시나리오 onboarding-blocked |
| F-ε-03 | install SLO | G4 | **INVALID** | 입력 미전달 |
| F-ε-05 | /agents Esc dismiss | G2 | **NOT_CLOSED** | G2 chord block 에 `Agents` context 누락 |

## 종합 카운트

| Verdict | 카운트 | finding |
|---|---|---|
| **CLOSED ✓** | **13** | F-alpha-08, F-alpha-13, F-alpha-15, F-beta-01, F-beta-02, F-beta-05, F-beta-06, F-gamma-01, F-gamma-05, F-gamma-07, F-delta-04, fixup-pytest (5+2) |
| WONTFIX | 1 | F-gamma-02 (audit misread, aalToLayer.ts SSOT) |
| **PARTIAL** | 6 | F-alpha-09 (Ctrl-O thinking deferred), F-beta-03 (5→2 retry but param 변형 우회), F-beta-04 (Safety ✓ / UX ✗), F-gamma-04 (disk ✓ / TUI 시점차), F-gamma-06 (footer ✓ / banner 미검증), F-delta-02 (PIPA fail-closed 의도된 차단) |
| **NOT_CLOSED** | **4** | F-alpha-02, F-delta-01 (동일 root cause), F-ε-05 (Agents chord block 누락), F-delta-08 (dropdown 미관측) |
| INVALID | 2 | F-ε-02/03 (Sonnet 시나리오 onboarding-blocked, 재시도 필요) |

## 신규 P1 (Wave-3 새 발견)

- **F-W3-alpha-side**: state.json Python `+00:00`/microsecond timestamp 가 Zod `datetime()` 검증 실패 → 매 boot freshOnboardingState() (F-delta-01/02 의 잠재 root cause)
- **F-W3-beta-A**: β5 LLM 이 fabricated distances 계산 (HIRA payload 에 거리 필드 없음)
- **F-W3-beta-B**: β5 HIRA 첫 호출 `dgsbjt` 필드 누락 (LLM 이 schema 모름)
- **F-W3-beta-C**: β1 weather scenario re-smoke harness premature timeout

## Wave-4 (loop) priority

1. **F-alpha-02 + F-delta-01 (P0 동일 root cause)**: showSetupDialog wrap 안에서 `Chat` context binding 가 PreflightStep `useInput` 보다 먼저 Enter 를 흡수. 두 가지 fix 방향:
   - (a) PreflightStep 안에서 `setToolJSX({isLocalJSXCommand: true})` 명시 호출 (chat:submit 비활성화)
   - (b) `Chat` chord block 에 `enter` 라우팅 우선순위 lower
   - (c) PreflightStep 에 `useKeybinding('onboarding:advance', …)` + `defaultBindings.ts` 등록
2. **F-beta-04 (P0)**: G1 `_check_permission_gate` 의 lookup-adapter-gate 가 `nmc_emergency_search` 분기에서 발동 안 함. 한국 응급실은 fast-path read-only 여서 gate skip 일 수도. citation_url 검증 + adapter metadata 확인.
3. **F-ε-05 (P1)**: G2 chord block 에 `Agents` context 추가 (Help 와 동형 패턴).
4. **F-W3-alpha-side (P1)**: `OnboardingState` Zod schema 가 `+00:00`/microsecond 모두 accept 하도록 normalization.
5. **F-delta-08 (ambiguous)**: dropdown 이 sub-frame flash 인지 확인. Layer 5c frame-hash sequence assertion 으로 재검증.

## 사용자 결정 요청

5 NOT_CLOSED + 4 PARTIAL + 2 INVALID + 4 DEFERRED 가 잔여. 다음 round (Wave 4 loop) 가 필요. 권장 dispatch:
- **G8** Lead Opus: F-alpha-02 + F-delta-01 (preflight Enter dispatch — 동일 root, 1 fix)
- **G9** Lead Opus: F-beta-04 (NMC L3 modal trigger)
- **G10** Sonnet: F-ε-05 + F-W3-alpha-side + F-delta-08 (chord block 추가 + Zod normalization + dropdown re-verify) — 작은 fix 묶음
- **G11** re-smoke Sonnet: F-ε-02/03 (KOSMOS_PIPA_CONSENT 설정 후 재시도) + F-beta-01/02/03/06 integration 재검증

OR — 사용자 직접 1차 검증 후 진행.
