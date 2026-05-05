# Audit-5 — /agents + Ministry agent + Subscribe primitive integration (PROD readiness)

> **VERDICT — PRODUCTION READY: NO.** 6 P0 blockers, 4 P1 issues, 3 dead-code surfaces.
> The static UI shells (empty state, --detail column header, FU-5 placeholder) all render correctly.
> The dynamic chain — citizen → subscribe primitive → registry record → /agents row — is broken at three independent layers (P0-1 inherited from audit-4, P0-2 backend handle synthesis, P0-3 Esc dismiss). Swarm threshold (UI-D.2 A+C union) is dead code: defined, exported, imported, never called.
>
> Date: 2026-05-04 · Lead Opus · Scope: /agents + AgentVisibilityPanel + subscribe primitive + worker_status frame + ministry-agent surfaces.
> Run env: macOS Darwin 25.2.0, tmux 3.6a, bun 1.3.12, K-EXAONE on FriendliAI.
> Captures: `specs/audit-prod/snap-5-agents-subscribe/` (snap-000 .. snap-005 valid + 1 timeout).
> Backend smoke (bypass UI): `python -c "subscribe(...)"` → all 3 modalities yield events successfully.

---

## P0 findings (production blockers)

| # | Severity | Surface | Finding | Evidence |
|---|---|---|---|---|
| **P0-1** | CRITICAL | TUI permission gauntlet | **Y/A/N selector functionally frozen — INHERITED from audit-4 P0-1.** PermissionPrompt uses `CustomSelect` (`tui/src/components/CustomSelect/use-select-input.ts:255-282`) which only accepts `/^[0-9]+$/` digits + arrow+Enter; `Y`/`A`/`N` letters are pure label text with no hotkey binding. Even sending `1` through tmux fails because PromptInput captures stdin first (audit-4 P0-1 root cause). Result: every subscribe primitive call permanently freezes at the permission gauntlet — `subscriptionRegistry.record()` is unreachable in any citizen flow. | `snap-006-stage3-cbs-permission-or-result.txt` (run 1) shows modal mounted; subsequent `Y` keystrokes get echoed into the `❯` prompt buffer (snap-013 line 18 `❯ Y                      n_id":"929a5931...`) and never dismiss the modal. |
| **P0-2** | CRITICAL | Backend stdio.py | **subscribe primitive returns a SYNTHETIC `subscription_id` instead of the real `SubscriptionHandle.subscription_id`.** stdio.py:1822-1830 calls `subscribe(inp_sub)`, gets the iterator, then writes `"subscription_id": str(uuid.uuid4())` — a fresh UUID disconnected from the iterator's actual handle. The TUI subscriptionRegistry records this synthetic ID; if streaming events were ever wired (T069 deferred), they would arrive with a different `subscription_id` and never correlate. | `src/kosmos/ipc/stdio.py:1825-1828`. Confirmed by reading `kosmos.primitives.subscribe._SubscribeIterator._start():422` which generates the canonical `subscription_id` only when `__anext__` is first awaited — but the dispatcher returns BEFORE `__anext__` is called. |
| **P0-3** | CRITICAL | TUI overlay | **Esc does NOT dismiss /agents panel.** AgentsCommandView in `tui/src/commands/agents.tsx:117-122` registers `useInput((_,k)=>k.escape && onExit())`, AND REPL.tsx mounts it with `isLocalJSXCommand: false` per AGENTS.md insight #3. But snap-003 (after Esc post-/agents) and snap-005 (after Esc post-/agents --detail) both retain the panel. The PromptInput's own Esc handler ("esc to interrupt" footer at snap-002 line 27) is consuming the keystroke. | `snap-003-stage1-after-esc.txt` lines 6-12 = identical to snap-002 panel; `snap-005-stage2-after-esc.txt` lines 6-13 = identical to snap-004. Across both runs, deterministic. |
| **P0-4** | CRITICAL | Backend → TUI | **`worker_status` frame is DEFINED but never EMITTED anywhere in the backend.** `frame_schema.py:512-545` declares `WorkerStatusFrame`, but `grep -rn worker_status src/kosmos/agents/{worker,coordinator}.py src/kosmos/ipc/stdio.py` returns **zero hits** outside the schema declaration. AgentVisibilityPanel.tsx:159-211 listens for `frame.kind === 'worker_status'` — the listener will never fire. Spec 027 Agent Swarm wire is half-built. The Lead-FU-5 subscriptionRegistry workaround partially compensates IF P0-1/P0-2 were fixed; they aren't. | `grep -rn worker_status /Users/um-yunsang/KOSMOS/src` → only frame_schema.py:62/512/516/520/1335/1405 + __init__.py:9/26/40 (all schema/export — no emit). |
| **P0-5** | CRITICAL | UI-D.2 wiring | **Swarm threshold (3+ ministries OR complex tag) is DEAD CODE.** `shouldActivateSwarm` is exported from `schemas/ui-l2/agent.ts:45`, imported once at `screens/REPL.tsx:358`, and **never called** anywhere in the entire `tui/src/` tree. The `swarmActivated` i18n string ("Swarm 모드 활성화 (3+ 부처 또는 복잡 질의)") at `i18n/uiL2.ts:138/225` is defined but never read. Migration tree §UI-D.2 "A+C 혼합" is unimplemented. | `grep -rn "shouldActivateSwarm\b" tui/src` → 2 hits: definition + import. `grep -rn "swarmActivated" tui/src` → 3 hits: type + 2 locale strings. No consumer. |
| **P0-6** | CRITICAL | UI corruption | **Raw IPC NDJSON spilled into the prompt input AND the panel borders.** `snap-013-stage6-after-esc.txt` line 18 shows `❯ Y                      n_id":"929a5931-8f46-43b1-ba2c-4bf583f1127b","correlation_id":"8ffccaa4-7f59-4788-b9ea-f01e3d772a13","ts":"...","role":"tui","frame_se` — the raw NDJSON envelope leaking into the rendered terminal. This is the same class of bug as audit-4 P0-8 (`process.stdout.write` racing with the Ink renderer). Manifests when the agents overlay is up AND a subscribe call is in flight. tmux session crashed shortly after (run 1 stage 8 → "can't find pane"). | `snap-013/14/15` (run 1). The leak corrupts both the prompt buffer and the panel border (snap-014 line 18 `❯ Y/agents --detail` shows the queued message stuck in the buffer). |

## P1 findings (high — fix before production)

| # | Severity | Surface | Finding |
|---|---|---|---|
| P1-1 | HIGH | UX cosmetic | Permission gauntlet label "Y  한 번만 허용" is misleading — citizens reasonably expect `Y` to be a hotkey. The CustomSelect accepts only digits or arrow+Enter (`use-select-input.ts:257`). Either add letter-shortcut handling or rename labels to `1.` / `2.` / `3.` exclusively. |
| P1-2 | HIGH | TUI render | `subscriptionRegistry.deriveMinistryFromToolId` (`subscriptionRegistry.ts:87-99`) hardcodes prefix → label mapping. `mock_cbs_disaster_v1` → "MOCK" (fallback to `head.toUpperCase()` of `mock`), NOT "CBS" (regex `^cbs_/i` requires the toolId to START with `cbs_`, not contain it). The 3 documented mock tool_ids all begin with `mock_*`, so all 3 collapse into the single ministry label "MOCK" — citizen sees indistinguishable rows in /agents. |
| P1-3 | HIGH | Backend feature gap | T069 streaming events are deferred (stdio.py:1820 comment). The TUI's `⎿` prefix promise ("실시간 스트림은 대화창에서 별도 ⎿ 인용으로 전달됩니다." in `SubscribePrimitive.ts:293`) is unfulfilled — no event ever arrives at the citizen. |
| P1-4 | HIGH | Two-source split | resolveInitialEntries (subscriptionRegistry — TUI-only) and the worker_status listener (backend — never fires) are **two parallel data sources** that never merge. AgentVisibilityPanel naively concatenates. Future backend `worker_status` emission for subscribe will create double-counting (registry-row + worker-row for the same handle). Needs a unique-key reconciler keyed on `subscription_id` BEFORE either path goes live. |

## P2 findings (medium)

| # | Severity | Surface | Finding |
|---|---|---|---|
| P2-1 | MED | UX | /agents footer hint "ESC 종료" lies (P0-3). |
| P2-2 | MED | Schema | `AgentVisibilityEntry.sla_remaining_ms` and `rolling_avg_response_ms` are nullable; subscriptionRegistry always sets them to `null`. The --detail column shows "—" placeholder rows for every subscription — the only data the column was supposed to surface. SLA/health/avg-response are unfetched even though the schema permits the fields. |
| P2-3 | MED | OTEL | `SubscribePrimitive.call` emits no OTEL event on `subscriptionRegistry.record()`. The Lead-FU-5 mirror is invisible to Langfuse. |

## Backend ↔ Frontend wiring matrix

| Surface | Expected (per spec) | Observed | Status |
|---|---|---|---|
| `/agents` empty render | "활성 부처 에이전트 없음" placeholder | YES — snap-002 line 9 | OK |
| `/agents --detail` column header | 부처 / 상태 / SLA / 건강 / 평균응답 | YES — snap-004 line 9 | OK |
| `/agents --detail` empty placeholder row | "subscribe 도구 호출 시 여기에…" | YES — snap-004 line 12 (FU-5 fix landed) | OK |
| Esc dismiss /agents | panel unmounts | NO — P0-3 | FAIL |
| LLM picks subscribe primitive | tool_call frame with primitive=subscribe | YES — snap-006 line 9 ("∴ Thinking — 사용자가 재난방송 CBS 긴급재난문자 알림 구독을 요청했습니다") + permission modal mounts | OK |
| Permission gauntlet renders | layer ⓶, "main" tool, PIPA citation | YES — snap-006 lines 12-23 | OK |
| Y/A/N selector accepts citizen decision | Enter/digit/letter | NO — P0-1 | FAIL |
| subscribe primitive returns real handle_id | from `SubscriptionHandle.subscription_id` | NO — P0-2 (synthetic UUID) | FAIL |
| `subscriptionRegistry.record()` fires | on ok=true subscribe response | UNREACHABLE in citizen flow (P0-1 blocks) | FAIL |
| /agents shows 3 subscription rows | 3 entries with ministry labels | UNREACHABLE (and P1-2 would collapse to 1 row "MOCK") | FAIL |
| --detail SLA/건강/평균응답 columns populated | non-null values | NO — P2-2 (always null → "—") | FAIL |
| `worker_status` frame emitted | Spec 027 Agent Swarm | NEVER (P0-4) | FAIL |
| AgentVisibilityPanel `bridge.frames()` listener | updates entries on worker_status | dead receiver (P0-4) | FAIL |
| Swarm activation banner on 3+ ministries | UI-D.2 A+C union | NEVER (P0-5) | FAIL |
| `swarmActivated` i18n string used | rendered when threshold tripped | dead string (P0-5) | FAIL |
| Stream events arrive at TUI `⎿` | post-handle event delivery | NEVER (P1-3, T069 deferred) | FAIL |

## Static UI shells — what works

These are the ONLY surfaces of this audit that pass:

1. /agents empty state (`activate 부처 에이전트 없음`) — snap-002.
2. /agents --detail empty state with column header AND FU-5 placeholder row — snap-004.
3. Permission gauntlet mounting (layer ⓶ banner + "main" tool + PIPA §22-2/26 citation Korean text) — snap-006.
4. Backend subscribe primitive (verified via direct Python call): all 3 mock adapters yield events on a 2-second lifetime.

Everything else fails.

## Backend smoke (bypass UI) — 100% PASS

```
$ python -c "asyncio.run(test 3 mock subscribe adapters)"
mock_cbs_disaster_v1: iterator returned (async iterator OK)
  → events emitted: 1
mock_rss_public_notices_v1: iterator returned (async iterator OK)
  → events emitted: 1
mock_rest_pull_tick_v1: iterator returned (async iterator OK)
  → events emitted: 1
```

Backend subscribe primitive + 3 mock adapter registrations work as designed. The backend is NOT the bottleneck. **Every blocker is in the IPC + TUI seam.**

## Production readiness — verdict

**NO.** Six P0 blockers prevent the citizen-facing /agents + subscribe + ministry-agent chain from functioning end-to-end:

- P0-1 (inherited from audit-4): permission gauntlet frozen → no subscribe call ever completes.
- P0-2: even if P0-1 were fixed, backend hands TUI a synthetic UUID disconnected from the real handle.
- P0-3: even if P0-1+P0-2 were fixed, citizen cannot dismiss /agents and continue.
- P0-4: even if P0-1+2+3 were fixed, worker_status path is permanently dead — Spec 027 Agent Swarm contributes zero data.
- P0-5: even if P0-1+2+3+4 were fixed, swarm activation logic (UI-D.2) never runs.
- P0-6: NDJSON terminal corruption + tmux crash suggests a pre-existing race in the stdout writer that gets exposed when /agents is up + LLM is streaming.

The static empty states + permission modal cosmetic shell pass. Nothing dynamic does.

## Recommended remediation order

1. Fix P0-1 (audit-4 inheritance) — wire CustomSelect Y/A/N letter shortcuts OR rename to 1/2/3-only labels AND fix PromptInput stdin precedence (audit-4 root-cause).
2. Fix P0-2 — surface `iterator._handle.subscription_id` from stdio.py (defer T069 streaming events but at least return the canonical handle so registry records the right ID).
3. Fix P0-3 — debug Esc routing in /agents overlay; PromptInput's Esc handler must yield to overlay's useInput when isLocalJSXCommand=false.
4. Fix P0-6 (audit-4 P0-8 sibling) — funnel all backend → TUI writes through the IPC bridge, never `process.stdout.write` direct.
5. Fix P1-2 — extend `MINISTRY_PREFIXES` regex set to match `^mock_(cbs|rss|rest)_*` so the 3 documented mock adapters render distinct labels.
6. Either implement P0-4 (emit worker_status from worker.py / coordinator.py for the swarm path) OR delete the listener wire from AgentVisibilityPanel + the `worker_status` frame + Spec 027 mailbox path.
7. Either implement P0-5 (call shouldActivateSwarm from REPL onSubmit + render swarmActivated banner when true) OR delete the import + i18n strings + the predicate.
8. Fix P1-3 — wire T069 streaming events through ToolResultFrame chunks OR document the `⎿` prefix promise as Phase-2 only.
9. Re-run audit-5 end-to-end and confirm 3 subscribe → 3 /agents rows → /agents --detail populates SLA/health/avg.

Until at minimum P0-1 through P0-4 are fixed, the L1 pillar B (Tool System) primitive `subscribe` is non-functional from the citizen surface, and the L1 pillar B / UI L2 §D.1 (`/agents`) command is purely decorative.
