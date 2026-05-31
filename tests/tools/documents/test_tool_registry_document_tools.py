# SPDX-License-Identifier: Apache-2.0
"""US5 ToolRegistry exposure tests for the Public AX document harness."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Collection
from typing import cast

import pytest
from pydantic import BaseModel

from ummaya.tools.documents.contracts import (
    DocumentToolContractCatalog,
    load_document_tool_contracts,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.models import GovAPITool
from ummaya.tools.register_all import register_all_tools
from ummaya.tools.registry import ToolRegistry

_CONTRACTS = load_document_tool_contracts()
_RegisterDocumentTools = Callable[[ToolRegistry, ToolExecutor], object]


def _schema_ref_name(schema_ref: str) -> str:
    return schema_ref.removeprefix("#/$defs/")


def _load_document_registry_api() -> tuple[_RegisterDocumentTools, frozenset[str]]:
    try:
        module = importlib.import_module("ummaya.tools.documents.registry")
    except ModuleNotFoundError as exc:
        if exc.name == "ummaya.tools.documents.registry":
            pytest.fail(
                "Expected future API "
                "ummaya.tools.documents.registry.register_document_tools and "
                "DOCUMENT_TOOL_IDS to exist.",
                pytrace=False,
            )
        raise

    register_document_tools = getattr(module, "register_document_tools", None)
    document_tool_ids = getattr(module, "DOCUMENT_TOOL_IDS", None)

    if not callable(register_document_tools):
        pytest.fail("register_document_tools(registry, executor) must be callable.")
    if not isinstance(document_tool_ids, (tuple, frozenset)):
        pytest.fail("DOCUMENT_TOOL_IDS must be an immutable collection of tool IDs.")

    return cast(_RegisterDocumentTools, register_document_tools), frozenset(
        cast(Collection[str], document_tool_ids),
    )


def _registered_document_tools() -> tuple[ToolRegistry, ToolExecutor]:
    register_document_tools, _ = _load_document_registry_api()
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    register_document_tools(registry, executor)

    return registry, executor


def _document_tools_by_id(registry: ToolRegistry) -> dict[str, GovAPITool]:
    return {tool.id: tool for tool in registry.all_tools()}


def test_document_tool_ids_match_contract_extension() -> None:
    """The future registry constant mirrors x-ummaya-tools exactly."""
    _, document_tool_ids = _load_document_registry_api()

    assert document_tool_ids == frozenset(_CONTRACTS.tool_ids)
    assert len(document_tool_ids) == 9


def test_register_document_tools_registers_exact_contract_ids() -> None:
    """register_document_tools() exposes exactly the nine contract tools."""
    registry, executor = _registered_document_tools()

    assert {tool.id for tool in registry.all_tools()} == set(_CONTRACTS.tool_ids)
    assert set(executor._adapters) == set(_CONTRACTS.tool_ids)


def test_document_tool_definitions_match_contract_metadata() -> None:
    """Registered tools keep contract primitive and Pydantic schema bindings."""
    registry, _ = _registered_document_tools()
    tools_by_id = _document_tools_by_id(registry)

    for contract in _CONTRACTS.tools:
        tool = tools_by_id[contract.tool_id]

        assert tool.primitive == contract.primitive
        assert issubclass(tool.input_schema, BaseModel)
        assert issubclass(tool.output_schema, BaseModel)
        assert tool.input_schema.__name__ == _schema_ref_name(contract.input_schema)
        assert tool.output_schema.__name__ == _schema_ref_name(contract.output_schema)
        assert tool.input_schema.model_json_schema()
        assert tool.output_schema.model_json_schema()
        assert tool.llm_description is not None
        assert tool.llm_description.strip()
        assert tool.search_hint.strip()


def test_document_tool_primitive_buckets_match_contract() -> None:
    """Document tools stay under find/check/send; no new root primitive is added."""
    registry, _ = _registered_document_tools()
    tools_by_id = _document_tools_by_id(registry)
    expected_by_primitive = _tools_by_primitive(_CONTRACTS)

    actual_by_primitive = {
        primitive: {
            tool_id
            for tool_id in _CONTRACTS.tool_ids
            if tools_by_id[tool_id].primitive == primitive
        }
        for primitive in ("find", "check", "send")
    }

    assert actual_by_primitive == expected_by_primitive


def test_register_all_tools_includes_document_inspect_in_routing_index() -> None:
    """Boot registration must route document_inspect without live document calls."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    routing_index = register_all_tools(registry, executor)

    assert "document_inspect" in registry
    assert "document_inspect" in routing_index.by_tool_id
    assert routing_index.by_tool_id["document_inspect"].primitive == "find"
    assert routing_index.by_tool_id["document_inspect"] in routing_index.by_primitive["find"]


def _tools_by_primitive(
    contracts: DocumentToolContractCatalog,
) -> dict[str, set[str]]:
    return {
        primitive: {
            contract.tool_id for contract in contracts.tools if contract.primitive == primitive
        }
        for primitive in ("find", "check", "send")
    }
