# KOSMOS API Catalog

This directory documents every active adapter registered with KOSMOS at the close of the Claude Code → Korean public-service harness migration (Initiative #1631, Epic P6 #1637). Twenty-one adapters span seven Korean ministries and agencies: twelve call live `data.go.kr` or public-infrastructure endpoints, eight replay public-spec-mirrored fixtures (six identity-verification and two submission), and one is the `resolve_location` meta-tool. Subscription adapters are intentionally deferred until KOSMOS has an app/push-notification runtime.

The catalog is intended for three audiences:

- **Citizen developers** (and external plugin contributors) discovering what KOSMOS already ships.
- **Release validators** confirming the registered surface against documentation.
- **Maintainers** keeping schemas in sync with `src/kosmos/tools/` source.

Every adapter spec follows the seven-section template in [`specs/1637-p6-docs-smoke/contracts/adapter-spec-template.md`](../../specs/1637-p6-docs-smoke/contracts/adapter-spec-template.md): YAML front matter (`tool_id` · `primitive` · `tier` · `permission_tier`) followed by Overview · Envelope · Search hints · Endpoint · Permission tier rationale · Worked example · Constraints. JSON Schema Draft 2020-12 exports for every adapter live under [`schemas/`](./schemas/) and are produced deterministically by [`scripts/build_schemas.py`](../../scripts/build_schemas.py).

## How to use this catalog

1. **Find an adapter** — scan Matrix A (by source) when the ministry is known, Matrix B (by primitive) when the verb (`lookup` / `submit` / `verify`) is known. Both matrices are sorted alphabetically by `tool_id`.
2. **Read the spec** — open the linked Markdown file. The seven mandatory sections give classification, envelope reference, bilingual search hints, endpoint, permission rationale, worked example, and constraints.
3. **Consume the schema** — the JSON Schema file linked from each row is Draft 2020-12 and validates against any generic schema validator. Re-run `python scripts/build_schemas.py --check` to verify the on-disk schemas still match the source Pydantic models.

## Matrix A — adapters by source

| Source | tool_id | Primitive | Tier | Permission | Spec | Schema |
|---|---|---|---|---|---|---|
| KOROAD | `koroad_accident_search` | `lookup` | live | 1 | [koroad/accident_search.md](./koroad/accident_search.md) | [koroad_accident_search.json](./schemas/koroad_accident_search.json) |
| KOROAD | `koroad_accident_hazard_search` | `lookup` | live | 1 | [koroad/accident_hazard_search.md](./koroad/accident_hazard_search.md) | [koroad_accident_hazard_search.json](./schemas/koroad_accident_hazard_search.json) |
| KMA | `kma_current_observation` | `lookup` | live | 1 | [kma/current_observation.md](./kma/current_observation.md) | [kma_current_observation.json](./schemas/kma_current_observation.json) |
| KMA | `kma_short_term_forecast` | `lookup` | live | 1 | [kma/short_term_forecast.md](./kma/short_term_forecast.md) | [kma_short_term_forecast.json](./schemas/kma_short_term_forecast.json) |
| KMA | `kma_ultra_short_term_forecast` | `lookup` | live | 1 | [kma/ultra_short_term_forecast.md](./kma/ultra_short_term_forecast.md) | [kma_ultra_short_term_forecast.json](./schemas/kma_ultra_short_term_forecast.json) |
| KMA | `kma_weather_alert_status` | `lookup` | live | 1 | [kma/weather_alert_status.md](./kma/weather_alert_status.md) | [kma_weather_alert_status.json](./schemas/kma_weather_alert_status.json) |
| KMA | `kma_pre_warning` | `lookup` | live | 1 | [kma/pre_warning.md](./kma/pre_warning.md) | [kma_pre_warning.json](./schemas/kma_pre_warning.json) |
| KMA | `kma_forecast_fetch` | `lookup` | live | 1 | [kma/forecast_fetch.md](./kma/forecast_fetch.md) | [kma_forecast_fetch.json](./schemas/kma_forecast_fetch.json) |
| HIRA | `hira_hospital_search` | `lookup` | live | 1 | [hira/hospital_search.md](./hira/hospital_search.md) | [hira_hospital_search.json](./schemas/hira_hospital_search.json) |
| NMC | `nmc_emergency_search` | `lookup` | live | 3 | [nmc/emergency_search.md](./nmc/emergency_search.md) | [nmc_emergency_search.json](./schemas/nmc_emergency_search.json) |
| NFA119 | `nfa_emergency_info_service` | `lookup` | live | 1 | [nfa119/emergency_info_service.md](./nfa119/emergency_info_service.md) | [nfa_emergency_info_service.json](./schemas/nfa_emergency_info_service.json) |
| MOHW | `mohw_welfare_eligibility_search` | `lookup` | live | 1 | [mohw/welfare_eligibility_search.md](./mohw/welfare_eligibility_search.md) | [mohw_welfare_eligibility_search.json](./schemas/mohw_welfare_eligibility_search.json) |
| Mock — Verify | `mock_verify_digital_onepass` | `verify` | mock | 2 | [verify/digital_onepass.md](./verify/digital_onepass.md) | [mock_verify_digital_onepass.json](./schemas/mock_verify_digital_onepass.json) |
| Mock — Verify | `mock_verify_mobile_id` | `verify` | mock | 2 | [verify/mobile_id.md](./verify/mobile_id.md) | [mock_verify_mobile_id.json](./schemas/mock_verify_mobile_id.json) |
| Mock — Verify | `mock_verify_gongdong_injeungseo` | `verify` | mock | 3 | [verify/gongdong_injeungseo.md](./verify/gongdong_injeungseo.md) | [mock_verify_gongdong_injeungseo.json](./schemas/mock_verify_gongdong_injeungseo.json) |
| Mock — Verify | `mock_verify_geumyung_injeungseo` | `verify` | mock | 2 | [verify/geumyung_injeungseo.md](./verify/geumyung_injeungseo.md) | [mock_verify_geumyung_injeungseo.json](./schemas/mock_verify_geumyung_injeungseo.json) |
| Mock — Verify | `mock_verify_ganpyeon_injeung` | `verify` | mock | 2 | [verify/ganpyeon_injeung.md](./verify/ganpyeon_injeung.md) | [mock_verify_ganpyeon_injeung.json](./schemas/mock_verify_ganpyeon_injeung.json) |
| Mock — Verify | `mock_verify_mydata` | `verify` | mock | 2 | [verify/mydata.md](./verify/mydata.md) | [mock_verify_mydata.json](./schemas/mock_verify_mydata.json) |
| Mock — Submit | `mock_traffic_fine_pay_v1` | `submit` | mock | 2 | [submit/traffic_fine_pay.md](./submit/traffic_fine_pay.md) | [mock_traffic_fine_pay_v1.json](./schemas/mock_traffic_fine_pay_v1.json) |
| Mock — Submit | `mock_welfare_application_submit_v1` | `submit` | mock | 2 | [submit/welfare_application.md](./submit/welfare_application.md) | [mock_welfare_application_submit_v1.json](./schemas/mock_welfare_application_submit_v1.json) |
| Geocoding | `resolve_location` | `lookup` (meta) | live | 1 | [resolve_location/index.md](./resolve_location/index.md) | [resolve_location.json](./schemas/resolve_location.json) |

## Matrix B — adapters by primitive

### `lookup` (13 entries — 12 ministry adapters + `resolve_location` meta)

| tool_id | Source | Tier | Permission | Spec |
|---|---|---|---|---|
| `hira_hospital_search` | HIRA | live | 1 | [hira/hospital_search.md](./hira/hospital_search.md) |
| `kma_current_observation` | KMA | live | 1 | [kma/current_observation.md](./kma/current_observation.md) |
| `kma_forecast_fetch` | KMA | live | 1 | [kma/forecast_fetch.md](./kma/forecast_fetch.md) |
| `kma_pre_warning` | KMA | live | 1 | [kma/pre_warning.md](./kma/pre_warning.md) |
| `kma_short_term_forecast` | KMA | live | 1 | [kma/short_term_forecast.md](./kma/short_term_forecast.md) |
| `kma_ultra_short_term_forecast` | KMA | live | 1 | [kma/ultra_short_term_forecast.md](./kma/ultra_short_term_forecast.md) |
| `kma_weather_alert_status` | KMA | live | 1 | [kma/weather_alert_status.md](./kma/weather_alert_status.md) |
| `koroad_accident_hazard_search` | KOROAD | live | 1 | [koroad/accident_hazard_search.md](./koroad/accident_hazard_search.md) |
| `koroad_accident_search` | KOROAD | live | 1 | [koroad/accident_search.md](./koroad/accident_search.md) |
| `mohw_welfare_eligibility_search` | MOHW | live | 1 | [mohw/welfare_eligibility_search.md](./mohw/welfare_eligibility_search.md) |
| `nfa_emergency_info_service` | NFA119 | live | 1 | [nfa119/emergency_info_service.md](./nfa119/emergency_info_service.md) |
| `nmc_emergency_search` | NMC | live | 3 (gated) | [nmc/emergency_search.md](./nmc/emergency_search.md) |
| `resolve_location` | Geocoding (juso/sgis/kakao) | live (meta) | 1 | [resolve_location/index.md](./resolve_location/index.md) |

### `submit` (2 entries)

| tool_id | Source | Tier | Permission | Spec |
|---|---|---|---|---|
| `mock_traffic_fine_pay_v1` | data.go.kr (mock) | mock | 2 | [submit/traffic_fine_pay.md](./submit/traffic_fine_pay.md) |
| `mock_welfare_application_submit_v1` | KFTC MyData (mock) | mock | 2 | [submit/welfare_application.md](./submit/welfare_application.md) |

### `verify` (6 entries)

| tool_id | Family | Tier | Permission | Spec |
|---|---|---|---|---|
| `mock_verify_digital_onepass` | 디지털원패스 | mock | 2 | [verify/digital_onepass.md](./verify/digital_onepass.md) |
| `mock_verify_ganpyeon_injeung` | 간편인증 | mock | 2 | [verify/ganpyeon_injeung.md](./verify/ganpyeon_injeung.md) |
| `mock_verify_geumyung_injeungseo` | 금융인증서 | mock | 2 | [verify/geumyung_injeungseo.md](./verify/geumyung_injeungseo.md) |
| `mock_verify_gongdong_injeungseo` | 공동인증서 | mock | 3 | [verify/gongdong_injeungseo.md](./verify/gongdong_injeungseo.md) |
| `mock_verify_mobile_id` | 모바일 신분증 | mock | 2 | [verify/mobile_id.md](./verify/mobile_id.md) |
| `mock_verify_mydata` | 마이데이터 | mock | 2 | [verify/mydata.md](./verify/mydata.md) |

## Meta surface — `lookup`

The `lookup` meta-tool is the LLM's primary entry point for `lookup`-class operations. It accepts `mode` (`"search"` for BM25 retrieval, `"fetch"` for adapter invocation) plus `tool_id` + `params` and dispatches to the correct adapter under the hood. `lookup` itself has its own JSON Schema export at [`schemas/lookup.json`](./schemas/lookup.json) but is NOT a content-bearing adapter — it is the dispatch surface every adapter row above flows through.

For implementation details see [`src/kosmos/tools/lookup.py`](../../src/kosmos/tools/lookup.py) and the BM25 + dense hybrid retrieval backend under [`src/kosmos/tools/retrieval/`](../../src/kosmos/tools/retrieval/).

## Conventions

- **English source text only** in all spec files. Korean appears only inside the bilingual "Search hints" section and inside Korean conversation snippets within "Worked example" — per [`AGENTS.md § Hard rules`](../../AGENTS.md) and [`Spec 1637 FR-021`](../../specs/1637-p6-docs-smoke/spec.md).
- **Permission tier classification** follows [Spec 033 (Permission v2 Spectrum)](../../specs/033-permission-v2-spectrum/spec.md). Tier 1 is fail-open public data, Tier 2 requires AAL2 identity, Tier 3 requires AAL3 plus gate.
- **Mock public-spec citations** are mandatory: every Mock-tier adapter cites a public document, URL, or KISA/government standard per memory `feedback_mock_evidence_based`.
- **Fail-closed defaults** (Constitution Principle II) are inherited from the source Pydantic envelopes — see each adapter's "Constraints" section for the explicit fail-closed rendering.
- **No new runtime dependencies** were introduced for this catalog (Spec 1637 FR-022); `scripts/build_schemas.py` uses stdlib + Pydantic v2 only.

## Out of scope for this catalog

- External plugin adapters published under `kosmos-plugin-store/<repo>` carry their own `README.ko.md` per the Spec 1636 plugin DX. Their docs live in the plugin repo, not here.
- OPAQUE-tier mock stubs (`barocert/`, `npki_crypto/`, `omnione/` placeholder packages) have no entries here per the [Mock-vs-Scenario rule](../scenarios/README.md) — they belong in `docs/scenarios/`.
- Live API regression coverage is `@pytest.mark.live` skipped by default; this catalog documents fixture-replay behavior only.
