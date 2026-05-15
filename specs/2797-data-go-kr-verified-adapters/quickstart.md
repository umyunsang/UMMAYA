# Quickstart: data.go.kr Verified Adapter Wave

## 1. Verify Scope

```bash
rg -n "Confirmed Callable|Reachable But Not Yet Callable|Not Live-Probed" \
  docs/api/data-go-kr-candidate-docs/LIVE-PROBE-RESULTS-2026-05-16.md
```

Only rows under `Confirmed Callable` are in scope.

## 2. Verify Registered Adapters

```bash
uv run pytest tests/tools/verified_data_go_kr/test_adapter_registration.py
```

Expected:

- 14 verified adapters are registered.
- All 14 use `primitive="find"`.
- No adapter from `SCOPED-NEW-30-manifest.json` is registered.

## 3. Replay Fixtures

```bash
uv run pytest tests/tools/verified_data_go_kr/test_adapter_fixture_replay.py
```

Expected:

- JSON and XML fixtures parse into `kind="collection"` outputs.
- Zero-result fixtures stay successful.
- Error fixtures become fail-closed error envelopes.

## 4. Run Focused Registry Tests

```bash
uv run pytest tests/tools/test_registration.py tests/tools/test_routing_index.py
```

Expected:

- Tool count updates to include the 14 new verified adapters.
- Routing index validation passes.

## 5. Run Backend Verification

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not live"
```

Expected:

- No lint, type, or fixture-replay failures.
- No live public API calls in the default test set.

## 6. Run UMMAYA Real-Use Smoke

Use local credentials only outside CI. The initial smoke should use a verified small read-only API such as 부산 장례비산출 or AirKorea.

```bash
UMMAYA_LIVE_ADAPTER_MODE=direct uv run ummaya
```

Citizen prompts to verify:

```text
부산 영락공원 장례식장 시설 사용료를 찾아줘
서울 대기오염 측정소별 실시간 정보를 조회해줘
대전 5번 버스 노선 정보를 찾아줘
```

Expected:

- UMMAYA searches and calls the matching `find` adapter.
- Tool result is grounded in the adapter output.
- No fabricated fallback result appears after an adapter error.
- Permission flow stays read-only and does not request identity for public data.

## 7. PR Evidence

PR description must include:

- Spec path.
- List of 14 included verified APIs.
- Fixture-only test command output.
- UMMAYA real-use smoke summary.
- `TUI no-change` unless `tui/src/**` is modified.
