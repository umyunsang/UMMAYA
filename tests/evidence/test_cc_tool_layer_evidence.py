# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

_TOOL_LAYER_ARTIFACT_PATH = Path(
    "tests/fixtures/evidence/cc-original-tool-layer-port/task-17-agentfix-tui-matrix.txt"
)


def test_run_dataset_does_not_synthesize_tool_layer_events_from_routes() -> None:
    from ummaya.evidence.runner import run_dataset

    evidence = run_dataset(source_ref="global-codefix")

    assert evidence.route_trace_records
    assert evidence.tool_layer_events == ()
    assert "correlation_id" in evidence.trace_join_keys
    assert "frame_hash" in evidence.trace_join_keys

    encoded = json.loads(evidence.model_dump_json())
    assert encoded["tool_layer_events"] == []


def test_accepts_joinable_real_tool_layer_artifact_fixture() -> None:
    from ummaya.evidence.runner import run_dataset
    from ummaya.evidence.tool_layer import ToolLayerEvidenceEvent, build_tool_layer_events

    evidence = run_dataset(source_ref="global-codefix")
    route = evidence.route_trace_records[0]
    artifact_path = _TOOL_LAYER_ARTIFACT_PATH
    artifact_bytes = artifact_path.read_bytes()
    event = ToolLayerEvidenceEvent(
        event_id="tool-layer-global-codefix-fixture",
        scenario_id=route.scenario_id,
        trace_id=route.trace_id,
        correlation_id=route.correlation_id,
        frame_hash=sha256(artifact_bytes).hexdigest(),
        render_frame="blocked_state",
        selected_tool="Agent",
        exposure_state="permission-gated-callable",
        trust_tier=4,
        permission_decision="denied",
        source_url=None,
        source_local_handle=str(artifact_path),
        source_citation_id="cite-global-codefix-agent-fixture",
        provenance_id="prov-global-codefix-agent-fixture",
        source_trust="trusted",
        source_prompt_injection="not_detected",
        source_instruction_visibility="evidence_only",
        result_status="blocked",
        result_summary=None,
        error_summary="Agent delegation was blocked in the captured TUI artifact.",
        blocked_state="blocked_by_permission",
    )

    events = build_tool_layer_events(evidence.route_trace_records, observed_events=(event,))

    assert events == (event,)


def test_rejects_unjoinable_tool_layer_artifact_fixture() -> None:
    from ummaya.evidence.runner import run_dataset
    from ummaya.evidence.tool_layer import (
        ToolLayerEvidenceEvent,
        ToolLayerEvidenceJoinError,
        build_tool_layer_events,
    )

    evidence = run_dataset(source_ref="global-codefix")
    artifact_path = _TOOL_LAYER_ARTIFACT_PATH
    event = ToolLayerEvidenceEvent(
        event_id="tool-layer-global-codefix-stale",
        scenario_id="not-a-scenario",
        trace_id="not-a-trace",
        correlation_id="not-a-correlation",
        frame_hash="b" * 64,
        render_frame="tool_result",
        selected_tool="WebSearch",
        exposure_state="deferred-searchable",
        trust_tier=3,
        permission_decision="not_required",
        source_url=None,
        source_local_handle=str(artifact_path),
        source_citation_id="cite-global-codefix-stale",
        provenance_id="prov-global-codefix-stale",
        source_trust="trusted",
        source_prompt_injection="not_detected",
        source_instruction_visibility="evidence_only",
        result_status="succeeded",
        result_summary="This stale event must not be accepted.",
        error_summary=None,
        blocked_state="not_blocked",
    )

    with pytest.raises(ToolLayerEvidenceJoinError, match="does not join"):
        build_tool_layer_events(evidence.route_trace_records, observed_events=(event,))


def test_rejects_malformed_tool_layer_evidence_records() -> None:
    from ummaya.evidence.tool_layer import ToolLayerEvidenceEvent

    valid_record = {
        "event_id": "tool-layer-test",
        "scenario_id": "TAX-001",
        "trace_id": "route-tax-001",
        "correlation_id": "corr-route-test",
        "frame_hash": "a" * 64,
        "render_frame": "tool_result",
        "selected_tool": "WebFetchTool",
        "exposure_state": "permission-gated-callable",
        "trust_tier": 3,
        "permission_decision": "approved",
        "source_url": None,
        "source_local_handle": str(_TOOL_LAYER_ARTIFACT_PATH),
        "source_citation_id": "cite-policy",
        "provenance_id": "prov-policy",
        "source_trust": "untrusted",
        "source_prompt_injection": "not_detected",
        "source_instruction_visibility": "evidence_only",
        "result_status": "succeeded",
        "result_summary": "Source fetched with a citation handle.",
        "error_summary": None,
        "blocked_state": "not_blocked",
    }

    without_selected_tool = dict(valid_record)
    del without_selected_tool["selected_tool"]
    with pytest.raises(ValidationError, match="selected_tool"):
        ToolLayerEvidenceEvent.model_validate(without_selected_tool)

    with_extra_field = dict(valid_record)
    with_extra_field["adapter_id"] = "internal-adapter-leak"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ToolLayerEvidenceEvent.model_validate(with_extra_field)

    missing_result = dict(valid_record)
    missing_result["result_summary"] = None
    with pytest.raises(ValidationError, match="succeeded tool-layer event requires result_summary"):
        ToolLayerEvidenceEvent.model_validate(missing_result)


def test_run_evidence_defaults_tool_layer_events_for_existing_consumers() -> None:
    from ummaya.evidence.models import EvidenceGate, RunEvidence

    evidence = RunEvidence(
        source_ref="legacy-consumer",
        dataset_id="legacy-dataset",
        scenario_count=0,
        scenario_ids=(),
        gates=(
            EvidenceGate(
                name="contract",
                status="pass",
                summary="legacy direct constructor",
            ),
        ),
    )

    encoded = json.loads(evidence.model_dump_json())

    assert evidence.tool_layer_events == ()
    assert encoded["tool_layer_events"] == []


def test_scenario_prompt_text_does_not_leak_tool_layer_identifiers() -> None:
    prompt_text = "\n".join(
        (
            Path("evidence/tasks/national-ax-core/instruction.md").read_text(encoding="utf-8"),
            Path("evidence/tasks/national-ax-core/task.toml").read_text(encoding="utf-8"),
            Path("evidence/scenarios/national_ax_citizen_requests_v1.yaml").read_text(
                encoding="utf-8"
            ),
        )
    )

    for leaked_token in (
        "WebFetchTool",
        "BashTool",
        "MCPTool",
        "expected_tool",
        "adapter_id",
    ):
        assert leaked_token not in prompt_text
