# SPDX-License-Identifier: Apache-2.0
"""T028 — Unit tests for mock_lookup_module_hometax_simplified.

Covers:
1. Happy path: response carries six transparency fields.
2. BM25 discovery: BM25 search for bilingual search hint keywords surfaces this tool.
3. Scope validation (with DelegationContext): matching scope passes, mismatched rejects.
4. No-delegation path: adapter proceeds without DelegationContext.
5. Registration: adapter registers correctly in ToolRegistry + ToolExecutor.

Contract: specs/2296-ax-mock-adapters/tasks.md T028
"""

from __future__ import annotations

import pytest
import pytest_asyncio  # noqa: F401 — ensures pytest-asyncio plugin is present

from kosmos.tools.mock.lookup_module_hometax_simplified import (
    MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL,
    HometaxSimplifiedInput,
    handle,
    register,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VALID_INPUT = HometaxSimplifiedInput(year=2024, resident_id_prefix="851201")

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
        delegation_token="del_" + "x" * 24,
        scope=scope,
        issuer_did="did:web:mobileid.go.kr",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        **{"_mode": "mock"},
    )
    return DelegationContext(
        token=token,
        purpose_ko="홈택스 간소화 자료 조회",
        purpose_en="Hometax simplified data lookup",
    )


# ---------------------------------------------------------------------------
# 1. Happy path — six transparency fields present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_happy_path_carries_six_transparency_fields() -> None:
    """handle() without delegation context returns all six transparency fields.

    LookupOutput envelope fix — transparency fields live inside ``item`` so
    the outer envelope passes ``LookupRecord`` (``extra='forbid'``) validation.
    """
    result = await handle(_VALID_INPUT)
    assert result["kind"] == "record", f"expected LookupRecord envelope, got {result!r}"
    item = result["item"]
    assert isinstance(item, dict)

    for field in _TRANSPARENCY_FIELDS:
        value = item.get(field)
        assert value is not None, f"Missing transparency field: {field!r}"
        assert isinstance(value, str), f"Field {field!r} is not a string"
        assert value.strip(), f"Field {field!r} is empty or whitespace-only"


@pytest.mark.asyncio
async def test_handle_happy_path_mode_is_mock() -> None:
    """_mode is always 'mock' for Epic ε mock adapters (lives inside item)."""
    result = await handle(_VALID_INPUT)
    assert result["item"]["_mode"] == "mock"


@pytest.mark.asyncio
async def test_handle_happy_path_reference_impl() -> None:
    """_reference_implementation is 'public-mydata-read-v240930' per spec catalog."""
    result = await handle(_VALID_INPUT)
    assert result["item"]["_reference_implementation"] == "public-mydata-read-v240930"


@pytest.mark.asyncio
async def test_handle_happy_path_international_ref() -> None:
    """_international_reference is 'UK HMRC Making Tax Digital' per spec catalog."""
    result = await handle(_VALID_INPUT)
    assert result["item"]["_international_reference"] == "UK HMRC Making Tax Digital"


@pytest.mark.asyncio
async def test_handle_happy_path_domain_payload() -> None:
    """Happy path returns a domain payload with expected keys (inside item)."""
    result = await handle(_VALID_INPUT)
    item = result["item"]
    assert item.get("year") == 2024
    # The domain fixture's internal `kind` (legacy field name from the
    # 마이데이터 read v240930 shape) lives inside `item`. The outer envelope's
    # `kind` is "record" (the LookupOutput discriminator).
    assert item.get("kind") == "simplified_data_summary"
    assert isinstance(item.get("items"), list)
    assert len(item["items"]) > 0


# ---------------------------------------------------------------------------
# 2. BM25 discovery — bilingual search hint keywords surface this tool
# ---------------------------------------------------------------------------


def test_bm25_discovery_korean_keyword() -> None:
    """BM25 search for '홈택스 간소화' surfaces mock_lookup_module_hometax_simplified."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("홈택스 간소화")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_hometax_simplified" in tool_ids, (
        f"BM25 search for '홈택스 간소화' did not surface the adapter. Got: {tool_ids}"
    )


def test_bm25_discovery_english_keyword() -> None:
    """BM25 search for 'hometax simplified' surfaces mock_lookup_module_hometax_simplified."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("hometax simplified")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_hometax_simplified" in tool_ids, (
        f"BM25 search for 'hometax simplified' did not surface the adapter. Got: {tool_ids}"
    )


def test_bm25_discovery_year_end_tax_keyword() -> None:
    """BM25 search for '연말정산' surfaces mock_lookup_module_hometax_simplified."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    results = registry.search("연말정산")
    tool_ids = [r.tool.id for r in results]
    assert "mock_lookup_module_hometax_simplified" in tool_ids, (
        f"BM25 search for '연말정산' did not surface the adapter. Got: {tool_ids}"
    )


# ---------------------------------------------------------------------------
# 3. Scope validation with DelegationContext
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_with_matching_scope_succeeds() -> None:
    """Matching scope 'lookup:hometax.simplified' passes delegation check."""
    delegation = _make_delegation_context("lookup:hometax.simplified")
    result = await handle(_VALID_INPUT, delegation_context=delegation)

    # Happy path — record envelope with transparency stamped inside item.
    assert result.get("kind") == "record", f"Expected success record, got {result!r}"
    item = result["item"]
    assert item.get("_mode") == "mock"
    for field in _TRANSPARENCY_FIELDS:
        assert item.get(field), f"Missing field {field!r} after successful delegation"


@pytest.mark.asyncio
async def test_handle_with_mismatched_scope_returns_scope_violation() -> None:
    """Wrong scope 'submit:gov24.minwon' triggers a LookupError envelope.

    Scope-violation maps to the closed-set ``LookupErrorReason.auth_required``
    (the closed enum has no ``scope_violation`` member). Transparency fields
    are not present on error envelopes — ``LookupError`` schema is
    ``extra='forbid'``; ``meta.source`` (injected later by ``normalize()``)
    carries adapter identity instead.
    """
    delegation = _make_delegation_context("submit:gov24.minwon")
    result = await handle(_VALID_INPUT, delegation_context=delegation)

    assert result.get("kind") == "error"
    assert result.get("reason") == "auth_required"
    assert result.get("retryable") is False
    # Scope context is preserved in the message for citizen-facing diagnostics.
    msg = result.get("message", "")
    assert "lookup:hometax.simplified" in msg
    assert "submit:gov24.minwon" in msg


@pytest.mark.asyncio
async def test_handle_with_multi_scope_containing_required_passes() -> None:
    """Multi-scope token that includes 'lookup:hometax.simplified' passes."""
    delegation = _make_delegation_context("lookup:hometax.simplified,submit:hometax.tax-return")
    result = await handle(_VALID_INPUT, delegation_context=delegation)

    assert result.get("kind") == "record", (
        f"Multi-scope with required scope should succeed: {result}"
    )
    assert result["item"].get("_mode") == "mock"


# ---------------------------------------------------------------------------
# 4. No-delegation path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_without_delegation_context_proceeds() -> None:
    """Adapter proceeds without DelegationContext (lookups are read-only)."""
    result = await handle(_VALID_INPUT, delegation_context=None)
    assert result.get("kind") == "record"
    item = result["item"]
    assert item.get("_mode") == "mock"
    # The fixture's internal kind (마이데이터 read v240930 legacy shape) is
    # inside `item`; the outer envelope kind is "record".
    assert item.get("kind") == "simplified_data_summary"


# ---------------------------------------------------------------------------
# 5. Registration into ToolRegistry + ToolExecutor
# ---------------------------------------------------------------------------


def test_registration_adds_tool_to_registry() -> None:
    """register() adds mock_lookup_module_hometax_simplified to the ToolRegistry."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    assert "mock_lookup_module_hometax_simplified" in registry._tools


def test_registration_adds_adapter_to_executor() -> None:
    """register() binds the adapter function in the ToolExecutor."""
    from kosmos.tools.executor import ToolExecutor
    from kosmos.tools.registry import ToolRegistry

    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register(registry, executor)

    assert "mock_lookup_module_hometax_simplified" in executor._adapters


def test_tool_definition_primitive_is_lookup() -> None:
    """GovAPITool primitive field is 'lookup'."""
    assert MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL.primitive == "lookup"


def test_tool_definition_adapter_mode_is_mock() -> None:
    """GovAPITool adapter_mode is 'mock'."""
    assert MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL.adapter_mode == "mock"


def test_tool_definition_policy_gate_is_read_only() -> None:
    """GovAPITool policy.citizen_facing_gate is 'read-only'."""
    assert MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL.policy is not None
    assert MOCK_LOOKUP_MODULE_HOMETAX_SIMPLIFIED_TOOL.policy.citizen_facing_gate == "read-only"


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
