# 15094093 건강보험심사평가원_병원평가정보서비스

## Collection Status

- Source: <https://www.data.go.kr/data/15094093/openapi.do>
- Provider: 건강보험심사평가원
- Department: 빅데이터실
- Category: 보건 - 건강보험
- Service type: REST, XML
- Application status: approved in data.go.kr usage list on 2026-05-16
- Usage-list evidence: `[승인] 건강보험심사평가원_병원평가정보서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`
- Development quota: 10,000 calls per day
- Review policy: development account auto-approved, production account reviewed after use-case registration
- Update cycle: data.go.kr page says realtime; provider guide says daily refresh
- License: Kogl type 1/source attribution, with third-party rights notice

## Saved Artifacts

- `data-go-kr-detail.html`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`
- `OpenAPI활용가이드_건강보험심사평가원(병원평가정보서비스)_20250219.docx`
- `OpenAPI활용가이드_건강보험심사평가원(병원평가정보서비스)_20250219.docx.txt`

## Endpoint Summary

Base URL:

```text
https://apis.data.go.kr/B551182/hospAsmInfoService1
```

The provider guide lists `http://apis.data.go.kr/B551182/hospAsmInfoService1`; the portal Swagger also lists HTTPS. Prefer HTTPS for adapters unless live probing proves an endpoint-specific issue.

### getHospAsmInfo1

Purpose: retrieve hospital quality-rating grades for evaluated healthcare institutions.

```http
GET /getHospAsmInfo1
```

Required query parameters:

- `serviceKey`: data.go.kr service key
- `pageNo`: page number, sample `1`
- `numOfRows`: rows per page, sample `10`

Optional query parameters:

- `ykiho`: encrypted healthcare institution identifier. The guide states this is obtained from 건강보험심사평가원 병원정보서비스 > 병원기본목록 `getHospBasisList1`. The original identifier is not provided and cannot be decrypted.

Important response fields:

- `ykiho`: encrypted institution identifier
- `yadmNm`: institution name
- `clCd`, `clCdNm`: institution class code/name
- `addr`: address
- `asmGrd01`: acute stroke rating
- `asmGrd03`: hemodialysis rating
- `asmGrd04`: medical-aid psychiatry rating
- `asmGrd05`: surgical-site infection prevention antibiotic rating
- `asmGrd06`: coronary artery bypass graft rating
- `asmGrd07`: acute upper respiratory infection antibiotic-prescription rate rating
- `asmGrd08`: injection prescription rate rating
- `asmGrd09`: number-of-medications rating
- `asmGrd10`: long-term care hospital rating
- `asmGrd12`: colon cancer rating
- `asmGrd13`: stomach cancer rating
- `asmGrd14`: breast cancer rating
- `asmGrd15`: lung cancer rating
- `asmGrd16`: asthma good-institution disclosure
- `asmGrd17`: chronic obstructive pulmonary disease rating
- `asmGrd18`: pneumonia rating
- `asmGrd19`: intensive care unit rating
- `asmGrd20`: neonatal intensive care unit rating
- `asmGrd21`: anesthesia rating
- `asmGrd22`: mental-health inpatient-area rating
- `asmGrd23`: acute lower respiratory infection antibiotic-prescription rate rating
- `asmGrd24`: hypertension/diabetes rating

## Semantics And Constraints

- Rating values are generally `1` through `5` or `등급제외`; `asmGrd16` uses the provider's "good institution disclosed" semantics.
- `ykiho` is a matched encrypted identifier. Do not expose this as a reversible institution ID and do not promise decryption.
- For name/address discovery, compose with HIRA hospital information APIs that return the encrypted `ykiho`, then call this API for evaluation grades.
- The guide lists maximum message size `4000` bytes, average response time `500ms`, and `30 tps`.
- Provider result codes include `00 NORMAL SERVICE`, `10 INVALID_REQUEST_PARAMETER_ERROR`, `20 SERVICE_ACCESS_DENIED_ERROR`, `22 LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR`, `30 SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, and `31 DEADLINE_HAS_EXPIRED_ERROR`.

## Adapter Fit

- Primitive: `lookup`
- Suggested tool name: `hira_hospital_quality_rating_lookup`
- Read-only public-data adapter.
- Good first use cases:
  - lookup hospital quality ratings by encrypted `ykiho`
  - combine with HIRA hospital basic list APIs to answer institution-name or location driven quality-rating questions
  - normalize the `asmGrdXX` fields into human-readable evaluation categories
- Avoid medical advice wording. The adapter should report official evaluation grades and source date/agency, not recommend treatment.

## Curl Shape

Use after key propagation; do not commit the real key.

```bash
curl --get 'https://apis.data.go.kr/B551182/hospAsmInfoService1/getHospAsmInfo1' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10'
```

With an encrypted institution identifier:

```bash
curl --get 'https://apis.data.go.kr/B551182/hospAsmInfoService1/getHospAsmInfo1' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'ykiho=<ENCRYPTED_YKIHO_FROM_HIRA_HOSPITAL_BASIC_LIST>'
```
