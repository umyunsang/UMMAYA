# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_capture_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "tui-realuse-pty-capture.py"
    spec = importlib.util.spec_from_file_location("tui_realuse_pty_capture", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_strip_ansi_does_not_emit_replacement_for_incomplete_utf8_tail() -> None:
    module = load_capture_module()

    text = module.strip_ansi("UMMAYA ─".encode()[:-1])

    assert "\ufffd" not in text
    assert text == "UMMAYA "
