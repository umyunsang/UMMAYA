# CC Migration Audit — 사용자 결정 사항 자체 판단

> 2026-05-03 Lead Opus 자체 판단. CORE THESIS (KOSMOS = CC + 2 swap만, byte-identical default) 기준.

## S2 Tool System
- **R4 AgentTool 11파일 정밀 byte 비교** → **Epic B 에 포함** (별도 추적)

## S3 Components
- **D1 TeleportResumeWrapper** → **양쪽 DROP**. claude.ai cloud teleport feature, swap-1 종속이라 KOSMOS 에서 제거 정당. CC 측은 NEVER-PORT 명단에 박제. **CLOSED 2026-05-03 (Epic #2639)** — `tui/src/dialogLaunchers.tsx` 의 `launchTeleportResumeWrapper` export + 관련 type-only import 제거; `tui/src/components/.never-port.md` 신규 + `scope-S3-components-screens.md` § 4/§ 9/§ 10 갱신.
- **D2 SHA-256 fail-build CI invariant** → **수용**. 브랜드 화이트리스트(W1~W12) 외 발산을 CI 단계에서 차단해 회귀 방지. **CLOSED 2026-05-03 (Epic #2639)** — `.github/workflows/cc-byte-identical-guard.yml` + `scripts/cc_byte_identical_guard.py` + `tui/src/.cc-byte-identical-whitelist.yaml` (60 entries) + vendored CC baseline (`specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`, 397 entries). W13 (dead-code-cleanup) 신규 enum 도입.
- **D3 5파일 SWAP 주석 백필** → **수용**. AssistantTextMessage / ExitPlanMode / replLauncher / interactiveHelpers / REPL 에 in-file `// SWAP:` 주석 추가. **CLOSED 2026-05-03 (Epic #2639)** — 5파일 모두 head 에 5-line 표준 `// SWAP:` 블록 박제 (cause + CC reference + LOC + spec citation + justification).

## S5 Commands/Skills
- **claude-api/ 29파일 SDK docs** → **제거**. Anthropic SDK 사용 안 함, K-EXAONE docs 는 별도 Epic 으로 신설 시 진행.
- **P0 auto-stub 21 commands** → **즉시 삭제** (Epic D 단일 cleanup 으로 묶음).
- **CC sourcemap gap 3파일** (extra-usage-core / generateSessionName / reviewRemote) → **caller-graph 재검증 후 PORT 또는 DROP** (Epic D 에서 처리).

## S6 Services
- **api/client.ts 중복 `getAnthropicClient` 정의** → **즉시 fix** (Epic E P1).
- **teamMemorySync + settingsSync** → **방안 B (claude.ts-style 박제 헤더 + dead-call gate)**. claude.ts 패턴 일관성.

## S7 IPC Bridge
- **remote/ 4파일** → **DROP + directConnectManager dead type-stub 정리** (claude.ai sync 종속).
- **notification_push arm CC 대응 검증** → **Epic F 에서 처리** (CC restored-src/src/ipc/ 정밀 비교).
- **TS↔Python frame schema codegen drift CI gate** → **신설** (회귀 위험 차단).
- **mcpb-compat.ts ADR 등록** → **수용** (KOSMOS-original 혁신 박제).

## S8 State/Boot/Misc
- **events_mono types byte-copy 전체 복원** → **즉시 P0** (CC 865 LOC vs KOSMOS 21 LOC 회귀).
- **Proxy stub 5파일 byte-copy** (constants/{messages,xml,figures}.ts + types/logs.ts + constants/oauth.ts) → **즉시 P0**.
- **cli/print.ts PORT** → **수용** (--print headless mode 핵심).
- **sdk re-declaration drift sprint** → **Epic A 에 포함** (P0 회귀 복구 일부).

## S9 Utils
- **utils/telemetry/instrumentation.ts PORT** → **즉시 P0** (Spec 021/028 OTEL 초기화 회복).
- **utils/secureStorage/ DROP 확정** (.env 단일 의존). 향후 다중 부처 키 보관 필요 시 별도 Epic.
- **utils/sessionTitle.ts PORT** → **수용** (K-EXAONE 으로 마이그레이션, 자동 제목 기능).
- **utils/mcp/dateTimeParser.ts PORT** → **수용** (MCP 한국어 시각 파싱 필수).
- **utils/permissions/permissions.ts inline-stub** → **Path B (모듈 분리)**. CC 구조 보존 원칙.
- **Stage-1 NO-OP stub** (protectedNamespace.ts / systemThemeWatcher.ts / ultraplan/prompt.txt) → **CC source 부재 확정** — CC restored-src 에 동일 파일명 없음. KOSMOS-only stub 박제 처리 (Epic A #2637 완료). TUI Fidelity Meta-Epic deferred (#TBD-protectedNamespace, #TBD-systemThemeWatcher, #TBD-ultraplan). SWAP/no-cc-source(2637) 헤더 각 파일에 박제.

---

## Epic 그룹화 (7 Epic)

| Epic | 제목 | 우선순위 | 포함 항목 | 추정 작업량 |
|---|---|---|---|---|
| **A** | P0 회귀 즉시 복구 | P0 | events_mono / Proxy stub 5 / cli/print / constants/oauth / instrumentation / Stage-1 NO-OP / toolExecution telemetry | 4~6시간 |
| **B** | Tool System 잔존 정리 | P1 | S2 R3 14 dead-import / R4 AgentTool 11 byte 비교 / tools.ts isReplModeEnabled 분기 | 3~4시간 |
| **C** | UI 정합성 가드 | P1 | S3 D2 SHA-256 fail-build CI / D3 5파일 SWAP 주석 / D1 TeleportResumeWrapper DROP | 2~3시간 |
| **D** | Commands/Skills 정리 | P1 | S5 claude-api/ 29 제거 / P0 auto-stub 21 삭제 / sourcemap gap 3 검증 | 3~4시간 |
| **E** | Services swap-1 마무리 | P1 | S6 api/client.ts 중복 / teamMemorySync 박제 / settingsSync 박제 | 2~3시간 |
| **F** | IPC/Bridge 정리 | P1 | S7 remote/ DROP / notification_push 검증 / schema drift CI / mcpb-compat ADR | 3~4시간 |
| **G** | Utils 잔존 정리 (P0 외) | P2 | S9 sessionTitle PORT / dateTimeParser PORT / permissions Path B 분리 / secureStorage DROP ADR | 4~5시간 |
