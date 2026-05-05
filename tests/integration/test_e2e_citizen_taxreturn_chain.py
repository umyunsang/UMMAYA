# SPDX-License-Identifier: Apache-2.0
"""T032 — US1 end-to-end integration: citizen tax-return chain.

Covers all 4 US1 acceptance scenarios from spec.md:

  Scenario 1 (happy chain):
    verify(modid) → lookup(hometax_simplified) → submit(hometax_taxreturn)
    Asserts exactly 3 ledger events sharing the same delegation_token.

  Scenario 2 (submit scope validation):
    A valid delegation token with correct scope reaches submit and succeeds.
    Asserts receipt_id in the response and in the delegation_used event.

  Scenario 3 (scope violation):
    A submit call with a token that does NOT carry the required submit scope
    is rejected.  Asserts 4 ledger events (1 issued + 1 lookup-used + 2 submit
    attempts — but only 3 are the canonical happy-chain events; this scenario
    verifies the reject path separately).

  Scenario 4 (transparency fields):
    Every response in the verify → lookup → submit chain carries all six
    transparency fields (_mode, _reference_implementation, _actual_endpoint_when_live,
    _security_wrapping_pattern, _policy_authority, _international_reference).

Strategy:
- Import mock adapters directly (in-process — no subprocess).
- Use a temporary ledger directory (tmp_path fixture) so tests are isolated.
- Chain: invoke verify_module_modid → invoke lookup_module_hometax_simplified → invoke
  submit_module_hometax_taxreturn using the DelegationContext returned by verify.

SC-001: chain completes < 30 s wall-clock.
SC-002: 3 ledger lines for happy chain, all sharing the same delegation_token.
SC-007: scope-violation path returns SubmitStatus.rejected, not an exception.
FR-005: all six transparency fields present and non-empty.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

# Six transparency field keys (FR-005)
_TRANSPARENCY_KEYS = frozenset(
    {
        "_mode",
        "_reference_implementation",
        "_actual_endpoint_when_live",
        "_security_wrapping_pattern",
        "_policy_authority",
        "_international_reference",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_session_id() -> str:
    """Return a fresh UUID4 session identifier."""
    return str(uuid.uuid4())


def _invoke_modid_verify(
    session_id: str,
    scope_list: list[str],
    ledger_root: Path,
) -> dict:
    """Invoke the modid verify adapter and return the stamped dict.

    Imports are lazy so the test module can be collected without circular imports.
    """
    from kosmos.tools.mock.verify_module_modid import invoke  # noqa: PLC0415

    return invoke(
        {
            "scope_list": scope_list,
            "session_id": session_id,
            "purpose_ko": "2024년 귀속 종합소득세 신고",
            "purpose_en": "Filing 2024 comprehensive income tax return",
            "ledger_root": ledger_root,
        }
    )


async def _invoke_hometax_lookup(
    delegation_context: object,
    year: int = 2024,
    resident_id_prefix: str = "900101",
    session_id: str = "",
    ledger_root: Path | None = None,
) -> dict:
    """Invoke the hometax simplified lookup adapter."""
    from kosmos.tools.mock.lookup_module_hometax_simplified import (  # noqa: PLC0415
        HometaxSimplifiedInput,
        handle,
    )

    inp = HometaxSimplifiedInput(year=year, resident_id_prefix=resident_id_prefix)

    # If a delegation_context is provided, validate scope + append ledger event.
    from kosmos.primitives.delegation import DelegationContext  # noqa: PLC0415

    if isinstance(delegation_context, DelegationContext) and ledger_root is not None:
        # Manually append delegation_used for lookup (the handle() function does not
        # auto-append because lookup is read-only; the ledger append is the submit
        # adapter's responsibility for write operations, and lookup delegates to the
        # adapter's own scope check).  For the integration test we simulate the
        # delegation_used event for a lookup (mirrors quickstart § 4).
        token = delegation_context.token
        from kosmos.memdir.consent_ledger import (  # noqa: PLC0415
            DelegationUsedEvent,
            append_delegation_used,
        )

        append_delegation_used(
            DelegationUsedEvent(
                ts=datetime.now(UTC),
                session_id=session_id,
                delegation_token=token.delegation_token,
                consumer_tool_id="mock_lookup_module_hometax_simplified",
                outcome="success",
                receipt_id=None,
            ),
            ledger_root=ledger_root,
        )

    return await handle(inp, delegation_context=delegation_context)


async def _invoke_hometax_submit(
    delegation_context: object,
    session_id: str,
    ledger_root: Path,
) -> object:
    """Invoke the hometax tax-return submit adapter with a patched ledger root.

    The submit adapter imports ``append_delegation_used`` at module level (top-level import),
    so we must patch it at the submit module's namespace:
        ``kosmos.tools.mock.submit_module_hometax_taxreturn.append_delegation_used``

    ``FileLedgerReader`` is imported lazily inside ``invoke()``, so patching
    ``kosmos.memdir.consent_ledger.FileLedgerReader`` (the source module) ensures the
    lazy import gets the test-scoped class.
    """
    from unittest.mock import patch  # noqa: PLC0415

    import kosmos.tools.mock.submit_module_hometax_taxreturn as _submit_mod  # noqa: PLC0415
    from kosmos.tools.mock.submit_module_hometax_taxreturn import invoke  # noqa: PLC0415

    params = {
        "tax_year": 2024,
        "income_type": "종합소득",
        "total_income_krw": 42_000_000,
        "session_id": session_id,
        "delegation_context": delegation_context,
    }

    from kosmos.memdir.consent_ledger import (  # noqa: PLC0415
        DelegationUsedEvent,
        FileLedgerReader,
        append_delegation_used,
    )

    patched_reader = FileLedgerReader(ledger_root=ledger_root)
    original_append = append_delegation_used

    def _patched_append(event: DelegationUsedEvent, **kwargs: object) -> Path:
        return original_append(event, ledger_root=ledger_root)

    # Patch append_delegation_used where it was bound (top-level import in submit module).
    # Patch FileLedgerReader at source module (lazy import inside invoke()).
    with (
        patch.object(_submit_mod, "append_delegation_used", side_effect=_patched_append),
        patch(
            "kosmos.memdir.consent_ledger.FileLedgerReader",
            return_value=patched_reader,
        ),
    ):
        return await invoke(params)


def _read_ledger_events(ledger_root: Path) -> list:
    """Read all delegation events from the ledger root."""
    from kosmos.memdir.consent_ledger import read_delegation_events  # noqa: PLC0415

    return read_delegation_events(ledger_root=ledger_root)


def _has_all_transparency_fields(d: dict) -> bool:
    """Return True if the dict contains all six transparency fields with non-empty values.

    Also accepts the LookupOutput envelope shape ``{"kind": "record", "item": {...}}``
    (B1 envelope-contract fix, 2026-05-04) — the six transparency fields live
    inside ``item`` because the outer LookupRecord envelope is ``extra='forbid'``.
    """
    # Lookup envelope variant — fields live inside `item`.
    if d.get("kind") == "record" and isinstance(d.get("item"), dict):
        return all(d["item"].get(k, "") for k in _TRANSPARENCY_KEYS)
    # Verify (typed AuthContext.model_dump) / submit (adapter_receipt dict) shapes
    # still stamp at the top level.
    return all(d.get(k, "") for k in _TRANSPARENCY_KEYS)


# ---------------------------------------------------------------------------
# Scenario 1 — Happy chain: verify → lookup → submit; 3 ledger events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_chain_verify_lookup_submit(tmp_path: Path) -> None:
    """Scenario 1: full citizen tax-return chain succeeds.

    SC-001: < 30 s wall-clock.
    SC-002: exactly 3 ledger events sharing the same delegation_token.
    """
    t0 = time.monotonic()
    session_id = _new_session_id()
    ledger_root = tmp_path / "consent"

    # Register the issuance session in the ledger BEFORE submit (so session-binding check passes).
    # Step 1: verify
    scope_list = ["lookup:hometax.simplified", "submit:hometax.tax-return"]
    verify_result = _invoke_modid_verify(session_id, scope_list, ledger_root)

    # Spec 2296 Codex P1 #2446 fix — verify mocks now return typed AuthContext
    # variants instead of stamped dicts. ModidContext wraps the DelegationContext
    # under the `delegation_context` field; transparency fields surface as
    # `transparency_*` attributes.
    from kosmos.primitives.verify import ModidContext  # noqa: PLC0415

    assert isinstance(verify_result, ModidContext), (
        f"verify result must be a typed ModidContext (Codex P1 #2446); "
        f"got {type(verify_result).__name__}"
    )
    assert verify_result.transparency_mode == "mock", (
        f"verify result missing transparency_mode='mock'; got {verify_result.transparency_mode!r}"
    )
    delegation_ctx = verify_result.delegation_context

    # Step 2: lookup
    lookup_result = await _invoke_hometax_lookup(
        delegation_ctx,
        year=2024,
        resident_id_prefix="900101",
        session_id=session_id,
        ledger_root=ledger_root,
    )

    assert isinstance(lookup_result, dict), "lookup result must be a dict"
    assert _has_all_transparency_fields(lookup_result), (
        f"lookup response missing transparency fields: {lookup_result.keys()}"
    )

    # Step 3: submit — _invoke_hometax_submit patches the ledger helpers internally.
    submit_result = await _invoke_hometax_submit(delegation_ctx, session_id, ledger_root)

    from kosmos.primitives.submit import SubmitOutput, SubmitStatus  # noqa: PLC0415

    assert isinstance(submit_result, SubmitOutput), (
        f"Expected SubmitOutput, got {type(submit_result).__name__}"
    )
    assert submit_result.status == SubmitStatus.succeeded, (
        f"Expected succeeded, got {submit_result.status}"
    )

    # receipt_id must be a hometax- prefixed string.
    receipt_id = submit_result.adapter_receipt.get("receipt_id")
    assert isinstance(receipt_id, str) and receipt_id.startswith("hometax-"), (
        f"Expected hometax- receipt_id, got {receipt_id!r}"
    )

    # SC-002: read ledger, assert 3 events with the same delegation_token.
    events = _read_ledger_events(ledger_root)
    token_value = delegation_ctx.token.delegation_token

    # Filter events for this session token.
    relevant = [e for e in events if e.delegation_token == token_value]
    assert len(relevant) == 3, (
        f"Expected 3 ledger events for token {token_value[:12]}..., got {len(relevant)}: "
        f"{[type(e).__name__ + ':' + e.kind for e in relevant]}"
    )

    kinds = [e.kind for e in relevant]
    assert "delegation_issued" in kinds, "Missing delegation_issued event"
    delegation_used_events = [e for e in relevant if e.kind == "delegation_used"]
    assert len(delegation_used_events) == 2, (
        f"Expected 2 delegation_used events, got {len(delegation_used_events)}"
    )

    # SC-001: < 30 s.
    elapsed = time.monotonic() - t0
    assert elapsed < 30.0, f"Happy chain took {elapsed:.2f}s (SC-001 limit: 30s)"


# ---------------------------------------------------------------------------
# Scenario 2 — Submit succeeds with matching scope + token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_succeeds_with_matching_scope(tmp_path: Path) -> None:
    """Scenario 2: submit with correct scope → succeeded + receipt_id in response."""
    session_id = _new_session_id()
    ledger_root = tmp_path / "consent"

    # Issue a token with the submit scope.
    scope_list = ["submit:hometax.tax-return"]
    verify_result = _invoke_modid_verify(session_id, scope_list, ledger_root)
    delegation_ctx = verify_result.delegation_context

    submit_result = await _invoke_hometax_submit(delegation_ctx, session_id, ledger_root)

    from kosmos.primitives.submit import SubmitOutput, SubmitStatus  # noqa: PLC0415

    assert isinstance(submit_result, SubmitOutput)
    assert submit_result.status == SubmitStatus.succeeded

    receipt_id = submit_result.adapter_receipt.get("receipt_id")
    assert isinstance(receipt_id, str) and receipt_id.startswith("hometax-"), (
        f"receipt_id must start with 'hometax-', got {receipt_id!r}"
    )

    # The delegation_used event in the ledger must carry the receipt_id.
    events = _read_ledger_events(ledger_root)
    from kosmos.memdir.consent_ledger import DelegationUsedEvent  # noqa: PLC0415

    used_events = [
        e
        for e in events
        if isinstance(e, DelegationUsedEvent)
        and e.consumer_tool_id == "mock_submit_module_hometax_taxreturn"
        and e.outcome == "success"
    ]
    assert len(used_events) >= 1
    assert used_events[-1].receipt_id == receipt_id, (
        f"Ledger receipt_id {used_events[-1].receipt_id!r} != response {receipt_id!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Scope violation: rejected path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scope_violation_rejected(tmp_path: Path) -> None:
    """Scenario 3: token with wrong scope → SubmitStatus.rejected (SC-007).

    The token is issued with only the lookup scope; the submit adapter requires
    'submit:hometax.tax-return' — scope check fails.
    """
    session_id = _new_session_id()
    ledger_root = tmp_path / "consent"

    # Issue a token with ONLY the lookup scope (missing submit scope).
    scope_list = ["lookup:hometax.simplified"]
    verify_result = _invoke_modid_verify(session_id, scope_list, ledger_root)
    delegation_ctx = verify_result.delegation_context

    submit_result = await _invoke_hometax_submit(delegation_ctx, session_id, ledger_root)

    from kosmos.primitives.submit import SubmitOutput, SubmitStatus  # noqa: PLC0415

    assert isinstance(submit_result, SubmitOutput), (
        f"Expected SubmitOutput on scope violation, got {type(submit_result).__name__}"
    )
    assert submit_result.status == SubmitStatus.rejected, (
        f"Expected rejected status on scope violation, got {submit_result.status}"
    )

    # The adapter_receipt should indicate scope_violation.
    error_val = submit_result.adapter_receipt.get("error", "")
    assert "scope_violation" in str(error_val), (
        f"Expected scope_violation in adapter_receipt, got {submit_result.adapter_receipt}"
    )

    # Ledger should have delegation_issued + delegation_used(scope_violation).
    events = _read_ledger_events(ledger_root)
    token_value = delegation_ctx.token.delegation_token
    relevant = [e for e in events if e.delegation_token == token_value]

    # At minimum: 1 issued + 1 used(scope_violation).
    assert len(relevant) >= 2, (
        f"Expected >= 2 ledger events for scope-violation scenario, got {len(relevant)}"
    )

    from kosmos.memdir.consent_ledger import DelegationUsedEvent  # noqa: PLC0415

    used_events = [
        e for e in relevant if isinstance(e, DelegationUsedEvent) and e.outcome == "scope_violation"
    ]
    assert len(used_events) >= 1, "Expected at least one delegation_used(scope_violation) event"


# ---------------------------------------------------------------------------
# Scenario 4 — All six transparency fields present in every step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_transparency_fields_in_chain(tmp_path: Path) -> None:
    """Scenario 4: every step in the chain carries all six transparency fields.

    FR-005, SC-005: _mode, _reference_implementation, _actual_endpoint_when_live,
    _security_wrapping_pattern, _policy_authority, _international_reference all present
    and non-empty.
    """
    session_id = _new_session_id()
    ledger_root = tmp_path / "consent"

    scope_list = ["lookup:hometax.simplified", "submit:hometax.tax-return"]

    # Step 1: verify
    verify_result = _invoke_modid_verify(session_id, scope_list, ledger_root)
    # Spec 2296 Codex P1 #2446 fix — typed AuthContext returns instead of dict.
    # The 6 transparency fields are now attributes (transparency_*) on the typed
    # context; we serialize via model_dump(by_alias=True) to apply the same
    # _has_all_transparency_fields check that we use for downstream dict responses.
    verify_dump = verify_result.model_dump(by_alias=True)
    assert _has_all_transparency_fields(verify_dump), (
        f"verify response missing transparency fields.\n"
        f"Present keys: {sorted(verify_dump.keys())}\n"
        f"Missing: {_TRANSPARENCY_KEYS - set(verify_dump.keys())}"
    )
    delegation_ctx = verify_result.delegation_context

    # Step 2: lookup
    lookup_result = await _invoke_hometax_lookup(
        delegation_ctx,
        year=2024,
        resident_id_prefix="851201",
        session_id=session_id,
        ledger_root=ledger_root,
    )
    assert isinstance(lookup_result, dict)
    assert _has_all_transparency_fields(lookup_result), (
        f"lookup response missing transparency fields.\n"
        f"Present keys: {sorted(lookup_result.keys())}\n"
        f"Missing: {_TRANSPARENCY_KEYS - set(lookup_result.keys())}"
    )

    # Step 3: submit — ledger patched inside _invoke_hometax_submit.
    submit_result = await _invoke_hometax_submit(delegation_ctx, session_id, ledger_root)

    from kosmos.primitives.submit import SubmitOutput  # noqa: PLC0415

    assert isinstance(submit_result, SubmitOutput)
    # The adapter_receipt carries the transparency fields (merged by stamp_mock_response).
    assert _has_all_transparency_fields(submit_result.adapter_receipt), (
        f"submit adapter_receipt missing transparency fields.\n"
        f"Present keys: {sorted(submit_result.adapter_receipt.keys())}\n"
        f"Missing: {_TRANSPARENCY_KEYS - set(submit_result.adapter_receipt.keys())}"
    )
