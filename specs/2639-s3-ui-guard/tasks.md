# Tasks: S3 UI 정합성 가드 (Epic C · #2639)

**Spec**: [`spec.md`](./spec.md) · **Plan**: [`plan.md`](./plan.md) · **Initiative**: #2636

총 12 task · 5 task group · D1·D2·D3 mostly file-disjoint → Lead solo 처리 (overhead < dispatch).

## Phase 0 — Setup (Lead)

### T001 — fixtures/ 디렉토리 + cc-baseline-shas.txt 생성 [P]

- 위치: `specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`
- 명령: CC restored-src 의 components/ + screens/ + outputStyles/ + moreright/ + 3 top-level (`dialogLaunchers.tsx`, `interactiveHelpers.tsx`, `replLauncher.tsx`) 를 sort + shasum -a 256 로 enumerate.
- 검증: 파일 라인 count ≈ 397 (audit § 1 의 395 + outputStyles 1 + moreright 1).

## Phase 1 — D2 Whitelist + CI workflow (Lead)

### T002 — `tui/src/.cc-byte-identical-whitelist.yaml` 작성 [P]

- 60+ entry. 출처: audit § 5 의 divergence 매트릭스 + § 5.1 18 sdk-compat 파일 + § 5.2 brand 4파일 + § 5.3 sourceMappingURL 1파일 + § 5.4 cosmetic 12파일 + § 5.5 documented swap 8파일 + § 5.6 mascot 5파일 + § 5.7 top-level 3파일.
- cause enum: W1~W13 (W13 = dead-code-cleanup, 신규 도입).
- spec_ref 필드: github issue # OR doc path. 미상 시 `audit § 5.x`.
- 검증: `python3 -c "import yaml; print(len(yaml.safe_load(open('tui/src/.cc-byte-identical-whitelist.yaml'))['entries']))"` 60+ 출력.

### T003 — `scripts/cc_byte_identical_guard.py` 작성

- stdlib + pyyaml. argparse `--baseline <path> --whitelist <path> --slice-root <path>`.
- algorithm: plan.md § 2.2 의 pseudocode 그대로.
- exit 0 PASS, exit 1 FAIL with `::error file=...::` GitHub Actions 형식.
- 검증: 로컬 실행 → 현재 main 상태 PASS.
- 의존: T001, T002

### T004 — `.github/workflows/cc-byte-identical-guard.yml` 작성

- on: pull_request[paths: 위 slice 7개] + push[branches: main, paths: 동일].
- steps: checkout · setup-python 3.12 · `pip install pyyaml` · `python3 scripts/cc_byte_identical_guard.py --baseline specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt --whitelist tui/src/.cc-byte-identical-whitelist.yaml --slice-root tui/src`.
- 의존: T003

### T005 — regression fixture 작성 (`fixtures/intentional-divergence-test.md`)

- 5-step reproducible scenario: branch · 변경 · CI fail 확인 · revert · merge.
- 검증: 로컬 시뮬레이션 (별 branch 안 만들어도 script 만 실행)해서 fail expected output 박제.
- 의존: T003

## Phase 2 — D3 SWAP 주석 (Lead, 5파일 모두 head 주석만)

### T006 — `tui/src/components/messages/AssistantTextMessage.tsx` SWAP 주석 [P]

- plan.md § 3 의 5 줄 형식 주석을 file head 첫 줄 (compiler-runtime import 위) 에 삽입.

### T007 — `tui/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx` SWAP 주석 [P]

- plan.md § 3 형식.

### T008 — `tui/src/replLauncher.tsx` SWAP 주석 [P]

- plan.md § 3 형식.

### T009 — `tui/src/interactiveHelpers.tsx` SWAP 주석 [P]

- plan.md § 3 형식.

### T010 — `tui/src/screens/REPL.tsx` SWAP 주석 [P]

- plan.md § 3 형식. file head 의 biome-ignore-all 주석 위에 삽입.

## Phase 3 — D1 TeleportResumeWrapper DROP (Lead)

### T011 — dialogLaunchers.tsx 의 `launchTeleportResumeWrapper` export 제거 + .never-port.md 생성 + audit § 10 갱신

- 3 sub-step (single task — 자연 commit unit):
  1. `tui/src/dialogLaunchers.tsx`: lines ~87-96 의 `launchTeleportResumeWrapper` 함수 + 주석 제거. `TeleportRemoteResponse` import 가 다른 launcher 에서 안 쓰이면 함께 제거.
  2. `tui/src/components/.never-port.md`: 신규. audit § 10 6 entry + 7th `TeleportResumeWrapper.tsx` entry. CC reference path + 1P-Anthropic rationale.
  3. `specs/cc-migration-audit/scope-S3-components-screens.md`: § 10 markdown block 에 7th 라인 추가. § 4 #7 verdict 갱신 ("PORT-P2 (deferred)" → "DROP-CONFIRMED · NEVER-PORT").

## Phase 4 — Verification (Lead)

### T012 — `bun test` parity + Layer 5 tmux smoke + commit

- `bun test` (cwd: tui/) → pre-PR pass count baseline 과 비교.
- `python3 scripts/cc_byte_identical_guard.py` 로컬 실행 → PASS.
- `scripts/tui-tmux-capture.sh specs/2639-s3-ui-guard/frames/ specs/2639-s3-ui-guard/scripts/smoke-help.sh` 실행. 기대: snap-000-boot.txt + snap-001-help.txt + snap-002-exit.txt 3개 박제.
- `git add` + Conventional Commits commit (`feat(2639): epic c — s3 ui guard (D1 TeleportResumeWrapper DROP + D2 SHA-256 fail-build CI + D3 5파일 SWAP 주석)`) + push origin feat/2639-s3-ui-guard.
- `gh pr create` with body `Closes #2639`.
- `gh pr checks --watch --interval 10`.
- Codex inline review 응답.
- Copilot Gate 확인.

## Parallel-safe annotation summary

- T001 [P], T002 [P]: file-disjoint (fixtures/ vs tui/src/.cc-byte-identical-whitelist.yaml). 동시 작성 가능.
- T006-T010 [P]: 5파일 file-disjoint. 동시 편집 가능.
- T003 → T004 → T005: 의존 chain.
- T011: file-disjoint with all above.
- T012: 의존 ALL.

## Estimated effort

- T001~T011: 90분 (mechanical, 모두 박제·삽입·생성).
- T012: 60-120분 (CI watch + Codex 응답).
- Total: ≤ 4시간 (decisions.md § S3 estimate "2~3시간" 보다 약간 위 — D2 의 60-entry whitelist 수동 작성 추가 이슈).
