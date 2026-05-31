# SPDX-License-Identifier: Apache-2.0
"""Conversation-style smoke evidence for the Public AX document harness."""

from __future__ import annotations

import hashlib
import json
import socket
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from ummaya.evidence.document_harness import load_document_harness_scenario
from ummaya.tools.documents.baselines import (
    BaselineField,
    BaselineTableGeometry,
    BaselineTextAnchor,
    ConformanceBaseline,
    ConformanceBaselineCatalog,
)
from ummaya.tools.documents.engines import DocumentEngineRegistry
from ummaya.tools.documents.models import (
    DocumentExtraction,
    DocumentFormat,
    DocumentPatch,
    FormField,
    ParagraphBlock,
    TableBlock,
    TableCell,
)
from ummaya.tools.executor import ToolExecutor
from ummaya.tools.registry import ToolRegistry


class ConversationDocxEngine:
    """Promoted offline engine double for inspect-to-save conversation smoke."""

    document_format = DocumentFormat.docx
    engine_id = "conversation-docx-engine"

    def inspect(self, path: Path, *, artifact_id: str) -> DocumentExtraction:
        return DocumentExtraction(
            artifact_id=artifact_id,
            paragraphs=[
                ParagraphBlock(
                    block_id="paragraph-001",
                    text="Civil application body text",
                    source_path=f"engine://{self.engine_id}/{path.name}/paragraph/1",
                )
            ],
            tables=[
                TableBlock(
                    block_id="table-001",
                    source_path=f"engine://{self.engine_id}/{path.name}/table/1",
                    cells=[
                        TableCell(
                            row_index=0,
                            column_index=0,
                            text="Applicant",
                            source_path=f"engine://{self.engine_id}/{path.name}/table/1/r1c1",
                        )
                    ],
                )
            ],
            fields=[
                FormField(
                    field_id="applicant_name",
                    label="Applicant name",
                    path="/word/document.xml/field[applicant_name]",
                    field_type="text",
                    required=True,
                    current_value="Prepared applicant",
                    source_confidence=Decimal("1"),
                )
            ],
            metadata={"engine_id": self.engine_id, "format": "docx"},
        )

    def apply_patch(self, path: Path, patch: DocumentPatch) -> bytes:
        marker = "|".join(operation.operation_id for operation in patch.operations)
        return path.read_bytes() + f"\npatched:{marker}".encode()

    def render(self, path: Path, *, artifact_id: str, output_dir: Path) -> tuple[bytes, ...]:
        return (f"render:{artifact_id}:{path.name}:{output_dir.name}".encode(),)


@pytest.mark.asyncio
async def test_conversation_style_inspect_to_save_smoke_evidence_is_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ummaya.tools.documents.registry import DocumentToolRuntime, register_document_tools

    monkeypatch.setenv("UMMAYA_RETRIEVAL_BACKEND", "bm25")
    _forbid_network(monkeypatch)

    scenario = load_document_harness_scenario(Path("evidence/scenarios/document_harness_v1.yaml"))
    source = tmp_path / "civil-form.docx"
    _write_minimal_docx(source)
    source_sha256_before = hashlib.sha256(source.read_bytes()).hexdigest()

    engine_registry = DocumentEngineRegistry()
    engine_registry.register(ConversationDocxEngine())
    runtime = DocumentToolRuntime(
        session_id="session-doc-conversation-smoke",
        artifact_root=tmp_path / "artifacts",
        engine_registry=engine_registry,
        baseline_catalog=_baseline_catalog(),
    )
    registry = ToolRegistry()
    executor = ToolExecutor(registry)
    register_document_tools(registry, executor, runtime=runtime)

    session_identity = object()
    evidence_turns: list[dict[str, object]] = []

    async def invoke_turn(
        *,
        user_intent: str,
        tool_id: str,
        params: dict[str, object],
        request_id: str,
        authenticated: bool = False,
    ) -> dict[str, object]:
        discovered = registry.search(
            f"{user_intent} {tool_id} public document harness",
            max_results=9,
        )
        discovered_tool_ids = tuple(result.tool.id for result in discovered)
        assert discovered_tool_ids
        assert tool_id in discovered_tool_ids

        result = await executor.invoke_raw(
            tool_id,
            params,
            request_id=request_id,
            session_identity=session_identity if authenticated else None,
        )
        assert isinstance(result, dict)
        assert result["tool_id"] == tool_id
        assert result["correlation_id"] == params["correlation_id"]
        assert result["status"] == "ok"
        artifact_refs = _artifact_refs(result)
        evidence_turns.append(
            {
                "user_intent": user_intent,
                "discovered_tool_ids": discovered_tool_ids,
                "tool_id": tool_id,
                "correlation_id": params["correlation_id"],
                "status": result["status"],
                "artifact_refs": tuple(artifact_refs),
            }
        )
        return result

    inspect_result = await invoke_turn(
        user_intent="업로드한 DOCX 공문서 구조를 검사해줘.",
        tool_id="document_inspect",
        params={
            "correlation_id": "corr-doc-smoke-001",
            "document": {"path": str(source), "expected_format": "docx"},
        },
        request_id="req-doc-smoke-001",
    )
    source_artifact_id = _last_artifact_ref(inspect_result)

    await invoke_turn(
        user_intent="제출양식 입력칸을 확인해줘.",
        tool_id="document_form_schema",
        params={
            "correlation_id": "corr-doc-smoke-002",
            "document": {"artifact_id": source_artifact_id},
        },
        request_id="req-doc-smoke-002",
    )

    copy_result = await invoke_turn(
        user_intent="원본은 건드리지 말고 편집본을 만들어줘.",
        tool_id="document_copy_for_edit",
        params={
            "correlation_id": "corr-doc-smoke-003",
            "document": {"artifact_id": source_artifact_id},
        },
        request_id="req-doc-smoke-003",
        authenticated=True,
    )
    working_artifact_id = _last_artifact_ref(copy_result)

    fill_result = await invoke_turn(
        user_intent="작성할 값을 신청서 필드에 입력해줘.",
        tool_id="document_apply_fill",
        params={
            "correlation_id": "corr-doc-smoke-004",
            "document": {"artifact_id": working_artifact_id},
            "patches": [
                {
                    "target_path": "/word/document.xml/field[applicant_name]",
                    "value": "Kim",
                }
            ],
        },
        request_id="req-doc-smoke-004",
        authenticated=True,
    )
    filled_artifact_id = _last_artifact_ref(fill_result)

    render_result = await invoke_turn(
        user_intent="작성본을 검토할 수 있게 렌더 증거를 만들어줘.",
        tool_id="document_render",
        params={
            "correlation_id": "corr-doc-smoke-005",
            "document": {"artifact_id": filled_artifact_id},
        },
        request_id="req-doc-smoke-005",
    )
    assert _last_artifact_ref(render_result).startswith("render-corr-doc-smoke-005")

    validation_result = await invoke_turn(
        user_intent="제출 전 공문서 서식이 맞는지 검증해줘.",
        tool_id="document_validate_public_form",
        params={
            "correlation_id": "corr-doc-smoke-006",
            "document": {"artifact_id": filled_artifact_id},
            "template_id": "civil-form-docx-conversation",
        },
        request_id="req-doc-smoke-006",
    )
    validation_report = validation_result["validation_report"]
    assert isinstance(validation_report, dict)
    assert validation_report["decision"] == "pass"

    save_result = await invoke_turn(
        user_intent="검토가 끝난 완성본을 로컬 최종 파일로 저장해줘.",
        tool_id="document_save",
        params={
            "correlation_id": "corr-doc-smoke-007",
            "document": {"artifact_id": filled_artifact_id},
            "destination_display_name": "civil-form-final.docx",
        },
        request_id="req-doc-smoke-007",
        authenticated=True,
    )
    assert _last_artifact_ref(save_result).startswith("export-corr-doc-smoke-007")

    smoke_evidence = {
        "scenario_id": scenario.scenario_id,
        "network_policy": scenario.network_policy,
        "required_sequence": scenario.required_sequence,
        "turns": tuple(evidence_turns),
    }
    encoded_evidence = json.dumps(smoke_evidence, ensure_ascii=False, sort_keys=True)

    assert tuple(turn["tool_id"] for turn in evidence_turns) == scenario.required_sequence
    assert scenario.acceptance_gates.live_government_calls == "forbidden"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha256_before
    assert "document_bytes" not in encoded_evidence
    assert "Kim" not in encoded_evidence
    assert str(source) not in encoded_evidence


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_connect(self: socket.socket, address: object) -> None:
        raise AssertionError(f"Unexpected live network connect to {address!r}")

    def blocked_connect_ex(self: socket.socket, address: object) -> int:
        raise AssertionError(f"Unexpected live network connect_ex to {address!r}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect_ex)


def _write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<w:document/>")


def _artifact_refs(result: dict[str, object]) -> list[str]:
    artifact_refs = result["artifact_refs"]
    assert isinstance(artifact_refs, list)
    return [str(artifact_ref) for artifact_ref in artifact_refs]


def _last_artifact_ref(result: dict[str, object]) -> str:
    artifact_refs = _artifact_refs(result)
    assert artifact_refs
    return artifact_refs[-1]


def _baseline_catalog() -> ConformanceBaselineCatalog:
    return ConformanceBaselineCatalog(
        version=1,
        catalog_id="document-conversation-smoke-baseline",
        source_policy="offline_fixtures_only",
        live_network_allowed=False,
        baselines=(
            ConformanceBaseline(
                template_id="civil-form-docx-conversation",
                schema_id="civil-form-docx-conversation-v1",
                format=DocumentFormat.docx,
                authoritative_standard="ECMA-376 Office Open XML",
                authority_refs=("tests/tools/documents/test_document_conversation_smoke.py",),
                supports_conformance=True,
                required_fields=(
                    BaselineField(
                        field_id="applicant_name",
                        label="Applicant name",
                        path="/word/document.xml/field[applicant_name]",
                    ),
                ),
                protected_text=(
                    BaselineTextAnchor(
                        text="Civil application body text",
                        anchor="/word/document.xml/p[1]",
                    ),
                ),
                table_geometries=(
                    BaselineTableGeometry(
                        table_id="table-001",
                        anchor="/word/document.xml/tbl[1]",
                        rows=1,
                        columns=1,
                    ),
                ),
            ),
        ),
    )
