# Feature Specification: S3 UI 정합성 가드 (Epic C · #2639)

**Feature Branch**: `feat/2639-s3-ui-guard`
**Created**: 2026-05-03
**Status**: Draft
**Initiative**: #2636 — CC Migration Audit-Driven Realignment
**Epic**: #2639
**Input**: "Epic C — UI 정합성 가드. D1 (TeleportResumeWrapper 양쪽 DROP, NEVER-PORT 박제), D2 (SHA-256 fail-build CI invariant + whitelist 시스템), D3 (5파일 in-source SWAP 주석 백필). UI 영역은 byte-identical default."

## CORE THESIS 정합

KOSMOS = CC + 2 swap (LLM provider, tool surface). 그 외 byte-identical. 본 Epic 은 swap 영역 밖인 S3 (Components + Screens) 의 byte-identical default 를 **CI 게이트로 박제**하고, 이미 발산 중인 5파일에 swap 정당화 in-source 주석을 백필한다.

**Audit 결과 (S3-Opus, 2026-05-03)**: CC 395 vs KOSMOS 452 파일 중 공통 382 의 85% (329파일) byte-identical. PORT 후보는 1 (`TeleportResumeWrapper`) 이지만 claude.ai cloud Teleport 종속 → DROP 정당.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — D2 SHA-256 fail-build CI invariant (Priority: P1)

CC restored-src 와 KOSMOS `tui/src/components/`·`screens/` 의 SHA-256 발산을 PR 단계에서 자동 차단한다. brand whitelist (W1~W12, audit § 7) 외 발산은 fail-build.

**Why P1**: 본 Epic 의 핵심 회귀 방지 장치. 신규 PR 이 audit 기준 (85% byte-identical) 을 깰 경우 머지 차단 → 가장 큰 영향.

**Independent Test**: `.github/workflows/cc-byte-identical-guard.yml` 워크플로우와 `.cc-byte-identical-whitelist.yaml` 가 작성되고, 의도적 byte 변경 fixture (e.g., 임의 components/Markdown.tsx 한 줄 추가) 가 CI 에서 실패하는지 검증.

**Acceptance Scenarios**:

1. **Given** PR 이 `tui/src/components/` 의 byte-identical 파일을 변경, **When** CI 실행, **Then** SHA-256 mismatch 감지 → fail (whitelist 미등록 시).
2. **Given** PR 이 whitelist 등록 파일 (e.g., Markdown.tsx) 을 변경, **When** CI 실행, **Then** PASS (whitelist 가 cause + spec citation 보유).
3. **Given** main 브랜치 현재 상태, **When** workflow 실행, **Then** 329 byte-identical 파일 + 60 whitelisted divergence 모두 PASS.

---

### User Story 2 — D3 5파일 in-source SWAP 주석 백필 (Priority: P2)

발산 중인 5파일 head 에 swap 종속 정당화 주석 박제. audit 재실행 시 자동 분류 가능.

**Why P2**: D2 의 whitelist 시스템 위에서 동작. 주석 자체는 회귀 방지 안 하지만 audit 가독성 + 미래 grep 기반 audit 자동화의 기반.

**Independent Test**: 각 파일 head 의 `// SWAP:` 주석을 grep 으로 카운트해 5/5 PASS.

**Acceptance Scenarios**:

1. **Given** `tui/src/components/messages/AssistantTextMessage.tsx`, **When** head 30줄 grep `^// SWAP:`, **Then** 1+ match (Spec 1633/2293 cleanup citation).
2. **Given** `tui/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx`, **When** head grep, **Then** 1+ match (Spec 1633/2293 cleanup citation).
3. **Given** `tui/src/replLauncher.tsx`, **When** head grep, **Then** 1+ match (cosmetic formatting, sourceMappingURL strip 종속 명시).
4. **Given** `tui/src/interactiveHelpers.tsx`, **When** head grep, **Then** 1+ match (Anthropic Grove + analytics + auth 제거 종속 citation).
5. **Given** `tui/src/screens/REPL.tsx`, **When** head grep, **Then** 1+ match (대규모 swap-1+swap-2 entry point, 발산 LOC + spec citation).

---

### User Story 3 — D1 TeleportResumeWrapper 양쪽 DROP + NEVER-PORT 박제 (Priority: P3)

CC 측에 있고 KOSMOS 에 missing 인 유일 PORT 후보 `TeleportResumeWrapper.tsx` 를 영구 NEVER-PORT 명단에 박제. dialogLaunchers.tsx 의 dead launcher (`launchTeleportResumeWrapper`) 도 제거.

**Why P3**: 코드 변경 minimal (1 export 제거 + 명단 1줄 추가). 회귀 위험 lowest. claude.ai cloud Teleport (Anthropic 계정 동기화) = swap-1 종속.

**Independent Test**: `tui/src/dialogLaunchers.tsx` 에서 `launchTeleportResumeWrapper` export 제거 + `tui/src/components/.never-port.md` 명단에 `TeleportResumeWrapper.tsx` 추가 + audit 문서 § 10 NEVER-PORT 명단에 entry 추가 후 grep 확인.

**Acceptance Scenarios**:

1. **Given** `tui/src/dialogLaunchers.tsx`, **When** grep `launchTeleportResumeWrapper`, **Then** 0 matches (export 제거).
2. **Given** `tui/src/components/.never-port.md`, **When** grep `TeleportResumeWrapper`, **Then** 1+ match.
3. **Given** `bun test` 실행, **When** TUI 컴포넌트 테스트 통과, **Then** dialogLaunchers 의존 회귀 0.

---

### Edge Cases

- **whitelist drift**: 새 swap-driven 발산이 whitelist 등록 없이 머지될 위험 → CI fail-build 가 차단. 신규 발산은 whitelist update + spec citation 동반 PR 로만 머지 가능.
- **CC restored-src absence in CI**: `.references/` 가 .gitignore → CI checkout 단계에서 git clone CC sourcemap subrepo 또는 vendored snapshot 필요. 본 spec 은 vendored snapshot 방식 채택 (audit fixture 재사용).
- **stale-source 케이스**: CC 가 2.1.88 이상으로 갱신될 경우 SHA-256 비교 baseline 변경 필요 → ADR-004 (Spec 287) update 별도 cycle.
- **launcher caller**: `launchTeleportResumeWrapper` 가 grep 결과 caller 0 → 제거 안전. caller 발견 시 caller 도 동시 제거.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 (D2)**: System MUST CI workflow `.github/workflows/cc-byte-identical-guard.yml` 를 도입해 PR / main push 시 `tui/src/components/`, `tui/src/screens/`, `tui/src/dialogLaunchers.tsx`, `tui/src/interactiveHelpers.tsx`, `tui/src/replLauncher.tsx`, `tui/src/outputStyles/`, `tui/src/moreright/` 의 모든 `.ts`/`.tsx` 파일을 SHA-256 비교한다.
- **FR-002 (D2)**: System MUST `.cc-byte-identical-whitelist.yaml` (또는 동등 형식) 를 도입해 의도된 swap-driven divergence 60파일 + Korean IME / brand / mascot / sdk-compat / sourceMappingURL strip 케이스를 enumerate. 각 entry 는 `path`, `cause` (W1~W12 enum), `spec_ref` (issue or doc), `expected_sha256` (선택) 필드 보유.
- **FR-003 (D2)**: System MUST whitelist 미등록 + SHA-256 mismatch + CC 측 파일 존재 시 CI fail. CC 측 파일 부재 (KOSMOS-only) 는 PASS.
- **FR-004 (D2)**: System MUST CC sourcemap reference 를 CI runner 에 제공한다 (vendored fixture: `specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt` 형식 — `<sha256>  <relative_path>` 라인 enumeration, `shasum -a 256` 형식). audit 재실행 시 baseline 갱신.
- **FR-005 (D2)**: System MUST regression fixture (`specs/2639-s3-ui-guard/fixtures/intentional-divergence-test.md`) 로 의도적 byte 변경 시 fail-build 동작을 문서화 + 로컬 reproducibility 보장.
- **FR-006 (D3)**: System MUST 5파일 (`tui/src/components/messages/AssistantTextMessage.tsx`, `tui/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx`, `tui/src/replLauncher.tsx`, `tui/src/interactiveHelpers.tsx`, `tui/src/screens/REPL.tsx`) head 에 in-source `// SWAP:` 주석 블록을 추가한다. 형식:

```ts
// SWAP: <swap-1 LLM provider | swap-2 tool surface | brand | dead-code-cleanup>
// CC reference: .references/claude-code-sourcemap/restored-src/<absolute path>
// Divergence LOC: <approximate count>
// Spec citation: <issue # or spec/<feature>/spec.md>
// Justification: <one-sentence>
```

- **FR-007 (D1)**: System MUST `tui/src/dialogLaunchers.tsx` 의 `launchTeleportResumeWrapper` export 를 제거한다 (dead launcher, caller 0).
- **FR-008 (D1)**: System MUST NEVER-PORT 명단 (`tui/src/components/.never-port.md`) 에 7번째 entry `TeleportResumeWrapper.tsx` 추가. CORE THESIS 명시 — claude.ai cloud Teleport = swap-1 종속.
- **FR-009 (D1)**: System MUST `specs/cc-migration-audit/scope-S3-components-screens.md` § 10 의 NEVER-PORT 명단에 `TeleportResumeWrapper.tsx` 추가. 기존 6 entry → 7 entry.
- **FR-010**: System MUST `bun test` 회귀 0 (current main 대비 pass count 동일).
- **FR-011**: System MUST 본 Epic 은 zero new runtime dependency. CI 워크플로우는 stdlib `shasum`, `bash`, `python3` (fixture parsing) 만 사용.
- **FR-012**: System MUST whitelist 와 spec/decisions.md § S3 entries 를 cross-reference. D1/D2/D3 close 시 decisions.md § S3 의 모든 항목이 implementation 경로 보유.

### Key Entities

- **CcByteIdenticalWhitelist**: YAML 파일. fields = `path` (relative to repo root), `cause` (enum: W1 sdk-compat, W2 brand-string, W3 mascot, W4 brand-glyph, W5 i18n, W6 palette, W7 1p-removed, W8 sourcemap-strip, W9 llm-render, W10 ime-fix, W11 sandbox-strip, W12 otel-instrumentation, OR W13 dead-code-cleanup), `spec_ref` (string), `expected_sha256` (optional).
- **CcByteIdenticalBaseline**: text 파일. `<sha256>  <relative-path>` 라인 list. `specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`. CC restored-src 의 components/screens/top-level 파일 SHA-256 enumeration.
- **NeverPortRegistry**: markdown 파일. `tui/src/components/.never-port.md`. 영구 NEVER-PORT 명단 (Feedback, Grove, GuestPassesUpsell, OverageCreditUpsell, Passes, Settings/Usage, TeleportResumeWrapper).

## Success Criteria *(mandatory)*

- **SC-001**: CI workflow 가 머지 전 `tui/src/{components,screens,...}` SHA-256 baseline + whitelist 검증 PASS. baseline mismatch + whitelist 미등록 → fail.
- **SC-002**: 5파일 head 에 `// SWAP:` 주석 박제. grep `// SWAP:` count = 5 (D3 대상 파일 한정).
- **SC-003**: `dialogLaunchers.tsx` 에서 `launchTeleportResumeWrapper` 0 occurrence. NEVER-PORT 명단에 7th entry 추가.
- **SC-004**: `bun test` parity (current main 통과 카운트 = ±0).
- **SC-005**: Layer 5 tmux capture 로 TUI boot + branding + `/help` 정상 동작 확인 (D3 주석 추가가 런타임 회귀 없음 증명).
- **SC-006**: Zero new runtime dependency (TS 또는 Python).
- **SC-007**: `specs/cc-migration-audit/decisions.md § S3` 의 D1, D2, D3 항목 모두 implementation 완료 표시 가능.
- **SC-008**: regression fixture (intentional-divergence-test.md) 가 의도적 byte 변경 시 CI fail 을 reproducibility 보장.

## Out of Scope

- whitelist 의 60+ entry 마다 spec issue 신설 — 기존 spec citation 만 채움. 신규 issue 는 audit gap 발견 시에만.
- TUI 의 KOSMOS-only 64 파일 (5-primitive renderers, onboarding, citizen UI 등) audit registry 신설 — D4 (LOW) 항목, 본 Epic 범위 밖.
- W1~W12 외의 신규 whitelist enum 도입 — W13 (dead-code-cleanup) 만 본 spec 에서 도입. 추가 enum 은 차후 spec.
- CC sourcemap 갱신 (2.1.88 → 차기 버전) baseline regen — ADR-004 separate cycle.
- TeleportProgress / TeleportError / TeleportStash / TeleportRepoMismatchDialog 의 잔존 caller graph 정리 — 본 Epic 은 ResumeWrapper 만. 나머지는 Spec 2293 (UI residue cleanup) deferred.
