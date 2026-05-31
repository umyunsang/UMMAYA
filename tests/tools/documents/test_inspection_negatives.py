# SPDX-License-Identifier: Apache-2.0
"""Negative inspection tests for unsafe document artifacts."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from ummaya.tools.documents.inspection import inspect_document
from ummaya.tools.documents.intake import DEFAULT_INTAKE_POLICY


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in entries.items():
            package.writestr(name, payload)
    return buffer.getvalue()


def test_inspection_blocks_corrupt_package_before_engine_delegation(tmp_path: Path) -> None:
    source = tmp_path / "broken.docx"
    source.write_bytes(b"PK\x03\x04not-a-valid-package")

    result = inspect_document(source, expected_format="docx")

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "corrupt"
    assert result.extraction is None


def test_inspection_blocks_macro_package_before_engine_delegation(tmp_path: Path) -> None:
    source = tmp_path / "macro.docx"
    source.write_bytes(
        _zip_bytes(
            {
                "[Content_Types].xml": b"<Types/>",
                "word/document.xml": b"<w:document/>",
                "word/vbaProject.bin": b"macro",
            }
        )
    )

    result = inspect_document(source, expected_format="docx")

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "macro_detected"


def test_inspection_blocks_raw_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    source.write_bytes(b"%PDF-1.7\n" + b"A" * 128)
    policy = DEFAULT_INTAKE_POLICY.model_copy(update={"max_raw_bytes": 16})

    result = inspect_document(source, expected_format="pdf", policy=policy)

    assert result.status.value == "blocked"
    assert result.blocked_reason is not None
    assert result.blocked_reason.value == "oversized_raw_bytes"
