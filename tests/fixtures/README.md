# Test Fixtures

This directory contains recorded HTTP response fixtures used by the UMMAYA tool
adapter test suite. Fixtures allow tests to run without making live API calls to
`data.go.kr` or any other external service.

## Purpose

- Enable deterministic, fast, offline testing for all tool adapters.
- Capture real wire responses (including quirks) from government APIs.
- Provide a stable baseline for regression testing when adapter code changes.

## Directory Layout

```
tests/fixtures/
├── README.md            # this file
├── kma/                 # KMA (기상청) response fixtures
│   └── .gitkeep
└── koroad/              # KOROAD (도로교통공단) response fixtures
    ├── .gitkeep
    └── koroad_accident_search.json   # recorded happy-path response
```

Additional per-adapter fixtures live under the adapter's own test directory:

```
tests/tools/
├── kma/fixtures/
│   ├── kma_alert_empty.json          # zero active alerts response
│   ├── kma_alert_error.json          # non-"00" resultCode response
│   ├── kma_alert_success.json        # multiple active warnings
│   ├── kma_obs_error.json            # observation API error response
│   ├── kma_obs_rn1_dash.json         # RN1="-" sentinel edge case
│   └── kma_obs_success.json          # normal observation with all categories
└── koroad/fixtures/
    ├── koroad_empty.json             # zero hotspots response
    ├── koroad_error.json             # non-"00" resultCode response
    ├── koroad_single_item.json       # single hotspot (dict, not list)
    └── koroad_success.json           # multiple hotspots
```

## Fixture Convention

- One JSON file per adapter response scenario, named `{tool_id}.json` for the
  canonical happy-path fixture under `tests/fixtures/{provider}/`.
- Additional scenario-specific fixtures live under `tests/tools/{provider}/fixtures/`
  and are named descriptively (e.g., `kma_obs_rn1_dash.json`).
- Fixtures represent the **raw wire response** returned by the API (the full JSON
  body including `response.header` and `response.body`).
- Fixture files must not contain real API keys, PII, or sensitive data.

## Existing Fixtures

| File                                             | Tool                     | Scenario                          |
|--------------------------------------------------|--------------------------|-----------------------------------|
| `koroad/koroad_accident_search.json`             | `koroad_accident_search` | Happy path — multiple hotspots    |
| `tools/koroad/fixtures/koroad_success.json`      | `koroad_accident_search` | Happy path — multiple hotspots    |
| `tools/koroad/fixtures/koroad_single_item.json`  | `koroad_accident_search` | Single hotspot (dict normalization)|
| `tools/koroad/fixtures/koroad_empty.json`        | `koroad_accident_search` | No results — empty items          |
| `tools/koroad/fixtures/koroad_error.json`        | `koroad_accident_search` | API error — non-"00" resultCode   |
| `tools/kma/fixtures/kma_alert_success.json`      | `kma_weather_alert_status`| Multiple active warnings          |
| `tools/kma/fixtures/kma_alert_empty.json`        | `kma_weather_alert_status`| No active alerts                  |
| `tools/kma/fixtures/kma_alert_error.json`        | `kma_weather_alert_status`| API error — non-"00" resultCode   |
| `tools/kma/fixtures/kma_obs_success.json`        | `kma_current_observation` | Normal observation, all categories|
| `tools/kma/fixtures/kma_obs_rn1_dash.json`       | `kma_current_observation` | RN1="-" no-precipitation sentinel |
| `tools/kma/fixtures/kma_obs_error.json`          | `kma_current_observation` | API error — non-"00" resultCode   |

## Recording New Fixtures

To record a new fixture from a live API response:

1. Write a `@pytest.mark.live` test that calls the real adapter with real credentials.
2. Capture the raw HTTP response body (before parsing).
3. Save it as a JSON file following the naming convention above.
4. Replace sensitive values (API keys, internal identifiers) with placeholder strings.
5. Add the new fixture to the table in this README.

Example test skeleton for recording:

```python
import json
import pytest
import httpx

@pytest.mark.live
async def test_record_koroad_fixture():
    """Run with: uv run pytest -m live tests/tools/koroad/ -v"""
    import os
    api_key = os.environ["UMMAYA_KOROAD_API_KEY"]
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://apis.data.go.kr/B552061/frequentzoneLg/getRestFrequentzoneLg",
            params={
                "serviceKey": api_key,
                "searchYearCd": "2025119",
                "siDo": 11,
                "numOfRows": 5,
                "pageNo": 1,
                "_type": "json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        raw = response.json()

    # Redact the API key from any echoed parameters before saving
    with open("tests/fixtures/koroad/koroad_accident_search.json", "w") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
```

Live tests are skipped by default (`uv run pytest` without `-m live`). To run them:

```bash
UMMAYA_KOROAD_API_KEY=... UMMAYA_DATA_GO_KR_API_KEY=... uv run pytest -m live -v
```

See `docs/design/verification-fabric-v2.md` for the live-test marker and CI policy.
