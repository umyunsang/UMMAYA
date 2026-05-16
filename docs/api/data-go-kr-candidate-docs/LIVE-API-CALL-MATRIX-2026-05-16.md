# Live API Call Matrix And UMMAYA Coverage Analysis - 2026-05-16

## Reference Bootstrap

- UMMAYA thesis/docs: `docs/vision.md` frames `data.go.kr` as one adapter family inside the broader national administrative AX surface. The active primitives are `find`, `locate`, `send`, and `check`.
- Tool-system requirements: `docs/requirements/ummaya-migration-tree.md` requires one callable agency module to become one registered tool, classified as Live, Mock, or scenario-only with adapter-level policy citations.
- Adapter/API sources: `docs/api/README.md`, `LIVE-PROBE-RESULTS-2026-05-16.md`, `P0-P1-WRAPPING-NOTES.md`, `P2-WRAPPING-NOTES.md`, `SCOPED-ADDITIONAL-30-2026-05-16.md`, per-candidate `usage-notes-2026-05-16*.md`, inline Swagger files, and downloaded official guides.
- External primary sources: official `data.go.kr` pages and provider guide artifacts already saved under each candidate folder.
- Probe method: direct local `curl` calls with real parameters and local env-secret injection. Header/body artifacts are saved under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16-direct-check/`. Secrets were redacted after capture; `remaining_secret_occurrences=0`.
- Blocker-resolution probe method: the original five blockers were re-tested against the official DOCX/Swagger parameter names and saved under `docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16-blocker-resolution/`. See `LIVE-API-BLOCKER-RESOLUTION-2026-05-16.md`.
- Implementation constraint: this document is an evidence and analysis artifact only. It does not authorize adapter implementation without the active Spec Kit workflow and fixture-safe tests.

## Executive Result

Direct probes covered 33 API candidates that had either prior successful evidence or local application/usage notes from the approved-use batch. Result:

- **30 callable now**: approved-use credential path, endpoint, parameters, and success/zero-result response shape are proven.
- **3 approved-batch key/service mapping blockers**: these are not treated as "unapproved"; direct control probes show that the current key is not accepted by the provider/service backend for these specific services yet.
- **Probe scope**: only each API's documented 조회/fetch operation was invoked.

The callable set is strongest for **approved public-service data lookup and status checks**: safety locations, medical/facility information, drug information, transit facts, public jobs, SME support notices, air quality, marine water quality, funeral fees, university finance/student statistics, public procurement, and public finance/market terminology. The analysis below therefore focuses on which citizen or evaluator questions these approved APIs can answer, what resolver steps are needed, and which response shapes should become adapter fixtures.

## Probe Matrix

| ID | API / candidate adapter | Probe parameters used | Observed response | UMMAYA status |
|---|---|---|---|---|
| `15043459` | FSC corporate finance summary / `fsc_corporate_finance_summary` | `crno=1746110000741`, `bizYear=2019`, `resultType=json` | HTTP 200 JSON, `resultCode=00`, `totalCount=2` | Callable `find` |
| `15073861` | AirKorea city/province air quality / `airkorea_ctprvn_air_quality` | `sidoName=서울`, `returnType=json`, `ver=1.0` | HTTP 200 JSON, `resultCode=00`, `totalCount=40` | Callable `find` / status check |
| `15091886` | FTC large corporate group status / `ftc_large_group_status` | `presentnYear=202105` | HTTP 200 XML, `resultCode=00`, `totalCount=71` | Callable `find` |
| `15091910` | FTC public year-month list / `ftc_public_ym_list` | `jobSeCode=0001`, `presentnYear=2021` | HTTP 200 XML, `resultCode=00`, `totalCount=1` | Callable helper `find` |
| `15098529` | TAGO bus route search / `tago_bus_route_search` | `cityCode=25`, `routeNo=5` | HTTP 200 XML, `resultCode=00`, `totalCount=17` | Callable `find` |
| `15098530` | TAGO bus arrival / `tago_bus_arrival_search` | `cityCode=25`, `nodeId=DJB8001793` | HTTP 200 XML, `resultCode=00`, `totalCount=4` | Callable `check`-like `find` |
| `15098533` | TAGO bus location / `tago_bus_location_search` | `cityCode=25`, `routeId=DJB30300052` | HTTP 200 XML, `resultCode=00`, `totalCount=5` | Callable `check`-like `find` |
| `15098534` | TAGO bus station / `tago_bus_station_search` | `cityCode=25`, `nodeNm=전통시장`, `nodeNo=44810` | HTTP 200 XML, `resultCode=00`, `totalCount=1` | Callable `locate`-adjacent `find` |
| `15101360` | KEPCO contract-type power usage / `kepco_contract_power_usage` | `year=2020`, `month=11`, `metroCd=11`, `cityCd=110`, `cntrCd=100`, provider `apiKey` | HTTP 200 JSON data rows | Callable `find`; provider-key, not data.go.kr key |
| `15129394` | PPS bid notice / `pps_bid_public_info` | `inqryDiv=2`, `bidNtceNo=R25BK00934017`, `type=json` | HTTP 200 JSON, `resultCode=00`, `totalCount=1` | Callable `find` |
| `15134761` | REB real-estate statistics table / `reb_real_estate_stat_table` | `Type=json`, `pIndex=1`, `pSize=5`, provider `KEY` | HTTP 200 JSON, `INFO-000`, list count `738` | Callable `find`; provider-key |
| `15157485` | Busan funeral area fee / `bfc_funeral_area_fee` | `resultType=json`, `pageNo=1`, `numOfRows=5` | HTTP 200 JSON, `resultCode=00`, `totalCount=4` | Callable `find` |
| `15158680` | KCUE regional tuition finance / `kcue_finance_regional_tuition` | `schlDivCd=02` | HTTP 200 XML, `resultCode=00`, `totalCount=20` | Callable `find` |
| `15158684` | KCUE regional foreign students / `kcue_student_regional_foreign` | `schlDivCd=02` | HTTP 200 XML, `resultCode=00`, `totalCount=20` | Callable `find` |
| `15121954` | MOJ village lawyer lookup / `moj_village_lawyer_lookup` | `pageNo=1`, `numOfRows=5`; HTTPS gateway failed, HTTP gateway succeeded | HTTPS HTTP 502; HTTP 200 XML, `resultCode=0`, `totalCount=3008` | Callable only via `http://apis.data.go.kr/...`; adapter must pin scheme evidence |
| `15073554` | MOIS facility safety integrated search / `mois_facility_safety_info_lookup` | `resultType=json`, `fclts_nm=호텔` | HTTP 200 JSON, `resultCode=00`, `totalCount=43909` | Callable `find`; two-step detail lookup needed |
| `15001699` | HIRA medical institution detail / `hira_medical_institution_detail` | `getDtlInfo2.7`, `_type=json`, known encrypted `ykiho` | HTTP 200 JSON, `resultCode=00`, `totalCount=1` | Callable follow-up adapter after `hira_hospital_search` |
| `15155046` | MOIS emergency call box / `mois_emergency_call_box_lookup` | `returnType=json`, road-address LIKE `서울` | HTTP 200 JSON, `resultCode=0`, `totalCount=20772` | Callable `locate` + `find` |
| `15158794` | Daejeon metro time/distance/fare / `djtc_subway_segment_fare_time_check` | `strstnno=104`, `endstnno=111` | HTTP 200 XML, `resultCode=00`, distance/fare/time returned | Callable `check`; needs station-name resolver |
| `15096040` | Gyeryong assistive-device charger / `gyeryong_assistive_device_charging_place_locate` | `currentPage=1`, `perPage=5`, `INDOOR_OTDR=실내` | HTTP 200 JSON, `resultCode=00`, `totalRows=7` | Callable `locate` |
| `15000652` | NMC national AED locations / `nmc_aed_site_locate` | `Q0=서울특별시`, `Q1=종로구` | HTTP 200 XML, `resultCode=00`, `totalCount=486` | Callable high-priority `locate` |
| `15127779` | MOF realtime marine water quality / `mof_ocean_water_quality_check` | `rtm_wq_wtch_sta_cd=SEA3003`, `_type=xml` | HTTP 200 XML, `resultCode=00`, `totalCount=294857` | Callable `check`; station resolver needed |
| `15075057` | MFDS eYak easy drug info / `mfds_easy_drug_info_lookup` | `itemName=타이레놀`, `type=json` | HTTP 200 JSON, `resultCode=00`, `totalCount=7` | Callable high-priority `find` with medical safety caveat |
| `15156780` | MPM public job notices / `mpm_public_job_lookup` | `Pblanc_ty=e01`, `Instt_se=g01`, `Sort_order=내림차순` | HTTP 200 XML, `resultCode=00`, `totalCount=57001`; `g03` control produced valid zero-result | Callable `find`; enum mapping required |
| `15129471` | PPS shopping mall product/procurement info / `pps_shopping_mall_product_lookup` | `getShoppingMallPrdctInfoList`, `inqryDiv=1`, `prdctClsfcNoNm=의자`, `type=json` | HTTP 200 JSON, `resultCode=00`, `totalCount=4050` | Callable `find`; procurement only, no purchase/submit |
| `15158905` | KSD financial term dictionary / `ksd_financial_term_lookup` | `term=주식` | HTTP 200 XML, `resultCode=00`, `totalCount=26` | Callable `find`; non-commercial license caveat |
| `15157820` | MSS SME support announcements / `mss_sme_support_notice_lookup` | `dataType=json`, `hashtags=소상공인` | HTTP 200 JSON, `resultCode=00`, `totalCount=189` | Callable high-priority `find` |
| `15140950` | Constitutional Court publication documents / `ccourt_publication_documents` | `getSerialPublicationList`, `type=json`, `title=헌법` | HTTP 200 JSON, `resultCode=0`, `totalCount=5` | Callable `find` |
| `15038392` | Legacy AcademyInfo finance endpoint / `kcue_academyinfo_finance_lookup` | `schlId=0000149`, `svyYr=2018`, both `ServiceKey` and `serviceKey` tested | HTTP 200 XML, `resultCode=99`, `SERVICE ACCESS DENIED ERROR` | Hold wrapping until the approved-key/service mapping is confirmed; newer `15158680` is callable |
| `15063444` | Uiryeong civil defense shelters / `data_go_kr_uiryeong_civil_defense_shelters` | Provider HTTPS endpoint with `ServiceKey`; browser-like headers and both key casings tested | HTTP 200 XML envelope, `resultCode=99`, `등록되지 않은 서비스키입니다`; fake-key control returns the same provider error | Hold wrapping until the approved-key/service mapping is confirmed |
| `15058923` | EKAPE animal trace / `ekape_animal_trace_lookup` | `traceNo=L01709271277007`, `optionNo=9`, `corpNo=1178522046`; both key casings tested | HTTP 200 XML, `resultCode=99`, `SERVICE KEY IS NOT REGISTERED ERROR` | Hold wrapping until the approved-key/service mapping is confirmed |
| `15149906` | MOJ stay-person counter / `moj_stay_person_counter` | `ServiceKey` uppercase, `pageNo=1`, `numOfRows=5`, `searchYm=202504` | HTTP 200 XML, `resultCode=0`, `resultMsg=Success`, `totalCount=3` | Callable `find`; Swagger says `serviceKey`, but live gateway requires `ServiceKey` |
| `15074634` | MSIT business announcements / `msit_business_announcement_lookup` | `serviceKey`, `numOfRows=10`, `pageNo=1`, `returnType=xml`, browser-like `User-Agent` | HTTP 200 XML, `resultCode=00`, live 2026 business-announcement items returned | Callable `find`; default curl UA is blocked |

## User And Query Coverage

### High-Value Citizen Workflows

| User | Natural-language query UMMAYA can now support | Adapter chain | Boundary |
|---|---|---|---|
| Patient, caregiver, emergency helper | `종로구 자동심장충격기 위치랑 건물 안 어디 있는지 알려줘.` | `locate` -> `nmc_aed_site_locate` | Official AED location data, not emergency dispatch or CPR instruction. |
| Parent, night commuter, local resident | `아이 통학길 주변 경찰 연계 비상벨 위치 알려줘.` | `locate` -> `mois_emergency_call_box_lookup` | Can show recorded emergency-bell metadata; not real-time operational guarantee. |
| Patient choosing a hospital | `이 병원 응급실이 밤에도 운영되는지, 주차 정보가 있는지 봐줘.` | `hira_hospital_search` -> `hira_medical_institution_detail` | Requires official encrypted `ykiho`; no patient record access. |
| Medication user | `타이레놀 효능, 복용법, 주의사항을 공식 자료로 알려줘.` | `mfds_easy_drug_info_lookup` | Information only; no diagnosis, prescription, or emergency triage. |
| Small-business owner | `소상공인 지원사업 중 지금 신청 가능한 공고 찾아줘.` | `mss_sme_support_notice_lookup` | Can list notice, period, target, application URL; eligibility finality stays with official notice. |
| Job seeker | `이번 주 마감하는 국가공무원 채용 공고 찾아줘.` | `mpm_public_job_lookup` | Can search/list/detail public-job notices; no application submission. |
| Mobility-impaired visitor in Gyeryong | `계룡시에 실내 전동휠체어 충전 장소 알려줘.` | `gyeryong_assistive_device_charging_place_locate` | Local-only dataset; no national coverage yet. |
| Transit rider in Daejeon | `대전역에서 시청역까지 지하철 요금과 시간 알려줘.` | station-code resolver -> `djtc_subway_segment_fare_time_check` | API accepts station numbers, so adapter must ship a station-name resolver. |
| Bus rider in supported cities | `대전 5번 버스 노선이랑 도착 예정 정보 알려줘.` | `tago_bus_route_search` -> station/arrival/location adapters | City and station/route IDs must be resolved; real-time quality depends on TAGO feed. |
| Family arranging funeral | `부산시설공단 장례식장 이용료가 지역 주민이면 얼마야?` | `bfc_funeral_area_fee` | Fee lookup only; no reservation or payment. |
| Rural/small-city resident needing legal help | `우리 동네 마을변호사와 담당 공무원 찾아줘.` | `locate` -> `moj_village_lawyer_lookup` | HTTP endpoint works; adapter must cite scheme-specific evidence and avoid legal advice. |

### Policy, Research, And Public-Transparency Workflows

| User | Query UMMAYA can answer | Adapter(s) | Fit |
|---|---|---|---|
| Student, parent, school counselor | `전문대 등록금 지역별 현황 비교해줘.` | `kcue_finance_regional_tuition` | Good education-decision support. |
| University evaluator | `외국인 학생 현황을 지역별로 확인해줘.` | `kcue_student_regional_foreign` | Useful evaluator/research adapter. |
| Housing or real-estate analyst | `한국부동산원 통계표 목록에서 아파트 관련 통계를 찾아줘.` | `reb_real_estate_stat_table` | Public stats discovery; follow-up data endpoint still needed for full analysis. |
| Procurement analyst, civic watchdog | `공공기관 의자 조달 내역과 공급업체를 찾아줘.` | `pps_shopping_mall_product_lookup`, `pps_bid_public_info` | Strong transparency use; no purchasing or bid submission. |
| Investor, journalist, market educator | `대량주식 보유상황 공시제도 뜻을 공식 용어로 설명해줘.` | `ksd_financial_term_lookup` | Good helper adapter; watch non-commercial license. |
| Corporate analyst | `이 법인의 2019년 재무요약을 조회해줘.` | `fsc_corporate_finance_summary` | Uses corporate registration number; not consumer credit or personal finance. |
| Environment watcher | `서울 미세먼지 측정소별 현재 수치를 알려줘.` | `airkorea_ctprvn_air_quality` | High everyday value. |
| Coastal resident, fishery worker | `부산 수영 관측소 해양수질 최근 pH랑 용존산소 확인해줘.` | station resolver -> `mof_ocean_water_quality_check` | Official readings, not health/safety certification. |
| Constitutional-law researcher | `헌법재판소 발간자료 중 헌법 관련 자료 찾아줘.` | `ccourt_publication_documents` | Research/reference use, not legal advice. |
| Immigration/public-policy analyst | `2025년 4월 장단기 체류외국인 수를 구분별로 알려줘.` | `moj_stay_person_counter` | Official aggregate statistics only; not personal immigration records. |
| Research office, university lab, R&D company | `최근 과기정통부 AI 관련 사업공고와 첨부파일 링크 찾아줘.` | `msit_business_announcement_lookup` | Notice discovery only; no application submission. |

## Adapter Priority Recommendation

### P0 - Implement First

These directly answer frequent or high-consequence citizen queries and have clean live evidence:

1. `nmc_aed_site_locate` (`15000652`) - emergency-location infrastructure.
2. `mfds_easy_drug_info_lookup` (`15075057`) - high-frequency medication questions with safety caveats.
3. `hira_medical_institution_detail` (`15001699`) - natural follow-up to existing hospital search.
4. `mois_emergency_call_box_lookup` (`15155046`) - citizen safety-location workflow.
5. `mss_sme_support_notice_lookup` (`15157820`) - actionable application-notice discovery.
6. `mpm_public_job_lookup` (`15156780`) - public employment discovery.
7. `msit_business_announcement_lookup` (`15074634`) - R&D and science/technology support-opportunity discovery.
8. TAGO bus route/arrival/location/station family (`15098529`, `15098530`, `15098533`, `15098534`) - practical transport workflow.

### P1 - Implement After Resolver/Normalization Work

These are useful but need local code tables, resolver steps, or stronger boundary wording:

1. `djtc_subway_segment_fare_time_check` (`15158794`) - needs official station-name-to-number mapping.
2. `mof_ocean_water_quality_check` (`15127779`) - needs station-name/place resolver.
3. `gyeryong_assistive_device_charging_place_locate` (`15096040`) - local-only but accessibility-relevant.
4. `moj_village_lawyer_lookup` (`15121954`) - works only through HTTP gateway in current probe.
5. `mois_facility_safety_info_lookup` (`15073554`) - two-step facility search/detail model.
6. `bfc_funeral_area_fee` (`15157485`) - useful family-cost decision support.

### P2 - Implement As Public-Transparency / Evaluator Tools

These are valid live APIs but less central to everyday citizen administrative execution:

- `fsc_corporate_finance_summary`, `ftc_large_group_status`, `ftc_public_ym_list`, `pps_bid_public_info`, `pps_shopping_mall_product_lookup`, `reb_real_estate_stat_table`, `ksd_financial_term_lookup`, `kcue_finance_regional_tuition`, `kcue_student_regional_foreign`, `kepco_contract_power_usage`, `ccourt_publication_documents`, `moj_stay_person_counter`.

### Hold Until Probe Blocker Is Resolved

- `15038392` legacy AcademyInfo finance: the current approved key is recognized as a real key but returns `SERVICE ACCESS DENIED ERROR` for both the target finance operation and BasicInformationService control operations; use callable `15158680` for this batch unless the portal/provider confirms the legacy service mapping.
- `15058923` EKAPE animal trace: official DOCX sample calls with both `serviceKey` and `ServiceKey` return the same `SERVICE KEY IS NOT REGISTERED ERROR` as a fake-key control; confirm approved-key/service mapping before adapter registration.
- `15063444` Uiryeong civil-defense shelter: official endpoint is reachable after HTTPS redirect and browser-like headers, but the provider returns the same `등록되지 않은 서비스키입니다` envelope as a fake-key control; confirm approved-key/service mapping before adapter registration.

## UMMAYA System Implications

1. **The current live expansion should follow the approved API operation shape.** Every callable probe above maps naturally to `find`, `locate`, or `check` because the approved operations themselves are lookup/status endpoints.
2. **Several adapters need resolver sub-steps.** Daejeon metro requires station codes, ocean water quality requires station codes, HIRA detail requires `ykiho`, TAGO workflows require city/route/node IDs, and emergency-call-box ranking needs location normalization.
3. **Zero-result is not failure.** Public-job `g03` returned a valid normal zero-result, then `g01` returned data. Adapter tests must preserve both.
4. **Provider-key APIs must remain separate.** KEPCO and REB worked with provider-issued keys, not the shared data.go.kr key.
5. **HTTP/header behavior must be captured per adapter.** MOJ village lawyer succeeds over `http://apis.data.go.kr/...` while the HTTPS gateway returns 502. MSIT business announcements require a browser-like `User-Agent` even though the official guide uses a plain HTTP callback URL. Do not normalize schemes or headers without evidence.
6. **National AX coverage improves in the exact domains represented by the approved batch.** This wave materially improves public-service discovery, location lookup, official notice retrieval, and status/fact checks. Coverage claims should be phrased API-by-API rather than generalized into unrelated transaction domains.
