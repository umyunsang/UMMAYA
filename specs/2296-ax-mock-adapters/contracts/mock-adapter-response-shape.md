# Contract — Mock Adapter Response Shape (Six Transparency Fields)

**Spec**: [../spec.md](../spec.md) FR-005 / FR-006 / FR-024 / FR-025 / SC-005
**Data model**: [../data-model.md § 7 + § 8](../data-model.md)

---

## 1. The contract

Every Mock adapter response payload (the dict returned by `invoke()` or the result of `call()`) MUST contain six top-level transparency fields. These fields are stamped by a single shared helper to prevent drift.

```python
# src/kosmos/tools/transparency.py

from typing import Any, Final

_MODE_VALUE: Final = "mock"

def stamp_mock_response(
    payload: dict[str, Any],
    *,
    reference_implementation: str,
    actual_endpoint_when_live: str,
    security_wrapping_pattern: str,
    policy_authority: str,
    international_reference: str,
) -> dict[str, Any]:
    """Stamp the six transparency fields onto a Mock adapter response payload.

    Pure function — caller passes a dict, gets a new dict back.

    Raises ValueError if any of the five caller-supplied values is empty.
    The `_mode` field is always 'mock' for Epic ε.
    """
    if not all(s.strip() for s in (
        reference_implementation,
        actual_endpoint_when_live,
        security_wrapping_pattern,
        policy_authority,
        international_reference,
    )):
        raise ValueError("All five transparency-field values must be non-empty strings.")

    return {
        **payload,
        "_mode": _MODE_VALUE,
        "_reference_implementation": reference_implementation,
        "_actual_endpoint_when_live": actual_endpoint_when_live,
        "_security_wrapping_pattern": security_wrapping_pattern,
        "_policy_authority": policy_authority,
        "_international_reference": international_reference,
    }
```

## 2. Field semantics + canonical examples

| Field | Type | Canonical examples | Constraint |
|---|---|---|---|
| `_mode` | `Literal["mock"]` | always `"mock"` | constant for Epic ε |
| `_reference_implementation` | `str` | `"ax-infrastructure-callable-channel"`, `"public-mydata-action-extension"`, `"public-mydata-read-v240930"` | non-empty |
| `_actual_endpoint_when_live` | `str` (URL) | `"https://api.gateway.kosmos.gov.kr/v1/verify/modid"`, `"https://hometax.go.kr/.../mock-future-llm-channel"` | non-empty, URL-shaped |
| `_security_wrapping_pattern` | `str` | `"OAuth2.1 + mTLS + scope-bound bearer"`, `"OID4VP + DID-resolved RP"`, `"마이데이터 표준동의서 OAuth2 + finAuth"` | non-empty |
| `_policy_authority` | `str` (URL) | `"https://www.mois.go.kr/.../public-mydata.do"`, `"https://www.kdca.go.kr/.../mobile-id.html"` | non-empty, URL-shaped, agency-published |
| `_international_reference` | `str` | `"Singapore APEX"`, `"Estonia X-Road"`, `"EU EUDI Wallet"`, `"Japan マイナポータル API"`, `"UK HMRC Making Tax Digital"` | non-empty |

## 3. Per-adapter constants (recommended pattern)

Every Mock adapter declares its five caller-supplied values as module-level constants:

```python
# src/kosmos/tools/mock/verify_module_modid.py

_REFERENCE_IMPL: Final = "ax-infrastructure-callable-channel"
_ACTUAL_ENDPOINT: Final = "https://api.gateway.kosmos.gov.kr/v1/verify/modid"
_SECURITY_WRAPPING: Final = "OID4VP + DID-resolved RP + DPoP"
_POLICY_AUTHORITY: Final = "https://www.mois.go.kr/.../mobile-id-policy.do"
_INTERNATIONAL_REF: Final = "EU EUDI Wallet"

def invoke(session_context: dict[str, Any]) -> dict[str, Any]:
    delegation = _build_delegation_payload(session_context)
    return stamp_mock_response(
        delegation,
        reference_implementation=_REFERENCE_IMPL,
        actual_endpoint_when_live=_ACTUAL_ENDPOINT,
        security_wrapping_pattern=_SECURITY_WRAPPING,
        policy_authority=_POLICY_AUTHORITY,
        international_reference=_INTERNATIONAL_REF,
    )
```

## 4. Catalog of canonical values per adapter

| Adapter (after Epic ε) | `_reference_implementation` | `_international_reference` |
|---|---|---|
| **NEW verify mocks** | | |
| `mock_verify_module_simple_auth` | `ax-infrastructure-callable-channel` | `Japan マイナポータル API` |
| `mock_verify_module_modid` | `ax-infrastructure-callable-channel` | `EU EUDI Wallet` |
| `mock_verify_module_kec` | `ax-infrastructure-callable-channel` | `Singapore APEX` |
| `mock_verify_module_geumyung` | `public-mydata-read-v240930` | `Singapore Myinfo` |
| `mock_verify_module_any_id_sso` | `ax-infrastructure-callable-channel` | `UK GOV.UK One Login` |
| **NEW submit mocks** | | |
| `mock_submit_module_hometax_taxreturn` | `ax-infrastructure-callable-channel` | `UK HMRC Making Tax Digital` |
| `mock_submit_module_gov24_minwon` | `ax-infrastructure-callable-channel` | `Singapore APEX` |
| `mock_submit_module_public_mydata_action` | `public-mydata-action-extension` | `Estonia X-Road` |
| **NEW lookup mocks** | | |
| `mock_lookup_module_hometax_simplified` | `public-mydata-read-v240930` | `UK HMRC Making Tax Digital` |
| `mock_lookup_module_gov24_certificate` | `public-mydata-read-v240930` | `Estonia X-Road` |
| **EXISTING (retrofitted)** | | |
| `mock_verify_mobile_id` | `public-mydata-read-v240930` | `EU EUDI Wallet` |
| `mock_verify_gongdong_injeungseo` | `public-mydata-read-v240930` | `Estonia X-Road (NPKI analog)` |
| `mock_verify_geumyung_injeungseo` | `public-mydata-read-v240930` | `Singapore Myinfo` |
| `mock_verify_ganpyeon_injeung` | `public-mydata-read-v240930` | `Japan JPKI` |
| `mock_verify_mydata` | `public-mydata-read-v240930` | `Singapore Myinfo` |
| `mock_traffic_fine_pay_v1` | `ax-infrastructure-callable-channel` | `UK GOV.UK Pay` |
| `mock_welfare_application_submit_v1` | `public-mydata-action-extension` | `Estonia X-Road` |
| `mock_cbs_disaster_v1` | `ax-infrastructure-callable-channel` | `EU CB-PWS (Cell Broadcast Public Warning System)` |
| `mock_rest_pull_tick_v1` | `ax-infrastructure-callable-channel` | `(generic REST polling)` |
| `mock_rss_public_notices_v1` | `ax-infrastructure-callable-channel` | `(generic RSS feed)` |

The `_actual_endpoint_when_live`, `_security_wrapping_pattern`, and `_policy_authority` per-adapter values are defined per-adapter in module-level constants; reviewers may copy from agency policy pages during implementation. URLs MUST be reachable at the time of merge (broken-URL CI check is a deferred concern; during implementation, manual verification suffices).

## 5. Regression test (FR-006)

The registry-wide transparency scan in `tests/unit/tools/test_mock_transparency_scan.py`:

```python
@pytest.mark.parametrize("adapter_id", _all_mock_adapter_ids())
async def test_mock_adapter_response_carries_six_transparency_fields(adapter_id: str) -> None:
    adapter = _resolve_adapter(adapter_id)
    response = await _invoke_with_synthetic_input(adapter)

    assert response.get("_mode") == "mock", f"{adapter_id} response missing _mode='mock'"
    for field in (
        "_reference_implementation",
        "_actual_endpoint_when_live",
        "_security_wrapping_pattern",
        "_policy_authority",
        "_international_reference",
    ):
        value = response.get(field)
        assert value is not None and isinstance(value, str) and value.strip(), \
            f"{adapter_id} response missing or empty {field!r}"
```

`_all_mock_adapter_ids()` enumerates all 20 Mock adapter IDs across all four sub-registries + main `ToolRegistry`. The test FAILS if any single adapter omits any single field. **One adapter, one omission → CI red**. This is the canonical drift-prevention.

## 6. Korean-language allowance (FR-024)

Korean text is permitted ONLY inside three transparency-field values:
- `_policy_authority` if the citation URL points to a Korean-language gov page (URL itself is ASCII)
- (Outside the six fields) `search_hint` and `llm_description` per Constitution § III

All other source text — variable names, comments, error messages, frame `kind` literal values, scope strings, citation-rendering UI labels — MUST be English.

## 7. Live-mode forward compatibility

Live adapters (when they ship in a future epic) MUST NOT call `stamp_mock_response`. The contract is:

- **Mock adapters**: stamp via `stamp_mock_response`; six fields populated
- **Live adapters**: do not stamp; six fields absent (or `_mode == "live"` if a Live-mode shape is added later)

The retrofit on existing context types adds the six fields as `Optional[str] = None`. Live adapters leave them `None`; the regression test filters by `source_mode == "mock"` before asserting non-None.

## 7a. Evidence-grade extension

Privileged channels whose public API exists but is institution-gated MAY attach two extra fields through `stamp_mock_response()`:

| Field | Type | Semantics |
|---|---|---|
| `_mock_fidelity_grade` | `str` | Human-readable evidence grade, e.g. `A-official-api-published`, `B-official-flow-private-spec-inferred`, `C-policy-mandated-inferred`. |
| `_mock_evidence` | `dict` | Evidence object with `credential_status`, `basis_urls`, `supports`, `inference_boundary`, and `live_swap_requirements`. |

These fields are additive. They do not replace the six mandatory transparency fields and they do not claim that KOSMOS knows a private agency schema. The required pattern is:

1. Record the official or policy source that proves the channel/flow exists.
2. State exactly which private payload details are inferred.
3. State which credentials or approvals would let the adapter swap from Mock to Live without changing the public primitive envelope.

## 8. Failure modes

| Mode | Trigger | Behaviour |
|---|---|---|
| **Adapter forgets to stamp** | New mock adapter author skips `stamp_mock_response` | Regression test FAILS in CI with the offending adapter ID and which field is missing |
| **Adapter passes empty string** | Bug in per-adapter constants | `stamp_mock_response` raises `ValueError` at call time |
| **Live adapter accidentally stamps** | Mistake | No CI catch from this contract; reviewer comment expected. Future epic could add a `source_mode != "mock"` assertion in the helper |
