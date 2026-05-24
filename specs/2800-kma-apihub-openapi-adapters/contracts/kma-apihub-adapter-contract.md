# Contract: KMA APIHub Structured Adapter

## Tool Registration Contract

Each structured operation MUST register exactly one `GovAPITool` unless an
existing specialized KMA adapter already owns that citizen-facing behavior. In
that case, the generated operation tool may still exist as a situational
catalog tool but MUST NOT replace the specialized tool's public id.

Required tool metadata:

- `id`: Stable snake_case id derived from KMA + service + operation.
- `ministry`: `KMA`.
- `primitive`: `find`.
- `auth_type`: `api_key`.
- `adapter_mode`: `live` for approved or live-capable read-only operations;
  authorization-pending state is represented in operation metadata and fail-
  closed runtime handling.
- `endpoint`: `https://apihub.kma.go.kr/api/typ02/openApi/<service>/<operation>`.
- `policy.real_classification_url`: KMA public-data policy URL.
- `is_concurrency_safe`: `true` for read-only operations.
- `cache_ttl_seconds`: Non-zero only when the official data cadence supports caching.
- `search_hint`: Korean and English operation/category terms.

## Credential Contract

- Environment variable: `UMMAYA_KMA_API_HUB_AUTH_KEY`.
- Upstream query parameter: `authKey`.
- The data.go.kr key MUST NOT be accepted for APIHub operations.
- Missing or empty credential MUST raise `ConfigurationError`.
- Secret values MUST NOT be logged, persisted, or returned in tool output.

## Request Contract

- LLM-visible fields use UMMAYA snake_case names.
- Upstream request fields use official APIHub names.
- `authKey` is injected by the adapter, not accepted from model input.
- `dataType=XML` is the conservative default where the official API supports both XML and JSON.
- JSON may be requested only through an explicit `data_type="JSON"` field where supported.

## Response Contract

Successful responses normalize to `KmaApiHubStructuredOutput`:

```json
{
  "operation": "ServiceName/getOperation",
  "result_code": "00",
  "result_msg": "NORMAL_SERVICE",
  "page_no": 1,
  "num_of_rows": 10,
  "total_count": 1,
  "items": [
    {
      "field": "value"
    }
  ],
  "raw_format": "xml"
}
```

Failure handling:

- HTTP status errors become `ToolExecutionError` with a secret-safe upstream summary.
- Official non-success result codes become `ToolExecutionError`.
- Authorization rejection becomes `ToolExecutionError` naming APIHub utilization approval as the likely gate when the operation is not approved.
- Unsupported response shapes become `ToolExecutionError`.
- The adapter MUST NOT fabricate weather or public-data values.

## Test Contract

Default tests MUST cover:

- Catalog count and duplicate-id checks.
- Credential resolver behavior with and without `UMMAYA_KMA_API_HUB_AUTH_KEY`.
- One success fixture using XML/default response.
- One success fixture using JSON response when supported.
- One authorization/HTML error fixture.
- One official non-success result-code fixture.
- Registry integration: every generated operation tool is discoverable and has an executor binding.
