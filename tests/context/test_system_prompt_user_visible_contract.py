"""User-visible prompt contract checks."""

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYSTEM_PROMPT = _REPO_ROOT / "prompts" / "system_v1.md"


def test_system_prompt_does_not_teach_internal_turn_labels() -> None:
    """The citizen prompt must not prime models to emit internal labels."""
    text = _SYSTEM_PROMPT.read_text(encoding="utf-8")

    forbidden_labels = [
        "의사분석",
        "Final answer",
        "Final answer turn",
        "도구 호출:",
    ]

    for label in forbidden_labels:
        assert label not in text


def test_system_prompt_requires_natural_user_visible_progress() -> None:
    """Tool preambles should be citizen-visible prose, not transcript metadata."""
    text = _SYSTEM_PROMPT.read_text(encoding="utf-8")

    assert "짧은 진행 문장" in text
    assert "자연어 문장만 작성" in text


def test_system_prompt_forbids_pre_tool_local_file_absence_claims() -> None:
    """Local document preambles must not claim absence before the tool checks."""
    text = _SYSTEM_PROMPT.read_text(encoding="utf-8")

    assert "로컬 문서/파일 진행 문장 guard" in text
    assert "존재 여부를 단정하지 말고" in text
    assert "파일 존재 여부는 도구 결과를 받은 뒤에만 말하십시오" in text
