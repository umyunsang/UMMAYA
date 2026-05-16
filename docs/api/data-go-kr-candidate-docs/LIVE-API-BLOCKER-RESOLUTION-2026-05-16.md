# Live API Blocker Resolution - 2026-05-16

## Purpose

This note resolves the five blockers from `LIVE-API-CALL-MATRIX-2026-05-16.md` by checking the saved official DOCX/Swagger specifications, re-sending direct `curl` calls with spec-matched parameters, and comparing each response against a fake-key control where key mapping was ambiguous.

Artifacts:

- Probe summary: `_probe-summaries/live-2026-05-16-blocker-resolution/summary.tsv`
- Per-API headers and bodies: `<candidate-id>/probes/live-2026-05-16-blocker-resolution/`

No secret values are stored in the artifacts. `ServiceKey` values in headers/bodies are redacted to `${UMMAYA_DATA_GO_KR_API_KEY}`.

## Resolution Summary

| ID | Result | Root Cause | Correct Adapter Handling |
|---|---|---|---|
| `15149906` | Resolved, callable | Inline Swagger lists `serviceKey`, but the live data.go.kr gateway succeeds only with uppercase `ServiceKey`; the HTTPS gateway can still return provider 502, while HTTP succeeds. | Use `http://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter` with uppercase `ServiceKey`. |
| `15074634` | Resolved, callable | The official guide URL is correct, but the provider/gateway blocks default curl-style requests. Browser-like `User-Agent` returns normal XML. | Use `serviceKey`, `numOfRows=10`, `pageNo`, `returnType`, and a non-empty browser-like `User-Agent`. |
| `15038392` | Not locally fixable by parameter change | The approved key is recognized as a real key, but service access is denied across the finance target and BasicInformationService controls. Fake key returns a different unregistered-key error. | Do not register this legacy adapter until data.go.kr/provider service mapping is corrected. Use callable newer KCUE paths such as `15158680` for this batch. |
| `15058923` | Not locally fixable by parameter change | Official DOCX sample calls, both key casings, multiple trace-number samples, and fake-key control all return the same unregistered-key error. | Do not register live until the approved key is visible to the EKAPE provider backend. |
| `15063444` | Not locally fixable by parameter change | The official provider endpoint is reachable after HTTPS redirect and browser-like headers, but the provider returns the same unregistered-key envelope as a fake-key control. | Do not register live until the approved key is visible to the Uiryeong provider backend. |

## Per-API Findings

### `15149906` - MOJ Stay-Person Counter

Official inline Swagger says:

- host: `apis.data.go.kr/1270000/stay_person_counter`
- path: `/getstaypersoncounter`
- parameters: `serviceKey`, `pageNo`, `numOfRows`, optional `startYm`, `endYm`, `searchYm`, `eNum`
- provider operation URL: `https://www.moj.go.kr/purchasesgoodsApi/stay_person_counter`

The initial failing calls used lowercase `serviceKey` and returned `HTTP 502 Error forwarding request to backend server`. Terminal smoke later reproduced the same provider 502 on the HTTPS gateway even with uppercase `ServiceKey`. A direct `curl` re-probe with the same approved key and parameters against the HTTP gateway returned:

```text
HTTP 200
resultCode=0
resultMsg=Success
totalCount=3
items: 단기체류, 장기체류거소, 장기체류등록
```

Correct live request shape:

```text
GET http://apis.data.go.kr/1270000/stay_person_counter/getstaypersoncounter
  ?ServiceKey=${UMMAYA_DATA_GO_KR_API_KEY}
  &pageNo=1
  &numOfRows=5
  &searchYm=202504
```

Adapter implication: use uppercase `ServiceKey` despite the Swagger parameter table, and pin the data.go.kr gateway to `http://` for this operation. Treat provider-direct `https://www.moj.go.kr/...` as non-canonical for the adapter because it loops through `307` redirects in local probes.

### `15074634` - MSIT Business Announcements

Official guide says:

- service URL: `http://apis.data.go.kr/1721000/msitannouncementinfo`
- operation: `businessAnnouncMentList`
- required parameters: `serviceKey`, `numOfRows`, `pageNo`
- optional parameter: `returnType`, with `xml` default and `json` supported
- sample URL: `http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList?serviceKey=...&numOfRows=10&pageNo=1&returnType=xml`

The failing call was not a key or parameter failure. Default curl-style requests returned `HTTP 400 Request Blocked`. The same URL with a browser-like `User-Agent` returned:

```text
HTTP 200
resultCode=00
resultMsg=NORMAL_CODE
first item subject=2026년도 제2차 과학기술분야 연구기획과제 재공모
```

Correct live request shape:

```text
GET http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList
  ?serviceKey=${UMMAYA_DATA_GO_KR_API_KEY}
  &numOfRows=10
  &pageNo=1
  &returnType=xml
User-Agent: Mozilla/5.0 UMMAYA-live-probe/2026-05-16
Accept: application/xml,text/xml,*/*
```

Adapter implication: configure a stable `User-Agent` in the adapter HTTP client. Do not switch to uppercase `ServiceKey`; that path returned gateway forwarding failure.

### `15038392` - Legacy AcademyInfo Finance

Official portal and guide agree on the legacy provider URL family:

- service URL: `http://openapi.academyinfo.go.kr/openapi/service/rest/FinancesService/getComparisonTuitionCrntSt`
- required parameters: `serviceKey` or `ServiceKey`, `svyYr`, `schlId`
- useful control service: `BasicInformationService/getNoticeSvyYear` and `BasicInformationService/getUniversityCode`

Re-probes:

```text
real key + FinancesService/getComparisonTuitionCrntSt -> SERVICE ACCESS DENIED ERROR
real key + BasicInformationService/getNoticeSvyYear -> SERVICE ACCESS DENIED ERROR
real key + BasicInformationService/getUniversityCode -> SERVICE ACCESS DENIED ERROR
fake key + FinancesService/getComparisonTuitionCrntSt -> SERVICE KEY IS NOT REGISTERED ERROR
```

Root cause: this is not a malformed parameter, key casing, endpoint, or URL-encoding issue. The provider distinguishes the current approved key from a fake key, but denies service access for the legacy AcademyInfo service family.

Adapter implication: keep `15038392` out of live registration until the portal/provider mapping is corrected. For UMMAYA education-finance coverage, use the already callable newer KCUE regional APIs in this batch, especially `15158680`.

### `15058923` - EKAPE Animal Trace

Official DOCX says:

- service URL: `http://data.ekape.or.kr/openapi-data/service/user/animalTrace`
- operation: `/traceNoSearch`
- required parameters: `traceNo`, service key
- optional parameters: `optionNo`, `corpNo`
- application note: EKAPE APIs are automatic-approval, but public-data portal synchronization can take about one hour; if it still fails after that, the public-data portal should be contacted.

Re-probes used the DOCX samples:

```text
traceNo=002075264204, optionNo=9, corpNo=1178522046
traceNo=L01709271277007, optionNo=9, corpNo=1178522046
traceNo=170003000058, optionNo=3
```

Both `ServiceKey` and `serviceKey` returned the same provider envelope:

```text
HTTP 200
resultCode=99
resultMsg=SERVICE KEY IS NOT REGISTERED ERROR.
```

A fake-key control returned the same result.

Root cause: the current approved key is not registered in the EKAPE provider backend for this service. This is not a trace-number, casing, or option-number problem.

Adapter implication: do not implement a fallback or fake success path. Re-test only after the approved key/service mapping is corrected.

### `15063444` - Uiryeong Civil-Defense Shelters

Official DOCX says:

- service URL: `http://data.uiryeong.go.kr/rest/uiryeongclnsshuntfclty/getUiryeongclnsshuntfcltyList`
- required parameter: `ServiceKey`
- optional parameters: `numOfRows`, `pageNo`, shelter-name filter
- sample URL uses `ServiceKey`, `numOfRows=10`, `pageNo=1`

Re-probes show the endpoint path is reachable:

```text
HTTP exact official URL -> 302 to HTTPS
HTTPS + browser-like headers + ServiceKey -> HTTP 200 XML envelope, resultCode=99, 등록되지 않은 서비스키입니다
HTTPS + browser-like headers + serviceKey -> same provider error
HTTPS + browser-like headers + fake key -> same provider error
```

Root cause: the initial `Request Blocked` was a client/header/redirect symptom, not the final blocker. Once the official endpoint is reached, the real blocker is provider key registration: the Uiryeong backend does not recognize the approved key for this service.

Adapter implication: do not register the live adapter until a real-key probe returns `resultCode=00`. When it is fixed, the adapter should use the HTTPS provider endpoint and browser-like headers.
