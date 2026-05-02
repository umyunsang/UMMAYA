# Debug-infra-rebuild — Round 2 parallel dispatch (Phase 3-next + Phase 4 + ops + push)

> **Lead**: Opus
> **Triggered**: 2026-05-02 (sequel to round 1 commits 65b3041 / 48469d8 / 444b056)
> **User**: "동시진행해" — 4 follow-up tracks in parallel

## Tree

```
(1) Phase 3 next batch — Spec 1979 × 4 expect port      ┐
       sonnet-1979-port                                  │
                                                         │
(2) Phase 4 — per-render Ink snapshot + frame_commit OTEL│ parallel
       sonnet-phase4-snapshot                            │
                                                         │
(4) aimock spin-up + live fixture validation             │
       sonnet-aimock-validate                            ┘

(3) push + PR + CI monitor — Lead Opus solo (after all 3 teammates report)
```

## Teammate scope

### sonnet-1979-port (≤5 task / ≤10 file)

Continue RFC § 5 Phase 3 by porting the 4 Spec 1979 plugin-DX-TUI-integration smokes:
- `specs/1979-plugin-dx-tui-integration/scripts/debug-direct.expect`
- `specs/1979-plugin-dx-tui-integration/scripts/debug-enter.expect`
- `specs/1979-plugin-dx-tui-integration/scripts/debug-help.expect`
- `specs/1979-plugin-dx-tui-integration/scripts/debug-install.expect`

Deliverables:
1. 4 new `specs/1979-plugin-dx-tui-integration/scenarios/<name>-tmux.sh`
2. Live proof captures at `specs/1979-plugin-dx-tui-integration/proof-runs/tmux-migration/<scenario>/snap-NNN-*.txt`
3. RFC § 5 Phase 3 status — bump checkbox

Migration patterns same as round 1 (commit 444b056). Reference scenario:
`specs/2519-korean-ime-enter-fix/scenarios/smoke-tmux.sh`. Helpers:
`scripts/tui-tmux-capture.sh` exports `wait_for_pane` / `snapshot_pane` /
`send_text_pane` / `send_enter_pane` / `send_keys_pane` / `send_ctrlc_pane`.

Hard rules: do NOT delete legacy `.expect` (kept for offline pyte replay).
Do NOT touch tui/src/** or src/kosmos/**. Do NOT commit.

### sonnet-phase4-snapshot (≤5 task / ≤10 file)

Implement RFC § 5 Phase 4 — per-render Ink snapshot stream + `kosmos.tui.frame_commit` OTEL event. The visual safety net AGENTS.md anti-pattern #1 needs to be permanently retired by.

Deliverables:
1. `tui/src/test-utils/frameStreamSnapshot.ts` — helper that wraps ink-testing-library's `render()` and exposes the `frames` array as a hash-of-state sequence.
2. `tui/src/utils/frameCommitOtel.ts` — small module that emits `kosmos.tui.frame_commit` OTEL span events on every Ink reconcile. Use `@opentelemetry/api` (already on the dep tree from Spec 021). Attributes: `kosmos.correlation_id` + `kosmos.tui.frame_hash` + `kosmos.tui.frame_seq`.
3. Wire it into the TUI render path in `tui/src/components/Messages.tsx` or the central reconcile callback (whichever is least invasive — stay byte-copy-compatible with CC).
4. ≥3 unit tests in `tui/tests/test-utils/frameStreamSnapshot.test.tsx` covering:
   - `assertFrameSequence(result, [hash1, hash2, hash3])` — passes for matched sequence
   - `assertFrameSequence` fails with diff diagnostic on hash mismatch
   - dedup of consecutive identical frames
5. AGENTS.md "Layer 5c" stub — note that Layer 5c (Ink frames sequence hash) is now available; Phase 4 done.

Hard rules: do NOT add new runtime dependencies (AGENTS.md hard rule). Use `@opentelemetry/api` only — already shipped. Do NOT commit. Stay ≤ 10 files.

### sonnet-aimock-validate (≤5 task / ≤10 file)

Live-validate Phase 2 (commit 65b3041) by actually spinning up aimock and running the existing busan smoke against it.

Deliverables:
1. Run `docker compose -f docker-compose.aimock.yml up -d`. Verify container healthy on port 4010.
2. With `KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1` + `KOSMOS_FRIENDLI_TOKEN=aimock-test`, run:
   `scripts/tui-tmux-capture.sh /tmp/tdb-aimock specs/debug-infra-rebuild/scenarios/busan-weather.sh`
3. Capture proof outputs at `specs/debug-infra-rebuild/proof-runs/aimock-busan-weather/`. Verify timeline: total run time should be < 15s (aimock ttft=200ms + tps=50 fixture; vs 60-90s with real FriendliAI).
4. If aimock's actual fixture format differs from what the teammate authored in commit 65b3041 (likely — RFC was speculative on the JSON shape), iterate the fixture until it works. Document the actual observed format in `tests/fixtures/llm/README.md`.
5. Tear down: `docker compose -f docker-compose.aimock.yml down`. Update `specs/debug-infra-rebuild/aimock-quickstart.md` with any corrections.

Hard rules: do NOT modify src/** or tui/src/**. The aimock service should be transparent to KOSMOS code (just env switch). If aimock's JSON shape is different, ONLY edit the fixture files + the quickstart doc. Do NOT commit.

If the aimock image is broken or the RFC's speculative format is wildly off, write up the gap honestly in `specs/debug-infra-rebuild/aimock-quickstart.md` with a "known issues" section + a fallback (e.g., switch to a different mock server). Do NOT pretend success.

## Lead serialization (after all 3 teammates report)

1. Verify each teammate's diff vs scope, run regression sweep (`bun test`, `pytest`).
2. Bundle into 1-3 commits depending on cohesion:
   - 1979 port → one commit (sequel to 444b056)
   - Phase 4 snapshot + OTEL → one commit (new layer)
   - aimock validation results → one commit (or amend 65b3041 if format-only fix)
3. Push branch, create PR, monitor CI. PR title: "feat(2521 + debug-infra): full layout + invalid_params + tmux harness + Phase 2/3/4". Description cites all 7 commits.
4. Address Codex inline review.
