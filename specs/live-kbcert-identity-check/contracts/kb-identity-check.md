# Contract: Live KB Identity Check Adapter

## Tool Contract

Tool id: `live_verify_kb_identity`

Primitive: `check`

Family hint: `kb_identity`

Invocation shape:

```json
{
  "tool_id": "live_verify_kb_identity",
  "params": {
    "mode": "request",
    "reqTxId": "synthetic-req-tx-id",
    "requestType": "NONE"
  }
}
```

Result lookup shape:

```json
{
  "tool_id": "live_verify_kb_identity",
  "params": {
    "mode": "result",
    "reqTxId": "synthetic-req-tx-id",
    "certTxId": "synthetic-cert-tx-id",
    "requestType": "NONE"
  }
}
```

## Environment Contract

| Variable | Required for live | Purpose |
|----------|-------------------|---------|
| `UMMAYA_KBCERT_BASE_URL` | yes | KB staging or production base URL |
| `UMMAYA_KBCERT_API_KEY` | yes | KB `apiKey` header |
| `UMMAYA_KBCERT_HS_KEY` | yes | KB `hsKey` header |
| `UMMAYA_KBCERT_COMPANY_CD` | yes | KB `companyCd` body field |
| `UMMAYA_KBCERT_REQUEST_TYPE` | no | Defaults to `NONE` |

## KB Wire Contract

Request endpoint: `POST /kbsign/api/sign_request2`

Result endpoint: `POST /kbsign/api/sign_result`

Headers:

```text
apiKey: <UMMAYA_KBCERT_API_KEY>
hsKey: <UMMAYA_KBCERT_HS_KEY>
Content-Type: application/json; charset=UTF-8
Accept: application/json
```

## Success Contract

A KB response is successful only when all available success indicators agree:

- `dataHeader.resultCode == "0000"`
- `dataHeader.successCode == "0"`
- `dataBody.result-code == "ok"`
- required transaction ids are present
- result lookup response `reqTxId` matches the requested `reqTxId`

## Redaction Contract

The adapter must recursively drop identity keys before building model outputs, log messages, error messages, or docs snippets:

```text
CI, DI, userNm, birthday, receiverHP, receiverName, receiverBirthday,
gender, krnFrgnDstcd, phone, name, birthdate
```

Tests use sentinel values for these keys and assert they never appear in returned context dumps.
