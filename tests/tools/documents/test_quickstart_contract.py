# SPDX-License-Identifier: Apache-2.0
"""Quickstart contract coverage for the Public AX document harness."""

from __future__ import annotations

from pathlib import Path

from ummaya.tools.documents.contracts import load_document_tool_contracts

QUICKSTART_PATH = Path("specs/2802-public-doc-harness/quickstart.md")


def test_quickstart_lists_all_model_visible_document_tools() -> None:
    quickstart = QUICKSTART_PATH.read_text(encoding="utf-8")
    catalog = load_document_tool_contracts()

    for tool_id in catalog.tool_ids:
        assert tool_id in quickstart


def test_quickstart_keeps_offline_and_evidence_expectations() -> None:
    quickstart = QUICKSTART_PATH.read_text(encoding="utf-8")

    assert "No live `data.go.kr` request is allowed in CI." in quickstart
    assert "Permission is requested before derivative writes." in quickstart
    assert ".evidence/run.json" in quickstart
    assert "artifact IDs" in quickstart
