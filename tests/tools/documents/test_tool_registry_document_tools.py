# SPDX-License-Identifier: Apache-2.0
"""ToolRegistry exposure tests for the Public AX document primitive."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Collection
from typing import cast

import pytest
from pydantic import BaseModel

from ummaya.tools.documents.contracts import load_document_tool_contracts
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
    """The model-facing registry constant mirrors the single document primitive."""
    _, document_tool_ids = _load_document_registry_api()

    assert document_tool_ids == frozenset({"document"})
    assert _CONTRACTS.tool_ids == ("document",)


def test_register_document_tools_registers_exact_contract_ids() -> None:
    """register_document_tools() exposes one model-facing document primitive."""
    registry, executor = _registered_document_tools()

    assert {tool.id for tool in registry.all_tools()} == {"document"}
    assert set(executor._adapters) == {"document"}


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


def test_document_contract_guides_single_call_edit_and_review() -> None:
    """The model-facing surface must describe one edit call with automatic review."""
    registry, _ = _registered_document_tools()
    tool = _document_tools_by_id(registry)["document"]

    schema_text = json.dumps(tool.input_schema.model_json_schema(), ensure_ascii=False)
    model_surface = f"{tool.llm_description or ''}\n{tool.search_hint}\n{schema_text}"

    assert tool.primitive == "document"
    assert "document.path" in model_surface
    assert "local file path" in model_surface
    assert "single document primitive" in model_surface
    assert "automatic compact diff" in model_surface
    assert "Do not call locate" in model_surface
    assert "Do not call document_inspect" in model_surface
    assert "Do not call document_render" in model_surface


def test_document_tool_primitive_bucket_is_document() -> None:
    """Document work is a first-class primitive, not a find/send/check adapter chain."""
    registry, _ = _registered_document_tools()
    tools_by_id = _document_tools_by_id(registry)

    assert tools_by_id["document"].primitive == "document"


def test_register_all_tools_includes_document_in_routing_index() -> None:
    """Boot registration must route document as a dedicated primitive."""
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    routing_index = register_all_tools(registry, executor)

    assert "document" in registry
    assert "document" in routing_index.by_tool_id
    assert routing_index.by_tool_id["document"].primitive == "document"
    assert routing_index.by_tool_id["document"] in routing_index.by_primitive["document"]
