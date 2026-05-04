# Research: HIRA Baked/Brewed timeout (Epic #2766 issue C)

## Diagnosis

Citizen reported `동아대학교 근처 내과 병원 알려줘` resulting in:
- `✻ Baked for 1m 5s` then `✻ Brewed for 1m 4s` on retry
- Both attempts perceived as "fail" — no useful output rendered

`tui/src/constants/turnCompletionVerbs.ts` confirms `Baked` / `Brewed` are
**past-tense success verbs** (turn completed). The dispatch returned, but the
citizen saw no answer. Two factors compounded:

1. **HIRA upstream latency** — `getHospBasisList` regional queries (large
   radius / dense urban areas) regularly take 20-45 s on cold cache. The
   pre-fix `httpx.AsyncClient(timeout=30.0)` (`src/kosmos/tools/hira/hospital_search.py:141`)
   sometimes fired `httpx.ReadTimeout` on the first attempt, returning
   `LookupError(reason='upstream_unavailable')`.

2. **Render-order bug (Epic #2766 issue B)** — even when HIRA returned data,
   the K-EXAONE preamble suppressed the next-turn answer's visual prominence.
   Citizen saw only `lookup → record` then completion verb, no readable text.

## Fix (US3)

- `src/kosmos/tools/hira/hospital_search.py:141` — bump `timeout=30.0` →
  `timeout=60.0`. Genuine network outages still produce a clean error
  envelope (executor `_classify_adapter_exception` → `upstream_unavailable`).
- `src/kosmos/tools/executor.py` — annotate `execute_tool` span with
  `kosmos.tool.stage` (`fetch | fetch_failed | parse`) and
  `kosmos.tool.fetch_ms` so OTLP / Langfuse traces show where time was
  spent. Citizen support can now distinguish slow upstream vs slow LLM
  thinking vs slow envelope parse.

## Why no `httpx.ReadTimeout` retry?

A single transient retry would double-charge HIRA's API quota (each call
counts against the `data.go.kr` daily limit). Adapters that need it can opt
in via per-tool `retry_policy` in a future spec; for now the timeout bump is
the surgical fix.

## Why issue C resolves with US2 + US3 stack

US2 fixes the render-order so when HIRA returns successfully, the next-turn
answer appears as a single readable chunk after `tool_call → tool_result`.
US3 ensures HIRA actually returns successfully on slow regional queries.
Combined, the citizen sees `⏺ lookup(...) → ⎿ record(15 hospitals) →
⏺ <markdown table of hospitals>`.

## Verification

- Layer 1: `tests/tools/test_hira_hospital_search.py` (existing) PASS.
- Layer 1: existing `test_otel_spans_preserved` confirms the new
  `kosmos.tool.stage` attribute does not break the required-keys check.
- Live verification deferred to manual citizen flow (HIRA `@pytest.mark.live`
  test gated behind `KOSMOS_DATA_GO_KR_API_KEY`).
