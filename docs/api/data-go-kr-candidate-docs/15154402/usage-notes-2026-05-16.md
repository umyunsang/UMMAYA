# 15154402 문화체육관광부 국립중앙도서관_서지 정보 제공 서비스

## Collection Status

- Source: <https://www.data.go.kr/data/15154402/openapi.do>
- Provider: 문화체육관광부 국립중앙도서관
- Department: 디지털정보기획과
- Category: 문화체육관광 - 문화예술
- Service type: REST, JSON/XML
- Application status: approved in data.go.kr usage list on 2026-05-16
- Usage-list evidence: `[승인] 문화체육관광부 국립중앙도서관_서지 정보 제공 서비스`, 신청일 `2026-05-16`, 만료예정일 `2028-05-16`
- Development quota: 10,000 calls per operation per day
- Review policy: development account auto-approved, production account reviewed after use-case registration
- Update cycle: realtime
- License: 이용허락범위 제한 없음

## Saved Artifacts

- `data-go-kr-detail.html`
- `data-go-kr-inline-swagger.json`
- `intake-record.json`

## Endpoint Summary

Base URL:

```text
https://apis.data.go.kr/1371029/BookInformationService_v2
```

The Swagger also lists `http`; prefer HTTPS for adapters unless live probing proves an endpoint-specific issue.

Common required query parameters for all operations:

- `serviceKey`: data.go.kr service key
- `pageNo`: page number
- `numOfRows`: rows per page
- `type`: result type selector

### Bibliographic List Operations

These operations return bibliographic metadata records. Shared optional filters are:

- `label`: 표제명
- `controlNumber`: 제어번호
- `isbn`: 국제표준도서번호
- `publisher`: 발행처
- `titleOfSeries`: 총서표제

Operations:

```http
GET /getbookList_v2
GET /getNonbookList_v2
GET /getElectronicBookList_v2
GET /getElectronicJournalList_v2
GET /getMultimediaList_v2
```

Primary response fields include:

- `BIBLIO_ID`: 국립중앙도서관 서지 제어번호
- `URI`: linked-data URI
- `DCTERMS_title`, `RDFS_label`: title/label
- `DC_creator`, `DCTERMS_creator`: creator metadata
- `BIBO_isbn`, `BIBO_issn`: standard identifiers where present
- `DCTERMS_subject`, `NLON_keyword`: subject and keyword metadata
- `DCTERMS_publisher`, `DCTERMS_issued`: publisher and issued date fields where present
- `DCTERMS_description`, `DCTERMS_abstract`: descriptive metadata where present

### Relationship Operations

These operations return author or subject relationships for a known control number. Shared optional filter:

- `controlNumber`: 제어번호

Operations:

```http
GET /getOfflineBookAuthorList_v2
GET /getOfflineBookSubjectList_v2
GET /getOfflineNonBookAuthorList_v2
GET /getOfflineNonBookSubjectList_v2
GET /getOnlineElectronicBookAuthorList_v2
GET /getOnlineElectronicBookSubjectList_v2
GET /getOnlineElectronicJournalAuthorList_v2
GET /getOnlineElectronicJournalSubjectList_v2
GET /getOnlineMultimediaAuthorList_v2
GET /getOnlineMultimediaSubjectList_v2
```

Use these after a list lookup returns a `BIBLIO_ID` or control-number-equivalent field.

## Adapter Fit

- Primitive: `lookup`
- Suggested tool name: `nlk_bibliographic_metadata_lookup`
- Secondary operation group: `nlk_bibliographic_relation_lookup`
- Read-only public-data adapter.
- Good first use cases:
  - title/ISBN/publisher lookup across national bibliography records
  - retrieve normalized National Library bibliographic identifiers and linked-data URIs
  - expand a known bibliographic control number into author or subject relationships
- Do not treat the relationship endpoints as full-text search. They are follow-up lookups keyed by bibliographic control number.

## Curl Shape

Use after key propagation; do not commit the real key.

```bash
curl --get 'https://apis.data.go.kr/1371029/BookInformationService_v2/getbookList_v2' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'type=json' \
  --data-urlencode 'label=인공지능'
```

Relationship lookup shape:

```bash
curl --get 'https://apis.data.go.kr/1371029/BookInformationService_v2/getOfflineBookAuthorList_v2' \
  --data-urlencode "serviceKey=${DATA_GO_KR_SERVICE_KEY}" \
  --data-urlencode 'pageNo=1' \
  --data-urlencode 'numOfRows=10' \
  --data-urlencode 'type=json' \
  --data-urlencode 'controlNumber=<BIBLIO_ID_OR_CONTROL_NUMBER>'
```
