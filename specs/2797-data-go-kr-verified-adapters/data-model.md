# Data Model: data.go.kr Verified Adapter Wave

## Verified API Candidate

Represents one directly proven public-service API operation or operation family allowed into this wave.

Fields:

- `data_go_kr_id`: official data.go.kr ID where applicable.
- `tool_id`: stable snake_case UMMAYA adapter ID.
- `api_name_ko`: Korean official or portal-visible API name.
- `institution`: owning agency or provider.
- `primitive`: always `find` for this wave.
- `endpoint`: official endpoint URL or provider endpoint for `LINK` APIs.
- `credential_family`: `data_go_kr_service_key`, `kepco_power_data_key`, or `reb_r_one_key`.
- `evidence_body_path`: saved successful direct-call response body.
- `evidence_header_path`: saved successful direct-call response headers.
- `response_format`: `json` or `xml`.
- `citizen_domain`: citizen-facing topic label.

Validation rules:

- `primitive` must equal `find`.
- `evidence_body_path` must point to an existing saved direct successful probe body.
- `credential_family` must match the source endpoint family.
- APIs from `SCOPED-NEW-30-manifest.json` are invalid for this wave.

## Adapter Registration

Represents the ToolRegistry entry for one verified adapter.

Fields:

- `id`: stable snake_case `tool_id`.
- `name_ko`: Korean display name.
- `ministry`: existing `Ministry` enum value, using `OTHER` only when no precise enum exists yet.
- `category`: non-empty topic tags.
- `endpoint`: official endpoint.
- `auth_type`: `api_key`.
- `input_schema`: Pydantic v2 request model.
- `output_schema`: Pydantic v2 response model.
- `search_hint`: bilingual Korean/English discovery text.
- `policy`: agency/portal citation with `citizen_facing_gate="read-only"`.
- `adapter_mode`: `live`.
- `primitive`: `find`.

Validation rules:

- No registered adapter may omit `primitive`.
- No registered adapter may use a root primitive outside `find`, `locate`, `send`, `check`.
- No registered adapter from this wave may require session identity for default read-only execution.
- No registered adapter may cite UMMAYA-invented permission classes as its policy source.

## Verified Public Data Input

Represents one adapter-specific Pydantic input model.

Shared fields where applicable:

- `page_no`: 1-indexed page number, bounded by the official API contract.
- `num_of_rows`: page size, bounded by the official API contract.
- Format selectors such as `result_type`, `return_type`, or `type` are fixed by the adapter when the evidence proves one reliable format.

Adapter-specific fields:

- FSC finance: `crno`, `biz_year`.
- AirKorea: `sido_name`, optional `ver`.
- FTC large group: `presentn_year`.
- FTC public year/month: `job_se_code`, `presentn_year`.
- TAGO route: `city_code`, `route_no`.
- TAGO arrival: `city_code`, `node_id`.
- TAGO bus location: `city_code`, `route_id`.
- TAGO station: `city_code`, optional `node_name`, optional `node_no`.
- KEPCO power usage: `year`, `month`, optional `metro_cd`, optional `city_cd`, optional `cntr_cd`.
- PPS bid: `inqry_div`, `bid_ntce_no`.
- REB stats table: optional `statbl_id`, `page_index`, `page_size`.
- BFC funeral cost: `page_no`, `num_of_rows`.
- KCUE finance: `schl_div_cd`.
- KCUE student: `schl_div_cd`.

Validation rules:

- Required fields must match official probe/contract names semantically, while Python model fields use snake_case.
- Adapter code maps snake_case fields to official wire params.
- Models use `extra="forbid"` to reject accidental unsupported params.

## Verified Public Data Output

Represents normalized adapter output before `find` envelope normalization.

Fields:

- `kind`: `collection`.
- `items`: list of typed public-data records.
- `total_count`: total upstream count if available, otherwise item count.

## Verified Public Data Item

Represents one heterogeneous public API record.

Fields:

- `record`: map from official field names to typed JSON-like values.

Allowed value types:

- string
- integer
- float
- boolean
- null
- list of allowed values
- map of string to allowed values

Validation rules:

- No `Any` appears in the public output schema.
- Empty strings are preserved when they come from official data.
- Secrets and service keys are never included.

## Fixture Set

Represents recorded payloads used by tests.

Fields:

- `success_body`: response body for a successful upstream call.
- `success_headers`: response headers for a successful upstream call.
- `zero_result_body`: optional successful zero-result body.
- `error_body`: upstream error body.
- `format`: `json` or `xml`.

Validation rules:

- Default tests may read fixtures only.
- Fixtures must not contain API keys, citizen identifiers, or secret headers.
- Error fixtures must preserve upstream result code and sanitized message.

## State Transitions

```text
candidate documented
  -> direct successful probe saved
  -> included in spec
  -> adapter registration authored
  -> fixture replay tests pass
  -> routing/search smoke passes
  -> UMMAYA real-use smoke passes
```

Deferred candidates remain:

```text
candidate documented
  -> blocked / unauthorized / unsafe / no successful probe
  -> deferred tracking issue
  -> future Spec Kit cycle after evidence changes
```
