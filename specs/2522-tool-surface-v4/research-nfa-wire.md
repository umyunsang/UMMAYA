# T030 — NFA Wire Param Research

Source: `/tmp/kosmos-domain-docs/nfa_emg.txt` (NIA-IFT 공공데이터 오픈API 활용가이드, 소방청 구급정보서비스 v1.0)
Cross-checked: `/tmp/kosmos-evidence/medical-evidence.md`

## Status: CONFIRMED (camelCase wire params, operation-specific ym field)

---

## Endpoint

```
Base URL: https://apis.data.go.kr/1661000/EmergencyInformationService
Sub-endpoint: /<operation>
Method: GET
Auth: serviceKey (query param, URL-encoded)
Format: resultType=json (wire param name is `resultType`, value is `json` or `xml`)
```

---

## Wire Param Mapping (all 6 sub-operations)

All shared params use camelCase throughout. The critical disambiguation:

| Input schema field     | Wire param name    | Notes                                               |
|------------------------|--------------------|-----------------------------------------------------|
| `sido_hq_ogid_nm`      | `sidoHqOgidNm`     | Optional (항목구분=0), max 22 chars                  |
| `rsac_gut_fstt_ogid_nm`| `rsacGutFsttOgidNm`| Required (항목구분=1), max 7 chars                  |
| `stmt_ym`              | **operation-specific** — see table below             |
| `page_no`              | `pageNo`           | Required                                            |
| `num_of_rows`          | `numOfRows`        | Required                                            |
| `result_type`          | `resultType`       | `json` or `xml`                                     |

### Year-Month param — critical per-operation divergence

| Operation (value)              | Wire ym param name | Korean label  | Notes                       |
|--------------------------------|-------------------|---------------|-----------------------------|
| `getEmgencyActivityInfo`       | `gutYm`           | 출동년월       | ALSO accepts optional `egrcSidoCdNm` + `egrcSiggCdNm` |
| `getEmgPatientTransferInfo`    | `stmtYm`          | 신고년월       |                             |
| `getEmgPatientConditionInfo`   | `stmtYm`          | 신고년월       |                             |
| `getEmgPatientFirstaidInfo`    | `stmtYm`          | 신고년월       |                             |
| `getEmgVehicleDispatchInfo`    | `stmtYm`          | 신고년월       |                             |
| `getEmgVehicleInfo`            | `stmtYm` / none   | (static data) | No ym required (vehicle registry, not time-series) |

**Note on getEmgVehicleInfo**: The NIA guide shows no `stmtYm` in the request spec. The call URL example omits it. This is a vehicle registry snapshot, not a time-series query. The adapter still accepts `stmt_ym` from the user for consistency, but does NOT forward it for `vehicle_info` — avoids resultCode 10.

### getEmgencyActivityInfo — additional optional wire params

| Input schema field  | Wire param name | Korean label  | Required |
|---------------------|-----------------|---------------|----------|
| (none in current schema) | `egrcSidoCdNm`  | 긴급구조시    | Optional |
| (none in current schema) | `egrcSiggCdNm`  | 긴급구조구    | Optional |

These are not in the current `NfaEmergencyInfoServiceInput` schema and are not added (YAGNI — the input schema is not being extended in this task).

---

## Evidence: resultCode 10 root cause

From `medical-evidence.md`:
> All param combinations tested → `resultCode: 10 INVALID REQUEST PARAMETER ERROR`
> - `stmtYm=202101&rsacGutFsttOgidNm=공주소방서` → resultCode 10
> - `gutYm=202101&rsacGutFsttOgidNm=천안동남소방서` → resultCode 10

Root cause: the evidence tests used the base URL `https://apis.data.go.kr/1661000/EmergencyInformationService` without the operation suffix. The correct URL is `<base>/<operation>` e.g. `.../getEmgencyActivityInfo`. The NIA guide confirms via Call Back URLs:
```
http://apis.data.go.kr/1661000/EmergencyInformationService/getEmgPatientTransferInfo
http://apis.data.go.kr/1661000/EmergencyInformationService/getEmgPatientConditionInfo
...
```

**The fix**: append `/{operation}` to the base URL.

---

## Response JSON structure

The API returns JSON (when `resultType=json`) with the same structure as HIRA/KMA:

```json
{
  "response": {
    "header": { "resultCode": "00", "resultMsg": "NORMAL SERVICE" },
    "numOfRows": 2,
    "pageNo": 1,
    "totalCount": 162,
    "body": {
      "items": {
        "item": [ {...}, {...} ]
      }
    }
  }
}
```

Note: `numOfRows`, `pageNo`, `totalCount` are at the `response` level (not inside `body`), matching KMA/HIRA pattern. The `body.items.item` path is a list (or a single dict when totalCount=1 — standard data.go.kr quirk).

---

## Confirmed per-operation output fields (from NIA guide examples)

### getEmgencyActivityInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `rcptPathCdNm`, `cptcSeCdNm`, `gutYm`, `gutHh`, `sptMvmnDtc`, `ptntAge`, `ptntSdtSeCdNm`, `egrcSidoCdNm`, `egrcSiggCdNm`, `frnrAt`, `ruptOccrPlcCdNm`, `ruptSptmCdNm`, `ptntOccrTyCd1Nm`, `ptntOccrTyCd2Nm`, `ptntOccrTyCd3Nm`, `emtpQlcClCd1Nm`, `emtpQlcClCd2Nm`, `emtpQlcClCd3Nm`

### getEmgPatientTransferInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `stmtYm`, `stmtHh`, `rlifAcdAsmCdNm`, `ptntAge`, `ptntSdtSeCdNm`, `frnrAt`, `ptntTyCdNm`, `ruptOccrPlcCdNm`, `rlifOccrTyCdNm`, `anmlInctCdNm`, `wmhtDamgCdNm`

### getEmgPatientConditionInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `stmtYm`, `stmtHh`, `ptntAge`, `lwsBpsr`, `topBpsr`, `ptntHbco`, `ptntBfco`, `ptntOsv`, `ptntBht`, `ruptSptmCdNm`

### getEmgPatientFirstaidInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `stmtYm`, `stmtHh`, `ptntAge`, `ptntSdtSeCdNm`, `fstaCdNm`

### getEmgVehicleDispatchInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `stmtYm`, `stmtHh`, `vctpCdNm`, `vhclSeCd`, `vhclNo`, `vhclStatCdNm`, `gotFrmtAt`, `vhcn`, `vhclGrCdNm`, `mnm`, `mdnm`, `gutPcnt`, `tnkCpct`, `gutOdr`

### getEmgVehicleInfo
Wire fields: `sidoHqOgidNm`, `rsacGutFsttOgidNm`, `vhclSeCd`, `vhclNo`, `vctpCdNm`, `vhclStatCdNm`, `gotFrmtAt`, `vhcn`, `vhclGrCdNm`, `mnm`, `mdnm`, `bdgPcnt`, `tnkCpct`, `stde`

---

## Implementation decisions

1. **URL construction**: `f"{_BASE_URL}/{inp.operation.value}"` — operation suffix is the sub-endpoint name.
2. **ym param routing**: `gutYm` for `activity`, `stmtYm` for all others; omit for `vehicle_info`.
3. **Single-item unwrap**: `body.items.item` may be a dict (not list) when totalCount=1 — normalize with `items if isinstance(items, list) else [items]`.
4. **resultType=json**: wire param is `resultType` (capital T), value `json` (lowercase).
5. **pageNo/numOfRows**: camelCase wire names.
6. **Error handling**: resultCode ≠ "00" → `ToolExecutionError`. resultCode "10" = INVALID_REQUEST_PARAMETER_ERROR (400 equiv).
