# SPDX-License-Identifier: Apache-2.0
"""Tests for document contract loading and schema export helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

import ummaya.tools.documents as documents
from ummaya.tools.documents.contracts import (
    DocumentToolContractCatalog,
    export_pydantic_schema,
    load_document_tool_contracts,
)


class _ProbeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


def test_load_document_tool_contracts_reads_checked_in_schema() -> None:
    catalog = load_document_tool_contracts()

    assert isinstance(catalog, DocumentToolContractCatalog)
    assert catalog.version == "0.1.0"
    assert len(catalog.tools) == 9
    assert catalog.tool_ids == (
        "document_inspect",
        "document_extract",
        "document_form_schema",
        "document_copy_for_edit",
        "document_apply_fill",
        "document_apply_style",
        "document_render",
        "document_validate_public_form",
        "document_save",
    )


def test_loaded_document_tool_contracts_keep_closed_primitives() -> None:
    catalog = load_document_tool_contracts()

    assert {tool.primitive for tool in catalog.tools} == {"find", "check", "send"}
    assert catalog.by_tool_id("document_validate_public_form").primitive == "check"


def test_export_pydantic_schema_preserves_closed_model_shape() -> None:
    schema = export_pydantic_schema(_ProbeModel)

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["value"]


def test_package_exports_engine_backed_patch_harness_surface() -> None:
    assert documents.DocumentMutationEngine is not None
    assert documents.DocumentPatchResult is not None
    assert documents.DocumentDiff is not None
    assert documents.DocumentChange is not None
    assert documents.DocumentReReadResult is not None
    assert documents.DocumentRenderResult is not None
    assert documents.DocumentPatchValidationError is not None
    assert documents.PromotionDecisionManifest is not None
    assert documents.PromotionDecisionRecord is not None
    assert documents.PublicFormMetricScore is not None
    assert documents.RenderArtifactRecord is not None
    assert documents.ReReadMismatch is not None
    assert callable(documents.copy_for_edit)
    assert callable(documents.apply_document_patch)
    assert callable(documents.compute_public_form_metrics)
    assert callable(documents.render_document_evidence)
    assert callable(documents.reread_derivative)
    assert callable(documents.load_promotion_decision_manifest)
    assert callable(documents.persist_promotion_decision_manifest)
    assert callable(documents.validate_document_patch)
