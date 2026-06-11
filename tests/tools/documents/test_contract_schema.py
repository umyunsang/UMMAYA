# SPDX-License-Identifier: Apache-2.0
"""Contract schema smoke tests for document tool definitions."""

from __future__ import annotations

import json
from pathlib import Path

CONTRACT_PATH = (
    Path(__file__).parents[3]
    / "specs"
    / "2803-document-production-hardening"
    / "contracts"
    / "document-tools.schema.json"
)


def test_document_tool_contract_declares_all_model_visible_tools() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    tool_ids = {tool["tool_id"] for tool in schema["x-ummaya-tools"]}

    assert tool_ids == {"document"}


def test_document_tool_contract_uses_dedicated_document_primitive() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    primitives = {tool["primitive"] for tool in schema["x-ummaya-tools"]}

    assert primitives == {"document"}


def test_document_tool_contract_has_closed_contract_objects() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_def = schema["$defs"]["ToolContract"]

    assert contract_def["additionalProperties"] is False
    assert set(contract_def["required"]) == {
        "tool_id",
        "primitive",
        "input_schema",
        "output_schema",
        "permission",
    }
