# Debug-infra-rebuild — Phase 2 + invalid_params parallel dispatch

> **Lead**: Opus (this session)
> **Triggered**: 2026-05-02
> **Reason**: User said "병렬로 진행해" — two independent follow-ups from
> commit `182f4b7` (debug infra rebuild). The new tmux harness immediately
> exposed an `Invalid parameters` regression that was previously hidden
> by 90 s timeouts. Phase 2 (aimock fake LLM) and the invalid_params
> investigation are independent and parallelisable.

## Tree

```
Phase 2 — aimock fake-LLM HTTP server     ┐
   sonnet-aimock-phase2                   ├─ parallel
                                          │
invalid_params regression debug           │
   sonnet-debug-invalidparams             ┘

Lead Opus serializes:
   - reads both teammate reports
   - integrates into one (or two) commit(s)
   - runs full regression suite
   - decides next step
```

## Teammate scope

### sonnet-aimock-phase2 (≤ 5 tasks / ≤ 10 file changes)

Author Phase 2 of `specs/debug-infra-rebuild/RFC.md` § P0 / § 5:

1. Verify aimock / llmock package exists and is usable (npm or Docker
   image). RFC cites `copilotkit/llmock` — confirm or replace with
   alternative if upstream is dead.
2. Author `docker-compose.aimock.yml` (or `.devcontainer` extension)
   exposing aimock on a fixed port.
3. Author 2 fixtures under `tests/fixtures/llm/`: `busan-weather.json`
   (single tool_call → kma_forecast_fetch with valid lat/lon/base_date/
   base_time params) and `busan-multi-tool.json` (multi-tool turn used
   to verify Codex's `parallel_tool_calls=False` fix actually drops
   the extras when aimock emits 3 tool_calls).
4. Document the env switch: `KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010`
   + `KOSMOS_FRIENDLI_TOKEN=aimock-test`.
5. Verify the existing `bun test` + `pytest` suite stays green with
   aimock NOT running (i.e., aimock is opt-in, default real-FriendliAI
   path unchanged).

Hard rule: do NOT modify CI workflows yet. Just ship the infra so the
next Epic can wire it. Do NOT commit (Lead handles that).

### sonnet-debug-invalidparams (≤ 5 tasks / ≤ 10 file changes)

Diagnose why `kma_short_term_forecast` rejects K-EXAONE's params with
`invalid_params` despite the schema-dump suffix being in commit
`9a1a090`:

1. Trace the call path from the new `<available_adapters>` suffix
   (in `src/kosmos/ipc/stdio.py:_build_available_adapters_suffix`)
   to the actual system prompt sent to FriendliAI. Confirm the schema
   field signatures (`lat`, `lon`, `base_date`, `base_time` for
   `kma_forecast_fetch`) are present in the assembled system message.
2. Reproduce the K-EXAONE call with a httpx probe that mirrors KOSMOS's
   exact payload (use the prior probe at `/tmp/kosmos-payload-probe.py`
   as the seed). Capture the actual `tool_calls[0].function.arguments`
   K-EXAONE returns and compare to the schema KOSMOS sent.
3. Identify the gap. Hypotheses ordered by likelihood (apply RFC
   heuristic H2 — "verify the costliest hypothesis first"):
   (a) The dispatcher injects the suffix into a different system
       message than the one going out to FriendliAI.
   (b) `kma_short_term_forecast`'s schema requires `nx`/`ny` (KMA grid
       coords) which K-EXAONE doesn't have without a prior
       `resolve_location` call. The schema dump tells K-EXAONE this
       but K-EXAONE chooses to call without coords because it sees
       `params: {}` as valid in the meta-tool.
   (c) Adapter validation enforces something the JSON Schema doesn't
       reflect (e.g., extra `@model_validator`).
4. Author a minimal fix. Acceptable shapes:
   - Stricter pre-flight in `_build_available_adapters_suffix` to
     surface "you MUST call resolve_location FIRST when nx/ny required".
   - Or rewrite the system_v1.md `<turn_order>` rule to make the
     resolve_location → kma chain explicit.
   - Or add an example tool_call in the suffix.
5. Verify with the new tmux harness:
   `scripts/tui-tmux-capture.sh /tmp/aftermath specs/debug-infra-rebuild/scenarios/busan-weather.sh`
   should now show `⎿ <records>` (success) instead of
   `⎿ 검색 오류: Invalid parameters for tool`.

Hard rule: do NOT modify the LLM client (`client.py`) or the IPC
dispatcher beyond `_build_available_adapters_suffix` + `system_v1.md`.
Stay on the prompt-engineering / schema-rendering layer. Do NOT commit
(Lead handles that).

## Lead's serialization

After both teammates report:

1. Read each teammate's diff + reasoning.
2. If sonnet-debug-invalidparams's fix touches `system_v1.md`, run the
   prompt-manifest hash regen (`scripts/build_schemas.py` is irrelevant
   here, but `prompts/manifest.yaml` SHA may need an update — check).
3. Single regression sweep: `bun test` + `pytest tests/ipc tests/tools`.
4. Live verification: `scripts/tui-tmux-capture.sh` busan scenario,
   confirm `⎿ <records>` paint.
5. Commit Phase 2 separately from invalid_params fix (two commits,
   different concerns).
