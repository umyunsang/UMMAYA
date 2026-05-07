# Smoke checklist — KOSMOS v0.1-alpha pre-merge gate (T033)

**Branch**: `feat/1637-p6-docs-smoke`
**Run date**: 2026-04-26
**Validator**: project lead (automated frame-dump path) + PR reviewer (hand-driven path)
**Bun version**: `bun --version` → 1.3.12 (macOS arm64); CI: bun 1.2.x (linux x64)
**Capture method**: `tui/scripts/dump-tui-frames.tsx` — `ink-testing-library` `render()` per surface, `lastFrame()` written to `specs/1637-p6-docs-smoke/visual-evidence/<slug>.txt`

## Capture procedure (replicable)

```bash
cd /Users/um-yunsang/KOSMOS/tui
bun run scripts/dump-tui-frames.tsx
```

The script prints `[dump-tui-frames] N ok, M fail (out: ...)` and exits 0 if every surface rendered. Frames are deterministic — re-running the script must produce identical bytes per file (the only non-deterministic field is the `# Captured <timestamp>` comment header, which the validator ignores during diff review).

## Surfaces dumped automatically (18 active surfaces)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `onboarding-1-splash` | Onboarding step 1 — splash (WelcomeV2 logo + 별빛 + brand glyph) | Welcome banner + version string + brand glyph render | `visual-evidence/onboarding-1-splash.txt` (436 B) | ✓ |
| `onboarding-3-pipa` | Onboarding step 3 — PIPA § 26 trustee notice + ministry list + AAL2 label + Enter/Esc hints | All four ministries listed; AAL2 label visible; bilingual button hint | `visual-evidence/onboarding-3-pipa.txt` (272 B + Korean text) | ✓ |
| `onboarding-4-ministry` | Onboarding step 4 — ministry-scope acknowledgement (4 ministry checkboxes + ↑↓/Space/Enter hints) | Selected scope row marked ▶; all checkboxes ☑ by default; full keybinding row | `visual-evidence/onboarding-4-ministry.txt` (283 B) | ✓ |
| `plugin-browser` | Slash command — `/plugins` browser (3 mock plugins, ⏺ active vs ○ inactive glyphs, Space/i/r/a key row) | Brand glyph ✻ in title; correct active/inactive glyph per row; Korean descriptions | `visual-evidence/plugin-browser.txt` | ✓ |
| `error-llm-4xx` | Error envelope — LLM 4xx (purple border, 🧠 brain glyph, retry hint) | 🧠 glyph + 단/double border + retry "(R)" hint + Korean detail | `visual-evidence/error-llm-4xx.txt` (568 B) | ✓ |
| `error-tool-fail-closed` | Error envelope — tool fail-closed (orange border, 🔧 wrench glyph, no retry hint) | 🔧 glyph + "도구 호출 차단" header + L3 fail-closed message | `visual-evidence/error-tool-fail-closed.txt` (567 B) | ✓ |
| `error-network-timeout` | Error envelope — network timeout (red border, 📡 signal-broken glyph, retry hint) | 📡 glyph + "네트워크 시간 초과" header + 30 s timeout copy | `visual-evidence/error-network-timeout.txt` (555 B) | ✓ |
| `primitive-lookup-search` | `lookup` search-mode candidate list (CollectionList) | 5 BM25 candidates rendered with index + tool_id + Korean meta | `visual-evidence/primitive-lookup-search.txt` | ✓ |
| `primitive-lookup-fetch-point` | `lookup` fetch-mode point detail (DetailView) | 5 fields rendered (사고 빈발 지점, 사고 건수, 사고 유형, 제한 속도, 데이터 출처) | `visual-evidence/primitive-lookup-fetch-point.txt` | ✓ |
| `primitive-lookup-fetch-timeseries` | `lookup` fetch-mode timeseries (KMA forecast) | Timestamp / Value (°C) header + 5 forecast rows | `visual-evidence/primitive-lookup-fetch-timeseries.txt` | ✓ |
| `primitive-submit-receipt` | `submit` mock receipt (SubmitReceipt) | ✔ Submitted [MOCK: real_api_unreachable] + confirmation_id + Korean summary | `visual-evidence/primitive-submit-receipt.txt` | ✓ |
| `primitive-verify-auth-context` | `verify` identity card (AuthContextCard) | ✔ Verified + identity + 금융인증서 + NIST AAL2 | `visual-evidence/primitive-verify-auth-context.txt` | ✓ |
| `onboarding-2-theme` | Onboarding step 2 — theme selector (UFO mascot + 3 options) | UFO ASCII mascot + 보라 팔레트 + dark/light/system options + step 2/5 dots | `visual-evidence/onboarding-2-theme.txt` | ✓ |
| `onboarding-5-terminal` | Onboarding step 5 — terminal setup (4 a11y toggles) | 4 accessibility toggles + key hints + step 5/5 dots | `visual-evidence/onboarding-5-terminal.txt` | ✓ |
| `slash-consent-issued` | `/consent` receipt-issued toast | ✻ 발급됨 + receipt ID | `visual-evidence/slash-consent-issued.txt` | ✓ |
| `slash-consent-revoked` | `/consent revoke` receipt-revoked toast | ✻ 철회 완료 + receipt ID | `visual-evidence/slash-consent-revoked.txt` | ✓ |
| `slash-consent-already-revoked` | `/consent revoke` already-revoked toast | ✻ 이미 철회됨 | `visual-evidence/slash-consent-already-revoked.txt` | ✓ |
| `pdf-inline-render` | PDF inline-render loading state (Tier C fallback) | "PDF 인라인 렌더 중…" loading copy | `visual-evidence/pdf-inline-render.txt` | ✓ |

## Surfaces deferred to PR-review hand-driven validation (2 — `/agents` + `/help` only)

Two surfaces remain manual because they depend on hooks that require the full live keybinding-provider context tree (`useKeybinding` + `useShortcutDisplay` + `useExitOnCtrlCDWithKeybindings` + the merged-tools / app-state / settings-source provider stack). The `ink-testing-library` `render()` harness in `dump-tui-frames.tsx` does not stand up that full stack without effectively re-implementing the runtime — out of scope for the visual smoke.

The PR reviewer drives these two manually against `bun run tui` and attaches captured frames as a follow-up PR comment.

| Step ID | Description | Capture path | Status |
|---|---|---|---|
| `slash-agents` | `/agents` panel | `bun run tui` → `/agents` | manual |
| `slash-help` | `/help` panel | `bun run tui` → `/help` | manual |

## Visual contracts verified by automated dump

- **Brand glyph ✻** — present on plugin browser title (matches CC convention preserved in migration tree § brand).
- **Bilingual copy** — every surface renders Korean primary text (citizen-facing) and English secondary cues (key hints) per FR-021.
- **Ministry list** — KOROAD / KMA / HIRA / NMC names render in Korean with English code in parentheses (matches `docs/api/README.md` AdapterIndex naming).
- **AAL labels** — PIPA consent surface declares `2단계 인증 (AAL2)` per Spec 033 permission tier convention.
- **Error envelope visual differentiation** — three distinct icons (🧠 / 🔧 / 📡), three distinct border colors (purple / orange / red), retry hint conditional on `retry_suggested` flag (FR-012).
- **Keybinding hints rendered in surface** — every interactive surface advertises its keybinding row (Space/Enter/Esc/↑↓ etc.), matching the keybindings template generated by `dumpTier1Catalogue()`.

## Pre-existing automated coverage backing this checklist

- `bun test`: **928 pass / 4 skip / 3 todo / 0 fail / 0 errors / 935 total** — every surface above also has a passing component test (`tui/tests/components/*` + `tui/tests/onboarding/*` + `tui/tests/coordinator/*`).
- `bun test tui/tests/keybindings/`: **189 pass / 0 fail** — keybindings + chord resolution contract enforced.
- `cd tui && bun run tui:smoke`: PASS in CI Linux runner (TUI typecheck + unit tests + PTY boot smoke job, see PR #1977 checks).

## Sign-off

| Slot | Validator | Date | Result |
|---|---|---|---|
| Automated frame dump (7 surfaces) | project lead via `dump-tui-frames.tsx` | 2026-04-26 | PASS |
| Hand-driven primitive flows + slash commands + PDF render (11 surfaces) | PR reviewer | (pending) | (deferred to PR review) |

The automated dump satisfies SC-005 for the seven surfaces it covers (onboarding ×3 + plugin browser + error envelope ×3). The remaining eleven surfaces require live-state interaction; the PR review comment thread is the canonical record for those.
