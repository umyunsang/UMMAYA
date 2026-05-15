# Real-Use Smoke: data.go.kr Verified Adapter Wave

Date: 2026-05-16 KST
Mode: `UMMAYA_LIVE_ADAPTER_MODE=direct`
Entrypoint smoke: `uv run ummaya --version` returned `ummaya 0.1.9`.

Secrets were loaded from local `.env` and were not printed. Required env vars
were present:

- `UMMAYA_DATA_GO_KR_API_KEY`
- `UMMAYA_KEPCO_POWER_DATA_API_KEY`
- `UMMAYA_REB_REAL_ESTATE_STATS_API_KEY`

## Direct Adapter Calls

All fourteen read-only live adapters were invoked through `ToolExecutor.invoke()`
after `register_all_tools()` populated the UMMAYA registry.

| tool_id | Result |
|---|---|
| `fsc_corporate_finance_summary` | `collection`, `items=1`, `total_count=2` |
| `airkorea_ctprvn_air_quality` | `collection`, `items=5`, `total_count=40` |
| `ftc_large_group_status` | `collection`, `items=10`, `total_count=71` |
| `ftc_public_ym_list` | `collection`, `items=1`, `total_count=1` |
| `tago_bus_route_search` | `collection`, `items=10`, `total_count=17` |
| `tago_bus_arrival_search` | `collection`, `items=0`, `total_count=0` |
| `tago_bus_location_search` | `collection`, `items=0`, `total_count=0` |
| `tago_bus_station_search` | `collection`, `items=1`, `total_count=1` |
| `kepco_contract_power_usage` | `collection`, `items=1`, `total_count=1` |
| `pps_bid_public_info` | `collection`, `items=1`, `total_count=1` |
| `reb_real_estate_stat_table` | `collection`, `items=5`, `total_count=738` |
| `bfc_funeral_area_fee` | `collection`, `items=4`, `total_count=4` |
| `kcue_finance_regional_tuition` | `collection`, `items=5`, `total_count=20` |
| `kcue_student_regional_foreign` | `collection`, `items=5`, `total_count=20` |

The two TAGO zero-result calls matched the live-probe evidence shape and are
normal successful empty collections, not errors.

## Primitive Path

The LLM-facing primitive path was exercised through `lookup()`:

1. `find(mode="search", query="부산 장례식장 시설사용료", top_k=5)` returned
   `bfc_funeral_area_fee` as the top candidate.
2. `find(mode="fetch", tool_id="bfc_funeral_area_fee", params={...})` returned
   `LookupCollection(source="bfc_funeral_area_fee", items=4, total_count=4)`.

No adapter returned `LookupError`, no schema normalization error occurred, and
no permission gate blocked the read-only flows.
