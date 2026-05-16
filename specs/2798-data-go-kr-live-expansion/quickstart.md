# Quickstart: data.go.kr Live Expansion

## 1. Confirm Evidence Set

```bash
rg -n "30 callable now|Hold Until Probe Blocker|15149906|15074634" \
  docs/api/data-go-kr-candidate-docs/LIVE-API-CALL-MATRIX-2026-05-16.md \
  docs/api/data-go-kr-candidate-docs/LIVE-API-BLOCKER-RESOLUTION-2026-05-16.md
```

Expected:

- 30 callable APIs.
- `15038392`, `15058923`, `15063444` remain blocked.
- `15149906` and `15074634` have resolved callable evidence.

## 2. Run Fixture Tests

```bash
uv run pytest \
  tests/unit/tools/verified_data_go_kr \
  tests/unit/tools/test_registry_count_breakdown.py \
  -m "not live"
```

Expected:

- 30 verified adapter IDs in the manifest test.
- Main registry count 68.
- No live HTTP call from default tests.

## 3. Run Backend Verification

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not live"
```

## 4. Run Real UMMAYA Terminal Smoke

Use local credentials only. Do not paste or record secrets.

Representative prompts:

```text
종로구 자동심장충격기 위치 알려줘.
타이레놀 효능과 복용 주의사항을 공식 자료로 알려줘.
최근 과기정통부 AI 관련 사업공고 찾아줘.
대전역에서 시청역까지 지하철 요금과 시간 알려줘.
2025년 4월 장단기 체류외국인 수를 알려줘.
```

Record the observed root primitive, adapter ID, parameter object, success/error status, and abnormal-flow notes in `real-use-smoke.md`.

## 5. Secret Scan

```bash
rg -n "$UMMAYA_DATA_GO_KR_API_KEY|$UMMAYA_FRIENDLI_TOKEN|$UMMAYA_KAKAO_API_KEY" \
  specs/2798-data-go-kr-live-expansion docs/api/data-go-kr-candidate-docs \
  --glob '!*.png' --glob '!*.gif'
```

Expected: no matches.
