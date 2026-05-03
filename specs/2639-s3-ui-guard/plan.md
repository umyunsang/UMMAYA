# Implementation Plan: S3 UI 정합성 가드 (Epic C · #2639)

**Branch**: `feat/2639-s3-ui-guard`
**Spec**: [`spec.md`](./spec.md)
**Initiative**: #2636 — CC Migration Audit-Driven Realignment
**Created**: 2026-05-03

## Phase 0 — Reference materials (NON-NEGOTIABLE)

본 Phase 0 는 AGENTS.md § Spec-driven workflow "Every `/speckit-plan` Phase 0 must consult `.specify/memory/constitution.md` and `docs/vision.md § Reference materials`" 룰에 맞춰 모든 design decision 을 concrete reference 에 매핑한다.

| Decision | Reference |
|---|---|
| **D1 — TeleportResumeWrapper DROP** | `specs/cc-migration-audit/decisions.md § S3 D1` (양쪽 DROP, NEVER-PORT 박제) · `specs/cc-migration-audit/scope-S3-components-screens.md § 4 #7 + § 10 NEVER-PORT 명단` · `AGENTS.md § CORE THESIS` (KOSMOS = CC + 2 swap; 1P-Anthropic 비즈니스 surface 는 정당한 제3 제거) · `feedback_kosmos_scope_cc_plus_two_swaps` 메모리 |
| **D2 — SHA-256 fail-build CI invariant** | `specs/cc-migration-audit/decisions.md § S3 D2` · `specs/cc-migration-audit/scope-S3-components-screens.md § 9 D2 + § 7 W1~W12` · `AGENTS.md § TUI verification` (5 layer 가 catch 못 하는 stale-import / SHA drift 회귀 차단) · `.github/workflows/tui-attribution-gate.yml` + `tui/scripts/diff-upstream.sh` (FR-011/SC-9 패턴 재사용) |
| **D3 — 5파일 SWAP 주석 백필** | `specs/cc-migration-audit/decisions.md § S3 D3` · `specs/cc-migration-audit/scope-S3-components-screens.md § 5.5 8-66 lines table + § 9 D3` · CC restored-src 의 5 파일 본문 (divergence cause 식별) · 기존 `// SWAP:` 패턴 (Markdown.tsx, Messages.tsx, AssistantThinkingMessage.tsx) |
| **whitelist YAML schema** | `tui/src/sdk-compat.js` (W1 substitution path) · `docs/requirements/kosmos-migration-tree.md § 마스코트 · 브랜딩` (W2/W3/W4/W6) · `prompts/system_v1.md` (한국어 i18n W5 source) · Spec 2519 PR (W10 Korean IME) · Spec 2521 docs (W9 K-EXAONE multi-tool layout) |
| **CC sourcemap baseline distribution** | `.gitignore` 가 `.references/` 제외 → vendored snapshot 방식 (`specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`). 384 entry 정도 (audit § 11 enumeration). |

**Constitution check**: `.specify/memory/constitution.md` 의 "spec-first, ports byte-identical, swap-citations 필수" 원칙과 정합. 본 Epic 자체가 byte-identical default 를 박제하는 가드이므로 constitution 의 first-class 적용.

## Architecture overview

```
┌────────────────────────────────────────────────────────────────────────┐
│  CC restored-src/src/  (research-only, .gitignore 제외)                │
│    components/  (389)   screens/  (3)   dialogLaunchers.tsx  ...       │
│      │                                                                 │
│      │ shasum -a 256 (build-time, audit-time)                          │
│      ▼                                                                 │
│  specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt                  │
│    "<sha>  components/App.tsx" × 397 lines (vendored snapshot)         │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ (CI checkout + read)
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  .github/workflows/cc-byte-identical-guard.yml                         │
│    on: pull_request[paths: tui/src/components/**, screens/**, ...]     │
│    job:                                                                │
│      1. checkout (fetch-depth: 1)                                      │
│      2. read fixtures/cc-baseline-shas.txt                             │
│      3. read .cc-byte-identical-whitelist.yaml                         │
│      4. for each KOSMOS file in slice:                                 │
│           a. compute sha256                                            │
│           b. lookup CC baseline by relative path                       │
│           c. if path missing in CC → PASS (KOSMOS-only)                │
│           d. if sha matches CC → PASS                                  │
│           e. if sha mismatch + path in whitelist → PASS                │
│           f. else → FAIL with file + cause                             │
│      5. summary: <pass>/<total>, <whitelisted>/<diverged>              │
└──────────────────────────┬─────────────────────────────────────────────┘
                           │ blocks merge if FAIL
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│  KOSMOS PR author                                                      │
│    - SHA mismatch → choose:                                            │
│        (a) revert change to restore byte-identical, OR                 │
│        (b) add whitelist entry with cause + spec_ref                   │
└────────────────────────────────────────────────────────────────────────┘
```

## Phase 1 — Whitelist + baseline schemas (D2 enabling)

### 1.1 Whitelist YAML (`tui/src/.cc-byte-identical-whitelist.yaml`)

위치: TUI subtree 내부 (PR review 시 발견하기 쉽게), 단 CI 가 repo-root 에서 읽음.

스키마 (Pydantic 없이 stdlib `pyyaml` 만 — CI 에서 `python3 -c "import yaml; ..."`):

```yaml
version: 1
generated_by: "Epic #2639 Lead Opus, 2026-05-03"
schema:
  - path: relative path from repo root (string)
  - cause: enum [W1..W13]
  - spec_ref: GitHub issue # OR specs/<feature>/spec.md path
  - notes: optional human description (string)
  - expected_sha256: optional hex string (locks to specific divergence content)

causes:
  W1: "@anthropic-ai/sdk → src/sdk-compat.js import substitution"
  W2: "Brand string substitution (Claude Code → KOSMOS)"
  W3: "Mascot character swap (Clawd → UFO)"
  W4: "Brand glyph (✻ preserved)"
  W5: "Korean i18n string injection"
  W6: "Color palette (CC blue → KOSMOS violet #a78bfa)"
  W7: "Anthropic 1P-business surface removed (no replacement)"
  W8: "sourceMappingURL trailing line stripped"
  W9: "K-EXAONE-specific render (reasoning_content, multi-tool layout)"
  W10: "Korean IME hotfix (Hangul Jamo composition)"
  W11: "Sandbox-runtime install hint stripped"
  W12: "OTEL frame_commit instrumentation hook"
  W13: "Dead-code cleanup (Spec 1633/2293 — Anthropic services/api/auth/secureStorage removed)"

entries:
  - path: tui/src/components/messages/UserToolResultMessage/utils.tsx
    cause: W1
    spec_ref: docs/requirements/kosmos-migration-tree.md § L1-A
    notes: "@anthropic-ai/sdk import → src/sdk-compat.js"
  # ... ~60 entries total per audit § 5
```

### 1.2 Baseline fixture (`specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`)

생성 명령:
```bash
cd /Users/um-yunsang/KOSMOS/.references/claude-code-sourcemap/restored-src/src
{
  find components -type f \( -name '*.ts' -o -name '*.tsx' \)
  find screens -type f \( -name '*.ts' -o -name '*.tsx' \)
  find outputStyles moreright -type f \( -name '*.ts' -o -name '*.tsx' \)
  echo "dialogLaunchers.tsx"
  echo "interactiveHelpers.tsx"
  echo "replLauncher.tsx"
} | sort | xargs shasum -a 256 > /Users/um-yunsang/KOSMOS-w-2639/specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt
```

포맷: `shasum -a 256` 표준 출력 (`<hex_sha>  <relative_path>`).

### 1.3 NEVER-PORT registry (`tui/src/components/.never-port.md`)

새 markdown. audit § 10 의 6 entry + D1 의 7th entry. 각 entry: 파일명 · cause · CC reference path · related issue.

## Phase 2 — CI workflow (D2)

### 2.1 `.github/workflows/cc-byte-identical-guard.yml`

trigger: `pull_request[paths]` + `push[branches: main]`.

paths:
- `tui/src/components/**`
- `tui/src/screens/**`
- `tui/src/dialogLaunchers.tsx`
- `tui/src/interactiveHelpers.tsx`
- `tui/src/replLauncher.tsx`
- `tui/src/outputStyles/**`
- `tui/src/moreright/**`
- `tui/src/.cc-byte-identical-whitelist.yaml`
- `specs/2639-s3-ui-guard/fixtures/cc-baseline-shas.txt`
- `.github/workflows/cc-byte-identical-guard.yml`

step:
1. `actions/checkout@v4` (fetch-depth: 1)
2. `actions/setup-python@v5` (3.12)
3. `pip install pyyaml` (stdlib + 1 dep, allowed in CI per AGENTS.md "no new *runtime* deps" — CI tooling 은 별개)
4. `python3 scripts/cc_byte_identical_guard.py` — actual check 로직
5. summary print

### 2.2 `scripts/cc_byte_identical_guard.py` (CI runner)

stdlib + `pyyaml` (CI-only) 만 사용. argparse / hashlib / pathlib.

algorithm:
```python
baseline = {path: sha for path, sha in load(fixtures/cc-baseline-shas.txt)}
whitelist = {entry["path"]: entry for entry in load(.cc-byte-identical-whitelist.yaml)["entries"]}

slice_paths = walk(tui/src/{components,screens,outputStyles,moreright})
            + [tui/src/{dialogLaunchers,interactiveHelpers,replLauncher}.tsx]

failures = []
stats = {"total": 0, "byte_identical": 0, "whitelisted": 0, "kosmos_only": 0, "failed": 0}

for kosmos_path in slice_paths:
    rel = relative_to_tui_src(kosmos_path)  # e.g., "components/App.tsx"
    actual_sha = sha256(read(kosmos_path))
    cc_sha = baseline.get(rel)

    if cc_sha is None:
        stats["kosmos_only"] += 1; continue
    if actual_sha == cc_sha:
        stats["byte_identical"] += 1; continue

    repo_rel = f"tui/src/{rel}"
    wl = whitelist.get(repo_rel)
    if wl is None:
        failures.append((repo_rel, actual_sha, cc_sha, "NOT WHITELISTED"))
        stats["failed"] += 1; continue
    if wl.get("expected_sha256") and wl["expected_sha256"] != actual_sha:
        failures.append((repo_rel, actual_sha, wl["expected_sha256"], "SHA differs from whitelist pin"))
        stats["failed"] += 1; continue
    stats["whitelisted"] += 1

if failures:
    for f in failures: print(f"::error file={f[0]}::SHA-256 mismatch — {f[3]} (got {f[1][:12]}, expected {f[2][:12]})")
    sys.exit(1)
print(f"PASS · {stats['byte_identical']} byte-identical · {stats['whitelisted']} whitelisted · {stats['kosmos_only']} KOSMOS-only · {stats['failed']} failed")
```

## Phase 3 — D3 SWAP 주석 박제

5파일 각 head 에 다음 형식 주석 (existing imports 위에 삽입):

### `tui/src/components/messages/AssistantTextMessage.tsx`
```ts
// SWAP: dead-code-cleanup (Spec 1633 P1 + Epic #2293)
// CC reference: .references/claude-code-sourcemap/restored-src/src/components/messages/AssistantTextMessage.tsx
// Divergence LOC: 18 (services/api/errors inlined; secureStorage stub; sdk-compat import)
// Spec citation: #1633 (Anthropic services/api removal), #2293 (secureStorage removal)
// Justification: Anthropic services/api/errors and secureStorage modules removed by KOSMOS dead-code cleanup; constants and isMacOsKeychainLocked → false stub inlined to preserve component contract.
```

### `tui/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx`
```ts
// SWAP: dead-code-cleanup (Spec 1633 + Epic #2293)
// CC reference: .references/claude-code-sourcemap/restored-src/src/components/permissions/ExitPlanModePermissionRequest/ExitPlanModePermissionRequest.tsx
// Divergence LOC: 51 (autoNameSessionFromPlan no-op; UUID/generateSessionName/getSettings_DEPRECATED removed; sdk-compat)
// Spec citation: #1633 (Anthropic queryHaiku auto-naming removal), #2293 (utils/auth removal)
// Justification: Anthropic queryHaiku-driven auto-naming requires Anthropic SDK; KOSMOS exits plan mode without auto-naming.
```

### `tui/src/replLauncher.tsx`
```ts
// SWAP: brand (cosmetic — sourceMappingURL trailing line stripped + import block reformatted)
// CC reference: .references/claude-code-sourcemap/restored-src/src/replLauncher.tsx
// Divergence LOC: 10 (sourceMappingURL strip + brace formatting)
// Spec citation: audit § 5.7 + § 5.3 — W8 sourceMappingURL strip
// Justification: Build-pipeline cosmetic divergence; no semantic change.
```

### `tui/src/interactiveHelpers.tsx`
```ts
// SWAP: dead-code-cleanup (Anthropic Grove + analytics + auth removal)
// CC reference: .references/claude-code-sourcemap/restored-src/src/interactiveHelpers.tsx
// Divergence LOC: 51 (Grove dialog removed; logEvent calls removed; getClaudeAIOAuthTokens removed; channel-allowlist OAuth check fall-through)
// Spec citation: #1633 (Anthropic services/api/grove + utils/auth removal), audit § 5.7
// Justification: Grove growth-experiment, Anthropic OAuth, and tengu_* analytics events all swap-1 dependent (claude.ai 계정 + Anthropic telemetry); KOSMOS removes them and falls through to no-OAuth branches.
```

### `tui/src/screens/REPL.tsx`
```ts
// SWAP: swap-1 LLM provider + swap-2 tool surface + dead-code-cleanup (Specs 2521/032/2293)
// CC reference: .references/claude-code-sourcemap/restored-src/src/screens/REPL.tsx
// Divergence LOC: ~678 (LLM provider plumbing, IPC envelope routing, permission gauntlet integration, K-EXAONE multi-tool layout)
// Spec citation: #2521 (LLM swap), #032 (IPC stdio hardening), #2293 (services/api removal)
// Justification: Largest single file in TUI subtree (920 KB). Both swaps converge here — IPC frame routing, FriendliAI K-EXAONE streaming, permission decision propagation. Specific divergence sites have inline comments at point of edit.
```

## Phase 4 — D1 TeleportResumeWrapper DROP

### 4.1 `tui/src/dialogLaunchers.tsx`
- `launchTeleportResumeWrapper` export (lines 87-96 approx) 제거.
- 주석 라인 88 ("Site ~4549: TeleportResumeWrapper") 제거.
- `TeleportRemoteResponse` import 가 다른 launcher 에서도 쓰이는지 확인 후 보존 또는 제거.

### 4.2 `tui/src/components/.never-port.md` (신규)
audit § 10 6 entry + 7th entry `TeleportResumeWrapper.tsx`. 각 entry:
- 파일명
- CC restored-src 경로
- 1P-Anthropic 비즈니스 분류
- DROP rationale

### 4.3 `specs/cc-migration-audit/scope-S3-components-screens.md`
§ 10 NEVER-PORT 명단에 `src/components/TeleportResumeWrapper.tsx` 추가. § 4 (PORT bucket) 의 D1 항목 verdict 를 "DROP-CONFIRMED" 로 갱신.

## Phase 5 — Verification

### 5.1 unit verification
- `bun test` 실행 → current main 대비 pass count parity (자동화).
- `python3 scripts/cc_byte_identical_guard.py` 로컬 실행 → PASS.

### 5.2 regression fixture
- `specs/2639-s3-ui-guard/fixtures/intentional-divergence-test.md` 작성:
  1. branch 분기.
  2. `tui/src/components/App.tsx` (byte-identical, whitelist 미등록) 에 임의 한 줄 추가.
  3. CI 트리거 → `cc-byte-identical-guard` job FAIL 검증.
  4. revert.

### 5.3 Layer 5 tmux capture (TUI verification mandatory)
AGENTS.md § TUI verification 의 5-layer 중 본 Epic 변경이 모두 "comment-only or whitelist YAML or workflow YAML or 1 export 제거" 이므로 기능 회귀 위험 lowest. 그러나 D3 의 5 파일 head 에 주석 추가가 import 순서 / build 영향 없음을 증명하기 위해:

`scripts/tui-tmux-capture.sh specs/2639-s3-ui-guard/frames/ specs/2639-s3-ui-guard/scripts/smoke-help.sh`

5 probe points:
1. KEYSTROKE — `/help\r` 입력 로깅
2. IPC frame — 없음 (slash command 는 client-side 처리)
3. Tool dispatch — 없음
4. RENDER — frame_commit 발생 확인
5. Snapshot trigger — frames/ 디렉토리에 stage-별 snap-NNN-*.txt 박제

기대 frames:
- snap-000-boot.txt (KOSMOS 브랜딩 + tool_registry verified)
- snap-001-help.txt (help overlay rendered)
- snap-002-exit.txt (graceful shutdown)

### 5.4 5-layer chain summary
- Layer 1a (pytest): N/A (TS-only changes; Python 미변경)
- Layer 1b (bun test): MUST PASS parity
- Layer 2 (stdio JSONL): N/A (no IPC change)
- Layer 3 (PTY scenario): not required (no interactive flow change) but Layer 5 covers
- Layer 4 (vhs PNG keyframe): not required (no visual change beyond build) — skip declared in PR description per AGENTS.md "TUI no-change" 부분 적용 (변경된 파일은 byte-identical or comment-only)
- Layer 5 (tmux capture): MANDATORY — frames/ 박제

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| baseline fixture 가 CC 갱신 시 stale | CC 2.1.88 명시 + ADR-004 cycle 별도 추적 |
| whitelist over-permissive (모든 발산 등록) | cause enum 강제 + spec_ref 강제 (PR review 시 enforcement) |
| CI 가 너무 strict — 정당 swap PR 머지 차단 | whitelist add 가 PR 의 자연 part — 1 commit 추가로 해결 |
| `launchTeleportResumeWrapper` 의 caller 가 grep 에 잡히지 않은 dynamic import | bun test 통과 + tmux capture 의 boot path 검증으로 안전 확인 |
| `TeleportRemoteResponse` import 가 dialogLaunchers.tsx 에서 dead import 화 | 별도 import scan + 제거 (grep `TeleportRemoteResponse` ≤ 1 callsite 인지 확인) |

## Dispatch tree

5개 task 모두 하나의 spec dir 에 모이고 D1 ↔ D2 ↔ D3 가 file-disjoint (CI workflow vs 5 file head 주석 vs dialogLaunchers + .never-port). 그러나 본 Epic 의 task 총량 ≤ 8, 파일 변경 ≤ 12 → AGENTS.md § Agent Teams "1-2 tasks → Lead solo" 임계 근처. **Lead Opus solo 처리**가 dispatch overhead 보다 효율적. (D2 만 약간 무거운데 stdlib python3 스크립트 + YAML + workflow yaml 모두 mechanical.)

## Success Criteria recap (from spec.md)

SC-001 (CI workflow PASS) · SC-002 (5 SWAP comments) · SC-003 (Teleport DROP) · SC-004 (bun test parity) · SC-005 (tmux smoke) · SC-006 (zero new dep) · SC-007 (decisions.md § S3 closed) · SC-008 (regression fixture).
