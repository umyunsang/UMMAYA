# Contract — Shadow-Eval Fixture Schema

**Spec**: [../spec.md](../spec.md) FR-014 / FR-015
**Data model**: [../data-model.md § E-3](../data-model.md)
**Reference**: `specs/026-cicd-prompt-registry/spec.md` § Shadow-eval workflow

---

## 1. Directory Layout

```text
tests/fixtures/shadow_eval/citizen_chain/
├── _schema.py                          # NEW — Pydantic v2 fixture schema (≤ 30 LOC)
├── simple_auth_module.json             # NEW — Epic ε family fixture
├── modid.json                          # NEW — US1 canonical chain fixture
├── kec.json                            # NEW
├── geumyung_module.json                # NEW
├── any_id_sso.json                     # NEW — IdentityAssertion-only family
└── _existing_lookup_only/              # EXISTING (regression set, untouched)
    ├── weather_basic.json
    ├── hospital_search.json
    ├── emergency_room.json
    ├── road_accident.json
    ├── welfare_eligibility.json
    ├── location_resolve.json
    ├── no_tool_fallback.json
    └── kma_observation.json
```

The 5 NEW fixtures are at the citizen_chain root. The 8 existing lookup-only fixtures stay under `_existing_lookup_only/` (the underscore prefix matches Spec 026 convention for "regression set, do not delete").

## 2. Schema (Pydantic v2)

`tests/fixtures/shadow_eval/citizen_chain/_schema.py`:

```python
# SPDX-License-Identifier: Apache-2.0
"""Shadow-eval fixture schema for Epic η #2298 citizen chain teaching.

Each fixture file is a single JSON object loaded by
tests/integration/test_shadow_eval_citizen_chain_fixtures.py and consumed by
.github/workflows/shadow-eval.yml twin-run runner.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ExpectedToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: Literal["verify", "lookup", "submit", "subscribe", "resolve_location"]
    arguments: dict[str, str | list[str]] = Field(default_factory=dict)


class CitizenChainFixture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    fixture_id: str = Field(pattern=r"^[a-z0-9_]+$", min_length=3, max_length=64)
    citizen_prompt: str = Field(min_length=1, max_length=200)
    expected_first_tool_call: ExpectedToolCall
    expected_family_hint: str | None = None
    notes: str | None = None
```

Cross-field validation (asserted by the loader test, not the model):

- If `expected_first_tool_call.name == "verify"`, then `expected_family_hint` MUST be non-None and equal `expected_first_tool_call.arguments["family_hint"]`.
- `expected_family_hint`, when set, MUST be one of the 10 active family literals (NOT `digital_onepass`).

## 3. Fixture File Format

Five JSON files. Schema enforced at load time.

### 3.1 `modid.json` (US1 canonical, P1)

```json
{
  "fixture_id": "modid_taxreturn_canonical",
  "citizen_prompt": "내 종합소득세 신고해줘",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "family_hint": "modid"
    }
  },
  "expected_family_hint": "modid",
  "notes": "US1 canonical chain. Downstream chain: lookup(hometax_simplified) → submit(hometax_taxreturn). scope_list MUST include both find:hometax.simplified and send:hometax.tax-return."
}
```

### 3.2 `simple_auth_module.json` (P2)

```json
{
  "fixture_id": "simple_auth_gov24_minwon",
  "citizen_prompt": "정부24 민원 하나 신청해줘",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "family_hint": "simple_auth_module"
    }
  },
  "expected_family_hint": "simple_auth_module",
  "notes": "Citizen ambiguity: could match modid (AAL3) or simple_auth_module (AAL2). LLM MUST default to the lower AAL satisfying the request — that is simple_auth_module here."
}
```

### 3.3 `kec.json` (P2)

```json
{
  "fixture_id": "kec_corporate_registration",
  "citizen_prompt": "사업자 등록증 발급해줘",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "family_hint": "kec"
    }
  },
  "expected_family_hint": "kec",
  "notes": "Corporate authoritative document issuance — kec is the canonical family per Singapore APEX analog."
}
```

### 3.4 `geumyung_module.json` (P2)

```json
{
  "fixture_id": "geumyung_credit_lookup",
  "citizen_prompt": "내 신용정보 조회해줘",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "family_hint": "geumyung_module"
    }
  },
  "expected_family_hint": "geumyung_module",
  "notes": "Finance-domain. NOT mydata (mydata is broader / personal-data-portability-flavored), NOT modid (modid is identity not finance)."
}
```

### 3.5 `any_id_sso.json` (P2)

```json
{
  "fixture_id": "any_id_sso_login",
  "citizen_prompt": "다른 정부 사이트 SSO 로그인 좀",
  "expected_first_tool_call": {
    "name": "verify",
    "arguments": {
      "family_hint": "any_id_sso"
    }
  },
  "expected_family_hint": "any_id_sso",
  "notes": "any_id_sso returns IdentityAssertion only (no DelegationToken). The LLM MUST NOT chain a submit after this verify — UK GOV.UK One Login analog."
}
```

## 4. Loader Test Contract

`tests/integration/test_shadow_eval_citizen_chain_fixtures.py` (NEW, ≤ 80 LOC):

```python
"""T-XXX (Epic η) — Validate the 5 new shadow-eval fixtures load without error
and respect the cross-field invariants documented in
specs/2298-system-prompt-rewrite/contracts/shadow-eval-fixture-schema.md.

This test gates FR-015 + SC-004.
"""

from pathlib import Path
import json
import pytest
from tests.fixtures.shadow_eval.citizen_chain._schema import CitizenChainFixture

_FIXTURE_DIR = Path("tests/fixtures/shadow_eval/citizen_chain")
_ACTIVE_FAMILIES = frozenset({
    "gongdong_injeungseo", "geumyung_injeungseo", "ganpyeon_injeung",
    "mobile_id", "mydata",
    "simple_auth_module", "modid", "kec", "geumyung_module", "any_id_sso",
})

@pytest.mark.parametrize("fixture_path", sorted(_FIXTURE_DIR.glob("*.json")))
def test_fixture_loads_and_satisfies_invariants(fixture_path: Path) -> None:
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture = CitizenChainFixture.model_validate(raw)
    if fixture.expected_first_tool_call.name == "verify":
        assert fixture.expected_family_hint is not None, \
            f"{fixture_path.name}: verify call requires expected_family_hint"
        assert (
            fixture.expected_family_hint
            == fixture.expected_first_tool_call.arguments.get("family_hint")
        )
        assert fixture.expected_family_hint in _ACTIVE_FAMILIES
        assert fixture.expected_family_hint != "digital_onepass"

def test_fixture_count_matches_epic_target() -> None:
    """FR-015: exactly 5 new fixtures at the citizen_chain root."""
    json_files = [p for p in _FIXTURE_DIR.iterdir() if p.is_file() and p.suffix == ".json"]
    assert len(json_files) == 5, \
        f"Expected 5 new fixtures (FR-015), found {len(json_files)}: {[p.name for p in json_files]}"
```

## 5. Workflow Integration

`.github/workflows/shadow-eval.yml` already triggers on `prompts/**` PRs (Spec 026, FR-014). The new fixtures are auto-discovered by the workflow's twin-run runner because they sit in the canonical fixture root. The workflow:

1. Runs the `main` HEAD's `prompts/system_v1.md` against all fixtures (lookup-only + new citizen_chain) — produces `deployment.environment=main` OTEL spans.
2. Runs the PR head's `prompts/system_v1.md` against the same fixtures — produces `deployment.environment=shadow` OTEL spans.
3. Computes the diff: each fixture's `expected_first_tool_call` is matched (subset-match on arguments, exact match on name) against the LLM's first emitted tool_call.
4. Reports pass-rate per environment.

**SC-004 threshold**: shadow-environment pass rate ≥ 80 % on the 5 new citizen_chain fixtures. Lookup-only regression set MUST maintain its current pass rate (≥ 95 % per Spec 026 baseline; this Epic must not regress).

## 6. Failure Modes

| Mode | Trigger | Outcome |
|---|---|---|
| Fixture JSON malformed | `json.JSONDecodeError` | `pytest` fails at parametrize collection |
| `expected_family_hint = "digital_onepass"` | Author error | Cross-field test fails |
| `expected_first_tool_call.name = "verify"` but `expected_family_hint` is None | Author error | Cross-field test fails |
| Fixture count != 5 | Author adds/removes incorrectly | `test_fixture_count_matches_epic_target` fails |
| Shadow-eval pass rate < 80 % | Prompt regression | `.github/workflows/shadow-eval.yml` reports failure → PR cannot merge per SC-009 |
