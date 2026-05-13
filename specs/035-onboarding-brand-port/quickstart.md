# Quickstart: Onboarding + Brand Port

**Feature**: Epic H #1302
**Phase**: 1
**Audience**: UMMAYA developer (Lead or Sonnet Teammate) verifying the Epic H PR locally.

This walk-through proves every FR and SC from `spec.md` behaves as contracted. Execute in order; each step MUST pass before the next.

---

## Prerequisites

- Bun `v1.2.x` (existing Spec 287 stack).
- Python `3.12+` with `uv` (existing Spec 022 / 027 stack).
- Terminal supporting 24-bit colour (Terminal.app, iTerm2, Alacritty; Windows Terminal OK).
- Clean memdir state: `rm -rf ~/.ummaya/memdir/user/consent ~/.ummaya/memdir/user/ministry-scope` (or use a throwaway `$HOME`).

---

## 1 · Install + build

```bash
bun install
uv sync
```

**Expectation**: zero new dependencies installed. `bun install` output shows only Spec 287-era packages; `uv sync` output shows no new additions beyond the pre-existing `pydantic`, `httpx`, `pytest` set.

---

## 2 · Compile the TUI

```bash
bun run tui/src/main.tsx --help
```

**Expectation**: `tui/src/theme/tokens.ts` compiles with the new `ThemeToken` surface. Any consumer still referencing one of the 7 DELETE identifiers fails compilation — if that happens, grep for the failing identifier and replace with its UMMAYA equivalent.

---

## 3 · Run the compile-time assertion

```bash
bun test tui/tests/theme/tokens.compile.test.ts
```

**Expectation**: PASS. Asserts:
- Zero occurrences of `claude*`, `clawd_*`, `briefLabelClaude` in `ThemeToken`.
- Ten specific identifiers (`ummayaCore`, `ummayaCoreShimmer`, `orbitalRing`, `orbitalRingShimmer`, `wordmark`, `subtitle`, `agentSatelliteKoroad`, `agentSatelliteKma`, `agentSatelliteHira`, `agentSatelliteNmc`) present.
- Preserve-set cardinality exactly 62.

---

## 4 · Verify contrast measurements

```bash
bun run scripts/compute-contrast.mjs
```

**Expectation**: script exits 0. Emits `docs/design/contrast-measurements.md` with every pair ≥ threshold. A non-zero exit prints the failing pair (fg token, bg token, measured ratio, threshold) — fix by raising the failing token per `contracts/contrast-measurements.md § 3`.

---

## 5 · Run the onboarding snapshot suite

```bash
bun test tui/tests/onboarding/
```

**Expectation**: the following snapshots PASS:
- `Onboarding.snap.test.tsx` — full 3-step happy path.
- `PIPAConsentStep.snap.test.tsx` — accept branch (record written) + decline branch (no record, exit).
- `MinistryScopeStep.snap.test.tsx` — all four ministries enumerated + partial opt-in recorded correctly.

---

## 6 · Run the LogoV2 visual suite

```bash
bun test tui/tests/LogoV2/
```

**Expectation**: the following snapshots PASS:
- `LogoV2.snap.test.tsx` — 80-column full layout, 60-column condensed, 45-column fallback; each with reduced-motion on/off.
- `AnimatedAsterisk.snap.test.tsx` — shimmer frame snapshot + reduced-motion static.
- `WelcomeV2.snap.test.tsx` — Korean welcome screen dark-theme render.
- `CondensedLogo.snap.test.tsx` — UMMAYA header with mock model / effort / coordinatorMode.
- `Feed.snap.test.tsx` + `FeedColumn.snap.test.tsx` + `feedConfigs.test.tsx`.
- `UmmayaCoreIcon.snap.test.tsx` — shimmering vs. static.

---

## 7 · Run the Python memdir + router tests

```bash
uv run pytest tests/memdir/ tests/tools/test_main_router.py -v
```

**Expectation**: the following PASS:
- `test_user_consent.py::test_schema_roundtrip` — Pydantic model round-trips against the JSON schema.
- `test_user_consent.py::test_append_only` — writing twice yields two files, no overwrite.
- `test_user_consent.py::test_latest_consent` — reader returns the most recent valid record.
- `test_ministry_scope.py::test_schema_roundtrip` + `test_four_unique` + `test_append_only` + `test_latest_scope`.
- `test_main_router.py::test_opt_out_refusal` — declining a ministry in the scope record, then calling a tool targeting that ministry raises `MinistryOptOutRefusal` with the correct Korean message within 100 ms (SC-009).

---

## 8 · Launch the TUI — full onboarding (fresh citizen)

```bash
bun run tui/src/main.tsx
```

**Expectation**:
- Frame 1: splash renders with `#0a0e27` navy background, wordmark "UMMAYA" in `wordmark` colour, subtitle "KOREAN PUBLIC SERVICE MULTI-AGENT OS" in `subtitle` colour, `ummayaCore` asterisk centred inside the `orbitalRing` gradient arc, 4 ministry satellite nodes below.
- Frame 2 (after Enter): PIPA consent step renders with consent version `v1`, AAL `AAL1`, Korean plain-language summary of UMMAYA's § 26 수탁자 role.
- Frame 3 (after Enter): ministry scope step renders with 4 rows (KOROAD, KMA, HIRA, NMC) each showing Korean name + English code + accent colour + toggle.
- Frame 4 (after Enter with all toggles on): main TUI enters.
- Elapsed time ≤ 90 s (SC-002) for manual keypresses.
- Memdir USER now contains one consent record + one ministry-scope record with matching `session_id`.

---

## 9 · Launch the TUI — returning citizen (fast-path)

```bash
bun run tui/src/main.tsx
```

**Expectation**: splash renders (≤ 250 ms), auto-advances after 3 s (or first keypress) into the main TUI. No PIPA or ministry-scope step renders. Total elapsed ≤ 3 s (SC-012).

---

## 10 · Launch the TUI — reduced motion

```bash
UMMAYA_REDUCED_MOTION=1 bun run tui/src/main.tsx
```

**Expectation**: splash renders with static asterisk + static orbital-ring gradient (no shimmer animation). Every REWRITE component honours the flag per FR-024.

```bash
NO_COLOR=1 bun run tui/src/main.tsx
```

**Expectation**: identical to the above (NO_COLOR is the community-standard alias).

---

## 11 · Launch the TUI — narrow terminal

```bash
COLUMNS=70 bun run tui/src/main.tsx
```

**Expectation**: splash degrades to condensed-header layout; orbital-ring visual omitted; ministry list + feed hidden; no label truncation.

```bash
COLUMNS=45 bun run tui/src/main.tsx
```

**Expectation**: splash renders as single text line `UMMAYA — 한국 공공서비스 대화창` without error.

---

## 12 · Launch the TUI — decline consent

```bash
bun run tui/src/main.tsx
```

At the PIPA consent step, press Escape.

**Expectation**:
- Session exits with code 0.
- No record written in `~/.ummaya/memdir/user/consent/` or `ministry-scope/`.

---

## 13 · Launch the TUI — partial opt-in + refused tool call

```bash
bun run tui/src/main.tsx
```

Complete onboarding selecting KOROAD + KMA only. Decline HIRA + NMC. After reaching the main TUI, attempt a tool call that targets HIRA (e.g. the MVP meta-tool with a HIRA adapter query).

**Expectation**:
- Tool call is refused before any network invocation.
- TUI renders an error-styled message in Korean naming HIRA.
- Refusal latency < 100 ms from invocation (SC-009).
- Subsequent tool calls targeting KOROAD or KMA succeed normally.

---

## 14 · Screen-reader pathway spot check (manual)

With macOS VoiceOver enabled (Cmd+F5 in Terminal.app), launch the TUI and navigate onboarding by Enter alone.

**Expectation**:
- Every step announces its title ("UMMAYA 은하계 스플래시", "PIPA 개인정보 동의", "부처 API 범위 동의") as plain text.
- Every ministry row at the scope step announces its Korean name + English code + toggle state.
- Reduced-motion narration is sufficient to complete the flow without colour or animation cues.

---

## 15 · CI gate checklist

Before opening the Epic H PR, check:

- [X] `bun test` passes (full TUI suite) — 367 pass, 0 fail.
- [X] `uv run pytest` passes (full Python suite for Epic H deliverables) — `tests/memdir/` + `tests/tools/test_main_router.py` all green.
- [X] `scripts/compute-contrast.mjs` exits 0 — 17/17 pairs meet threshold.
- [X] Brand Guardian grep gate passes (10 new tokens, 0 BAN violations) — see `specs/035-onboarding-brand-port/artifacts/grep-gate-run.txt`.
- [X] `docs/design/brand-system.md § 3 / § 4 / § 5 / § 6 / § 7 / § 9` contain no "TBD" / "placeholder" / "Epic H (pending)" — all six sections populated (only § 8 Voice & tone remains placeholder, owned jointly by Epic H + Epic K per section's own scope rule).
- [X] `docs/design/contrast-measurements.md` exists and every row shows PASS.
- [X] `docs/tui/accessibility-gate.md § 7` handoff note acknowledges Epic H's measured ratios — see new § 7.1 subsection.
- [X] Every LogoV2 REWRITE file has a matching `.snap.test.tsx` file (AnimatedAsterisk, CondensedLogo, Feed, FeedColumn via Feed.test.tsx, feedConfigs via Feed.test.tsx, LogoV2, WelcomeV2, UmmayaCoreIcon).

When all boxes tick, the PR is ready for Code Reviewer sign-off and merge.
