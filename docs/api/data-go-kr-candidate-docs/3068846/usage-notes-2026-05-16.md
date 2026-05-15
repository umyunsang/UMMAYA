# 3068846 - 한국수출입은행 환율 정보

## Intake

- Source: data.go.kr OpenAPI detail page, LINK type.
- Provider: 한국수출입은행.
- Category: 일반공공행정 - 재정·금융.
- Data format on data.go.kr: XML; provider endpoint returns JSON.
- Update cycle: 실시간 in data.go.kr metadata; provider notice says daily exchange-rate data is updated around 11:00 on business days.
- License: data.go.kr says 이용허락범위 제한 없음.
- data.go.kr application action: the normal `활용신청` form is not present because this is a LINK API. The data.go.kr `바로가기` button was clicked from the logged-in Chrome session.
- External key application status: not completed. The provider's `인증키 발급신청` tab requires phone or i-PIN real-name authentication. Do not count this item as a completed 활용신청 until the user completes that external identity step.

## Saved Source Files

- `data-go-kr-detail.html`: data.go.kr detail page.
- `data-go-kr-catalog.json`: schema.org metadata from data.go.kr.
- `koreaexim-openapi-detail.html`: official Korea Eximbank Open API detail and development spec page.
- `koreaexim-auth-application-page.html`: provider key application page showing identity-authentication requirement.

## Provider Notices

- The old request domain `www.koreaexim.go.kr` was scheduled to end parallel operation on `2026-04-30`.
- Use the new API domain `oapi.koreaexim.go.kr`.
- Daily call limit: `1000` calls. Above the limit, `result: 4` is returned and data is not provided.
- Non-business-day data, or business-day requests before the daily update around 11:00, can return `null`.
- If `RESULT` is `3`, the auth key may be invalid or destroyed after personal-information retention expiration.

## Endpoint

```text
GET https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON
```

## Official Sample URL Shape

```text
https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey=<AUTHKEY>&searchdate=20180102&data=AP01
```

## Request Parameters

| Name | Type | Required | Description | Value Notes |
| --- | --- | --- | --- | --- |
| `authkey` | `String` | yes | 인증키 | Provider Open API key issued after external application |
| `searchdate` | `String` | no | 검색요청날짜 | `YYYY-MM-DD`, `YYYYMMDD`, or omitted for current date |
| `data` | `String` | yes | 검색요청 API 타입 | `AP01`: 환율, `AP02`: 대출금리, `AP03`: 국제금리 |

## Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `RESULT` / `result` | Integer | `1`: 성공, `2`: DATA 코드 오류, `3`: 인증코드 오류, `4`: 일일제한횟수 마감 |
| `CUR_UNIT` / `cur_unit` | String | 통화코드 |
| `CUR_NM` / `cur_nm` | String | 국가/통화명 |
| `TTB` / `ttb` | String | 전신환 송금 받으실 때 |
| `TTS` / `tts` | String | 전신환 송금 보내실 때 |
| `DEAL_BAS_R` / `deal_bas_r` | String | 매매 기준율 |
| `BKPR` / `bkpr` | String | 장부가격 |
| `YY_EFEE_R` / `yy_efee_r` | String | 년환가료율 |
| `TEN_DD_EFEE_R` / `ten_dd_efee_r` | String | 10일환가료율 |
| `KFTC_DEAL_BAS_R` / `kftc_deal_bas_r` | String | 서울외국환중개 매매기준율 |
| `KFTC_BKPR` / `kftc_bkpr` | String | 서울외국환중개 장부가격 |

## Adapter Notes

- Primitive fit: `lookup`.
- Live readiness: blocked until a Korea Eximbank Open API key is issued through the provider's external real-name authentication flow.
- Do not model this as a data.go.kr service-key API. The callable surface is the provider endpoint and the credential is `authkey`.
- The adapter should normalize both uppercase field names from the spec and lowercase names from the official sample JSON.
- Default query should use `data=AP01` for exchange rates unless the caller explicitly requests AP02/AP03.
