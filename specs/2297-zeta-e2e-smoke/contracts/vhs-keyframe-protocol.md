# Contract — vhs Keyframe Protocol (FR-012 + SC-002 + SC-012)

**Date**: 2026-04-30
**Owner**: `specs/2297-zeta-e2e-smoke/scripts/smoke-citizen-taxreturn.tape`

## I-K1 — Tape file structure

**Given** charm-vhs ≥ 0.11.

**Then** `smoke-citizen-taxreturn.tape` MUST:
1. Set output: `Output specs/2297-zeta-e2e-smoke/smoke-citizen-taxreturn.gif`.
2. Set canonical terminal sizing: `Set FontSize 14`, `Set Width 120`, `Set Height 36`, `Set Theme "Tokyo Night"`.
3. Spawn the TUI: `Type "cd ~/UMMAYA-w-2297/tui && bun run tui"`, `Enter`, `Sleep 5s`.
4. Capture **keyframe 1** (boot+branding): `Screenshot specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-1-boot.png`, `Sleep 1s`.
5. Type the citizen prompt: `Type "종합소득세 신고해줘"`, `Sleep 1s`, `Enter`, `Sleep 8s`.
6. Capture **keyframe 2** (dispatch active — verify just emitted, spinner visible OR the verify tool_call marker rendered): `Screenshot specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-2-dispatch.png`, `Sleep 1s`.
7. Wait for chain completion: `Sleep 60s` (most chain runs complete in <30s; 60s is safety margin).
8. Capture **keyframe 3** (receipt rendered — final assistant message contains 접수번호): `Screenshot specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-3-receipt.png`.
9. Send Ctrl+C to exit: `Ctrl+C`, `Sleep 1s`, `Ctrl+C`.

## I-K2 — Three minimum keyframes

**Given** AGENTS.md § Layer 4 (`docs/testing.md`).

**Then** the tape MUST emit ≥3 `Screenshot` directives at the canonical scenario stages above. Naming convention: `smoke-keyframe-{N}-{stage}.png` where N is 1-based and `stage` is one of `boot` / `dispatch` / `receipt` (chronological).

## I-K3 — Keyframe-3 visual verification (Lead Opus)

**Given** `smoke-keyframe-3-receipt.png` is committed.

**Then** Lead Opus MUST use the Read tool on this PNG (multimodal vision) and check:
- The image renders the citizen-facing assistant message containing `접수번호: hometax-2026-MM-DD-RX-XXXXX`.
- The UMMAYA branding is visible at the top.
- No stub markers (`status: stub`, `Lollygagging…` mid-spinner) are present in the final state.

If any of the above fails, the change is BLOCKED. Lead reports the specific anomaly in the PR description.

## I-K4 — No GIF-only verification

**Given** AGENTS.md § Layer 4 hard rule (2026-04-29 promotion).

**Then** the agent Read tool MUST NOT rely on the `.gif` file alone for visual verification. The `.gif` is supplementary; the 3 PNG keyframes are the canonical artefacts.

## I-K5 — macOS / Linux cross-render

**Given** charm-vhs may render slightly differently across OS.

**Then** the tape MUST be capture-able on Linux CI (existing primary). macOS local runs are advisory; if a keyframe renders differently on macOS vs Linux, Lead documents the diff in the PR but the Linux capture is canonical.

## I-K6 — Tape execution time budget

**Given** the tape's total `Sleep` time budget.

**Then** the tape MUST complete in ≤120s wall-clock. If slower, the chain is regressed (mock adapters should respond in <1s each; LLM streams in ~25s × 3 turns = 75s; total ≤95s with 25s margin).

## I-K7 — Pre-push verification gate

Per SC-012, Lead Opus MUST verify the 4 vhs artefacts (`.tape` + 3 PNG) are committed before push:
```bash
git ls-files specs/2297-zeta-e2e-smoke/scripts/smoke-*.tape \
              specs/2297-zeta-e2e-smoke/scripts/smoke-keyframe-*.png \
              specs/2297-zeta-e2e-smoke/smoke-citizen-taxreturn.gif
```
Output MUST list ≥5 paths (1 tape + 3 png + 1 gif).
