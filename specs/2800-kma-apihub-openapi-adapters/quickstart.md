# Quickstart: KMA APIHub OpenAPI Adapters

## Default Non-Live Validation

From the repository root:

```bash
uv run pytest tests/tools/kma/test_apihub_catalog.py tests/tools/kma/test_apihub_endpoint.py tests/tools/kma/test_apihub_structured_adapter.py
uv run pytest tests/tools/kma/test_kma_current_observation.py tests/tools/kma/test_kma_short_term_forecast.py tests/tools/kma/test_kma_ultra_short_term_forecast.py
uv run pytest tests/permissions/test_credentials.py tests/tools/test_registration.py tests/unit/tools/test_registry_count_breakdown.py
uv run python scripts/build_schemas.py --check --quiet
uv run ruff format --check src/ummaya/tools/kma/apihub_catalog.py src/ummaya/tools/kma/apihub_endpoint.py src/ummaya/tools/kma/apihub_structured_adapter.py src/ummaya/tools/kma/__init__.py src/ummaya/tools/register_all.py src/ummaya/permissions/credentials.py tests/tools/kma/test_apihub_catalog.py tests/tools/kma/test_apihub_endpoint.py tests/tools/kma/test_apihub_structured_adapter.py tests/permissions/test_credentials.py
uv run ruff check src/ummaya/tools/kma/apihub_catalog.py src/ummaya/tools/kma/apihub_endpoint.py src/ummaya/tools/kma/apihub_structured_adapter.py src/ummaya/tools/kma/__init__.py src/ummaya/tools/register_all.py src/ummaya/permissions/credentials.py tests/tools/kma/test_apihub_catalog.py tests/tools/kma/test_apihub_endpoint.py tests/tools/kma/test_apihub_structured_adapter.py tests/permissions/test_credentials.py
```

Expected result:

- The catalog contains 85 structured `typ02/openApi` operations.
- Tool ids are unique and valid.
- Missing `UMMAYA_KMA_API_HUB_AUTH_KEY` fails closed.
- Fixture XML/JSON responses decode to typed structured output.
- Existing current-weather and forecast adapters still pass.

## Optional Local Live Probe

Only run this locally with the operator-managed APIHub key and after checking
APIHub utilization approval. Do not add this to CI.

```bash
source ~/.ummaya/env
uv run pytest -m live tests/live/test_live_kma.py tests/live/test_live_kma_forecast.py
```

Expected result:

- Approved VilageFcst operations return KMA APIHub data.
- Unapproved operations, if probed manually, fail closed with an authorization
  or approval-state reason.

## TUI Smoke Scenario

For existing citizen-weather behavior:

```bash
cd tui
source ~/.ummaya/env
bun run tui
```

Prompt:

```text
부산 사하구 다대1동 날씨알려줘
```

Expected behavior:

- `locate(kakao_address_search)` resolves coordinates.
- Existing specialized KMA current/forecast tools return official KMA data.
- The answer is not duplicated and no fallback weather values are fabricated.

## Approval Matrix Audit

Use the feature evidence file:

```text
specs/2800-kma-apihub-openapi-adapters/evidence/apihub-catalog-2026-05-24.md
```

Before claiming a new operation live-working, update the approval evidence with
a sanitized APIHub My Page observation or direct `curl` probe showing endpoint,
status, result code, total count, and redacted response shape.
