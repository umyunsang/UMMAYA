# Phase 1 Data Model: data.go.kr Live Expansion

## VerifiedAdapterSpec Extension

Existing entity: `src/ummaya/tools/verified_data_go_kr/_models.py::VerifiedAdapterSpec`

Fields retained:

- `dataset_id`, `tool_id`, `module_name`, `name_ko`, `ministry`, `category`
- `endpoint`, `env_var`, `auth_query_param`, `response_format`
- `query_param_map`, `static_query_params`, `record_tag`
- `evidence_path`, `policy_url`, `policy_text`, `last_verified`
- `search_hint`, `llm_description`, `trigger_examples`
- `primitive`, `adapter_mode`, `citizen_facing_gate`

Fields added:

- `request_headers: dict[str, str] = {}` — optional adapter-specific HTTP headers proven by direct evidence.

Validation changes:

- `endpoint` accepts `https://` and `http://` because `15121954` has direct successful evidence only for the HTTP gateway.
- `request_headers` keys and values must be non-empty strings.

## Live Public-Data Adapter

Each new adapter is represented by:

- one manifest row in `_manifest.py`
- one thin module exposing `INPUT_SCHEMA`, `TOOL`, `handle()`, and `register()`
- one strict Pydantic v2 input model
- one generated schema file under `docs/api/schemas/<tool_id>.json`
- one fixture replay row in unit tests

State:

- `live_registered`: adapter appears in `VERIFIED_DATA_GO_KR_ADAPTERS` and `register_all_tools()`
- `blocked`: adapter is documented but not registered

Transitions:

- `candidate -> live_registered`: direct success evidence exists, schema is strict, fixture replay passes, docs/schema updated
- `candidate -> blocked`: live control probes prove provider/key mapping or safety blocker

## New Adapter Inputs

The input schemas are intentionally narrow and mirror the documented sample calls:

| Tool ID | Required Fields | Optional Fields |
|---------|-----------------|-----------------|
| `moj_village_lawyer_lookup` | none | `page_no`, `num_of_rows`, `sido`, `sigungu` |
| `mois_facility_safety_info_lookup` | none | `fclts_nm`, `page_no`, `num_of_rows` |
| `hira_medical_institution_detail` | `ykiho` | none |
| `mois_emergency_call_box_lookup` | none | `road_address`, `page_no`, `num_of_rows` |
| `djtc_subway_segment_fare_time_check` | `strstnno`, `endstnno` | none |
| `gyeryong_assistive_device_charging_place_locate` | none | `current_page`, `per_page`, `indoor_outdoor` |
| `nmc_aed_site_locate` | none | `q0`, `q1`, `page_no`, `num_of_rows` |
| `mof_ocean_water_quality_check` | `station_code` | `page_no`, `num_of_rows` |
| `mfds_easy_drug_info_lookup` | none | `item_name`, `page_no`, `num_of_rows` |
| `mpm_public_job_lookup` | none | `pblanc_ty`, `instt_se`, `sort_order`, `page_no`, `num_of_rows` |
| `pps_shopping_mall_product_lookup` | none | `inqry_div`, `prdct_clsfc_no_nm`, `page_no`, `num_of_rows` |
| `ksd_financial_term_lookup` | `term` | `page_no`, `num_of_rows` |
| `mss_sme_support_notice_lookup` | none | `hashtags`, `page_no`, `num_of_rows` |
| `ccourt_publication_documents` | none | `title`, `page_no`, `num_of_rows` |
| `moj_stay_person_counter` | `search_ym` | `page_no`, `num_of_rows` |
| `msit_business_announcement_lookup` | none | `page_no`, `num_of_rows`, `return_type` |

## Terminal Smoke Transcript

The smoke artifact records:

- prompt text
- selected root primitive
- selected adapter ID
- parameter object
- result status
- abnormal flow notes
- fix status

No API key, token, or secret value may be recorded.
