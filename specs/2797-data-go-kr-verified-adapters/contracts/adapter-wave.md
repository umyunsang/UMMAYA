# Contract: Verified Adapter Wave

## Scope

This contract defines the adapter registration requirements for the first data.go.kr verified API wave.

## Included Tool IDs

| Tool ID | Source ID | Primitive | Credential Family | Evidence Body |
|---------|-----------|-----------|-------------------|---------------|
| `fsc_corporate_finance_summary` | `15043459` | `find` | `data_go_kr_service_key` | `corporate-finance-summary.body.json` |
| `airkorea_ctprvn_air_quality` | `15073861` | `find` | `data_go_kr_service_key` | `airkorea-ctprvn.body.json` |
| `ftc_large_group_status` | `15091886` | `find` | `data_go_kr_service_key` | `ftc-large-group.body.xml` |
| `ftc_public_ym_list` | `15091910` | `find` | `data_go_kr_service_key` | `ftc-public-ym.body.xml` |
| `tago_bus_route_search` | `15098529` | `find` | `data_go_kr_service_key` | `tago-bus-route.body.xml` |
| `tago_bus_arrival_search` | `15098530` | `find` | `data_go_kr_service_key` | `tago-bus-arrival.body.xml` |
| `tago_bus_location_search` | `15098533` | `find` | `data_go_kr_service_key` | `tago-bus-location.body.xml` |
| `tago_bus_station_search` | `15098534` | `find` | `data_go_kr_service_key` | `tago-bus-station.body.xml` |
| `kepco_contract_power_usage` | `15101360` | `find` | `kepco_power_data_key` | `kepco-contract-type.body.json` |
| `pps_bid_public_info` | `15129394` | `find` | `data_go_kr_service_key` | `pps-bid-service.body.json` |
| `reb_real_estate_stat_table` | `15134761` | `find` | `reb_r_one_key` | `reb-stat-table.body.json` |
| `bfc_funeral_area_fee` | `15157485` | `find` | `data_go_kr_service_key` | `funeral-area-list.body.json` |
| `kcue_finance_regional_tuition` | `15158680` | `find` | `data_go_kr_service_key` | `finance-regional-tuition.body.xml` |
| `kcue_student_regional_foreign` | `15158684` | `find` | `data_go_kr_service_key` | `student-regional-foreign.body.xml` |

## Registration Requirements

Each included adapter MUST:

- Register a distinct `GovAPITool` with `primitive="find"`.
- Use `adapter_mode="live"`.
- Use `auth_type="api_key"`.
- Use a Pydantic v2 input schema with `extra="forbid"`.
- Use a Pydantic v2 output schema that does not contain `Any`.
- Provide bilingual `search_hint` text.
- Provide `trigger_examples` with citizen-facing Korean examples.
- Provide an `AdapterRealDomainPolicy` citation with `citizen_facing_gate="read-only"`.
- Bind an async executor adapter in `register(registry, executor)`.

## Exclusion Requirements

The implementation MUST NOT:

- Register any tool ID from `SCOPED-NEW-30-manifest.json`.
- Register any `Reachable But Not Yet Callable` API as a live adapter.
- Register any `Not Live-Probed` API as a live adapter.
- Add a new root primitive.
- Add a side-effecting `send` adapter in this wave.
- Add a `check` adapter in this wave.

## Registry Smoke Contract

After `register_all_tools(registry, executor)`:

- All 14 included tool IDs are present in the registry.
- All 14 included tool IDs are present in `executor._adapters`.
- Each included adapter has `primitive == "find"`.
- No included adapter is `is_core=True`.
- `lookup/search` can surface a representative included adapter from its Korean citizen query terms.
