# Pre-Epic Research · Epic #1979 vs #1980

> 작성일 2026-04-27 · 대상 main `f4d0e8f` (Epic #1978 머지 직후) · read-only 분석 · 코드 변경 0
> 본 문서는 Initiative #1631 차기 Epic 결정을 위한 inventory + 외부 레퍼런스 카탈로그.

## 0. TL;DR

**권고**: **Epic #1979 (Plugin DX TUI integration)을 먼저 진행한다.**

근거 3줄:
1. **Surface 작음** — `installer.py` 8-phase 흐름이 이미 끝나 있고 `plugin_op` 한 arm의 backend dispatcher 추가만 남았다. Epic #1980은 4-phase coordinator emit + worker spawn UI + permission 위임 ledger + 다부처 시나리오 디자인까지 동시에 풀어야 한다.
2. **Mock-only 데모 가능** — Spec 1636이 이미 4개 example plugin(seoul-subway / post-office / nts-homtax / nhis-check)을 ship했고 BM25 lookup ≤5s가 측정 PASS. 새 시나리오 디자인 없이 KSC 2026 시연 컷 확보 가능.
3. **Closure → Swarm 베이스 강화** — Plugin DX 끝나면 plugin tool이 LLM tool inventory에 합류 → Epic #1980 swarm worker가 호출 가능한 adapter 풀이 자연 확장. 순서를 뒤집으면 swarm 안에서 plugin tool을 어떻게 다룰지 한 번 더 결정해야 한다.

---

## 1. 코드베이스 인벤토리 (main `f4d0e8f`)

### 1.1 IPC frame 산출물 (Epic #1978 결과)

| Arm | 정의 | Backend emit | TUI consumer | 비고 |
|---|---|---|---|---|
| `user_input` | `frame_schema.py:194-199` | TUI→backend | — | LIVE |
| `assistant_chunk` | `frame_schema.py:206-215` | LLM 스트리밍 | `tui/src/ipc/codec.ts` | LIVE |
| `tool_call` | `frame_schema.py:222-233` | active primitives (lookup·resolve_location·submit·verify) | LIVE | demo at `ipc/demo/full_turn_probe.py:65-75` |
| `tool_result` | `frame_schema.py:250-258` | LIVE | LIVE | active primitive union |
| `coordinator_phase` | `frame_schema.py:265-274` | **0 emit** | `tui/src/ipc/codec.ts:265-268` | dead arm |
| `worker_status` | `frame_schema.py:281-297` | **0 emit** | `AgentVisibilityPanel` ready | dead arm |
| `permission_request` | `frame_schema.py:304-324` | partial (`agents/consent.py`) | TUI 모달 | 1978 deferred |
| `permission_response` | `frame_schema.py:331-341` | LIVE | LIVE | tests under `tests/agents/` |
| `session_event` | `frame_schema.py:348-364` | LIVE | LIVE | save/load/list/resume/new/exit |
| `error` | `frame_schema.py:371-387` | LIVE | LIVE | critical lane bypass (FR-017) |
| `payload_*` (3) | `frame_schema.py:398-500` | Spec 032 | LIVE | start/delta/end |
| `backpressure` | `ipc/backpressure.py:298-403` | LIVE | LIVE | tui_reader_saturated / writer_congested / upstream_429 |
| `resume_*` (3) | `frame_schema.py:520-580` | LIVE | LIVE | request/response/rejected |
| `heartbeat` | `frame_schema.py:585-600` | LIVE | LIVE | Spec 032 |
| `notification_push` | `frame_schema.py:605-622` | DEFERRED | DEFERRED | Requires a future app/push-notification runtime |
| **`plugin_op`** | `frame_schema.py:629-786` | request arm only TUI→backend | partial | progress/complete dead |

> Epic #1978 deferred (`#2068`/`#2069`/`#2070`/`#2071`)는 모두 OPEN로 남아있으며 본 결정에는 영향 없음.

### 1.2 Plugin DX 코드 인벤토리 (#1979 대상)

| 항목 | 경로 | 상태 |
|---|---|---|
| Slash command | `tui/src/commands/plugin.ts:1-209` | EXISTS · install/list/uninstall/pipa-text |
| Command wiring | `tui/src/commands/index.ts:13,29` | WIRED (registerCommand 됨) |
| `plugin_op` request emit | `tui/src/commands/plugin.ts:95-107,122-131,151-161` | EMIT (TUI→backend) |
| TUI plugin browser | `tui/src/components/plugins/PluginBrowser.tsx` | EXISTS · 5800B |
| TUI bundled fixtures | `tui/src/plugins/builtinPlugins.ts` | EXISTS · 4980B |
| Backend registry | `src/kosmos/plugins/registry.py` | ACTIVE · `auto_discover()` + OTEL emit |
| Backend installer | `src/kosmos/plugins/installer.py` | ACTIVE · 8-phase flow · **IPC emit 0** |
| Manifest schema | `src/kosmos/plugins/manifest_schema.py` | ACTIVE · Pydantic v2 |
| Validation checks | `src/kosmos/plugins/checks/q1..q10.py` | ACTIVE · 50-item matrix |
| Memdir path | `~/.kosmos/memdir/user/plugins/<id>/` | USED BY auto_discover |
| **Backend `plugin_op` dispatcher** | `src/kosmos/` | **MISSING** (H7 deferred) |

**핵심 갭**: TUI는 `plugin_op` request를 보낼 줄 알지만 backend는 받아서 `installer.py` 8-phase에 라우팅 + progress/complete emit하는 코드가 없다. **단일 모듈(`src/kosmos/plugins/dispatcher.py` 신설)** 가 핵심 작업.

### 1.3 Agent Swarm 코드 인벤토리 (#1980 대상)

| 항목 | 경로 | 상태 |
|---|---|---|
| Coordinator | `src/kosmos/agents/coordinator.py:78+` | ACTIVE · 4-phase (Research→Synthesis→Implementation→Verification) |
| Worker | `src/kosmos/agents/worker.py` | ACTIVE · Spec 027 mailbox 통합 |
| Mailbox base | `src/kosmos/agents/mailbox/base.py` | ACTIVE |
| File mailbox | `src/kosmos/agents/mailbox/file_mailbox.py` | ACTIVE · POSIX `~/.kosmos/mailbox/` |
| Messages | `src/kosmos/agents/mailbox/messages.py` | ACTIVE · discriminated union |
| Consent gateway | `src/kosmos/agents/consent.py` | ACTIVE · `AlwaysGrantConsentGateway` |
| TUI agents folder | `tui/src/components/agents/` | EXISTS · 18 files / 640KB |
| TUI `AgentVisibilityPanel` | `tui/src/components/agents/AgentVisibilityPanel.tsx` | EXISTS · listens for `worker_status` (no emit) |
| TUI `PhaseIndicator` | `tui/src/components/coordinator/PhaseIndicator.tsx` | EXISTS · listens for `coordinator_phase` (no emit) |
| `/agents` slash | `tui/src/commands/agents.tsx` | EXISTS · **NOT WIRED** in `commands/index.ts` |
| `coordinator_phase` emit | (search 결과 없음) | **0 emit** |
| `worker_status` emit | (search 결과 없음) | **0 emit** |
| Permission delegation across agents | (해당 코드 없음) | **MISSING** |
| Multi-ministry intent classifier | (해당 코드 없음) | **MISSING** |

**핵심 갭**: backend logic은 다 있는데 IPC 다리 + intent classifier + worker permission ledger + TUI wiring + 시연 시나리오 디자인이 모두 필요.

### 1.4 어댑터 / 프리미티브 인벤토리

| Primitive | 경로 | 상태 |
|---|---|---|
| `lookup` | `src/kosmos/tools/lookup.py` | ACTIVE · BM25 search + typed fetch |
| `resolve_location` | `src/kosmos/tools/resolve_location.py` | ACTIVE · geocoding |
| `submit` | `src/kosmos/primitives/submit.py` | ACTIVE · Spec 031 US1 |
| `subscribe` | — | DEFERRED · app/push runtime required |
| `verify` | `src/kosmos/primitives/verify.py` | ACTIVE · Spec 031 US2 |

활성 어댑터 14종 (`src/kosmos/tools/register_all.py:51-65`):
- core: `resolve_location`, `lookup`
- KOROAD ×2: accident_search, accident_hazard_search
- KMA ×6: weather_alert_status, current_observation, short/ultra-short forecast, pre_warning, forecast_fetch
- HIRA ×1: hospital_search · NMC ×1: emergency_search (L3 gated)
- NFA119 ×1: emergency_info_service (Phase 2 gated)
- MOHW ×1: welfare_eligibility_search (Phase 2 gated)

Mock 어댑터: `tools/mock/` 하위 6 family (verify) + `tools/mock/cbs|mydata|...` ship 완료.
Deprecated 어댑터 0 (composite 제거는 P3 epic으로 끝).

### 1.5 데드 frame arm 정리

| Arm | 상태 | 차기 Epic |
|---|---|---|
| `coordinator_phase` | 0 emit | #1980 |
| `worker_status` | 0 emit | #1980 |
| `plugin_op` (progress/complete) | 0 emit (request만 emit) | #1979 |
| `permission_request` | partial — `agents/consent.py` 내부만, TUI 경로 부재 | #1980 (delegation) + #1979 부분 |

---

## 2. Epic 비교표

| 축 | #1979 Plugin DX | #1980 Agent Swarm |
|---|---|---|
| Backend 핵심 작업 | `plugin_op` dispatcher 신설 + 8-phase progress emit | `coordinator_phase`/`worker_status` emit + intent classifier + permission delegation ledger |
| TUI 핵심 작업 | progress/complete consumer + browser 활성화 | `/agents` wiring + 4-phase 시각화 + worker row 스트리밍 |
| 신규 시나리오 디자인 | 불필요 (4 example plugin 재사용) | 필수 (이사 vs 응급 선택 + Mock-only path 검증) |
| 새 모듈 수 (예상) | 2-3개 (dispatcher + progress reporter + browser hook) | 6-8개 (intent classifier · phase emitter · worker scheduler · delegation ledger · /agents wiring · 시연 fixture 등) |
| 기존 산출물 활용 | Spec 1636 ≈ 95% 재사용 | Spec 027 ≈ 70% 재사용 (mailbox만 그대로) |
| Spec 인풋 준비도 | spec 미작성 — Epic body는 phase plan 명확 | spec 미작성 — Epic body 자체에 architectural questions 5개 (coordinator dispatch trigger / worker process model / correlation_id 전략 / failure 격리 / bypass-immune 권한) → /speckit-clarify 필요 |
| KSC 2026 시연 임팩트 | ★★★ — "외부 개발자가 기여한 도구 즉시 LLM에 노출" 메시지 | ★★★★★ — 다부처 swarm + 4-phase 시각화는 시각적으로 가장 강함 |
| Mock-only 데모 가능성 | ◎ (4 example plugin 즉시 사용) | ○ (이사=OPAQUE submit 부분, 응급=Mock 100% OK 둘 다 후보) |
| Hard dependency | Epic #1978 (CLOSED) | Epic #1978 (CLOSED) |
| Soft dependency | `kosmos-plugin-store/<repo>` 4종 publish 상태 | Mock 어댑터 인벤토리 (현재 6 family ship) |
| Sub-issue 예산 (≤90 cap) | M (≈30-40 task 추정) | L (≈60-90 task 추정 — 90 cap 위험) |
| Constitution §VI/§II 영향 | PIPA §26 ack flow가 IPC progress에 노출 | Bypass-immune permission steps 다부처 환경에서 재검토 필요 (§II) |

### 의존성 그래프

```
Initiative #1631
├── #1632 P0 [CLOSED]
├── #1633 P1+P2 [CLOSED]
├── #1634 P3 [CLOSED]
├── #1635 P4 [CLOSED]
├── #1636 P5 [CLOSED] ─┐
├── #1637 P6 [CLOSED]  ├── #1979 Plugin DX [OPEN] ──┐
├── #1978 IPC closure [CLOSED] ─┴── #1980 Agent Swarm [OPEN] ──┴── Initiative close
└── Deferred #2068·#2069·#2070·#2071 [OPEN]
```

`#1979`와 `#1980`은 둘 다 `#1978` 위에 직접 얹히고 서로는 soft dep (순서 뒤집어도 동작은 가능). 단 #1979 → #1980 순서면 swarm worker가 plugin tool을 invoke 가능한 풀이 자연 확장.

---

## 3. 외부 레퍼런스 카탈로그

### 3.1 Plugin DX (#1979 적용)

#### 모델 비교 매트릭스

| 모델 | discovery | capability | sandbox | auth | distribution | versioning |
|---|---|---|---|---|---|---|
| VSCode Extension | Marketplace + activationEvents | `package.json` `contributes.*` | 얕음 (Issue #52116/#59756 7년+ open) | 권한 시스템 부재 (#187386) · 2026 Copilot agent OS-sandbox | MS Marketplace | semver + `engines.vscode` |
| Cursor 2.5+ Plugins | Cursor Marketplace | bundle (MCP+skills+rules+hooks) | 격리 없음 | enterprise default-disabled | Cursor Marketplace + GitHub | manifest version |
| MCP 2025-11-25 → 2026 roadmap | `/.well-known/mcp/server-card.json` (SEP-1649) + Registry | `initialize` capability negotiation | host 책임 (stdio / Streamable HTTP) | OAuth 2.1 (draft) · RAR 논의(#1670) | MCP Registry | protocol version |
| Anthropic Skills | system prompt name+desc만 (~50-100 tok progressive disclosure) | `SKILL.md` YAML frontmatter | 격리 없음 | host 권한 위임 | Claude.ai / CC dir / API / Marketplace | manual |
| Claude Code Plugins | `/plugin` slash + marketplace.json | `.claude-plugin/plugin.json` (skills+commands+agents+hooks+MCP) | 격리 없음 | host 권한 위임 | `claude-plugins-official` GitHub | semver |
| Gemini CLI Extensions | extension list / GitHub | `gemini-extension.json` | 격리 없음 | host 권한 위임 | GitHub | manifest version |
| OpenAI Custom GPT Actions | (deprecated) GPT builder | OpenAPI 3.x | 외부 백엔드 책임 | OAuth 2.0 | GPT Store (deprecated) | OpenAPI version |
| **KOSMOS Spec 1636** | `kosmos plugin install` + 5-tier registry | `manifest.yaml` (Pydantic) — `tool_id` `plugin.<id>.<verb>` + verb + ko/en hint + permission level + auth_type + pipa_class | host 공유 (미구현) | 3-layer (Spec 033) + PIPA §26 SHA-256 ack | `kosmos-plugin-store/index` GitHub + SLSA verifier | semver + SLSA provenance |

#### 적용 표준 (2026-04 시점)

| 표준 | 상태 | KOSMOS 적합 지점 | 비용 |
|---|---|---|---|
| W3C VC 2.0 | Recommendation 2025-05-15 | `verify` 출력을 VC envelope wrap → EUDI Wallet 정합 | EdDSA/ECDSA suite + NPKI hybrid |
| OAuth 2.1 | draft-15 (미확정) | RFC 9700 BCP 인용이 안전 | — |
| RFC 9700 OAuth BCP | Published 2025-01 | KOSMOS auth 패턴에 PKCE 강제 upgrade | 낮음 |
| RFC 9396 RAR | Published 2023-05 | 부처 권한 세분화 receipt에 `authorization_details` 인코딩 | MCP 자체에서 미채택 — 선도 가능 |

#### 한국 공공 API 신규

| 채널 | 변화 | KOSMOS 적용 |
|---|---|---|
| 공공데이터포털 | 100,000개 데이터셋 돌파 (2024-12) | BM25 색인 월간 cron 권고 |
| 정부24 OpenAPI | 행안부 "공유서비스 OpenAPI 가이드라인 + 기술표준" 갱신 | adapter 작성 시 1차 참조 |
| 공공 마이데이터 | 2025-12 167종 (`adm.mydata.go.kr`) | `verify` 후속 어댑터 직접 매핑 — VC 2.0 envelope과 시너지 최대 |
| MOIS 행정정보 공동이용 | 마이데이터 활성화 정책 | verify Mock 6종 → Live 승격 1순위 |

#### KOSMOS 갭 인사이트 (#1979에서 도입 가치)

1. **`/.well-known/mcp/server-card.json` dual-publish** — KOSMOS plugin manifest를 MCP Server Card 호환으로 dual-publish 시 lock-in 회피 + 표준 영향력. CC `Tool.ts` 마이그레이션 정신과 일치.
2. **VC 2.0 envelope on verify primitive** — 어느 plugin DX도 verify를 W3C 표준 envelope으로 wrap하지 않았다. 한국 공공 + EUDI Wallet 호환성은 학술 contribution.
3. **RFC 9396 RAR로 Layer 3 권한 인코딩** — receipt JCS canonical JSON에 `authorization_details` 추가, MCP RAR 미채택 영역 선도.
4. **`engines.kosmos` 호환성 필드** — 현 manifest는 plugin semver만, host 호환성 미선언 (VSCode 패턴 차용).
5. **proposed-API 게이트** — 신규 primitive verb marketplace 게시 차단 + opt-in 발행. `subscribe` is deferred until app/push delivery exists.
6. **OS-level sandbox** (Copilot agent 2026 패턴) — PII 처리 plugin은 process-level isolation 권고.

### 3.2 Agent Swarm (#1980 적용)

#### 멀티에이전트 프레임워크 비교

| Framework | coordinator | worker spawn | state/메시지 | failure | permission | tracing |
|---|---|---|---|---|---|---|
| Anthropic Multi-agent Research | Lead(Opus) decompose + plan | sub-agent별 독립 context, 3-10 병렬 | sub→lead return only | context isolation | prompt-level scope 전달 | LangSmith-스타일 |
| AutoGen 0.4 (MS, 2025-01) | 분산 actor host (gRPC) | `agentworker.proto` unary + CloudEvents bidi | CloudEvents over gRPC | actor model crash isolation | Subscription Manager topic ACL | OTEL first-class |
| CrewAI | Crew Process(Sequential/Hierarchical) | role-based 정적 정의 | task output → next input | 약함 | role/tools whitelist | LangSmith / W&B Weave |
| LangGraph | StateGraph (DAG / cycle 허용) | node = function, edge = router | reducer-driven shared TypedDict + checkpoint | MemorySaver/Sqlite/Postgres replay | 사용자 코드 | LangSmith 1급 (Uber·LinkedIn·Klarna prod) |
| OpenAI Swarm → Agents SDK (2025-03) | Triage agent + handoff | handoff = function | stateless · Agents SDK + guardrail | Swarm 약함 / SDK retry+guardrail | scope-attenuated token 권장 | Swarm=없음 / SDK 자체 trace |
| Claude Code Task tool | main + Task spawning | 최대 10 concurrent fresh context | sub→main return only | context isolation 강함 | sub-agent type별 tool whitelist | Anthropic SDK trace |

**KOSMOS 매핑**: `coordinator.py` 4-phase ≈ Anthropic Lead-Sub 패턴, spawn은 POSIX mailbox = AutoGen actor 모델에 사상적으로 가까움.

#### Spec 027 mailbox 패턴 vs 외부

| KOSMOS 027 요소 | 가장 가까운 외부 패턴 | 평가 |
|---|---|---|
| `~/.kosmos/mailbox/<sid>/<sender>/<mid>.json` | qmail/Postfix Maildir + Akka.NET `AtLeastOnceDeliveryActor` | 잘 알려진 crash-safe 패턴 |
| `<mid>.json.consumed` sibling marker | Maildir `cur`/`new` + Postfix queue D flag | 동일 사상; rename atomic하므로 KOSMOS marker가 더 안전 |
| crash replay (no `.consumed` scan) | Akka.NET persistence journal · Ray actor `max_task_retries=-1` | KOSMOS는 marker로 idempotency 보장 → stateful 워커에도 OK |
| at-least-once delivery | Akka.NET ALOD · AutoGen gRPC + idempotency | filesystem 기반 외부 의존성 0 |

빌려올 만한 것: AutoGen 0.4 CloudEvent 스키마 (frame emit을 type+source+data triplet 표준화) · LangGraph time-travel replay (`.consumed` 마커 제거 = step replay) · Akka.NET dedup ID (sender_id+message_id).

#### KSC 2026 시연 시나리오 비교

| 시나리오 | 다부처 동시성 | Mock-only | 시각 임팩트 | 시간 압박 | 추천도 |
|---|---|---|---|---|---|
| 이사 (행안부 전입 + 국토부 부동산 + 건강보험 자격) | ★★★ | △ (행안부 submit OPAQUE — receipt mock 가능) | ★★ 폼/receipt 정적 | 없음 | ★★★★☆ — KOSMOS 미션 직설 |
| 응급 (119 위치 + 도로위험 + 응급실) | ★★ (3부처지만 순차 의존) | ◎ 모두 search/lookup Mock 100% OK | ★★★ 지도/위험점/혼잡도 동적 | ★★★ 분초 텐션 | ★★★★★ — 시연 임팩트 최강 |

**권고**: 응급=main demo, 이사=후속 30초 컷.

#### Permission delegation 표준

| 표준 | 적용 | KOSMOS 매핑 |
|---|---|---|
| W3C VC 2.0 | Rec 2025-05-15 | Spec 033 receipt를 VC wrap, PIPA §26 controller-vs-processor 매핑 필요 |
| GNAP (RFC 9635, 2024-10) | sub-agent attenuated token 위임 | coord → worker scope 축소 명시화 가능 |
| Authenticated Delegation (arXiv 2501.09674) | Human→Agent A→Agent B chain audit | Spec 033 ledger SHA-256 chain과 1:1 호환 |
| Agentic JWT (IETF I-D goswami, 2025) | 워커 버전+워크플로+위임체인 토큰 claim | OTEL `kosmos.permission.*` span으로 절반 커버 |
| Anthropic "scopes-not-prompts" (2025) | `flight.booking:create` capability grant | KOSMOS 4 primitive × adapter scope에 그대로 매핑 |

#### ReAct 후속 논문

| 논문 | 패턴 | KOSMOS 적용 |
|---|---|---|
| Reflexion (NeurIPS 2023) | verbal self-critique + episodic memory | △ single-agent reflexion same-blind-spot 강화 — coord-level cross-worker 검토가 효과적 |
| ReWOO (arXiv 2305.18323) | Planner → Worker(병렬 tool) → Solver | ◎◎ 4-phase가 ReWOO 변형. Research=Planner, Synthesis=Solver, Implementation=Worker 병렬 (5x token efficiency) |
| AgentInstruct / Orca-3 (MS 2024-07) | Content transform → Instruction gen → Refinement | △ runtime 부적합, Mock fixture 자동 생성에 응용 가능 |
| MIRROR (IJCAI 2025) | Planner → Tool agent → Executor → Answer agent | ◎ KOSMOS 4-phase 1:1 대응 · "임의가 아닌 IJCAI 검증된 분할" 주장 가능 |
| Plan-and-Execute (LangChain) | 큰 plan 한 번 + step + replan | △ ReWOO 약화판 |

> 시연/논문 narration: "ReAct 가 아니라 ReWOO + MIRROR 계열 plan-then-decompose" — `feedback_kosmos_uses_cc_query_engine` 메모리와 정합.

---

## 4. 권장 다음 에픽 결정

### 결정: **Epic #1979 Plugin DX 먼저**

#### 결정 매트릭스 점수

| 기준 (가중) | #1979 점수 | #1980 점수 |
|---|---|---|
| Surface 작음 (×3) | 8 → 24 | 5 → 15 |
| Spec input 준비도 (×2) | 7 → 14 | 4 → 8 (architectural questions 5개) |
| Mock-only 데모 가능 (×2) | 9 → 18 | 7 → 14 |
| KSC 2026 시연 임팩트 (×3) | 7 → 21 | 9 → 27 |
| Sub-issue 예산 안전 (×2) | 8 → 16 | 5 → 10 |
| 후속 Epic에 베이스 제공 (×2) | 8 → 16 | 5 → 10 |
| **합계** | **109** | **84** |

#### 후속 순서

```
[NOW] /speckit-specify Epic #1979 → spec/plan/tasks/analyze/taskstoissues/implement → 통합 PR Closes #1979
[다음] /speckit-specify Epic #1980 (이때 Plugin tool이 swarm worker invocable pool에 합류된 상태)
[Initiative #1631 close] #1979 + #1980 PR 머지 후 통합 PTY rehearsal 캡처
```

#### Epic #1979 첫 spec 진입 시 사전 의제 (Epic body의 6 phase A-F를 spec.md US로 매핑)

1. **US1**: `/plugin install seoul-subway` 시 backend dispatcher가 `plugin_op` request 수신 → installer 8-phase 진행 → progress emit 매 phase → complete emit (≤30s SC-005 보장)
2. **US2**: 설치 직후 다음 chat turn에서 LLM tool inventory에 `plugin.seoul-subway.*` 노출 — 1978 ChatRequestFrame에 합류 검증
3. **US3**: 시민 자연어 → BM25 lookup이 plugin tool 매칭 → active primitive로 invoke → permission gauntlet 정상 작동 (PIPA §26 ack flow)
4. **US4**: TUI plugin browser ⏺/○ Space i r a 키바인딩 활성화 (UI-E.3)
5. **US5**: 실패 path — SLSA verification 실패 / PIPA ack 미동의 / install timeout > 30s 각 시나리오
6. **US6**: PTY-driven E2E rehearsal (install → next turn invoke) without manual intervention

#### 차후 Epic #1980 진입 전 선행 검토 (Plugin DX closure 후 자동 unblock)

- **architectural question 5종** (Epic #1980 body 명시) — `/speckit-clarify`로 처리:
  1. Coordinator dispatch trigger — citizen-intent classifier vs `/agents start`?
  2. Worker process model — separate `kosmos.ipc.worker_server` subprocess vs in-process asyncio task?
  3. Frame envelope correlation — turn `correlation_id` vs per-worker subspan?
  4. Failure containment — single worker crash vs coordinator crash vs full swarm timeout?
  5. Bypass-immune permission steps under delegation — Constitution §II compliance.
- **시연 시나리오 확정** — 응급 (5분 main) + 이사 (30s 후속) 조합 추천.
- **표준 정합 명시** — Authenticated Delegation arXiv 2501.09674 + ReWOO/MIRROR 인용 narration 결정.

---

## 5. 참고 자료 (URL 카탈로그)

### Plugin DX

- VS Code Extension API · https://code.visualstudio.com/api
- VSCode Extension Permissions Issue #52116 · https://github.com/microsoft/vscode/issues/52116
- VSCode Sandbox Issue #59756 · https://github.com/microsoft/vscode/issues/59756
- VSCode Permission System #187386 · https://github.com/microsoft/vscode/issues/187386
- Cursor 2.5 Plugins · https://forum.cursor.com/t/cursor-2-5-plugins/152124
- MCP Spec 2025-11-25 · https://modelcontextprotocol.io/specification/2025-11-25
- 2026 MCP Roadmap · https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/
- SEP-1649 MCP Server Cards · https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1649
- MCP Issue #1670 RFC 9396 RAR · https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1670
- Anthropic Agent Skills · https://venturebeat.com/technology/anthropic-launches-enterprise-agent-skills-and-opens-the-standard
- Anthropic Skills repo · https://github.com/anthropics/skills
- Claude Code Plugins · https://code.claude.com/docs/en/plugins
- Gemini CLI Extension reference · https://geminicli.com/docs/extensions/reference/
- W3C VC 2.0 · https://www.w3.org/TR/vc-data-model-2.0/
- W3C VC 2.0 Press Release (May 2025) · https://www.w3.org/press-releases/2025/verifiable-credentials-2-0/
- RFC 9700 OAuth 2.0 BCP · https://www.rfc-editor.org/rfc/rfc9700.html
- draft-ietf-oauth-v2-1-15 · https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/
- RFC 9396 RAR · https://datatracker.ietf.org/doc/html/rfc9396
- 정부24 OpenAPI · https://www.gov.kr/openapi
- 행안부 OpenAPI 가이드라인 · https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000045&nttId=34426
- 공공데이터포털 · https://www.data.go.kr/
- 공공 마이데이터 가이드 v1.5 · https://adm.mydata.go.kr/images/guide.pdf

### Agent Swarm

- Anthropic — multi-agent research system · https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic — Building effective agents · https://www.anthropic.com/research/building-effective-agents
- AutoGen v0.4 announcement · https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/
- AutoGen Distributed Runtime · https://microsoft.github.io/autogen/stable//user-guide/core-user-guide/framework/distributed-agent-runtime.html
- LangGraph multi-agent 2025 · https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025
- OpenAI Swarm · https://github.com/openai/swarm
- OpenAI Cookbook — Orchestrating Agents · https://cookbook.openai.com/examples/orchestrating_agents
- Claude Code Sub-agents · https://code.claude.com/docs/en/sub-agents
- Akka.NET At-Least-Once Delivery · https://getakka.net/articles/persistence/at-least-once-delivery.html
- Files are hard (Dan Luu) · https://danluu.com/file-consistency/
- arXiv 2501.09674 Authenticated Delegation · https://arxiv.org/html/2501.09674v1
- RFC 9635 GNAP · https://datatracker.ietf.org/doc/html/rfc9635
- Agentic JWT IETF draft · https://www.ietf.org/archive/id/draft-goswami-agentic-jwt-00.html
- ReWOO arXiv 2305.18323 · https://arxiv.org/pdf/2305.18323
- MIRROR IJCAI 2025 · https://www.ijcai.org/proceedings/2025/0014.pdf
- AgentInstruct MS 2024-07 · https://www.microsoft.com/en-us/research/wp-content/uploads/2024/07/AgentInstruct.pdf

---

## 6. 운영 메모

- 본 문서는 read-only 분석 결과. 코드 변경 0.
- main 브랜치는 `f4d0e8f` 시점이며 Epic #1978 머지 직후. 사용자는 `docs/v0.1-alpha-presentation` 브랜치에서 발표 자료 수정 중 (uncommitted) — 본 문서는 별도 브랜치에서 commit 권고.
- 다음 단계: `git switch main && git switch -c spec/1979-plugin-dx-tui` → `/speckit-specify` 진입.
- Sub-issue 예산: ≤90 (cap). #1979는 ~30-40 추정 안전, #1980는 ~60-90 추정 (필요 시 응집 머지 검토).
- Spec workflow: AGENTS.md `§ Spec-driven workflow` 따라 specify → plan(`docs/vision.md § Reference materials` 인용) → tasks → analyze → taskstoissues → implement → 통합 PR `Closes #1979` only.
