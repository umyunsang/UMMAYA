# SPDX-License-Identifier: Apache-2.0
"""Integration tests — ``tool_id`` ↔ ``family_hint`` translation (US3 / T006 #2487).

Verifies that ``_VerifyInputForLLM.model_validate`` correctly translates the
LLM-emitted ``{tool_id, params}`` citizen shape to the legacy
``{family_hint, session_context}`` shape that ``_dispatch_primitive`` reads.

Covers contracts/verify-input-shape.md invariants I-V1 / I-V2 / I-V3 / I-V5.

US3 acceptance criterion:
  ``pytest tests/integration/test_tool_id_to_family_hint_translation.py -v``
  reports ≥12 PASS / 0 FAIL (10 canonical-family cases + 1 legacy + 1 unknown
  + 1 idempotency).

References
----------
- ``specs/2297-zeta-e2e-smoke/contracts/verify-input-shape.md`` — I-V1 … I-V8
- ``specs/2297-zeta-e2e-smoke/data-model.md § 1, § 2``
- ``specs/2297-zeta-e2e-smoke/tasks.md`` — T006 #2487
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kosmos.tools.mvp_surface import VERIFY_TOOL, _VerifyInputForLLM

# ---------------------------------------------------------------------------
# Parametrised canonical-family cases (I-V1)
# One case per canonical family; 10 total.
# ---------------------------------------------------------------------------

_CANONICAL_CASES: list[tuple[str, str]] = [
    ("mock_verify_gongdong_injeungseo", "gongdong_injeungseo"),
    ("mock_verify_geumyung_injeungseo", "geumyung_injeungseo"),
    ("mock_verify_ganpyeon_injeung", "ganpyeon_injeung"),
    ("mock_verify_mobile_id", "mobile_id"),
    ("mock_verify_mydata", "mydata"),
    ("mock_verify_module_simple_auth", "simple_auth_module"),
    ("mock_verify_module_modid", "modid"),
    ("mock_verify_module_kec", "kec"),
    ("mock_verify_module_geumyung", "geumyung_module"),
    ("mock_verify_module_any_id_sso", "any_id_sso"),
]

_SAMPLE_PARAMS: dict[str, object] = {
    "scope_list": [
        "lookup:hometax.simplified",
        "submit:hometax.tax-return",
    ],
    "purpose_ko": "종합소득세 신고",
    "purpose_en": "Comprehensive income tax filing",
}


def test_verify_openai_schema_requires_citizen_scope_payload() -> None:
    """The LLM-visible schema must make empty verify params unrepresentable."""
    tool_definition = VERIFY_TOOL.to_openai_tool()
    function = tool_definition["function"]
    assert isinstance(function, dict)
    assert function.get("strict") is True

    parameters = function["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["required"] == ["tool_id", "params"]
    assert parameters["additionalProperties"] is False

    properties = parameters["properties"]
    assert isinstance(properties, dict)
    assert "family_hint" not in properties
    assert "session_context" not in properties

    params_schema = properties["params"]
    assert isinstance(params_schema, dict)
    assert params_schema["required"] == ["scope_list", "purpose_ko", "purpose_en"]
    assert params_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("tool_id", "expected_family"),
    _CANONICAL_CASES,
    ids=[pair[0] for pair in _CANONICAL_CASES],
)
def test_citizen_shape_translates_to_correct_family_hint(
    tool_id: str, expected_family: str
) -> None:
    """I-V1 — LLM-emitted citizen shape MUST translate to the correct family_hint.

    ``_VerifyInputForLLM.model_validate({tool_id: ..., params: ...})`` MUST
    succeed and the resulting instance MUST have:
    - ``family_hint == expected_family`` (translated)
    - ``session_context`` contains the params fields (packed)
    - ``tool_id`` is preserved on the model instance
    - ``params`` is preserved on the model instance
    """
    instance = _VerifyInputForLLM.model_validate({"tool_id": tool_id, "params": _SAMPLE_PARAMS})

    assert instance.family_hint == expected_family, (
        f"tool_id={tool_id!r}: expected family_hint={expected_family!r}, "
        f"got family_hint={instance.family_hint!r}"
    )
    # session_context MUST contain the params fields (packed from params)
    assert instance.session_context.get("purpose_ko") == "종합소득세 신고", (
        "session_context MUST contain purpose_ko from params"
    )
    assert instance.session_context.get("purpose_en") == "Comprehensive income tax filing", (
        "session_context MUST contain purpose_en from params"
    )
    assert "scope_list" in instance.session_context, (
        "session_context MUST contain scope_list from params"
    )
    # Original citizen-shape fields MUST be preserved
    assert instance.tool_id == tool_id, f"tool_id MUST be preserved; got {instance.tool_id!r}"
    assert instance.params == _SAMPLE_PARAMS, "params MUST be preserved on model instance"


# ---------------------------------------------------------------------------
# Legacy shape backward-compat case (I-V2)
# ---------------------------------------------------------------------------


def test_legacy_shape_passes_through_unchanged() -> None:
    """I-V2 — Legacy ``{family_hint, session_context}`` shape MUST work unchanged.

    When the input already has ``family_hint`` set (non-empty), the pre-validator
    MUST return the dict unchanged.  ``tool_id`` defaults to ``None``.
    """
    legacy_input = {
        "family_hint": "modid",
        "session_context": {
            "scope_list": ["lookup:hometax.simplified"],
            "purpose_ko": "홈택스 조회",
        },
    }
    instance = _VerifyInputForLLM.model_validate(legacy_input)

    assert instance.family_hint == "modid"
    assert instance.session_context["purpose_ko"] == "홈택스 조회"
    assert instance.tool_id is None, "tool_id MUST default to None for legacy-shape input"
    assert instance.params is None, "params MUST default to None for legacy-shape input"


# ---------------------------------------------------------------------------
# Unknown tool_id case (I-V3)
# ---------------------------------------------------------------------------


def test_unknown_tool_id_raises_value_error() -> None:
    """I-V3 — Unknown ``tool_id`` MUST raise ``ValueError``.

    The error message MUST contain 'unknown verify tool_id' and the
    offending tool_id value.
    """
    unknown_tool_id = "mock_verify_module_NONEXISTENT"
    with pytest.raises((ValueError, ValidationError)) as exc_info:
        _VerifyInputForLLM.model_validate({"tool_id": unknown_tool_id, "params": {}})

    # Accept either raw ValueError or Pydantic-wrapped ValidationError
    exc_str = str(exc_info.value)
    assert "unknown verify tool_id" in exc_str, (
        f"Error message MUST contain 'unknown verify tool_id'; got: {exc_str!r}"
    )
    assert unknown_tool_id in exc_str, (
        f"Error message MUST contain the offending tool_id; got: {exc_str!r}"
    )


# ---------------------------------------------------------------------------
# Idempotency case (I-V5)
# ---------------------------------------------------------------------------


def test_double_validation_is_idempotent() -> None:
    """I-V5 — Pre-validator MUST be idempotent.

    If ``family_hint`` is already set in the input dict (indicating the dict
    was already translated or is a legacy caller), the pre-validator MUST
    return unchanged — no double translation, no key conflicts.
    """
    # Simulate a dict that has BOTH family_hint AND tool_id set (e.g. a legacy
    # caller that also happens to pass tool_id as extra context).
    both_shape = {
        "family_hint": "modid",
        "tool_id": "mock_verify_module_modid",
        "session_context": {"foo": "bar"},
        "params": {"baz": "qux"},
    }
    instance = _VerifyInputForLLM.model_validate(both_shape)

    # family_hint MUST be the original value — no re-translation
    assert instance.family_hint == "modid"
    # session_context MUST NOT have been overwritten with params
    # (pre-validator bailed out early because family_hint was set)
    assert instance.session_context.get("foo") == "bar", (
        "session_context MUST NOT be overwritten when family_hint is already set"
    )


# ---------------------------------------------------------------------------
# Additional correctness cases
# ---------------------------------------------------------------------------


def test_modid_citizen_shape_full_worked_example() -> None:
    """Verify the worked example from prompts/system_v1.md <verify_chain_pattern>."""
    # This is the exact LLM emit shape from the system prompt's worked example.
    emit = {
        "tool_id": "mock_verify_module_modid",
        "params": {
            "scope_list": [
                "lookup:hometax.simplified",
                "submit:hometax.tax-return",
            ],
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Comprehensive income tax filing",
        },
    }
    instance = _VerifyInputForLLM.model_validate(emit)

    assert instance.family_hint == "modid"
    assert isinstance(instance.session_context["scope_list"], list)
    assert len(instance.session_context["scope_list"]) == 2  # type: ignore[arg-type]


def test_empty_params_dict_accepted() -> None:
    """Empty params dict MUST be accepted (session_context defaults to empty dict)."""
    instance = _VerifyInputForLLM.model_validate(
        {"tool_id": "mock_verify_module_kec", "params": {}}
    )
    assert instance.family_hint == "kec"
    assert instance.session_context == {}


def test_none_params_accepted() -> None:
    """``params=None`` MUST be accepted; session_context defaults to empty dict."""
    instance = _VerifyInputForLLM.model_validate(
        {"tool_id": "mock_verify_mobile_id", "params": None}
    )
    assert instance.family_hint == "mobile_id"
    assert isinstance(instance.session_context, dict)
