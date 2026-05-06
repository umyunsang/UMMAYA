# SPDX-License-Identifier: Apache-2.0
"""B1 — LookupOutput envelope contract regression for lookup mock adapters.

Reproduces the snap-S8-002 regression where ``primitive='lookup'`` mock
adapters returned a flat stamped dict
without the ``kind`` discriminator, causing
``EnvelopeNormalizationError: tagged-union[…] Unable to extract tag``
inside ``kosmos.tools.envelope.normalize`` and triggering 2× LLM retry.

This regression test pins the contract:
  - ``handle()`` returns a dict shaped ``{"kind": "record", "item": {...}}``
    on the happy path.
  - ``handle()`` returns a dict shaped
    ``{"kind": "error", "reason": LookupErrorReason, "message": str,
       "retryable": bool}`` on scope violation (closed-set ``reason`` member).
  - The dict passes ``LookupOutput`` discriminated-union validation as
    performed by ``envelope.normalize()`` — i.e. the executor accepts it
    and emits a typed ``LookupRecord`` / ``LookupError`` to the agentic loop.
  - Domain payload fields the LLM relies on (e.g. ``certificate_type``,
    ``holder_name``, ``year``, ``items``) survive the envelope wrap inside
    ``item``.

Linked surfaces:
  - ``src/kosmos/tools/models.py``  — LookupOutput discriminated union.
  - ``src/kosmos/tools/envelope.py`` — normalize() / TypeAdapter.
  - ``src/kosmos/tools/mock/lookup_module_gov24_certificate.py`` (fix B1).
  - ``src/kosmos/tools/mock/lookup_module_hometax_simplified.py`` (fix B1).
  - ``src/kosmos/tools/mock/lookup_module_gov24_movein_sequence.py``.
"""

from __future__ import annotations

import pytest

from kosmos.tools.envelope import normalize
from kosmos.tools.errors import LookupErrorReason
from kosmos.tools.mock.lookup_module_gov24_certificate import (
    MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL,
    Gov24CertificateInput,
)
from kosmos.tools.mock.lookup_module_gov24_certificate import (
    handle as gov24_handle,
)
from kosmos.tools.mock.lookup_module_gov24_movein_sequence import (
    MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL,
    Gov24MoveInSequenceInput,
)
from kosmos.tools.mock.lookup_module_gov24_movein_sequence import (
    handle as movein_handle,
)
from kosmos.tools.mock.lookup_module_hometax_simplified import (
    MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL,
    HometaxSimplifiedInput,
)
from kosmos.tools.mock.lookup_module_hometax_simplified import (
    handle as hometax_handle,
)
from kosmos.tools.models import LookupError as KosmosLookupError
from kosmos.tools.models import LookupRecord

# ---------------------------------------------------------------------------
# Fixtures — minimal valid inputs for both adapters.
# ---------------------------------------------------------------------------

_GOV24_INPUT = Gov24CertificateInput(
    certificate_type="resident_registration",
    purpose="금융기관 제출용",
)

_HOMETAX_INPUT = HometaxSimplifiedInput(
    year=2024,
    resident_id_prefix="851201",
)

_MOVEIN_INPUT = Gov24MoveInSequenceInput(
    adm_cd="2638000000",
    address="부산 사하구 다대1동",
)


# ---------------------------------------------------------------------------
# 1. Happy-path envelope shape — kind discriminator + item wrap.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gov24_handle_returns_record_envelope() -> None:
    """gov24 happy path returns ``{"kind": "record", "item": {...}}``."""
    out = await gov24_handle(
        _GOV24_INPUT,
        delegation_context=_delegation("lookup:gov24.certificate"),
    )

    assert isinstance(out, dict), f"handle() must return dict, got {type(out).__name__}"
    assert out.get("kind") == "record", (
        f"kind discriminator missing or wrong (snap-S8-002 regression). got: {out!r}"
    )
    assert isinstance(out.get("item"), dict), "item must be a dict[str, object]"
    # Domain fields survive the wrap.
    item = out["item"]
    assert item["certificate_type"] == "resident_registration"
    assert item["holder_name"] == "홍길동 (MOCK)"
    assert isinstance(item["household_members"], list)


@pytest.mark.asyncio
async def test_hometax_handle_returns_record_envelope() -> None:
    """hometax happy path returns ``{"kind": "record", "item": {...}}``."""
    out = await hometax_handle(
        _HOMETAX_INPUT,
        delegation_context=_delegation("lookup:hometax.simplified"),
    )

    assert isinstance(out, dict), f"handle() must return dict, got {type(out).__name__}"
    assert out.get("kind") == "record", (
        f"kind discriminator missing or wrong (snap-S8-002 regression). got: {out!r}"
    )
    assert isinstance(out.get("item"), dict), "item must be a dict[str, object]"
    # Domain fields survive the wrap. Note the inner `kind` is the legacy
    # mydata-read shape's `simplified_data_summary` payload-type tag — it
    # must NOT be confused with the outer envelope discriminator.
    item = out["item"]
    assert item["year"] == 2024
    assert item["kind"] == "simplified_data_summary"
    assert isinstance(item["items"], list)
    assert len(item["items"]) >= 3


@pytest.mark.asyncio
async def test_gov24_movein_handle_returns_record_envelope() -> None:
    """move-in sequence happy path returns ``{"kind": "record", "item": {...}}``."""
    out = await movein_handle(
        _MOVEIN_INPUT,
        delegation_context=_delegation("lookup:gov24.movein"),
    )

    assert isinstance(out, dict), f"handle() must return dict, got {type(out).__name__}"
    assert out.get("kind") == "record"
    assert isinstance(out.get("item"), dict), "item must be a dict[str, object]"
    item = out["item"]
    assert item["workflow_kind"] == "gov24_movein_dependent_sequence"
    assert item["required_sequence"][0]["minwon_type"] == "전입신고"
    assert item["required_sequence"][1]["minwon_type"] == "주소변경"


# ---------------------------------------------------------------------------
# 2. Round-trip — envelope.normalize() validates without raising.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gov24_envelope_normalize_passes() -> None:
    """gov24 handle() output passes ``envelope.normalize()`` cleanly."""
    raw = await gov24_handle(
        _GOV24_INPUT,
        delegation_context=_delegation("lookup:gov24.certificate"),
    )
    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL,
        request_id="test-request-gov24-0001",
        elapsed_ms=42,
    )

    assert isinstance(validated, LookupRecord), (
        f"normalize() must produce LookupRecord, got {type(validated).__name__}"
    )
    assert validated.kind == "record"
    assert validated.meta.source == "mock_lookup_module_gov24_certificate"
    assert validated.meta.request_id == "test-request-gov24-0001"
    assert validated.meta.elapsed_ms == 42

    # Item still carries domain fields + transparency stamp.
    assert validated.item["certificate_type"] == "resident_registration"
    assert validated.item["holder_name"] == "홍길동 (MOCK)"
    assert validated.item["_mode"] == "mock"
    assert validated.item["_reference_implementation"] == "public-mydata-read-v240930"
    assert validated.item["_international_reference"] == "Estonia X-Road"


@pytest.mark.asyncio
async def test_hometax_envelope_normalize_passes() -> None:
    """hometax handle() output passes ``envelope.normalize()`` cleanly."""
    raw = await hometax_handle(
        _HOMETAX_INPUT,
        delegation_context=_delegation("lookup:hometax.simplified"),
    )
    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL,
        request_id="test-request-hometax-0001",
        elapsed_ms=17,
    )

    assert isinstance(validated, LookupRecord), (
        f"normalize() must produce LookupRecord, got {type(validated).__name__}"
    )
    assert validated.kind == "record"
    assert validated.meta.source == "mock_lookup_module_hometax_simplified"
    assert validated.meta.request_id == "test-request-hometax-0001"
    assert validated.meta.elapsed_ms == 17

    # Item still carries domain fields + transparency stamp.
    assert validated.item["year"] == 2024
    assert validated.item["kind"] == "simplified_data_summary"
    assert isinstance(validated.item["items"], list)
    assert validated.item["_mode"] == "mock"
    assert validated.item["_reference_implementation"] == "public-mydata-read-v240930"
    assert validated.item["_international_reference"] == "UK HMRC Making Tax Digital"


@pytest.mark.asyncio
async def test_gov24_movein_envelope_normalize_passes() -> None:
    """move-in sequence handle() output passes ``envelope.normalize()`` cleanly."""
    raw = await movein_handle(
        _MOVEIN_INPUT,
        delegation_context=_delegation("lookup:gov24.movein"),
    )
    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL,
        request_id="test-request-gov24-movein-0001",
        elapsed_ms=11,
    )

    assert isinstance(validated, LookupRecord)
    assert validated.kind == "record"
    assert validated.meta.source == "mock_lookup_module_gov24_movein_sequence"
    assert validated.item["workflow_kind"] == "gov24_movein_dependent_sequence"
    assert validated.item["_mode"] == "mock"


# ---------------------------------------------------------------------------
# 3. Scope-violation envelope — kind=error + closed-set reason.
# ---------------------------------------------------------------------------


def _delegation(scope: str) -> object:
    from datetime import UTC, datetime, timedelta

    from kosmos.primitives.delegation import DelegationContext, DelegationToken

    token = DelegationToken(
        vp_jwt="eyJhbGciOiJub25lIiwidHlwIjoidnArand0In0.eyJzdWIiOiJtb2NrIn0.mock-signature-not-cryptographic",
        delegation_token="del_" + "z" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="envelope test",
        purpose_en="envelope test",
    )


@pytest.mark.asyncio
async def test_gov24_scope_violation_returns_error_envelope() -> None:
    """Wrong-scope delegation produces a normalize()-clean LookupError."""
    raw = await gov24_handle(
        _GOV24_INPUT, delegation_context=_delegation("submit:hometax.tax-return")
    )

    assert raw["kind"] == "error"
    # Reason MUST be a member of the closed LookupErrorReason enum so the
    # envelope passes validation; "scope_violation" (legacy buggy value)
    # is rejected because it isn't in the enum.
    assert raw["reason"] == LookupErrorReason.auth_required.value

    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL,
        request_id="test-scope-violation-0001",
        elapsed_ms=3,
    )
    assert isinstance(validated, KosmosLookupError)
    assert validated.kind == "error"
    assert validated.reason == LookupErrorReason.auth_required
    assert validated.retryable is False
    assert validated.meta is not None
    assert validated.meta.source == "mock_lookup_module_gov24_certificate"


@pytest.mark.asyncio
async def test_hometax_scope_violation_returns_error_envelope() -> None:
    """Wrong-scope delegation on hometax produces a normalize()-clean LookupError."""
    raw = await hometax_handle(
        _HOMETAX_INPUT,
        delegation_context=_delegation("submit:gov24.minwon"),
    )

    assert raw["kind"] == "error"
    assert raw["reason"] == LookupErrorReason.auth_required.value

    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL,
        request_id="test-scope-violation-0002",
        elapsed_ms=5,
    )
    assert isinstance(validated, KosmosLookupError)
    assert validated.kind == "error"
    assert validated.reason == LookupErrorReason.auth_required
    assert validated.retryable is False
    assert validated.meta is not None
    assert validated.meta.source == "mock_lookup_module_hometax_simplified"


@pytest.mark.asyncio
async def test_gov24_movein_scope_violation_returns_error_envelope() -> None:
    """Wrong-scope delegation on move-in lookup produces a clean LookupError."""
    raw = await movein_handle(
        _MOVEIN_INPUT,
        delegation_context=_delegation("submit:gov24.minwon"),
    )

    assert raw["kind"] == "error"
    assert raw["reason"] == LookupErrorReason.auth_required.value

    validated = normalize(
        output=raw,
        tool=MOCK_LOOKUP_MODULE_GOV24_MOVEIN_SEQUENCE_TOOL,
        request_id="test-scope-violation-movein-0001",
        elapsed_ms=5,
    )
    assert isinstance(validated, KosmosLookupError)
    assert validated.kind == "error"
    assert validated.reason == LookupErrorReason.auth_required
    assert validated.retryable is False
    assert validated.meta is not None
    assert validated.meta.source == "mock_lookup_module_gov24_movein_sequence"


# ---------------------------------------------------------------------------
# 4. End-to-end integration through the lookup primitive
#    LookupFetchInput → lookup() → executor.invoke() → mock handle()
#    → envelope.normalize() → typed LookupRecord delivered to the agentic loop.
# ---------------------------------------------------------------------------


@pytest.fixture
def registry_with_mocks():
    """Fresh ToolRegistry + ToolExecutor with both lookup mocks registered."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.mock.lookup_module_gov24_certificate import (
        register as register_gov24,
    )
    from kosmos.tools.mock.lookup_module_gov24_movein_sequence import (
        register as register_movein,
    )
    from kosmos.tools.mock.lookup_module_hometax_simplified import (
        register as register_hometax,
    )
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_gov24(registry, executor)
    register_hometax(registry, executor)
    register_movein(registry, executor)
    return registry, executor


@pytest.mark.asyncio
async def test_primitive_lookup_fetch_gov24_returns_typed_record(
    registry_with_mocks: tuple[object, object],
) -> None:
    """End-to-end: lookup primitive surfaces a LookupRecord — no validation error."""
    from kosmos.tools.lookup import lookup
    from kosmos.tools.models import LookupFetchInput

    _registry, executor = registry_with_mocks
    inp = LookupFetchInput(
        mode="fetch",
        tool_id="mock_lookup_module_gov24_certificate",
        params={
            "certificate_type": "resident_registration",
            "purpose": "금융기관 제출용",
            "delegation_context": _delegation("lookup:gov24.certificate"),
        },
    )
    result = await lookup(inp, executor=executor, session_identity="test-session")

    # Pre-fix this raised EnvelopeNormalizationError → LookupError with
    # reason=upstream_unavailable. Post-fix the envelope passes validation
    # and the agentic loop receives a typed LookupRecord.
    assert isinstance(result, LookupRecord), (
        f"snap-S8-002 regression: expected LookupRecord (envelope normalize PASS), "
        f"got {type(result).__name__}: {result!r}"
    )
    assert result.kind == "record"
    assert result.meta.source == "mock_lookup_module_gov24_certificate"
    # Domain payload survives end-to-end for the LLM to summarise.
    assert result.item["certificate_type"] == "resident_registration"
    assert result.item["holder_name"] == "홍길동 (MOCK)"
    assert result.item["_mode"] == "mock"


@pytest.mark.asyncio
async def test_primitive_lookup_fetch_hometax_returns_typed_record(
    registry_with_mocks: tuple[object, object],
) -> None:
    """End-to-end: hometax mock also surfaces a typed LookupRecord."""
    from kosmos.tools.lookup import lookup
    from kosmos.tools.models import LookupFetchInput

    _registry, executor = registry_with_mocks
    inp = LookupFetchInput(
        mode="fetch",
        tool_id="mock_lookup_module_hometax_simplified",
        params={
            "year": 2024,
            "resident_id_prefix": "851201",
            "delegation_context": _delegation("lookup:hometax.simplified"),
        },
    )
    result = await lookup(inp, executor=executor, session_identity="test-session")

    assert isinstance(result, LookupRecord), (
        f"snap-S8-002 regression: expected LookupRecord, got {type(result).__name__}: {result!r}"
    )
    assert result.kind == "record"
    assert result.meta.source == "mock_lookup_module_hometax_simplified"
    assert result.item["year"] == 2024
    assert result.item["kind"] == "simplified_data_summary"
    assert isinstance(result.item["items"], list)
    assert result.item["_mode"] == "mock"


@pytest.mark.asyncio
async def test_primitive_lookup_fetch_gov24_movein_returns_typed_record(
    registry_with_mocks: tuple[object, object],
) -> None:
    """End-to-end: move-in sequence mock surfaces a typed LookupRecord."""
    from kosmos.tools.lookup import lookup
    from kosmos.tools.models import LookupFetchInput

    _registry, executor = registry_with_mocks
    inp = LookupFetchInput(
        mode="fetch",
        tool_id="mock_lookup_module_gov24_movein_sequence",
        params={
            "adm_cd": "2638000000",
            "address": "부산 사하구 다대1동",
            "delegation_context": _delegation("lookup:gov24.movein"),
        },
    )
    result = await lookup(inp, executor=executor, session_identity="test-session")

    assert isinstance(result, LookupRecord)
    assert result.kind == "record"
    assert result.meta.source == "mock_lookup_module_gov24_movein_sequence"
    assert result.item["workflow_kind"] == "gov24_movein_dependent_sequence"
    assert result.item["required_sequence"][0]["minwon_type"] == "전입신고"
    assert result.item["_mode"] == "mock"
