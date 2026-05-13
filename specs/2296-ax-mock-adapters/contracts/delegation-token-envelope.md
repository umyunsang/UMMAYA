# Contract — `DelegationToken` / `DelegationContext` Envelope

**Spec**: [../spec.md](../spec.md) FR-007 / FR-008 / FR-009 / FR-010 / FR-011 / FR-012 / FR-013 / FR-014
**Data model**: [../data-model.md § 1 + § 2 + § 3](../data-model.md)
**Reference**: `delegation-flow-design.md § 5.6` (origin shape) + `§ 12.7` (3rd correction final)

---

## 1. Issuance contract

A `DelegationToken` is **issued** by exactly one verify mock adapter as a side effect of a successful citizen-side ceremony simulation. The verify adapter MUST:

1. Construct a `DelegationToken` with all 7 fields populated and validators passing
2. Wrap it in a `DelegationContext` with bilingual purpose strings sourced from the citizen request (the LLM determines the purpose from the conversation context and supplies it via the verify call's `params.purpose_ko` / `params.purpose_en`)
3. Append a `delegation_issued` event to the consent ledger before returning
4. Return the `DelegationContext` to the caller (the LLM stores it in tool-call context for the next step)

Special case: `mock_verify_module_any_id_sso` does NOT issue a `DelegationToken`. It returns an `IdentityAssertion` instead (see [data-model.md § 3](../data-model.md)). Audit-ledger entry kind is `verify_identity_only` (existing Spec 035 event kind, NOT one of the new `delegation_*` kinds).

## 2. Consumption contract

A `DelegationToken` is **consumed** by exactly one submit or lookup adapter per call. The consumer adapter MUST:

1. Extract the token from the call context (typically a `DelegationContext` parameter)
2. Invoke `_validate_delegation(token, expected_scope=<adapter-declared-scope-prefix>, current_session_id)` which returns `Ok` or one of four rejection reasons:
   - `Expired` — `token.expires_at <= now()`
   - `ScopeViolation` — `token.scope` doesn't match the adapter's declared scope prefix (e.g., adapter declares `send:hometax.tax-return`; token scope is `send:gov24.minwon` → reject)
   - `SessionViolation` — token was issued in a different session than the consuming call
   - `Revoked` — the token appears in the session's in-memory revocation set
3. On rejection: append a `delegation_used` event with `outcome` set to the rejection reason; return error to caller; do NOT execute the agency action
4. On success: execute the agency action (in Mock: produce a synthetic 접수번호 from a deterministic fixture); append a `delegation_used` event with `outcome="success"` and `receipt_id` populated for submit; return result to caller

## 3. Scope grammar

`scope` strings follow the format `<verb>:<adapter_family>.<action>`:

```text
verb           = "lookup" | "submit" | "verify" | "subscribe"
adapter_family = lowercase identifier matching the adapter's domain root
                 (e.g., "hometax", "gov24", "modid", "kec")
action         = lowercase identifier with optional hyphens, identifying the action
                 (e.g., "tax-return", "minwon", "simplified")
```

**Examples**:
- `send:hometax.tax-return` — the `mock_submit_module_hometax_taxreturn` adapter's required scope
- `find:hometax.simplified` — the `mock_lookup_module_hometax_simplified` adapter's required scope
- `send:gov24.minwon` — the `mock_submit_module_gov24_minwon` adapter's required scope

A token whose scope is `send:hometax.tax-return` permits BOTH the submit adapter AND a lookup adapter that declares scope-prefix-match (e.g., a lookup that declares `find:hometax.simplified` does NOT match — the verbs differ; the scope must be reissued for the lookup verb). However, the cleanest UX is for the verify adapter to issue a **multi-scope token** by using a comma-joined scope string in the future. Epic ε ships **single-scope tokens only**; multi-scope is a deferred enhancement.

**Implication for US1 chain**: the citizen's "내 종합소득세 신고해줘" request requires the LLM to call `verify` requesting a scope that covers BOTH `find:hometax.simplified` AND `send:hometax.tax-return`. Epic ε's solution: the verify adapter's input includes a `scope_list: list[str]` parameter, and the issued token's `scope` field stores the comma-joined string `"find:hometax.simplified,send:hometax.tax-return"`. The validator regex updates to accept the comma-joined form: `^((lookup|submit|verify|subscribe):[a-z0-9_]+\.[a-z0-9_-]+)(,(lookup|submit|verify|subscribe):[a-z0-9_]+\.[a-z0-9_-]+)*$`.

The scope-violation acceptance scenario (US1 acceptance #3) tests that a token with `scope="find:hometax.simplified,send:hometax.tax-return"` is rejected by `mock_submit_module_gov24_minwon` (which requires `send:gov24.minwon` — not in the token's comma-list).

## 4. Token-validation function

```python
# src/ummaya/primitives/delegation.py

from datetime import datetime, UTC
from enum import Enum

class DelegationValidationOutcome(str, Enum):
    OK = "ok"
    EXPIRED = "expired"
    SCOPE_VIOLATION = "scope_violation"
    SESSION_VIOLATION = "session_violation"
    REVOKED = "revoked"

async def validate_delegation(
    context: DelegationContext,
    *,
    required_scope: str,
    current_session_id: str,
    revoked_set: set[str],
    ledger_reader: LedgerReader,
) -> DelegationValidationOutcome:
    """Validate a delegation token against scope, expiry, session, and revocation.

    All four checks are independent; the function returns the FIRST violation
    found, in the order: expired → scope → session → revoked. Order is
    chosen so the citizen sees the most actionable error first.
    """
    token = context.token

    if token.expires_at <= datetime.now(UTC):
        return DelegationValidationOutcome.EXPIRED

    if not _scope_matches(token.scope, required_scope):
        return DelegationValidationOutcome.SCOPE_VIOLATION

    issued_session_id = await ledger_reader.find_issuance_session(token.delegation_token)
    if issued_session_id != current_session_id:
        return DelegationValidationOutcome.SESSION_VIOLATION

    if token.delegation_token in revoked_set:
        return DelegationValidationOutcome.REVOKED

    return DelegationValidationOutcome.OK


def _scope_matches(token_scope: str, required: str) -> bool:
    """Return True if `required` (e.g., 'send:hometax.tax-return') is one
    of the comma-joined scope entries in `token_scope`.
    """
    return required in token_scope.split(",")
```

## 5. Audit ledger contract

Every issuance + use + revocation appends exactly one JSONL line to `~/.ummaya/memdir/user/consent/<YYYY-MM-DD>.jsonl`. The append path is unchanged from Spec 035 (`open(path, "a")` + `json.dumps()` + fsync); only the new event-kind union members are added.

**Per US1 chain run** (one citizen request, no scope violations), exactly **3** new ledger lines:

```jsonl
{"kind":"delegation_issued","ts":"2026-04-29T10:15:23.456Z","session_id":"sess-abc","delegation_token":"del_xyz123...","scope":"find:hometax.simplified,send:hometax.tax-return","expires_at":"2026-04-30T10:15:23.456Z","issuer_did":"did:web:mobileid.go.kr","verify_tool_id":"mock_verify_module_modid","_mode":"mock"}
{"kind":"delegation_used","ts":"2026-04-29T10:15:28.789Z","session_id":"sess-abc","delegation_token":"del_xyz123...","consumer_tool_id":"mock_lookup_module_hometax_simplified","receipt_id":null,"outcome":"success"}
{"kind":"delegation_used","ts":"2026-04-29T10:15:35.012Z","session_id":"sess-abc","delegation_token":"del_xyz123...","consumer_tool_id":"mock_submit_module_hometax_taxreturn","receipt_id":"hometax-2026-04-29-RX-7K2J9","outcome":"success"}
```

The scope-violation scenario (US1 acceptance #3) appends a 4th line:

```jsonl
{"kind":"delegation_used","ts":"2026-04-29T10:15:42.345Z","session_id":"sess-abc","delegation_token":"del_xyz123...","consumer_tool_id":"mock_submit_module_gov24_minwon","receipt_id":null,"outcome":"scope_violation"}
```

**SC-002** assertion: integration test invokes the US1 chain, then `read_consent_ledger()` and asserts exactly 3 new lines for the no-violation path (or 4 for the scope-violation path), all referencing the same `delegation_token` value.

## 6. Revocation flow

The TUI surfaces `/consent revoke <token_prefix>` as a slash command (existing Spec 035 surface). When the citizen invokes:

1. The TUI sends a backend RPC (existing `permission_response` frame variant or a new dedicated frame — Epic ε reuses the existing `SessionEventFrame` with `event_kind="consent_revoke"`)
2. The backend appends a `delegation_revoked` event to the ledger
3. The backend adds the token to the session's in-memory revocation set
4. The next attempt to use the token returns `DelegationValidationOutcome.REVOKED`

The session-scoped revocation set is **not** persisted across sessions because:
- Tokens have `expires_at <= 24h`; surviving the session is unlikely
- The audit ledger is the source of truth; on a session restart, the ledger reader can replay revocation events to rebuild the set if needed (deferred — current spec does not implement replay)

## 7. Failure modes

| Mode | Trigger | Outcome |
|---|---|---|
| Verify adapter constructs token with `expires_at <= issued_at` | Bug | `DelegationToken` validator raises `ValueError` at construction; verify call fails; no ledger entry; LLM sees `VerifyFailure` |
| Verify adapter mints token with malformed `scope` | Bug | Same as above (regex validator) |
| Submit adapter receives expired token | Token age > 24h | `outcome="expired"` ledger entry; LLM sees explicit `DelegationTokenExpired` error; LLM is expected to call `verify` again |
| Submit adapter receives scope-mismatched token | LLM mis-routes | `outcome="scope_violation"` ledger entry; LLM sees `ScopeViolation` error |
| Submit adapter receives token from a different session | Cross-session replay attempt | `outcome="session_violation"` ledger entry; LLM sees `SessionViolation` error |
| Citizen revokes mid-chain | `/consent revoke` between lookup and submit | `delegation_revoked` event appended; submit's token check returns `REVOKED`; submit fails closed |
| Mock backend forgets to append `delegation_issued` ledger event | Implementation bug | Subsequent `delegation_used` event references a token with no issuance record; the ledger-reader audit utility flags as orphan; CI test surfaces |

## 8. Test surface

Mandatory tests gated by this contract:

1. `test_delegation_token_construction.py` — happy + 4 validator failure paths
2. `test_delegation_token_scope_match.py` — `_scope_matches` table-driven 8+ cases (single, comma, prefix-not-substring, etc.)
3. `test_delegation_token_validation.py` — `validate_delegation` 5 outcome paths
4. `test_consent_ledger_delegation_events.py` — ledger append + parse round-trip for all 3 event kinds
5. `test_e2e_citizen_taxreturn_chain.py` — full US1 chain with ledger assertions (3 lines, matching token value)
6. `test_e2e_scope_violation_rejection.py` — US1 acceptance scenario #3 with ledger assertion (4 lines, last one `scope_violation`)
7. `test_e2e_token_expiry_midchain.py` — Edge case: token expiry between lookup and submit
8. `test_e2e_token_session_violation.py` — Edge case: token issued in session A, used in session B
9. `test_any_id_sso_returns_identity_assertion_not_delegation.py` — assert `mock_verify_module_any_id_sso` returns `IdentityAssertion`, not `DelegationContext`; downstream submit fails with `DelegationGrantMissing`
10. `test_revoke_via_consent_command.py` — full revocation flow round-trip

All ten tests gate FR-007–FR-014.
