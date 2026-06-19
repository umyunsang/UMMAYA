# SPDX-License-Identifier: Apache-2.0
"""JSON payload assembly for Evidence Fabric v2."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import assert_never

from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
from ummaya.evidence.json_types import JsonArray, JsonObject, JsonValue, parse_json_object
from ummaya.evidence.models import RunEvidence
from ummaya.evidence.payload_documents import append_document_harness_payload


def build_evidence_output_payload(
    evidence: RunEvidence,
    *,
    include_document_harness: bool = True,
    document_viewer_ux_artifacts: Sequence[DocumentViewerUxArtifact] = (),
    hwp_bridge_probe_env: Mapping[str, str] | None = None,
    hwp_bridge_probe_search_path: Sequence[str] | None = None,
    odf_probe_env: Mapping[str, str] | None = None,
    odf_probe_search_path: Sequence[str] | None = None,
    odf_probe_importable_modules: frozenset[str] | None = None,
    pdfa_probe_env: Mapping[str, str] | None = None,
    pdfa_probe_search_path: Sequence[str] | None = None,
    archive_probe_env: Mapping[str, str] | None = None,
    archive_probe_search_path: Sequence[str] | None = None,
    passive_probe_env: Mapping[str, str] | None = None,
    passive_probe_search_path: Sequence[str] | None = None,
    passive_probe_importable_modules: frozenset[str] | None = None,
    legacy_office_probe_env: Mapping[str, str] | None = None,
    legacy_office_probe_search_path: Sequence[str] | None = None,
) -> JsonObject:
    """Build the JSON payload emitted by the Evidence Fabric CLI."""
    payload = parse_json_object(evidence.model_dump(mode="json"))
    if document_viewer_ux_artifacts:
        payload["gates"] = _with_passed_ux_gate(payload["gates"])
        payload["ux_artifacts"] = [
            parse_json_object(artifact.model_dump(mode="json"))
            for artifact in document_viewer_ux_artifacts
        ]
    if include_document_harness:
        append_document_harness_payload(
            payload,
            document_viewer_ux_artifacts=document_viewer_ux_artifacts,
            hwp_bridge_probe_env=hwp_bridge_probe_env,
            hwp_bridge_probe_search_path=hwp_bridge_probe_search_path,
            odf_probe_env=odf_probe_env,
            odf_probe_search_path=odf_probe_search_path,
            odf_probe_importable_modules=odf_probe_importable_modules,
            pdfa_probe_env=pdfa_probe_env,
            pdfa_probe_search_path=pdfa_probe_search_path,
            archive_probe_env=archive_probe_env,
            archive_probe_search_path=archive_probe_search_path,
            passive_probe_env=passive_probe_env,
            passive_probe_search_path=passive_probe_search_path,
            passive_probe_importable_modules=passive_probe_importable_modules,
            legacy_office_probe_env=legacy_office_probe_env,
            legacy_office_probe_search_path=legacy_office_probe_search_path,
        )
    return payload


def _with_passed_ux_gate(gates: JsonValue) -> JsonArray:
    match gates:
        case list():
            promoted: JsonArray = []
            for gate in gates:
                match gate:
                    case dict() if gate.get("name") == "ux":
                        check_ids: JsonArray = ["document-viewer-playwright-png", "frame-hash"]
                        promoted.append(
                            {
                                **gate,
                                "status": "pass",
                                "summary": "Playwright document viewer UX artifacts are attached",
                                "check_ids": check_ids,
                            }
                        )
                    case dict() | list() | str() | int() | float() | bool() | None:
                        promoted.append(gate)
                    case unreachable:
                        assert_never(unreachable)
            return promoted
        case dict() | str() | int() | float() | bool() | None:
            return []
        case unreachable:
            assert_never(unreachable)
