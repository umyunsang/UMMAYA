# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from ummaya.ipc.route_diagnostics import log_route_decision_diagnostic
from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool
from ummaya.tools.registry import ToolRegistry
from ummaya.tools.routing import RouteDecisionService


class AviationWeatherInput(BaseModel):
    airport_name: str


class AviationWeatherOutput(BaseModel):
    report: str


def _policy() -> AdapterRealDomainPolicy:
    return AdapterRealDomainPolicy(
        real_classification_url="https://example.go.kr/policy",
        real_classification_text="Published agency policy",
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 6, 5, tzinfo=UTC),
    )


def test_log_route_decision_diagnostic_records_joinable_route_receipt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    registry = ToolRegistry()
    registry.register(
        GovAPITool(
            id="kma_airport_aviation_weather",
            name_ko="항공기상",
            ministry="KMA",
            category=["항공", "기상"],
            endpoint="internal://kma-airport",
            auth_type="public",
            primitive="find",
            policy=_policy(),
            input_schema=AviationWeatherInput,
            output_schema=AviationWeatherOutput,
            search_hint="김해공항 항공기상 AMOS METAR airport aviation weather",
        )
    )
    decision = RouteDecisionService(registry).select_adapters(
        "김해공항 항공기상과 AMOS 확인",
        initial_scores=(("kma_airport_aviation_weather", 12.0),),
    )

    logger = logging.getLogger("tests.route_diagnostics")
    with caplog.at_level(logging.INFO, logger="tests.route_diagnostics"):
        log_route_decision_diagnostic(
            logger=logger,
            turn_index=3,
            session_id="session-1",
            correlation_id="corr-1",
            decision=decision,
        )

    records = [record for record in caplog.records if "[ROUTE_DECISION]" in record.message]
    assert len(records) == 1
    payload = json.loads(records[0].message.split("payload=", maxsplit=1)[1])
    assert payload["turn_index"] == 3
    assert payload["session_id"] == "session-1"
    assert payload["correlation_id"] == "corr-1"
    assert payload["decision_id"] == decision.decision_id
    assert payload["manifest_hash"] == decision.manifest_hash
    assert payload["selected_tools"] == ["kma_airport_aviation_weather"]
    assert payload["stop_reason"] == "answerable"
    assert payload["schema_projection_level"] == "summary"
