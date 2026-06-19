# UMMAYA 마이그레이션 요구사항 트리

> 2026-04-24 사용자 승인 완료. 이 문서는 `docs/vision.md` 의 Layer 설계와
> L2 UI 결정사항을 통합한 **canonical 요구사항 트리**. 모든 후속 spec/PR
> 은 이 트리를 근거로 한다.

## ROOT · UMMAYA 미션

DX 기반 대한민국 국가 인프라(분야·부처·기관별 국가행정시스템)를 **AX화**
하기 위해 EXAONE LLM 위에 하네스를 구축. LLM이 각 기관 API/SDK를 자율
호출 + 메인 도구를 추상화해 국민이 국가행정시스템을 쉽게 이용.

> CC가 **"개발자 중심 코딩 하네스"** 라면 UMMAYA는 **"국민·국가·국가행정
> 시스템 작업 하네스"** (비교: `docs/vision.md § 3`).

## L1 기둥 3개

### L1-A · LLM Harness Layer  (✅ 머지 완료 · Initiative #1631 / Epic #1637 · 2026-04-26; P3 agentic loop closure superseded by Epic #1978 — ChatRequestFrame arm added 2026-04-27)

| 결정 | 값 | 근거 |
|---|---|---|
| A1 Provider | FriendliAI serverless + K-EXAONE 단일 고정 | 메모리 `project_friendli_tier_wait` |
| A2 Agent loop | CC 루프 1:1 보존 | Spec 031 |
| A3 Tool protocol | EXAONE native function calling | FriendliAI OpenAI-compat |
| A4 Context | `prompts/system_v1.md` · compaction · prompt cache | Spec 026 |
| A5 Session | `~/.ummaya/memdir/user/sessions/` JSONL · --continue/--resume/--fork/new | Spec 027 |
| A6 Error recovery | 일반 네트워크 retry only (429 제거 · Kakao 오탐 정정) | FriendliAI Tier 1 확정 |
| A7 Observability | 4-tier OTEL (GenAI / Tool / Permission / 로컬 Langfuse) · 외부 egress 0 | Spec 021 + Spec 028 |

### L1-B · 국가 행정 도구 시스템  (🔄 3차 정정 2026-04-29 · Initiative #2290)

| 결정 | 값 |
|---|---|
| B1 Registry | CC `Tool` 인터페이스 byte-identical 사용 · 각 기관의 기존 API/SDK/포털/신원 채널을 LLM-callable 모듈 1개 → 도구 1개로 래핑 → ToolRegistry 등록 |
| B2 Discovery | `find` 기반 BM25+dense 하이브리드 어댑터 발견 + fetch |
| B3 분류 | 3-tier: Live · Mock · OPAQUE-forever (시나리오만, 어댑터 X). 현재 본인확인 계열은 공식 credential이 없는 한 Mock/shape-mirrored이며, 해커톤 목표는 OmniOne CX/Open DID/Chain으로 이 경로를 Live 후보로 승격하는 것. |
| B4 Permission | 본인확인·동의·위임은 `check` primitive 어댑터에서 시작 · 현재는 mock/shape-mirrored 본인확인 도구가 같은 contract를 검증하고, Live 전환은 OmniOne CX/Open DID/Chain 연동으로 진행 · CC `<PermissionRequest>` byte-identical UX 사용 · 각 어댑터가 기관 자체 정책 citation. UMMAYA는 권한 정책 발명 X. |
| B5 커버리지 | 하이브리드: Live + Mock + 플러그인 인프라 (Spec 1636) |
| B6 Composite | 제거 · LLM primitive chain |
| B7 문서 | 어댑터별 Markdown + JSON Schema/OpenAPI + index |
| B8 Plugin DX | Full 5-tier · 한국어 primary · PIPA 수탁자 책임 명시 |
| B9 Caller 정체성 | UMMAYA = 국가AX 인프라가 정형화할 LLM-accessible 보안 wrapping 통로의 **client-side reference implementation**. LLM은 답변 참고용 RAG가 아니라 사용자 요청을 분해·계획하고 기존 공공채널 어댑터를 호출하는 실행 주체. 기관 시스템 변경 요구 X. 상세 구현은 Initiative #2290 spec-driven 진행. |

### L1-C · 메인 동사 추상화  (✅ 머지 완료 · Initiative #1631 / Epic #1637 · 2026-04-26)

| 결정 | 값 |
|---|---|
| C1 Primitive | `find` · `locate` · `send` · `check` · `document` (5개 active, 공개 alias `lookup`/`resolve_location`/`submit`/`verify`) · `subscribe` 제거/보류. `check`는 모바일신분증·마이데이터·인증서·OmniOne CX/QR 같은 본인확인/위임 채널을 도구 호출로 감싸고, 현재 mock contract를 해커톤에서 live OmniOne-backed tool로 전환하는 대상이며, `send`는 그 위임 결과로 신청·제출·납부형 공공채널 어댑터를 호출. `document`는 한국 공문서(HWP/HWPX/PDF/OOXML/ODF) 작성 harness로 Evidence Fabric+승인 게이트 통과 시에만 동작 (`send`·`document`는 heavy-gate, `check`는 light-gate) |
| C2 Envelope | 공통 `PrimitiveInput/Output` 표준 |
| C3 Routing | Self-classify + 중앙 `build_routing_index()` · CI consistency test |
| C4 LLM 노출 | system prompt에 primitive 서명만 + BM25 동적 제시 |
| C5 Permission | Adapter-level only (primitive default 없음) |
| C6 보조 도구 | Historical MVP helper-surface decision: MVP 7 (WebFetch · WebSearch · Task · Translate · Calculator · DateParser · ExportPDF) · Phase2 5 (TextToSpeech · SpeechToText · LargeFontRender · OCR · Reminder). For the full CC original tool-layer port, `docs/requirements/cc-tool-layer-scope-contract.md` supersedes the old blanket helper exclusion: Read, Write, Edit, Bash, Glob, Grep, and NotebookEdit can be registered capabilities when policy permits, but they are not automatically always-loaded. |
| C7 Primitive 확장 | `plugin.<id>.<verb>` 네임스페이스 · 4 root 예약 |

## UI L2 결정사항

### UI-A · Onboarding (5 step)
- A.1 Step 레이아웃: `preflight → theme → pipa-consent → ministry-scope → terminal-setup`
- A.2 `/onboarding` · `/onboarding <step>` 재실행
- A.3 한국어 primary · English fallback · 日本語 예정
- A.4 접근성 4종 토글 (스크린리더 · 큰글씨 · 고대비 · reduced motion)
- A.5 동의 철회: audit ledger / OTEL 보존 · 대화 기록 옵션

### UI-B · REPL Main
- B.1 스트리밍: **chunk (≈20 token)**
- B.2 긴 응답: CC `Ctrl-O` expand/collapse 방식
- B.3 Markdown:
  - (a) 인라인 미리보기 + **PDF 인라인 렌더** (Kitty/iTerm2 graphics protocol 감지 시 `pdf-to-img` WASM으로 PNG 변환 · 미지원 시 `open` fallback)
  - (b) 표 렌더는 CC `MarkdownTable` 방식 그대로
- B.4 에러 envelope 3종 (LLM · Tool · Network) 채택
- B.5 Multi-turn 맥락 인용: `⎿` 접두 + single-border 박스
- B.6 Slash command autocomplete: CC 방식 (드롭다운 + highlighted match + 인라인)

### UI-C · Permission Gauntlet
- C.1 Layer 색: 1=green ⓵ / 2=orange ⓶ / 3=red ⓷
- C.2 Modal `[Y 한번만 / A 세션 자동 / N 거부]` + receipt ID 표시
- C.3 `/consent list` 이력 조회
- C.4 `/consent revoke rcpt-<id>` 확인 모달
- C.5 Shift+Tab 모드 전환 · `bypassPermissions` 시 강화 확인

### UI-D · Ministry Agent
- (proposal-iv.mjs 5 states 확정)
- D.1 `/agents` 기본 + `/agents --detail` (SLA · 건강 · 평균응답)
- D.2 Swarm 임계치: **A + C 혼합** (3+ 부처 명시 트리거 + LLM "복잡" 태그 보정)

### UI-E · 보조 surface
- E.1 HelpV2 그룹화 (세션 / 권한 / 도구 / 저장)
- E.2 Config overlay · 비밀값은 `.env` 편집 격리
- E.3 Plugin browser (⏺/○ 토글 · Space · 상세 i · 제거 r · 스토어 a)
- E.4 Export PDF · 대화+도구+영수증 포함, OTEL/플러그인 내부 제외
- E.5 History search 필터 3종 (날짜 / 세션 / Layer)

## 마스코트 · 브랜딩 확정

- **UMMAYA 홈 시그널 마스코트** (지붕 + 출입구 + 호출 신호 · 4-pose CC Clawd 기법)
- **팔레트 웜 앰버** · body `#f59e0b` / background `#7c2d12`
- **Brand glyph ✻** CC 유지
- **Thread glyph ⏺ · ⎿** CC 유지

## 실행 Phase 순서

```
P0 · Baseline Runnable                — CC src 컴파일·런타임 복구
P1 · Dead code elimination            — ant-only · feature() · migration · telemetry
P2 · Anthropic → FriendliAI           — API · auth · OAuth → FriendliAI 상수
P3 · Tool system wiring               — Tool.ts + Python stdio MCP · 4 primitive  [superseded by Epic #1978: ChatRequestFrame (arm 21) + agentic loop wired 2026-04-27]
P4 · UI L2 구현                       — B/C/D/E/A 실제 컴포넌트 반영
P5 · Plugin DX                        — template · CLI · docs · examples · registry
P6 · Docs + Smoke                     — docs/api · docs/plugins · bun run tui 검증
```

## 추적

모든 Phase는 별도 Epic 이슈로 발행되며 이 문서를 canonical 근거로 인용.
Spec 작성 시 `docs/requirements/ummaya-migration-tree.md § N` 형식으로 참조.
