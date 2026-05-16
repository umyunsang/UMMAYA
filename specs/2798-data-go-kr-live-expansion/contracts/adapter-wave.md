# Adapter Wave Contract: data.go.kr Live Expansion

## Included Adapter Contract

Every included adapter must satisfy:

- One `VerifiedAdapterSpec` manifest row.
- One thin module under `src/ummaya/tools/verified_data_go_kr/`.
- `GovAPITool.adapter_mode == "live"`.
- `GovAPITool.policy.real_classification_url` points at the agency/data portal policy source.
- `GovAPITool.policy.citizen_facing_gate == "read-only"`.
- Strict Pydantic v2 input schema with `extra="forbid"`.
- Output schema is the verified public-data collection envelope.
- Default tests replay saved fixture bytes only.

## Special Transport Contracts

| Tool ID | Required Contract |
|---------|-------------------|
| `moj_stay_person_counter` | `auth_query_param="ServiceKey"` and `searchYm` query parameter. |
| `msit_business_announcement_lookup` | Browser-like `User-Agent` header on live HTTP calls. |
| `moj_village_lawyer_lookup` | HTTP gateway endpoint from direct successful evidence. |

## Exclusion Contract

The registry must not contain live tools for:

- `kcue_academyinfo_finance_lookup`
- `ekape_animal_trace_lookup`
- `data_go_kr_uiryeong_civil_defense_shelters`

Corresponding blocked dataset IDs:

- `15038392`
- `15058923`
- `15063444`

## Registry Count Contract

After implementation:

- Main registry total increases from 52 to 68.
- Live adapter count increases from 26 to 42.
- Verified public-data adapter count increases from 14 to 30.

## Terminal Smoke Contract

The real-use smoke must include at least these prompt classes:

1. Safety location: AED or emergency call box.
2. Medical/drug information: MFDS drug information or HIRA institution detail.
3. Support notice: MSIT business announcement or MSS SME support notice.
4. Transport: Daejeon subway fare/time or TAGO bus flow.
5. Statistics/transparency: MOJ stay-person counter, KSD term, or Constitutional Court publication.

For each class, record whether the LLM emitted the expected root primitive and adapter ID.
