# SPDX-License-Identifier: Apache-2.0
"""Document harness payload enrichment for Evidence Fabric output."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from ummaya.evidence.dataset_contract import _REPO_ROOT
from ummaya.evidence.document_harness import (
    DocumentEvidenceRecord,
    DocumentHarnessEvidenceError,
    authoring_cases_from_scenario,
    beta_cases_from_scenario,
    lifecycle_records_from_scenario,
    load_document_harness_scenario,
    negative_cases_from_scenario,
    records_from_scenario,
)
from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
from ummaya.evidence.json_types import JsonObject, parse_json_object
from ummaya.tools.documents.hwp_conversion_probe import (
    HWPXJS_CANDIDATE_ID,
    HwpToHwpxBridgeProbeReport,
    probe_hwp_to_hwpx_bridge,
)
from ummaya.tools.documents.legacy_office_promotion_probe import (
    LegacyOfficePromotionProbeReport,
    probe_legacy_office_promotion,
)
from ummaya.tools.documents.models import KnownDocumentFormat


def append_document_harness_payload(
    payload: JsonObject,
    *,
    document_viewer_ux_artifacts: Sequence[DocumentViewerUxArtifact],
    hwp_bridge_probe_env: Mapping[str, str] | None,
    hwp_bridge_probe_search_path: Sequence[str] | None,
    odf_probe_env: Mapping[str, str] | None,
    odf_probe_search_path: Sequence[str] | None,
    odf_probe_importable_modules: frozenset[str] | None,
    pdfa_probe_env: Mapping[str, str] | None,
    pdfa_probe_search_path: Sequence[str] | None,
    archive_probe_env: Mapping[str, str] | None,
    archive_probe_search_path: Sequence[str] | None,
    passive_probe_env: Mapping[str, str] | None,
    passive_probe_search_path: Sequence[str] | None,
    passive_probe_importable_modules: frozenset[str] | None,
    legacy_office_probe_env: Mapping[str, str] | None,
    legacy_office_probe_search_path: Sequence[str] | None,
) -> None:
    """Attach document harness records and local probe outputs to a payload."""
    scenario = load_document_harness_scenario()
    document_records = records_from_scenario(scenario)
    _validate_document_viewer_ux_joins(document_records, document_viewer_ux_artifacts)
    payload["document_evidence_records"] = [
        parse_json_object(record.model_dump(mode="json")) for record in document_records
    ]
    payload["document_lifecycle_records"] = [
        parse_json_object(record.model_dump(mode="json"))
        for record in lifecycle_records_from_scenario(scenario)
    ]
    payload["document_beta_cases"] = [
        parse_json_object(case.model_dump(mode="json"))
        for case in beta_cases_from_scenario(scenario)
    ]
    payload["document_negative_cases"] = [
        parse_json_object(case.model_dump(mode="json"))
        for case in negative_cases_from_scenario(scenario)
    ]
    payload["document_authoring_cases"] = [
        parse_json_object(case.model_dump(mode="json"))
        for case in authoring_cases_from_scenario(scenario)
    ]
    bridge_probe = probe_hwp_to_hwpx_bridge(
        env=hwp_bridge_probe_env,
        search_path=_default_hwp_bridge_probe_search_path(
            env=hwp_bridge_probe_env,
            explicit_search_path=hwp_bridge_probe_search_path,
        ),
    )
    payload["document_bridge_probe_records"] = [
        parse_json_object(bridge_probe.model_dump(mode="json"))
    ]
    _append_document_promotion_payload(
        payload,
        bridge_probe=bridge_probe,
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


def _append_document_promotion_payload(
    payload: JsonObject,
    *,
    bridge_probe: HwpToHwpxBridgeProbeReport,
    odf_probe_env: Mapping[str, str] | None,
    odf_probe_search_path: Sequence[str] | None,
    odf_probe_importable_modules: frozenset[str] | None,
    pdfa_probe_env: Mapping[str, str] | None,
    pdfa_probe_search_path: Sequence[str] | None,
    archive_probe_env: Mapping[str, str] | None,
    archive_probe_search_path: Sequence[str] | None,
    passive_probe_env: Mapping[str, str] | None,
    passive_probe_search_path: Sequence[str] | None,
    passive_probe_importable_modules: frozenset[str] | None,
    legacy_office_probe_env: Mapping[str, str] | None,
    legacy_office_probe_search_path: Sequence[str] | None,
) -> None:
    from ummaya.tools.documents.archive_container_probe import probe_archive_container_promotion
    from ummaya.tools.documents.format_completion_audit import audit_document_format_completion
    from ummaya.tools.documents.odf_promotion_probe import probe_odf_promotion
    from ummaya.tools.documents.passive_capability_probe import probe_passive_capabilities
    from ummaya.tools.documents.pdfa_promotion_probe import probe_pdfa_promotion

    odf_probe_records = probe_odf_promotion(
        env=odf_probe_env,
        search_path=odf_probe_search_path,
        importable_modules=odf_probe_importable_modules,
    )
    pdfa_probe_record = probe_pdfa_promotion(
        env=pdfa_probe_env,
        search_path=pdfa_probe_search_path,
    )
    archive_probe_records = probe_archive_container_promotion(
        env=archive_probe_env,
        search_path=archive_probe_search_path,
    )
    passive_probe_records = probe_passive_capabilities(
        env=passive_probe_env,
        search_path=passive_probe_search_path,
        importable_modules=passive_probe_importable_modules,
    )
    legacy_office_probe_records = probe_legacy_office_promotion(
        env=legacy_office_probe_env,
        search_path=legacy_office_probe_search_path,
    )
    payload["document_odf_probe_records"] = [
        parse_json_object(record.model_dump(mode="json")) for record in odf_probe_records
    ]
    payload["document_pdfa_probe_records"] = [
        parse_json_object(pdfa_probe_record.model_dump(mode="json"))
    ]
    payload["document_archive_probe_records"] = [
        parse_json_object(record.model_dump(mode="json")) for record in archive_probe_records
    ]
    payload["document_passive_probe_records"] = [
        parse_json_object(record.model_dump(mode="json")) for record in passive_probe_records
    ]
    payload["document_legacy_office_probe_records"] = [
        parse_json_object(record.model_dump(mode="json")) for record in legacy_office_probe_records
    ]
    format_completion_audit = audit_document_format_completion(
        derivative_promoted_formats=_derivative_promoted_formats_from_probe_records(
            bridge_probe=bridge_probe,
            legacy_office_probe_records=legacy_office_probe_records,
        ),
        pdfa_conformance_promoted=pdfa_probe_record.status == "candidate_available",
    )
    payload["document_format_completion_audit"] = parse_json_object(
        format_completion_audit.model_dump(mode="json")
    )


def _derivative_promoted_formats_from_probe_records(
    *,
    bridge_probe: HwpToHwpxBridgeProbeReport,
    legacy_office_probe_records: Sequence[LegacyOfficePromotionProbeReport],
) -> frozenset[KnownDocumentFormat]:
    promoted: set[KnownDocumentFormat] = set()
    if bridge_probe.status == "configured" or (
        bridge_probe.status == "available" and bridge_probe.candidate_id == HWPXJS_CANDIDATE_ID
    ):
        promoted.add(KnownDocumentFormat.hwp)
    for record in legacy_office_probe_records:
        if record.status == "candidate_available":
            promoted.add(record.known_format)
    return frozenset(promoted)


def _default_hwp_bridge_probe_search_path(
    *,
    env: Mapping[str, str] | None,
    explicit_search_path: Sequence[str] | None,
) -> Sequence[str] | None:
    if explicit_search_path is not None:
        return explicit_search_path
    if env is not None:
        return None
    paths: list[str] = []
    for root in (Path.cwd(), _REPO_ROOT):
        node_bin = root / "node_modules" / ".bin"
        node_bin_str = str(node_bin)
        if node_bin_str not in paths:
            paths.append(node_bin_str)
    process_path = os.environ.get("PATH", "")
    paths.extend(part for part in process_path.split(os.pathsep) if part)
    return tuple(paths) if paths else None


def _validate_document_viewer_ux_joins(
    document_records: Sequence[DocumentEvidenceRecord],
    document_viewer_ux_artifacts: Sequence[DocumentViewerUxArtifact],
) -> None:
    if not document_viewer_ux_artifacts:
        return
    valid_joins = {
        (record.structured_diff_id, record.correlation_id) for record in document_records
    }
    for artifact in document_viewer_ux_artifacts:
        if artifact.document_diff_id is None:
            raise DocumentHarnessEvidenceError(
                f"document viewer UX artifact does not carry a document_diff_id: "
                f"{artifact.artifact_id}"
            )
        join_key = (artifact.document_diff_id, artifact.correlation_id)
        if join_key not in valid_joins:
            raise DocumentHarnessEvidenceError(
                "document viewer UX artifact does not join a backend document diff "
                f"record by document_diff_id and correlation_id: {artifact.artifact_id}"
            )
