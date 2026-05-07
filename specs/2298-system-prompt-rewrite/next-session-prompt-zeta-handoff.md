# 다음 세션 — Epic ζ #2297 핸드오프

**작성일**: 2026-04-30 (Epic η #2298 머지 직후)
**Epic η 머지 commit**: `1321f77` (PR #2480 squash)
**Initiative**: #2290

---

## η가 남긴 것 (Epic ζ prerequisite)

✅ **Layer 1** — `prompts/system_v1.md` 4-paragraph + 4 nested XML tag (`<primitives>` / `<verify_families>` / `<verify_chain_pattern>` / `<scope_grammar>`), 10 mock_verify_* tool_id 매핑, TRIGGER + canonical 매핑. Manifest SHA `bda67fb…`.

✅ **Layer 2** — `src/kosmos/tools/mvp_surface.py` active GovAPITool surface (resolve_location + lookup + verify + submit) `is_core=True`. `_VerifyInputForLLM` / `_SubmitInputForLLM` envelope.

❌ **Layer 5** — Epic ζ 의 책임. TUI 4 primitive `call()` 가 stub.

---

## Epic ζ #2297 — Phase 0 + Phase 1

이슈 본문 갱신 완료 (2026-04-30). Epic ζ 가 **wiring → smoke → docs** 모두 책임.

### Phase 0 — TUI primitive call() wiring (NEW, mandate added 2026-04-30)

stub 교체 + IPC `tool_call`/`tool_result` frame backend emit:
- `tui/src/tools/{Lookup,Verify,Submit,Subscribe}Primitive/*.ts:248-263` — stub `call()` 4개 교체
- `src/kosmos/ipc/stdio.py:_handle_user_input_llm` — K-EXAONE function_call → IPC `tool_call` frame → primitive sub-dispatcher → `tool_result` frame 흐름 구축
- **#2481** "verify dispatcher tool_id↔family_hint translation" 해결: TUI는 `verify(tool_id, params)` 받음, backend dispatcher는 `verify(family_hint, session_context)` — bridge 가 변환 (Option A: TUI-side tool_id→family 추출) 또는 dispatcher 확장 (Option B: tool_id 직접 받기). spec.md 에서 둘 중 선택.

### Phase 1 — E2E smoke + policy mapping doc (carry forward)

- **PTY scenario**: 시민 "종합소득세 신고해줘" → `verify(modid)` → `lookup(simplified)` → `submit(taxreturn)` → 접수번호 표시. `specs/2298-system-prompt-rewrite/smoke-citizen-taxreturn-pty.txt` 참조 (η 의 stub-blocker 증거).
- **Layer 4 vhs**: keyframe 3 PNG 에 `접수번호: hometax-2026-MM-DD-RX-XXXXX` 시각 검증 (η T012 deferred to ζ).
- **policy-mapping.md**: KOSMOS adapter ↔ Singapore APEX / Estonia X-Road / EU EUDI / Japan マイナポータル.
- **5 OPAQUE scenario doc**: `docs/scenarios/{hometax-tax-filing,gov24-minwon-submit,mobile-id-issuance,kec-yessign-signing,mydata-live}.md`.

---

## 다음 세션 진입

```bash
cd /Users/um-yunsang/KOSMOS && git pull --ff-only
git worktree add ../KOSMOS-w-2297 -b 2297-zeta-e2e-smoke
cd ../KOSMOS-w-2297

# Lead Opus 첫 명령:
# /clear → 새 conversation
# 이 파일 (specs/2298-system-prompt-rewrite/next-session-prompt-zeta-handoff.md) 읽고
# Epic ζ #2297 resume. Phase 0 wiring + Phase 1 E2E smoke 순차로.
# /speckit-specify 부터 시작.
```

### Open sub-issues of Epic ζ (4 + this Epic)

- **#2481** verify dispatcher tool_id↔family_hint translation (Codex P1 from η)
- **#2457** [T011] Capture Layer 2+4 smokes (deferred from η)
- **#2458** [T012] Lead Opus visual verification (deferred from η)
- 5 deferred placeholders from η (#2475–#2479) — 별도 Epic 으로 promote 또는 won't-fix

### Codex P1 deferred 처리

η 는 Codex P1 #2 (mvp_surface input_schema) 즉시 fix, P1 #1 (verify dispatcher mismatch) → #2481 deferred. ζ 가 #2481 해결.

---

## 불변 규칙 (η에서 carry)

1. 1 Lead Opus = 1 Epic, dispatch unit = task/task-group (≤5 task / ≤10 file)
2. push/PR/CI/Codex = Lead 순차
3. PR title 첫 글자 lowercase
4. **vhs Layer 4 mandatory** for TUI 변경 — `.tape` + 3+ Screenshot PNG + Lead 시각 Read 검증
5. 이슈 추적 = GraphQL Sub-Issues API only
6. 신규 dep 0 (AGENTS.md hard rule)
7. **prompt 변경 시 manifest hash 재계산 + shadow-eval 통과** (Spec 026)
8. **TUI/src 변경 시 ruff format + ruff check + mypy 통과** (η fail 교훈 — push 전 로컬 검증)
