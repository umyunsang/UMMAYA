# Contract: Fixture Replay and Parser Behavior

## Scope

This contract defines how verified adapter fixtures are used in tests and how adapters normalize upstream responses.

## Fixture Sources

Successful fixture bodies come from:

```text
docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16/*.body.json
docs/api/data-go-kr-candidate-docs/<id>/probes/live-2026-05-16/*.body.xml
```

Successful fixture headers come from matching `*.headers.txt` files.

## Default Test Rule

Default tests MUST read fixture files from disk and MUST NOT call live upstream APIs.

Allowed:

- Unit tests for JSON parsing.
- Unit tests for XML parsing.
- Unit tests for result-code error extraction.
- Unit tests for adapter registration and executor binding.
- Integration tests that call adapter functions with fixture-injected clients.

Forbidden in default tests:

- Network calls to `apis.data.go.kr`.
- Network calls to `bigdata.kepco.co.kr`.
- Network calls to `www.reb.or.kr`.
- Network calls to TAGO, AirKorea, FTC, PPS, KCUE, or Busan Facilities endpoints.

## Parser Output Contract

Every parser returns:

```json
{
  "kind": "collection",
  "items": [
    {
      "record": {
        "officialFieldName": "official value"
      }
    }
  ],
  "total_count": 1
}
```

Rules:

- `kind` is always `collection` for successful adapter outputs in this wave.
- `items` is an array, even when the upstream returns a single object.
- `total_count` comes from upstream metadata when available; otherwise it equals `len(items)`.
- Official upstream field names are preserved inside `record`.
- API keys, request URLs with keys, and secret headers are never included in output.

## Error Contract

When an upstream response carries an error code or malformed body:

- The adapter raises a tool-domain exception.
- The executor converts it into the standard `LookupError` envelope.
- The error message includes sanitized upstream result code and message where available.
- The LLM-facing failure message tells the model not to fabricate results.

## XML Rules

XML parser behavior:

- Ignore XML namespaces for simple public-data records.
- Normalize repeated `item` elements into multiple records.
- Normalize single `item` objects into a one-record list.
- Read `resultCode` and `resultMsg` or agency-specific equivalents when present.
- Treat `00`, `0`, `NORMAL SERVICE.`, `NORMAL_CODE`, `SUCCESS`, and provider-specific normal codes documented by fixtures as success.

## JSON Rules

JSON parser behavior:

- Support common data.go.kr shapes such as `response.header`, `response.body.items.item`.
- Support provider shapes where records are under `data`, `result`, `items`, or top-level arrays.
- Normalize zero-result shapes into an empty `items` list with success.
- Treat service-key or quota error objects as upstream errors.
