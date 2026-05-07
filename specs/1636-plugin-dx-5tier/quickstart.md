# Quickstart — Contributor Walkthrough (verifies SC-001)

**Audience**: A developer who has never touched KOSMOS, has Python 3.12+ and uv installed, and wants to land their first KOSMOS plugin.
**Goal**: From `git clone` to a passing local `pytest` green in **under 30 minutes**. This file is the live reference for SC-001 and is itself the test artifact for that criterion (timed onboarding sessions follow this exact script).

This is the *plan-phase* quickstart; the user-facing rendering goes to `docs/plugins/quickstart.ko.md` once implementation lands. The English version here is the source-of-truth (per AGENTS.md "All source text in English"); the Korean rendering is the translation contributors actually read.

---

## Step 0 — Prerequisites (pre-clock)

- Python 3.12+ with `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- A GitHub account.
- A `data.go.kr` API key if you plan to write a Live-tier plugin (free at https://data.go.kr).
- Optional: KOSMOS TUI installed locally — only needed for `kosmos plugin init` interactive flow. CLI scaffolding can also run via `uvx kosmos-plugin-init <name>` (vendored entry-point) without the full TUI.

These prerequisites are NOT counted against the 30-minute budget; SC-001 measures from git clone forward.

---

## Step 1 — Clone the template (1 min)

Two options:

### Option A — GitHub "Use this template" (recommended)

1. Go to https://github.com/kosmos-plugin-store/kosmos-plugin-template
2. Click "Use this template" → "Create a new repository"
3. Name it `kosmos-plugin-<your-plugin-name>` (e.g., `kosmos-plugin-busan-bike`)
4. Clone locally:
   ```sh
   git clone https://github.com/<your-org>/kosmos-plugin-busan-bike
   cd kosmos-plugin-busan-bike
   ```

### Option B — `kosmos plugin init` CLI (if you have the TUI)

```sh
kosmos plugin init busan-bike
cd busan-bike
```

This emits the same scaffold as Option A but lets you set tier / layer / PII via interactive prompts. Useful when you already know the answers.

---

## Step 2 — Install + run the scaffold tests (3 min)

```sh
uv sync           # ~30 s (downloads pydantic, httpx, pytest)
uv run pytest     # ~5 s (single happy-path test on synthetic fixture)
```

Expected output:
```
============== 1 passed in 0.42s ==============
```

If green: the scaffold works. Move on. If red: something is misconfigured locally; check `uv --version` ≥ `0.5`, Python ≥ 3.12.

---

## Step 3 — Read the architecture (5 min)

Open `docs/plugins/architecture.md` (in this repo, vendored as a stub during scaffold; canonical version at https://github.com/umyunsang/KOSMOS/blob/main/docs/plugins/architecture.md). Skim:

- The active plugin primitives: `lookup`, `submit`, `verify`.
- Your plugin's `tool_id` MUST be `plugin.<plugin_id>.<verb>` where `<verb>` is one of those active plugin verbs.
- Your `adapter.py` registers a `GovAPITool` instance into the registry.
- Live tier vs Mock tier — pick before you write code.

For the busan-bike example, we'll use:
- `tool_id`: `plugin.busan_bike.lookup`
- `tier`: `live` (Busan Open Data Plaza)
- `permission_layer`: 1 (public bike availability — no PII)

---

## Step 4 — Edit `manifest.yaml` (3 min)

The scaffolded `manifest.yaml` looks like:

```yaml
plugin_id: busan_bike
version: 0.1.0
adapter:
  tool_id: plugin.busan_bike.lookup
  primitive: lookup
  module_path: plugin_busan_bike.adapter
  input_model_ref: plugin_busan_bike.schema:BusanBikeQueryInput
  source_mode: OPENAPI
  published_tier_minimum: null
  nist_aal_hint: null
tier: live
mock_source_spec: null
processes_pii: false        # public bike availability is non-personal
slsa_provenance_url: https://github.com/<your-org>/kosmos-plugin-busan-bike
otel_attributes:
  kosmos.plugin.id: busan_bike
search_hint_ko: "부산 자전거 따릉이 대여소 자전거 잔여대수 부산광역시"
search_hint_en: "Busan bike rental station availability"
permission_layer: 1
```

If `processes_pii: true`, add the `pipa_trustee_acknowledgment` block here (run `kosmos plugin pipa-text` to print the canonical text and SHA-256, or read `docs/plugins/security-review.md`).

---

## Step 5 — Edit `plugin_busan_bike/schema.py` (5 min)

```python
from pydantic import BaseModel, ConfigDict, Field

class BusanBikeQueryInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    district: str = Field(min_length=1, description="부산 구 이름 (예: 해운대구, 수영구)")

class BusanBikeStation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    station_id: str = Field(description="대여소 ID")
    station_name_ko: str = Field(description="대여소 한국어 이름")
    bikes_available: int = Field(ge=0, description="현재 잔여 자전거 수")

class BusanBikeQueryOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stations: list[BusanBikeStation] = Field(description="구 내 대여소 목록")
```

Rules (enforced by Q1-PYV2 / Q1-NOANY / Q1-FIELD-DESC):
- Pydantic v2 `BaseModel` with `frozen=True, extra="forbid"`.
- No `Any`. Every field has a type.
- Every `Field` has `description=`.

---

## Step 6 — Edit `plugin_busan_bike/adapter.py` (8 min)

```python
import os
import httpx

from kosmos.tools.models import GovAPITool

from .schema import BusanBikeQueryInput, BusanBikeQueryOutput, BusanBikeStation

ENDPOINT = "https://api.bts.go.kr/openapi/bike/stations"


def _build_tool() -> GovAPITool:
    """GovAPITool is a frozen Pydantic v2 BaseModel — instantiate via
    constructor, not class-attribute override (review eval D5)."""
    return GovAPITool(
        id="plugin.busan_bike.lookup",
        name_ko="부산 따릉이 대여소 잔여 자전거 조회",
        ministry="OTHER",   # post-Spec-1634 FR-010: `provider` field replaced by `ministry`
        category=["교통", "자전거"],
        endpoint=ENDPOINT,
        auth_type="api_key",
        input_schema=BusanBikeQueryInput,
        output_schema=BusanBikeQueryOutput,
        search_hint="부산 자전거 따릉이 대여소 잔여대수 / Busan bike rental availability",
        auth_level="AAL1",
        # GovAPITool's pipa_class enum: non_personal / personal / sensitive / identifier.
        # See docs/plugins/permission-tier.md "두 개의 pipa_class enum 표기" for the
        # mapping to the manifest layer's enum (personal_standard, etc).
        pipa_class="non_personal",
        is_irreversible=False,
        dpa_reference=None,            # null OK because pipa_class=non_personal
        is_personal_data=False,        # public availability counts
        primitive="lookup",
        published_tier_minimum="digital_onepass_level1_aal1",
        nist_aal_hint="AAL1",
        is_concurrency_safe=True,      # GET-only public availability data
        cache_ttl_seconds=60,          # bike availability changes minutely
        rate_limit_per_minute=30,
    )


_TOOL_CACHE = None


def __getattr__(name):
    """PEP 562 lazy TOOL — keeps standalone scaffold tests runnable
    without ``kosmos`` being installed."""
    global _TOOL_CACHE
    if name == "TOOL":
        if _TOOL_CACHE is None:
            _TOOL_CACHE = _build_tool()
        return _TOOL_CACHE
    raise AttributeError(name)


async def adapter(payload: BusanBikeQueryInput) -> dict:
    api_key = os.environ["KOSMOS_DATA_GO_KR_API_KEY"]
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
        r = await client.get(
            ENDPOINT,
            params={"serviceKey": api_key, "district": payload.district},
        )
        r.raise_for_status()
        data = r.json()
    return {
        "stations": [
            {
                "station_id": s["id"],
                "station_name_ko": s["name"],
                "bikes_available": s["available"],
            }
            for s in data["stations"]
        ]
    }
```

Rules:
- Read API key from `KOSMOS_*` env var (never hardcode — Q-NO-HARDCODED-KEY).
- Read every required GovAPITool field; defaults are conservative for fields you skip.
- For Live tier, write a real network call; for Mock tier, replace `httpx.get` with fixture replay (see `docs/plugins/live-vs-mock.md`).

---

## Step 7 — Update tests (3 min)

`tests/test_adapter.py` ships with a synthetic fixture `tests/fixtures/plugin.busan_bike.lookup.json` and a happy-path test that monkey-patches `httpx.get` to return the fixture. Edit the fixture to match your `output_schema`:

```json
{
  "stations": [
    {"station_id": "BTS-001", "station_name_ko": "해운대해수욕장", "bikes_available": 7},
    {"station_id": "BTS-002", "station_name_ko": "광안리해수욕장", "bikes_available": 3}
  ]
}
```

Add an error-path test (Q10-ERROR-PATH):

```python
@pytest.mark.asyncio
async def test_invalid_district_returns_empty(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient.get", _mock_404)
    adapter = BusanBikeAdapter()
    with pytest.raises(httpx.HTTPStatusError):
        await adapter.execute(BusanBikeQueryInput(district="존재하지않는구"))
```

Run:
```sh
uv run pytest
```

Expected: `2 passed`.

---

## Step 8 — Run validation locally (2 min)

```sh
uvx --from git+https://github.com/umyunsang/KOSMOS@main \
    kosmos-plugin-validate .
```

This runs all 50 review-checklist items locally — same checks the GitHub workflow runs on PR. Expected:
```
✓ 50 / 50 통과
```

If anything fails, the output shows the item id and a fix hint. Re-edit and re-run until green.

---

## Step 9 — Push and open PR (1 min)

```sh
git add -A
git commit -m "feat: initial busan-bike plugin"
git push origin main
```

Open a PR; the `plugin-validation.yml` workflow runs against your PR. Expected: green check + Korean summary comment "✓ 50 / 50 통과 — 검증 완료. 머지를 위해 maintainer 의 리뷰가 필요합니다."

---

## Wall-clock summary

| Step | Time | Cumulative |
|---|---|---|
| 0. Prerequisites | (pre-clock) | — |
| 1. Clone template | 1 min | 1 min |
| 2. Install + scaffold tests | 3 min | 4 min |
| 3. Read architecture | 5 min | 9 min |
| 4. Edit manifest | 3 min | 12 min |
| 5. Edit schema | 5 min | 17 min |
| 6. Edit adapter | 8 min | 25 min |
| 7. Update tests | 3 min | 28 min |
| 8. Local validation | 2 min | 30 min |
| 9. Push + PR | 1 min | 31 min |

**SC-001 budget**: ≤ 30 min. The walkthrough fits in 28 min before push (push happens in another team's CI cycle and is excluded from the 30-min wall-clock per spec phrasing "from cloning ... to a passing local pytest green").

## What's NOT in this quickstart

- PIPA acknowledgment flow — only triggered if `processes_pii: true`. See `docs/plugins/security-review.md`.
- Mock-tier path — see `docs/plugins/live-vs-mock.md`.
- Publishing to `kosmos-plugin-store` — out of scope for this quickstart; happens after PR merge.
- Marketplace browsing UI — deferred (#1820).
