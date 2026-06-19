# SPDX-License-Identifier: Apache-2.0
"""Evidence Fabric v2 dataset runner.

The runner is intentionally local and deterministic. It validates scenario
contracts and emits a typed RunEvidence document without calling live public
service channels, LLM providers, or observability backends.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ummaya.evidence.dataset_contract import (
    DEFAULT_DATASET_REF,
    DEFAULT_SCENARIO_PATH,
    DEFAULT_TASK_REGISTRY_PATH,
    EvidenceContractError,
    resolve_repo_path,
)
from ummaya.evidence.dataset_contract import (
    parse_dataset as _parse_dataset,
)
from ummaya.evidence.document_viewer_ux import DocumentViewerUxArtifact
from ummaya.evidence.gates import build_gates
from ummaya.evidence.models import RunEvidence
from ummaya.evidence.output_payload import build_evidence_output_payload
from ummaya.evidence.route_contracts import (
    route_selection_assertions as _route_selection_assertions,
)
from ummaya.evidence.route_contracts import (
    route_trace_records as _route_trace_records,
)
from ummaya.evidence.task_registry import EvidenceDatasetRef, load_task_registry
from ummaya.evidence.tool_layer import build_tool_layer_events


def _resolve_task_dataset(
    *,
    dataset_id: str,
    scenario_path: Path,
    task_registry_path: Path | None,
    dataset_ref: str,
) -> tuple[str | None, EvidenceDatasetRef | None]:
    if task_registry_path is None:
        return None, None
    registry = load_task_registry(task_registry_path)
    task_dataset = registry.resolve_dataset(dataset_ref)
    if task_dataset.dataset_id != dataset_id:
        raise EvidenceContractError(
            f"task registry dataset_id {task_dataset.dataset_id!r} does not match "
            f"scenario dataset_id {dataset_id!r}"
        )
    if resolve_repo_path(task_dataset.scenario_path) != resolve_repo_path(scenario_path):
        raise EvidenceContractError(
            f"task registry scenario_path {task_dataset.scenario_path} does not match "
            f"run scenario_path {scenario_path}"
        )
    return registry.registry_id, task_dataset


def run_dataset(
    *,
    scenario_path: Path = DEFAULT_SCENARIO_PATH,
    source_ref: str = "local",
    task_registry_path: Path | None = DEFAULT_TASK_REGISTRY_PATH,
    dataset_ref: str = DEFAULT_DATASET_REF,
) -> RunEvidence:
    """Validate a scenario dataset and return a typed evidence document."""

    dataset = _parse_dataset(scenario_path)
    task_registry_id, task_dataset = _resolve_task_dataset(
        dataset_id=dataset.dataset_id,
        scenario_path=scenario_path,
        task_registry_path=task_registry_path,
        dataset_ref=dataset_ref,
    )
    traces = _route_trace_records(dataset)
    return RunEvidence(
        source_ref=source_ref,
        dataset_id=dataset.dataset_id,
        task_registry_id=task_registry_id,
        dataset_ref=task_dataset.ref if task_dataset else None,
        task_count=len(task_dataset.tasks) if task_dataset else 0,
        task_ids=tuple(task.task_id for task in task_dataset.tasks) if task_dataset else (),
        scenario_count=len(dataset.scenarios),
        scenario_ids=tuple(scenario.id for scenario in dataset.scenarios),
        route_trace_records=traces,
        route_selection_assertions=_route_selection_assertions(dataset, traces),
        tool_layer_events=build_tool_layer_events(traces),
        gates=build_gates(dataset),
    )


def main() -> None:
    """CLI entrypoint for `python -m ummaya.evidence`."""

    parser = argparse.ArgumentParser(prog="python -m ummaya.evidence")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=DEFAULT_SCENARIO_PATH,
        help="Path to the Evidence Fabric scenario dataset.",
    )
    parser.add_argument(
        "--source-ref",
        default="local",
        help="Source revision or label recorded in the evidence document.",
    )
    parser.add_argument(
        "--task-registry",
        type=Path,
        default=DEFAULT_TASK_REGISTRY_PATH,
        help="Path to the Harbor-style Evidence Fabric task registry.",
    )
    parser.add_argument(
        "--dataset-ref",
        default=DEFAULT_DATASET_REF,
        help="Harbor-style dataset ref to resolve from the task registry.",
    )
    parser.add_argument(
        "--out", type=Path, default=Path(".evidence/run.json"), help="Output JSON path."
    )
    parser.add_argument(
        "--document-viewer-html",
        type=Path,
        action="append",
        default=None,
        help="Local document viewer HTML path to capture as a Playwright UX artifact.",
    )
    parser.add_argument(
        "--document-viewer-ux-out-dir",
        type=Path,
        default=None,
        help="Directory for Playwright document viewer PNG artifacts.",
    )
    parser.add_argument(
        "--document-viewer-correlation-id",
        default=None,
        help="Correlation ID to attach when the viewer manifest does not carry one.",
    )
    parser.add_argument(
        "--document-viewer-diff-id",
        default=None,
        help="Document diff ID to attach when the viewer manifest does not carry one.",
    )
    args = parser.parse_args()

    evidence = run_dataset(
        scenario_path=args.scenarios,
        source_ref=args.source_ref,
        task_registry_path=args.task_registry,
        dataset_ref=args.dataset_ref,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ux_out_dir = args.document_viewer_ux_out_dir or args.out.parent / "ux-artifacts"
    document_viewer_ux_artifacts: list[DocumentViewerUxArtifact] = []
    document_viewer_html_paths = tuple(args.document_viewer_html or ())
    if document_viewer_html_paths:
        from ummaya.evidence.document_viewer_ux import capture_document_viewer_ux_artifact

        for viewer_html_path in document_viewer_html_paths:
            document_viewer_ux_artifacts.append(
                capture_document_viewer_ux_artifact(
                    viewer_html_path=viewer_html_path,
                    output_dir=ux_out_dir,
                    source_ref=args.source_ref,
                    correlation_id=args.document_viewer_correlation_id,
                    document_diff_id=args.document_viewer_diff_id,
                )
            )
    payload = build_evidence_output_payload(
        evidence,
        document_viewer_ux_artifacts=tuple(document_viewer_ux_artifacts),
    )
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
