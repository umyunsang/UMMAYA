# 다음 세션 시작 프롬프트 — Initiative #2290 핸드오프 v6 (Epic δ 머지 완료 후)

**작성일**: 2026-04-29 (Epic δ 머지 직후)
**상태**: Epic α + β + δ 머지 완료. Epic γ / ε / ζ / η 모두 OPEN. 다음 세션이 별도 Lead Opus 로 다음 Epic 진행.

---

## 머지 결과 요약

| Epic | # | 상태 | 머지 commit |
|---|---|---|---|
| α cc-parity-audit | #2292 | CLOSED | `bc523b7` |
| β ui-residue-cleanup | #2293 | CLOSED | `43a7bd8` (PR #2363) |
| **δ backend-permissions-cleanup** | **#2295** | **CLOSED** | **`c6747dd` (PR #2364)** |
| γ 5-primitive-align (CC Tool.ts) | #2294 | OPEN | — |
| ε AX-mock-adapters | #2296 | OPEN | — |
| ζ E2E-smoke | #2297 | OPEN | — |
| η ? | #2298 | OPEN | — |

### Epic δ #2295 핵심 산출물 (이번 세션)

- **잔재 deletion**: `src/kosmos/permissions/` 14 source file + `steps/` + 4 test file 삭제. Spec 035 receipt set 8 + `models.py` (trimmed) + `credentials.py` 만 잔존 (11 entry).
- **AdapterRealDomainPolicy**: Pydantic v2 frozen 모델 신설 + 19 adapter metadata 마이그레이션.
- **Path B**: Spec 024/025/1636 V1-V6 invariants 를 `policy.citizen_facing_gate` derivation 기반으로 재작성 (신규 `src/kosmos/tools/policy_derivation.py` + `AdapterRegistration.@computed_field` backward-compat).
- **검증**: pytest 3160 pass / 0 fail / 0 error, ruff + mypy + 15 CI checks 모두 PASS, Codex P1 1건 처리, 신규 dep 0.
- **20 sub-issues closed** (#2341-#2360), #2362 deferred OPEN (real_classification_url 실 정책 검증).
- **영구 룰 박제**: 메모리 `feedback_path_b_policy_derivation.md` (★★ KOSMOS-invented 권한 cleanup 시 derivation table + computed_field 패턴).

---

## 다음 세션 진입 (1 Lead Opus = 1 Epic)

`memory feedback_dispatch_unit_is_task_group` (Two-layer parallelism) 따라 **각 Epic 마다 별도 Lead Opus session 분리** 필수.

### Epic γ #2294 — 5-primitive align (CC Tool.ts)

```bash
cd /Users/um-yunsang/KOSMOS  # main worktree
git pull --ff-only
git worktree add ../KOSMOS-w-2294 -b 2294-5-primitive-align
cd ../KOSMOS-w-2294
# /speckit-specify Epic γ 시작 — CC Tool.ts byte-identical 인터페이스 align
```

### Epic ε #2296 — AX-mock-adapters

```bash
cd /Users/um-yunsang/KOSMOS && git pull --ff-only
git worktree add ../KOSMOS-w-2296 -b 2296-ax-mock-adapters
cd ../KOSMOS-w-2296
# /speckit-specify Epic ε 시작 — Singapore APEX 식 통로 mirror Mock 어댑터 신설 + register_all 보강 (Epic δ deferred #2362)
```

### Epic ζ #2297 — E2E smoke + 정책 매핑 doc

```bash
cd /Users/um-yunsang/KOSMOS && git pull --ff-only
git worktree add ../KOSMOS-w-2297 -b 2297-e2e-smoke
cd ../KOSMOS-w-2297
# /speckit-specify Epic ζ 시작 — End-to-end smoke + 19 adapter real_classification_url 실 정책 검증
```

---

## 불변 규칙 (이번 세션 박제 + 강화)

1. **1 Lead Opus = 1 Epic** (Layer 1 parallelism). 의존성 없는 Epic 들은 **별도 session/worktree** 에서 동시 진행.
2. **Sonnet teammate 단위 = task/task-group** (≤ 5 task / ≤ 10 file). "1 Sonnet = 1 Epic" 금지.
3. **push/PR/CI/Codex = Lead** (sequential, sonnet teammates 완료 후).
4. **PR 머지 전 (TUI 변경 시) interactive PTY 시나리오 박제** — `tui/src/**` 안 건드린 PR 은 "TUI no-change" 명시로 bypass.
5. **KOSMOS-invented 권한 cleanup 시 Path B**: 단순 삭제 X / derivation table + computed_field backward-compat 패턴 (메모리 `feedback_path_b_policy_derivation`).
6. **신규 dep 0** (AGENTS.md hard rule). pyproject.toml `[project.dependencies]` 변경 X.
7. **이슈 추적 = GraphQL Sub-Issues API only** (`subIssues` / `parent` 필드, `trackedIssues` X).

---

## Spec scope 권장 (각 Epic)

- **γ**: CC `Tool.ts` 인터페이스 비교 → 5 primitive (lookup/resolve_location/submit/subscribe/verify) byte/shape align matrix → migration plan.
- **ε**: Mock 어댑터 신설 (Singapore APEX 모방) + Epic δ deferred 인 6 Mock verify + 2 Mock data 의 `register_all` chain 보강.
- **ζ**: 19 adapter URL 실 검증 + LLM agentic loop end-to-end smoke + `docs/scenarios/` OPAQUE 시나리오 수정 + KOSMOS v0.1-beta tag.

---

## 다음 세션 첫 명령 후보

```
/clear → 새 conversation
이 파일 (specs/1979-plugin-dx-tui-integration/next-session-prompt-v6-handoff.md) 읽고 Epic <γ/ε/ζ> #<번호> resume.
```

또는 사용자가 우선순위를 직접 지정.
