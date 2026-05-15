# Verified data.go.kr Adapter Wave

Feature: `specs/2797-data-go-kr-verified-adapters`
Epic: #2797

This catalog page covers the first direct-curl verified public-data wave. Every
adapter below is a live, read-only `find` adapter backed by a saved successful
probe under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16/`.
The thirty newly scoped candidates in `SCOPED-NEW-30-manifest.json` are not
included because they were still inside the post-application authorization
window when this wave was implemented.

## Included Adapters

| data.go.kr ID | tool_id | Source | Primitive | Env var | Evidence |
|---|---|---|---|---|---|
| `15043459` | `fsc_corporate_finance_summary` | 금융위원회 기업 재무정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15043459/probes/live-2026-05-16/corporate-finance-summary.body.json` |
| `15073861` | `airkorea_ctprvn_air_quality` | AirKorea 대기오염정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15073861/probes/live-2026-05-16/airkorea-ctprvn.body.json` |
| `15091886` | `ftc_large_group_status` | 공정위 대규모기업집단 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15091886/probes/live-2026-05-16/ftc-large-group.body.xml` |
| `15091910` | `ftc_public_ym_list` | 공정위 사용 가능 공개년월 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15091910/probes/live-2026-05-16/ftc-public-ym.body.xml` |
| `15098529` | `tago_bus_route_search` | TAGO 버스노선정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098529/probes/live-2026-05-16/tago-bus-route.body.xml` |
| `15098530` | `tago_bus_arrival_search` | TAGO 버스도착정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098530/probes/live-2026-05-16/tago-bus-arrival.body.xml` |
| `15098533` | `tago_bus_location_search` | TAGO 버스위치정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098533/probes/live-2026-05-16/tago-bus-location.body.xml` |
| `15098534` | `tago_bus_station_search` | TAGO 버스정류소정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15098534/probes/live-2026-05-16/tago-bus-station.body.xml` |
| `15101360` | `kepco_contract_power_usage` | 한국전력 계약종별 전력사용량 | `find` | `UMMAYA_KEPCO_POWER_DATA_API_KEY` | `15101360/probes/live-2026-05-16/kepco-contract-type.body.json` |
| `15129394` | `pps_bid_public_info` | 조달청 나라장터 입찰공고정보 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15129394/probes/live-2026-05-16/pps-bid-service.body.json` |
| `15134761` | `reb_real_estate_stat_table` | 한국부동산원 부동산통계 | `find` | `UMMAYA_REB_REAL_ESTATE_STATS_API_KEY` | `15134761/probes/live-2026-05-16/reb-stat-table.body.json` |
| `15157485` | `bfc_funeral_area_fee` | 부산시설공단 장례비산출 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15157485/probes/live-2026-05-16/funeral-area-list.body.json` |
| `15158680` | `kcue_finance_regional_tuition` | 대학알리미 재정 현황 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158680/probes/live-2026-05-16/finance-regional-tuition.body.xml` |
| `15158684` | `kcue_student_regional_foreign` | 대학정보공시 학생 현황 | `find` | `UMMAYA_DATA_GO_KR_API_KEY` | `15158684/probes/live-2026-05-16/student-regional-foreign.body.xml` |

## Excluded From This Wave

| Candidate set | Status | Handling |
|---|---|---|
| `SCOPED-NEW-30-manifest.json` | Applied less than two hours before implementation; service-key authorization unavailable. | Excluded from manifest and tests. Re-probe after authorization. |
| `15081808` NTS business status | Endpoint contract known, approved-key probes still returned upstream `-5`. | Deferred as a future `check` adapter. |
| `15000032` EMS submit/cancel | Real submit/cancel behavior with no sandbox evidence. | Deferred as a future `send` candidate; no live call. |
| `15149906` MOJ stay-person counter | Gateway/backend returned 502 or redirect loop during direct curl. | Deferred until callable evidence exists. |
| `15074634` MSIT announcement | Official endpoint returned gateway block responses. | Deferred until a working official sample is found. |

## Runtime Contract

- All adapters register as `GovAPITool` with `primitive="find"` and
  `adapter_mode="live"`.
- Default tests use fixture replay only; no live public API call is made in CI.
- Direct runtime calls require the listed environment variables and route through
  `ToolExecutor.invoke()` or the `find` meta-tool.
- Parser output is normalized to `{"kind": "collection", "items": [...],
  "total_count": N}` so it passes the existing `LookupCollection` envelope.
