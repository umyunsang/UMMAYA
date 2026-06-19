# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass

from ummaya.evidence.models import RouteTraceRecord
from ummaya.evidence.tool_layer_models import ToolLayerEvidenceEvent


@dataclass(frozen=True, slots=True)
class ToolLayerEvidenceJoinError(ValueError):
    """Raised when a tool-layer artifact cannot be joined to route evidence."""

    event_id: str

    def __str__(self) -> str:
        return f"tool-layer event does not join to route evidence: {self.event_id}"


def build_tool_layer_events(
    route_trace_records: tuple[RouteTraceRecord, ...],
    *,
    observed_events: tuple[ToolLayerEvidenceEvent, ...] = (),
) -> tuple[ToolLayerEvidenceEvent, ...]:
    """Return validated tool-layer artifacts without synthesizing sample events."""

    if not observed_events:
        return ()

    route_keys = {
        (record.scenario_id, record.trace_id, record.correlation_id)
        for record in route_trace_records
        if record.trace_kind == "scenario_route"
    }
    for event in observed_events:
        event_key = (event.scenario_id, event.trace_id, event.correlation_id)
        if event_key not in route_keys:
            raise ToolLayerEvidenceJoinError(event_id=event.event_id)
    return observed_events
