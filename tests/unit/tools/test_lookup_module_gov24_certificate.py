# SPDX-License-Identifier: Apache-2.0
"""T029 — Unit tests for mock_lookup_module_gov24_certificate.

Covers:
1. Happy path: response carries six transparency fields for all three cert types.
2. BM25 discovery: bilingual search hint keywords surface this tool.
3. Scope validation: matching DelegationContext scope passes, missing/mismatched rejects.
4. No-delegation path: adapter fails closed before returning certificate data.
5. Registration: adapter registers correctly in ToolRegistry + ToolExecutor.

Contract: specs/2296-ax-mock-adapters/tasks.md T029
"""

from __future__ import annotations

import pytest
import pytest_asyncio  # noqa: F401 — ensures pytest-asyncio plugin is present

from kosmos.tools.mock.lookup_module_gov24_certificate import (
    MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL,
    Gov24CertificateInput,
    handle,
    register,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_INPUT_RESIDENT = Gov24CertificateInput(
    certificate_type="resident_registration",
    purpose="금융기관 제출용",
)
_VALID_INPUT_FAMILY = Gov24CertificateInput(
    certificate_type="family_relations",
    purpose="취업 지원 제출용",
)
_VALID_INPUT_BUSINESS = Gov24CertificateInput(
    certificate_type="business_registration",
    purpose="입찰 제출용",
)

_TRANSPARENCY_FIELDS = (
    "_mode",
    "_reference_implementation",
    "_actual_endpoint_when_live",
    "_security_wrapping_pattern",
    "_policy_authority",
    "_international_reference",
)


def _make_delegation_context(scope: str) -> object:
    """Build a minimal DelegationContext for scope-validation testing."""
    from datetime import UTC, datetime, timedelta

    from kosmos.primitives.delegation import DelegationContext, DelegationToken

    token = DelegationToken(
        vp_jwt="eyJhbGciOiJub25lIiwidHlwIjoidnArand0In0.eyJzdWIiOiJtb2NrIn0.mock-signature-not-cryptographic",
        delegation_token="del_" + "y" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="정부24 증명서 조회",
        purpose_en="Gov24 certificate lookup",
    )


# ---------------------------------------------------------------------------
# 1. Happy path — six transparency fields for all three certificate types
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inp",
    [
        pytest.param(_VALID_INPUT_RESIDENT, id="resident_registration"),
        pytest.param(_VALID_INPUT_FAMILY, id="family_relations"),
        pytest.param(_VALID_INPUT_BUSINESS, id="business_registration"),
    ],
)
async def test_handle_happy_path_carries_six_transparency_fields(
    inp: Gov24CertificateInput,
) -> None:
    """handle() with delegated scope returns all six transparency fields.

    LookupOutput envelope fix — transparency fields live inside ``item`` so
    the outer envelope passes ``LookupRecord`` (``extra='forbid'``) validation.
    """
    result = await handle(
        inp,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    assert result["kind"] == "record", f"expected LookupRecord envelope, got {result!r}"
    item = result["item"]
    assert isinstance(item, dict)

    for field in _TRANSPARENCY_FIELDS:
        value = item.get(field)
        assert value is not None, (
            f"Missing transparency field: {field!r} (cert={inp.certificate_type})"
        )  # noqa: E501
        assert isinstance(value, str), f"Field {field!r} is not a string"
        assert value.strip(), f"Field {field!r} is empty or whitespace-only"


@pytest.mark.asyncio
async def test_handle_mode_is_mock() -> None:
    """_mode is always 'mock' for Epic ε mock adapters (lives inside item)."""
    result = await handle(
        _VALID_INPUT_RESIDENT,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    assert result["item"]["_mode"] == "mock"


@pytest.mark.asyncio
async def test_handle_reference_impl() -> None:
    """_reference_implementation is 'public-mydata-read-v240930' per spec catalog."""
    result = await handle(
        _VALID_INPUT_FAMILY,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    assert result["item"]["_reference_implementation"] == "public-mydata-read-v240930"


@pytest.mark.asyncio
async def test_handle_international_ref() -> None:
    """_international_reference is 'Estonia X-Road' per spec catalog."""
    result = await handle(
        _VALID_INPUT_BUSINESS,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    assert result["item"]["_international_reference"] == "Estonia X-Road"


@pytest.mark.asyncio
async def test_handle_resident_registration_domain_payload() -> None:
    """Resident registration returns the correct certificate_type_ko."""
    result = await handle(
        _VALID_INPUT_RESIDENT,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    item = result["item"]
    assert item.get("certificate_type") == "resident_registration"
    assert item.get("certificate_type_ko") == "주민등록등본"
    assert isinstance(item.get("household_members"), list)
    assert item["electronic_document_wallet"]["wallet_address"] == (
        "mock-wallet-address-not-routable"
    )
    assert "api_onboarding_flow" in item


@pytest.mark.asyncio
async def test_handle_happy_path_evidence_grade() -> None:
    """Privileged mock exposes evidence grade and live-swap requirements."""
    result = await handle(
        _VALID_INPUT_RESIDENT,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    item = result["item"]
    assert item["_mock_fidelity_grade"] == "B-official-api-onboarding-private-spec-inferred"
    evidence = item["_mock_evidence"]
    assert evidence["credential_status"] == "student_no_live_authority"
    assert "live_swap_requirements" in evidence


@pytest.mark.asyncio
async def test_handle_family_relations_domain_payload() -> None:
    """Family relations returns the correct certificate_type_ko."""
    result = await handle(
        _VALID_INPUT_FAMILY,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    item = result["item"]
    assert item.get("certificate_type") == "family_relations"
    assert item.get("certificate_type_ko") == "가족관계증명서"
    assert isinstance(item.get("family_members"), list)


@pytest.mark.asyncio
async def test_handle_business_registration_domain_payload() -> None:
    """Business registration returns the correct certificate_type_ko."""
    result = await handle(
        _VALID_INPUT_BUSINESS,
        delegation_context=_make_delegation_context("lookup:gov24.certificate"),
    )
    item = result["item"]
    assert item.get("certificate_type") == "business_registration"
    assert item.get("certificate_type_ko") == "사업자등록증"
    assert "registration_number" in item


# ---------------------------------------------------------------------------
# 2. BM25 discovery — bilingual search hint keywords surface this tool
# ---------------------------------------------------------------------------


def test_bm25_discovery_korean_keyword_jumindeung() -> None:
    """BM25 search for '주민등록등본' surfaces mock_lookup_module_gov24_certificate."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("주민등록등본")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_gov24_certificate" in tool_ids, (
        f"BM25 search for '주민등록등본' did not surface the adapter. Got: {tool_ids}"
    )


def test_bm25_discovery_korean_keyword_gov24() -> None:
    """BM25 search for '정부24 증명서' surfaces mock_lookup_module_gov24_certificate."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("정부24 증명서")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_gov24_certificate" in tool_ids, (
        f"BM25 search for '정부24 증명서' did not surface the adapter. Got: {tool_ids}"
    )


def test_bm25_discovery_english_keyword() -> None:
    """BM25 search for 'resident certificate' surfaces mock_lookup_module_gov24_certificate."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("resident certificate")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_gov24_certificate" in tool_ids, (
        f"BM25 search for 'resident certificate' did not surface the adapter. Got: {tool_ids}"
    )


# ---------------------------------------------------------------------------
# 3. Scope validation with DelegationContext
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_with_matching_scope_succeeds() -> None:
    """Matching scope 'lookup:gov24.certificate' passes delegation check."""
    delegation = _make_delegation_context("lookup:gov24.certificate")
    result = await handle(_VALID_INPUT_RESIDENT, delegation_context=delegation)

    assert result.get("kind") == "record", f"Expected success record, got {result!r}"
    item = result["item"]
    assert item.get("_mode") == "mock"
    for field in _TRANSPARENCY_FIELDS:
        assert item.get(field), f"Missing field {field!r} after successful delegation"


@pytest.mark.asyncio
async def test_handle_with_mismatched_scope_returns_scope_violation() -> None:
    """Wrong scope 'submit:hometax.tax-return' triggers a LookupError envelope.

    Scope-violation maps to the closed-set ``LookupErrorReason.auth_required``
    (the closed enum has no ``scope_violation`` member). Transparency fields
    are not present on error envelopes — ``LookupError`` schema is
    ``extra='forbid'``; ``meta.source`` (injected later by ``normalize()``)
    carries adapter identity instead.
    """
    delegation = _make_delegation_context("submit:hometax.tax-return")
    result = await handle(_VALID_INPUT_FAMILY, delegation_context=delegation)

    assert result.get("kind") == "error"
    assert result.get("reason") == "auth_required"
    assert result.get("retryable") is False
    # Scope context is preserved in the message for citizen-facing diagnostics.
    msg = result.get("message", "")
    assert "lookup:gov24.certificate" in msg
    assert "submit:hometax.tax-return" in msg


@pytest.mark.asyncio
async def test_handle_with_multi_scope_containing_required_passes() -> None:
    """Multi-scope token that includes 'lookup:gov24.certificate' passes."""
    delegation = _make_delegation_context("lookup:gov24.certificate,submit:gov24.minwon")
    result = await handle(_VALID_INPUT_BUSINESS, delegation_context=delegation)

    assert result.get("kind") == "record", (
        f"Multi-scope with required scope should succeed: {result}"
    )
    assert result["item"].get("_mode") == "mock"


# ---------------------------------------------------------------------------
# 4. No-delegation path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_without_delegation_context_fails_closed() -> None:
    """Adapter never returns citizen certificate data without DelegationContext."""
    result = await handle(_VALID_INPUT_RESIDENT, delegation_context=None)
    assert result.get("kind") == "error"
    assert result.get("reason") == "auth_required"
    assert result.get("retryable") is False
    assert "lookup:gov24.certificate" in str(result.get("message", ""))


# ---------------------------------------------------------------------------
# 5. Registration into ToolRegistry + ToolExecutor
# ---------------------------------------------------------------------------


def test_registration_adds_tool_to_registry() -> None:
    """register() adds mock_lookup_module_gov24_certificate to the ToolRegistry."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    assert "mock_lookup_module_gov24_certificate" in registry._tools


def test_registration_adds_adapter_to_executor() -> None:
    """register() binds the adapter function in the ToolExecutor."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    assert "mock_lookup_module_gov24_certificate" in executor._adapters


def test_tool_definition_primitive_is_lookup() -> None:
    """GovAPITool primitive field is 'lookup'."""
    assert MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL.primitive == "lookup"


def test_tool_definition_adapter_mode_is_mock() -> None:
    """GovAPITool adapter_mode is 'mock'."""
    assert MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL.adapter_mode == "mock"


def test_tool_definition_policy_gate_is_login() -> None:
    """GovAPITool policy.citizen_facing_gate is 'login' for personal certificate data."""
    assert MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL.policy is not None
    assert MOCK_LOOKUP_MODULE_GOV24_CERTIFICATE_TOOL.policy.citizen_facing_gate == "login"


def test_registration_duplicate_raises_error() -> None:
    """Registering the same tool twice raises AdapterIdCollisionError (FR-020)."""
    from kosmos.tools.errors import AdapterIdCollisionError
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    with pytest.raises(AdapterIdCollisionError):
        register(registry, executor)
