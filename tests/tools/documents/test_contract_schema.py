# SPDX-License-Identifier: Apache-2.0
"""Contract schema smoke tests for document tool definitions."""

from __future__ import annotations

import json
from pathlib import Path

CONTRACT_PATH = (
    Path(__file__).parents[3]
    / "specs"
    / "2802-public-doc-harness"
    / "contracts"
    / "document-tools.schema.json"
)


def test_document_tool_contract_declares_all_model_visible_tools() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    tool_ids = {tool["tool_id"] for tool in schema["x-ummaya-tools"]}

    assert tool_ids == {
        "document_inspect",
        "document_extract",
        "document_form_schema",
        "document_copy_for_edit",
        "document_apply_fill",
        "document_apply_style",
        "document_render",
        "document_validate_public_form",
        "document_save",
    }


def test_document_tool_contract_uses_existing_primitive_families_only() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    primitives = {tool["primitive"] for tool in schema["x-ummaya-tools"]}

    assert primitives <= {"find", "check", "send"}
    assert "locate" not in primitives


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
