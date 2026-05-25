# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def load_audit_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "tui-realuse-audit.py"
    spec = importlib.util.spec_from_file_location("tui_realuse_audit", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_audit(capture_dir: Path, **kwargs: object) -> dict[str, object]:
    module = load_audit_module()
    defaults = {
        "expected_chain": [],
        "required": [],
        "forbidden": [],
        "require_expanded_trace": False,
        "require_error_rendering": False,
        "allow_rejected": False,
        "strict_frames": False,
    }
    defaults.update(kwargs)
    result = module.run_audit(capture_dir=capture_dir, **defaults)
    assert isinstance(result, dict)
    return result


def write_capture(path: Path, name: str, text: str) -> None:
    target = path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def status_by_name(result: dict[str, object]) -> dict[str, str]:
    checks = result["checks"]
    assert isinstance(checks, list)
    return {str(check["name"]): str(check["status"]) for check in checks}


def test_passes_visible_resolve_lookup_trace(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "UMMAYA final answer\noutbound_traces status_code url")
    write_capture(tmp_path, "frames/frame_0000_boot.txt", "UMMAYA boot")
    write_capture(tmp_path, "frames/frame_0001_locate.txt", "⏺ locate(kakao_keyword_search)")
    write_capture(tmp_path, "frames/frame_0002_lookup.txt", "⏺ find(kma_forecast_fetch)")

    result = run_audit(
        tmp_path,
        expected_chain=["locate", "kma_forecast_fetch"],
        require_expanded_trace=True,
        strict_frames=True,
    )

    assert result["overall"] == "pass"
    assert (tmp_path / "audit.json").is_file()
    assert json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))["overall"] == "pass"


def test_chain_order_uses_chronological_frames_before_cumulative_final_raw(
    tmp_path: Path,
) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        "UMMAYA final answer\noutbound_traces status_code url",
    )
    write_capture(
        tmp_path,
        "final.raw.txt",
        "end-state summary mentions koroad_accident_search before locate text",
    )
    write_capture(tmp_path, "frames/frame_0000_boot.txt", "UMMAYA boot")
    write_capture(tmp_path, "frames/frame_0001_locate.txt", "⏺ locate(kakao_keyword_search)")
    write_capture(
        tmp_path,
        "frames/frame_0002_lookup.txt",
        "⏺ find(koroad_accident_search)",
    )

    result = run_audit(
        tmp_path,
        expected_chain=["locate", "koroad_accident_search"],
        require_expanded_trace=True,
        strict_frames=True,
    )

    assert result["overall"] == "pass"


def test_chain_order_accepts_ordered_sequence_inside_later_expanded_frame(
    tmp_path: Path,
) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        "UMMAYA final answer\noutbound_traces status_code url",
    )
    write_capture(tmp_path, "frames/frame_0000_boot.txt", "UMMAYA boot")
    write_capture(
        tmp_path,
        "frames/frame_0001_partial.txt",
        "⏺ find(koroad_accident_hazard_search)",
    )
    write_capture(
        tmp_path,
        "frames/frame_0002_expanded.txt",
        (
            "⏺ locate(kakao_address_search)\n"
            "⏺ find(koroad_accident_hazard_search)\n"
            "⏺ find(kma_current_observation)"
        ),
    )

    result = run_audit(
        tmp_path,
        expected_chain=[
            "locate",
            "koroad_accident_hazard_search",
            "kma_current_observation",
        ],
        require_expanded_trace=True,
        strict_frames=True,
    )

    assert result["overall"] == "pass"


def test_fails_utf8_replacement_character(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "UMMAYA 마이�레이션")
    write_capture(tmp_path, "frames/frame_0000_final.txt", "UMMAYA 마이�레이션")

    result = run_audit(tmp_path)

    statuses = status_by_name(result)
    assert result["overall"] == "fail"
    assert statuses["utf8_replacement_character"] == "fail"


def test_ignores_raw_pty_replacement_character(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "UMMAYA migration")
    write_capture(tmp_path, "final.raw.txt", "UMMAYA migration�")
    write_capture(tmp_path, "frames/frame_0000_final.txt", "UMMAYA migration")

    result = run_audit(tmp_path)

    statuses = status_by_name(result)
    assert result["overall"] == "pass"
    assert statuses["utf8_replacement_character"] == "pass"


def test_fails_recoverable_invalid_params_without_retry(tmp_path: Path) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        (
            "검색 오류: Invalid parameters. Missing lat, lon.\n"
            "도구 결과 기준으로 처리 상태를 정리합니다."
        ),
    )
    write_capture(
        tmp_path,
        "frames/frame_0000_error.txt",
        "find(kma_forecast_fetch)\nInvalid parameters",
    )

    result = run_audit(tmp_path, expected_chain=["locate", "kma_forecast_fetch"])

    statuses = status_by_name(result)
    assert result["overall"] == "fail"
    assert statuses["agentic_chain_order"] == "fail"
    assert statuses["recoverable_error_loop"] == "fail"


def test_fails_error_rendering_when_raw_has_no_red_ansi(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "Error: Invalid parameters")
    write_capture(tmp_path, "final.raw.txt", "Error: Invalid parameters")
    write_capture(tmp_path, "frames/frame_0000_error.txt", "Error: Invalid parameters")

    result = run_audit(tmp_path, require_error_rendering=True)

    statuses = status_by_name(result)
    assert result["overall"] == "fail"
    assert statuses["cc_error_rendering"] == "fail"


def test_passes_error_rendering_with_red_ansi(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "Error: Invalid parameters (Ctrl+O to see all)")
    write_capture(tmp_path, "final.raw.txt", "\x1b[31mError: Invalid parameters\x1b[0m")
    write_capture(tmp_path, "frames/frame_0000_error.txt", "Error: Invalid parameters")

    result = run_audit(tmp_path, require_error_rendering=True)

    statuses = status_by_name(result)
    assert statuses["cc_error_rendering"] == "pass"


def test_provider_abort_banner_is_not_tool_error_rendering(tmp_path: Path) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        "APIError:Theoperationwasaborted.\nShowing detailed transcript",
    )
    write_capture(tmp_path, "final.raw.txt", "APIError:Theoperationwasaborted.")
    write_capture(tmp_path, "frames/frame_0000_boot.txt", "UMMAYA")

    result = run_audit(tmp_path)

    statuses = status_by_name(result)
    assert result["overall"] == "pass"
    assert statuses["cc_error_rendering"] == "pass"


def test_fails_required_expanded_trace_when_absent(tmp_path: Path) -> None:
    write_capture(tmp_path, "final.txt", "UMMAYA final answer")
    write_capture(tmp_path, "frames/frame_0000_final.txt", "UMMAYA final answer")

    result = run_audit(tmp_path, require_expanded_trace=True)

    statuses = status_by_name(result)
    assert result["overall"] == "fail"
    assert statuses["expanded_tool_trace"] == "fail"


def test_passes_expanded_permission_denial_without_outbound_trace(tmp_path: Path) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        (
            "verify(\n"
            '응답 envelope:\n{"ok": false, "error": {"message": "permission_denied"}}\n'
            "권한 요청이 거부되어 작업을 진행하지 않았습니다. "
            "(code: permission_denied)\n"
            "Showing detailed transcript · ctrl+o to toggle\n"
        ),
    )
    write_capture(tmp_path, "frames/frame_0000_permission.txt", "permission_denied")

    result = run_audit(tmp_path, require_expanded_trace=True)

    statuses = status_by_name(result)
    assert result["overall"] == "pass"
    assert statuses["expanded_tool_trace"] == "pass"


def test_passes_expanded_mock_submit_envelope_without_outbound_trace(tmp_path: Path) -> None:
    write_capture(
        tmp_path,
        "final.txt",
        (
            "submit(\n"
            "응답 envelope:\n"
            '{"ok": true, "result": {"status": "succeeded", '
            '"adapter_receipt": {"receipt_id": "gov24-2026-05-06-MW-ABCD", '
            '"mock": true}, "transaction_id": "tx-123"}}\n'
            "Showing detailed transcript · ctrl+o to toggle\n"
        ),
    )
    write_capture(tmp_path, "frames/frame_0000_submit.txt", "mock_submit_module_gov24_minwon")
    write_capture(
        tmp_path,
        "backend.log",
        "Ledger record appended: sequence=1 tool_id=mock_submit_module_gov24_minwon\n",
    )

    result = run_audit(
        tmp_path,
        expected_chain=["mock_submit_module_gov24_minwon"],
        require_expanded_trace=True,
    )

    statuses = status_by_name(result)
    assert result["overall"] == "pass"
    assert statuses["expanded_tool_trace"] == "pass"
