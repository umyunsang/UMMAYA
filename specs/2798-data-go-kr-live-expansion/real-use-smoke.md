# Real-Use Smoke: data.go.kr Live Expansion

Date: 2026-05-16
Command: `OTEL_SDK_DISABLED=true uv run ummaya`
Scope: Representative terminal prompts plus full 30-adapter registration, fixture, and retrieval checks.
Secret handling: no plaintext credentials are recorded here; HTTP error URLs must show `ServiceKey=***` or `serviceKey=***`.

## Automated Coverage

| Check | Command | Result |
|---|---|---|
| Focused backend tests | `uv run pytest tests/engine/test_engine.py tests/unit/tools/verified_data_go_kr/test_manifest.py tests/unit/tools/verified_data_go_kr/test_registration.py tests/unit/tools/verified_data_go_kr/test_fixture_replay.py tests/unit/tools/test_registry_count_breakdown.py -m "not live"` | `65 passed` |
| HTTP error redaction unit | `uv run pytest tests/unit/tools/verified_data_go_kr/test_client.py -q` | `1 passed` |
| Full verified-adapter retrieval sweep | Python `search(spec.search_hint, registry.bm25_index, registry, top_k=3)` across `VERIFIED_DATA_GO_KR_ADAPTERS` | 30/30 adapters appeared in top-3; 30/30 had no missing candidate |

## Terminal Prompt Results

| Prompt | Expected adapter | Observed primitive | Observed adapter | Result | Abnormal flow |
|---|---|---:|---|---|---|
| `종로구 자동심장충격기 위치 알려줘.` | `nmc_aed_site_locate` | `find` | `nmc_aed_site_locate` | Success; returned Jongno AED locations and operating hours. | Initial run looped through `locate`; fixed by not treating `q0`/`q1` string filters as prior-locate-only schema keys. |
| `타이레놀 효능과 복용 주의사항을 공식 자료로 알려줘.` | `mfds_easy_drug_info_lookup` | `find` | `mfds_easy_drug_info_lookup` | Success; returned official MFDS easy-drug efficacy and precautions. | None after registration. |
| `최근 과기정통부 AI 관련 사업공고 찾아줘.` | `msit_business_announcement_lookup` | `find` | `msit_business_announcement_lookup` | Success after restart; returned recent MSIT AI-related notices. | First upstream attempt reproduced 502 and exposed raw auth query in the exception string; fixed by sanitizing HTTP status errors before executor rendering. |
| `대전역에서 시청역까지 지하철 요금과 시간 알려줘.` | `djtc_subway_segment_fare_time_check` | `find` | `djtc_subway_segment_fare_time_check` | Success; returned distance, fare, and travel time. | None after registration. |
| `2025년 4월 장단기 체류외국인 수를 알려줘.` | `moj_stay_person_counter` | `find` | `moj_stay_person_counter` | Success after endpoint fix; returned three MOJ stay-person categories and total. | `https://` endpoint returned data.go.kr 502; direct curl proved `http://` succeeds with the same approved key and params, so the manifest endpoint was corrected. |

## Debug Fixes Proven During Smoke

### AED primitive selection

- Root cause: `src/ummaya/engine/engine.py` treated `q0` and `q1` as generic location-dependent schema keys.
- Impact: public-data requests whose selected adapter used `q0`/`q1` as official region string filters exposed `locate` in the same turn, so the LLM repeatedly tried Kakao keyword lookup instead of `find`.
- Fix: keep location-dependent gating to coordinate, grid, administrative-code, and region-code fields; remove `q0`/`q1` from that generic set.
- Regression: `tests/engine/test_engine.py::test_available_adapters_context_constrains_aed_region_filters_to_find`.

### HTTP error credential redaction

- Root cause: `httpx.Response.raise_for_status()` embeds the full request URL in `HTTPStatusError.__str__()`, including `serviceKey` or `ServiceKey`.
- Impact: an upstream 502 could leak the approved API key into terminal tool-error output and executor logs.
- Fix: `src/ummaya/tools/verified_data_go_kr/_client.py` raises a sanitized `HTTPStatusError` whose message uses the existing outbound-trace URL redactor.
- Regression: `tests/unit/tools/verified_data_go_kr/test_client.py::test_http_status_error_message_redacts_service_key`.

### MOJ stay-person endpoint scheme

- Root cause: manifest used `https://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter`; direct curl returned 502 `Error forwarding request to backend server`.
- Direct evidence: the same approved key and params against `http://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter` returned HTTP 200 with XML `resultCode=0`, `totalCount=3`, and `단기체류`, `장기체류거소`, `장기체류등록` rows.
- Fix: manifest endpoint switched to `http://` and the transport contract test now asserts the scheme.
- Regression: `tests/unit/tools/verified_data_go_kr/test_manifest.py::test_special_transport_contracts_are_manifested`.

## Remaining Exclusions

These APIs are intentionally not registered as live adapters in this PR:

| data.go.kr ID | Reason |
|---|---|
| `15038392` | Approved key recognized, but the operation returned service-access denial. |
| `15058923` | Approved and synthetic keys returned the same unregistered-key envelope. |
| `15063444` | Approved and synthetic keys returned the same unregistered-key envelope. |
