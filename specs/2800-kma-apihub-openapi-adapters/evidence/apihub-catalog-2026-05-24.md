# KMA APIHub Catalog Evidence — 2026-05-24

## Verification Method

- Opened the user's current Google Chrome tab with Computer Use and verified the logged-in KMA APIHub site at `https://apihub.kma.go.kr/`.
- Navigated the visible `지상관측` category page and confirmed the page content was `https://apihub.kma.go.kr/apiList.do?seqApi=2`.
- Cross-checked the official APIHub category pages through direct public HTTP fetches for repeatable extraction.
- Redacted the user's API key, account email, phone number, and other personal details from this repository artifact.

## Chrome-Observed Category Navigation

The logged-in APIHub page exposed these category links:

- `apiList.do?seqApi=2` — 지상관측
- `apiList.do?seqApi=3` — 해양관측
- `apiList.do?seqApi=4` — 고층관측
- `apiList.do?seqApi=5` — 레이더
- `apiList.do?seqApi=6` — 위성
- `apiList.do?seqApi=7` — 지진/화산
- `apiList.do?seqApi=8` — 태풍
- `apiList.do?seqApi=9` — 수치모델
- `apiList.do?seqApi=10` — 예특보
- `apiList.do?seqApi=971` — 융합기상
- `apiList.do?seqApi=14` — 항공기상
- `apiList.do?seqApi=12` — 세계기상
- `specialApiList.do` — 산업특화

## Current Approval Evidence

The logged-in My Page showed four approved utilization applications. The approved visible operations were:

- `VilageFcstInfoService_2.0/getFcstVersion`
- `VilageFcstInfoService_2.0/getVilageFcst`
- `VilageFcstInfoService_2.0/getUltraSrtFcst`
- `typ01/url/fct_shrt_reg.php`

This proves that APIHub key issuance and per-operation utilization approval are separate. The credential itself is intentionally not recorded here.

## Category Extraction Summary

| seqApi | Official category title | Sample URLs | Type counts | Unique structured `typ02/openApi` operations |
|---:|---|---:|---|---:|
| 2 | 지상관측 | 19 | `typ01=6`, `typ02=12`, `typ03=1` | 12 |
| 3 | 해양관측 | 18 | `typ01=3`, `typ02=14`, `typ03=1` | 14 |
| 4 | 고층관측 | 11 | `typ01=5`, `typ02=6` | 6 |
| 5 | 레이더 | 9 | `typ01=7`, `typ02=2` | 2 |
| 6 | 위성 | 43 | `typ01=11`, `typ02=20`, `typ03=2`, `typ05=10` | 20 |
| 7 | 지진/화산 | 8 | `typ01=2`, `typ02=2`, `typ09=4` | 2 |
| 8 | 태풍 | 4 | `typ01=3`, `typ02=1` | 1 |
| 9 | 수치모델 | 46 | `typ01=6`, `typ02=8`, `typ06=32` | 8 |
| 10 | 예특보 | 21 | `typ01=12`, `typ02=7`, `typ03=2` | 7 |
| 971 | 융합기상 | 14 | `typ01=14` | 0 |
| 14 | 항공기상 | 12 | `typ01=2`, `typ02=10` | 10 |
| 12 | 세계기상 | 30 | `typ01=27`, `typ02=3` | 3 |

Across the twelve category pages, the public catalog exposed 235 unique sample URLs:

- `typ01`: 98
- `typ02`: 85
- `typ03`: 6
- `typ05`: 10
- `typ06`: 32
- `typ09`: 4

The separate `specialApiList.do` page exposed 6 sample URLs, all `typ01`; it added no structured `typ02/openApi` operation.

## Structured Service Coverage

The 85 structured operations are distributed across these APIHub services:

- `AmmIwxxmService`: 1
- `CloudSatlitInfoService`: 10
- `EqkInfoService`: 2
- `GtsInfoService`: 3
- `KIMModelInfoService`: 4
- `NwpModelInfoService`: 4
- `SeaMtlyInfoService`: 14
- `SfcMtlyInfoService`: 8
- `SfcYearlyInfoService`: 14
- `UppMtlyInfoService`: 6
- `VilageFcstInfoService_2.0`: 4
- `VilageFcstMsgService`: 3
- `WthrRadarInfoService`: 2
- `WthrSatlitInfoService`: 10

## Structured Operation Baseline

The operation list is the same as `docs/api/kma/apihub-openapi-inventory.md` and remains the baseline for this feature:

- Ground observation: 12 operations
- Marine observation: 14 operations
- Upper-air observation: 6 operations
- Radar: 2 operations
- Satellite: 20 operations
- Earthquake/volcano: 2 operations
- Typhoon: 1 operation
- Numerical model: 8 operations
- Forecast/warning: 7 operations
- Convergence weather: 0 operations
- Aviation weather: 10 operations
- World weather: 3 operations

Total structured operations: 85.

## Local Inventory Consistency Check

The official-page extraction found 85 structured `typ02/openApi` operations.
The local inventory contains the same 85 structured operations. A naive markdown
regex also matched the note text ``typ01/url/wrn_*`` in
`docs/api/kma/apihub-openapi-inventory.md`; that note is non-structured and is
not part of the 85-operation baseline.

The extracted sample URL parameter names confirm that the 85 operations are not
one homogeneous schema. Examples:

- `VilageFcstInfoService_2.0/getVilageFcst`: `pageNo`, `numOfRows`, `dataType`, `base_date`, `base_time`, `nx`, `ny`, `authKey`
- `AmmIwxxmService/getMetar`: `pageNo`, `numOfRows`, `dataType`, `icao`, `authKey`
- `EqkInfoService/getEqkMsgList`: `pageNo`, `numOfRows`, `dataType`, `fromTmFc`, `toTmFc`, `authKey`
- `KIMModelInfoService/getKIMLdapsUnisAll`: `baseTime`, `leadHour`, `dataTypeCd`, `dataType`, `authKey`
- `WthrSatlitInfoService/getGk2aIrArea`: `pageNo`, `numOfRows`, `dataType`, `dateTime`, `waveType`, `unitType`, `dongCode`, `authKey`
