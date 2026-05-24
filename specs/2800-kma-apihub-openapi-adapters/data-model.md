# Data Model: KMA APIHub OpenAPI Adapters

## KmaApiHubOperation

Represents one structured official APIHub operation.

Fields:

- `tool_id`: Stable UMMAYA snake_case tool id.
- `category_seq`: APIHub category id such as `2`, `10`, or `14`.
- `category_name_ko`: Official Korean category label.
- `service`: APIHub service segment, for example `VilageFcstInfoService_2.0`.
- `operation`: APIHub operation segment, for example `getVilageFcst`.
- `endpoint_path`: `/api/typ02/openApi/<service>/<operation>`.
- `sample_query`: Redacted query parameter defaults from the official sample URL.
- `request_params`: Ordered list of request parameter metadata.
- `response_fields`: Ordered list of response-field metadata when present.
- `approval_state`: `approved`, `approval_pending`, or `outside_structured_scope`.
- `search_hint_ko`: Korean discovery keywords.
- `search_hint_en`: English discovery keywords.

Validation rules:

- `tool_id` must match the existing `GovAPITool` snake_case id pattern.
- `endpoint_path` must start with `/api/typ02/openApi/`.
- `authKey` is recorded as a credential placeholder only, never as a literal key.
- `approval_state=approved` requires current approval evidence in the feature evidence file.

## KmaApiHubRequestParam

Represents one official request parameter.

Fields:

- `name`: Official APIHub parameter name.
- `label_ko`: Korean meaning from the official table when available.
- `description_ko`: Korean description from the official table when available.
- `required`: Conservative boolean; required when the official sample URL always includes it or the existing domain contract requires it.
- `default`: Redacted official sample value when useful and non-secret.
- `value_type`: `string`, `integer`, or `number`.

Validation rules:

- `authKey` must not be emitted as an LLM-fillable input field.
- Unknown or ambiguous official values default to `string`.

## KmaApiHubStructuredInput

Represents the per-operation request body exposed to the tool dispatcher.

Fields:

- Operation-specific request fields generated from `KmaApiHubRequestParam`,
  excluding `authKey`.
- `data_type`: `XML` or `JSON` where the operation supports the standard selector.
- `page_no` and `num_of_rows` use the existing UMMAYA naming convention for LLM-visible fields when the official parameters are `pageNo` and `numOfRows`.

Validation rules:

- Generated schemas must remain Pydantic v2 models.
- Values passed to the upstream request use official APIHub parameter names.
- Missing credential raises a configuration error before the HTTP request.

## KmaApiHubStructuredOutput

Represents a normalized official structured response.

Fields:

- `operation`: `<service>/<operation>` identifier.
- `result_code`: Official result code if present.
- `result_msg`: Official result message if present.
- `page_no`: Page number if present.
- `num_of_rows`: Row count if present.
- `total_count`: Total result count if present.
- `items`: List of scalar dictionaries normalized from XML or JSON item rows.
- `raw_format`: `xml`, `json`, or `text_error`.

Validation rules:

- `items` may contain only scalar JSON-compatible values: string, integer,
  float, boolean, or null.
- Non-success official result codes raise `ToolExecutionError` unless the
  operation-specific contract explicitly treats zero rows as a successful empty
  result.

## KmaApiHubApprovalState

Tracks whether the user's current APIHub account can live-call an operation.

States:

- `approved`: APIHub My Page or direct live probe confirms utilization approval.
- `approval_pending`: Official catalog exposes the operation but no current
  approval evidence is available.
- `outside_structured_scope`: The sample URL is not a structured `typ02/openApi`
  operation.

Transitions:

- `approval_pending` -> `approved` only after a new utilization approval or
  successful sanitized live probe.
- `approved` -> `approval_pending` if APIHub revokes access or a direct probe
  returns an authorization rejection.

## Relationships

- One `KmaApiHubOperation` has many `KmaApiHubRequestParam` entries.
- One `KmaApiHubOperation` produces one `GovAPITool`.
- One `GovAPITool` uses one generated Pydantic input schema and the shared
  structured output schema.
- Existing specialized KMA weather adapters remain separate tools and may share
  the same APIHub upstream operation where they provide better domain parsing.
