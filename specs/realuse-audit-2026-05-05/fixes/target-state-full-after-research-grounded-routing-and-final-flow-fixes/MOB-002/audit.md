# Real-Use Audit Report

- Root: `/Users/um-yunsang/KOSMOS/specs/realuse-audit-2026-05-05/fixes/target-state-full-after-research-grounded-routing-and-final-flow-fixes/MOB-002`
- Status: `pass`
- Files scanned: `258`
- Distinct sampled frames: `242`
- Tool calls observed: `8`

## Tool Calls

- `resolve_location` final-scrollback.txt:7 `부산 사하구 다대1동 → coords_and_admcd` — ⎿ 위치 해석 결과
- `lookup` final-scrollback.txt:11 `kma_forecast_fetch` — ⎿ timeseries — 24건
- `resolve_location` final-scrollback.txt:17 `부산 사하구 → coords_and_admcd` — ⎿ 위치 해석 결과
- `lookup` final-scrollback.txt:22 `koroad_accident_hazard_search` — ⎿ collection — 3건
- `resolve_location` final-scrollback.txt:28 `서울 강남구 → coords_and_admcd` — ⎿ 위치 해석 결과
- `lookup` final-scrollback.txt:33 `kma_forecast_fetch` — ⎿ timeseries — 24건
- `lookup` final-scrollback.txt:39 `koroad_accident_hazard_search` — ⎿ collection — 3건
- `subscribe` final-scrollback.txt:45 `mock_cbs_disaster_v1` — ⎿ 구독 완료: 59342023-3efe-4d9b-8c7f-4bd6cfbbd83f (subscribe) | 실시간 스트림은 대화창에서 별도 ⎿ 인용으로 전달됩니다.
