# SPDX-License-Identifier: Apache-2.0
"""Archive/container write-render-save workflow tests."""

from __future__ import annotations

import gzip
import io
import shutil
import subprocess
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from ummaya.tools.documents.models import BlockedReason, DocumentFormat, ToolResultStatus
from ummaya.tools.documents.registry import DocumentToolRuntime
from ummaya.tools.documents.tool_defs import (
    DocumentFieldPatch,
    DocumentInspectRequest,
    DocumentLocator,
    DocumentPrimitiveRequest,
)


@pytest.mark.parametrize(
    ("suffix", "document_format", "writer", "reader", "target_path", "replacement"),
    (
        (
            "zip",
            DocumentFormat.zip,
            lambda path: _write_zip(path, "forms/application.txt", "before"),
            lambda path: _read_zip(path, "forms/application.txt"),
            "/archive/forms/application.txt/body",
            "after",
        ),
        (
            "epub",
            DocumentFormat.epub,
            lambda path: _write_epub(path, "OPS/content.xhtml", "<html><body>before</body></html>"),
            lambda path: _read_zip(path, "OPS/content.xhtml"),
            "/archive/OPS/content.xhtml/body",
            "<html><body>after</body></html>",
        ),
        (
            "tar",
            DocumentFormat.tar,
            lambda path: _write_tar(path, "forms/application.txt", "before"),
            lambda path: _read_tar(path, "forms/application.txt"),
            "/archive/forms/application.txt/body",
            "after",
        ),
        pytest.param(
            "7z",
            DocumentFormat.seven_z,
            lambda path: _write_7z(path, "forms/application.txt", "before"),
            lambda path: _read_7z(path, "forms/application.txt"),
            "/archive/forms/application.txt/body",
            "after",
            marks=pytest.mark.skipif(
                shutil.which("bsdtar") is None,
                reason="7z archive workflow requires local bsdtar/libarchive.",
            ),
        ),
        (
            "gz",
            DocumentFormat.gz,
            lambda path: _write_gzip(path, "before"),
            lambda path: _read_gzip(path),
            "/gzip/payload",
            "after",
        ),
    ),
)
def test_archive_container_document_primitive_save_renders_rereads_and_diffs(
    tmp_path: Path,
    suffix: str,
    document_format: DocumentFormat,
    writer: Callable[[Path], Path],
    reader: Callable[[Path], str],
    target_path: str,
    replacement: str,
) -> None:
    source = writer(tmp_path / f"bundle.{suffix}")
    original = source.read_bytes()
    destination = tmp_path / "exports" / f"bundle-filled.{suffix}"
    runtime = DocumentToolRuntime(
        session_id=f"archive-container-{suffix}",
        artifact_root=tmp_path / f"store-{suffix}",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id=f"archive-container-{suffix}",
            document=DocumentLocator(path=str(source), expected_format=document_format),
            operation="save",
            instruction=(
                "컨테이너 안의 공공문서 child payload를 작성하고 새 archive derivative로 저장해."
            ),
            patches=(DocumentFieldPatch(target_path=target_path, value=replacement),),
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.ok
    assert result.diff is not None
    assert result.render_artifacts
    assert result.saved_exports
    assert result.saved_exports[0].local_path == destination.resolve()
    assert source.read_bytes() == original
    assert reader(destination) == replacement
    assert any(
        change.target_path == target_path and change.after_value == replacement
        for change in result.diff.changes
    )

    reread = runtime.inspect(
        DocumentInspectRequest(
            correlation_id=f"archive-container-{suffix}-reread",
            document=DocumentLocator(path=str(destination), expected_format=document_format),
        )
    )
    assert reread.status is ToolResultStatus.ok
    assert reread.extraction is not None


def test_archive_container_blocks_path_traversal_child_target_path(tmp_path: Path) -> None:
    source = _write_zip(tmp_path / "bundle.zip", "forms/application.txt", "before")
    original = source.read_bytes()
    destination = tmp_path / "exports" / "bundle-filled.zip"
    runtime = DocumentToolRuntime(
        session_id="archive-container-unsafe-target",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="archive-container-unsafe-target",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.zip),
            operation="save",
            instruction="컨테이너 안의 child payload를 새 archive derivative로 저장해.",
            patches=(DocumentFieldPatch(target_path="/archive/../evil.txt/body", value="owned"),),
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.path_traversal_detected
    assert not destination.exists()
    assert not result.saved_exports
    assert source.read_bytes() == original


def test_archive_container_blocks_path_traversal_source_member_path(tmp_path: Path) -> None:
    source = _write_zip(tmp_path / "bundle.zip", "../evil.txt", "owned")
    original = source.read_bytes()
    destination = tmp_path / "exports" / "bundle-filled.zip"
    runtime = DocumentToolRuntime(
        session_id="archive-container-unsafe-source",
        artifact_root=tmp_path / "store",
    )

    result = runtime.document(
        DocumentPrimitiveRequest(
            correlation_id="archive-container-unsafe-source",
            document=DocumentLocator(path=str(source), expected_format=DocumentFormat.zip),
            operation="save",
            instruction="컨테이너 안의 child payload를 새 archive derivative로 저장해.",
            patches=(
                DocumentFieldPatch(
                    target_path="/archive/forms/application.txt/body",
                    value="safe",
                ),
            ),
            destination_path=str(destination),
        )
    )

    assert result.status is ToolResultStatus.blocked
    assert result.blocked_reason is BlockedReason.path_traversal_detected
    assert not destination.exists()
    assert not result.saved_exports
    assert source.read_bytes() == original


def _write_zip(path: Path, member_name: str, payload: str) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, payload)
    return path


def _write_epub(path: Path, member_name: str, payload: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr(member_name, payload, compress_type=zipfile.ZIP_DEFLATED)
    return path


def _write_tar(path: Path, member_name: str, payload: str) -> Path:
    data = payload.encode("utf-8")
    info = tarfile.TarInfo(member_name)
    info.size = len(data)
    with tarfile.open(path, "w") as archive:
        archive.addfile(info, io.BytesIO(data))
    return path


def _write_gzip(path: Path, payload: str) -> Path:
    with gzip.open(path, "wb") as archive:
        archive.write(payload.encode("utf-8"))
    return path


def _write_7z(path: Path, member_name: str, payload: str) -> Path:
    source_root = path.parent / f"{path.stem}-src"
    member_path = source_root / member_name
    member_path.parent.mkdir(parents=True, exist_ok=True)
    member_path.write_text(payload, encoding="utf-8")
    _run_bsdtar(
        [
            "-cf",
            str(path),
            "--format=7zip",
            "-C",
            str(source_root),
            member_name,
        ]
    )
    return path


def _read_zip(path: Path, member_name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(member_name).decode("utf-8")


def _read_tar(path: Path, member_name: str) -> str:
    with tarfile.open(path) as archive:
        member = archive.extractfile(member_name)
        assert member is not None
        return member.read().decode("utf-8")


def _read_gzip(path: Path) -> str:
    with gzip.open(path, "rb") as archive:
        return archive.read().decode("utf-8")


def _read_7z(path: Path, member_name: str) -> str:
    result = _run_bsdtar(["-xOf", str(path), member_name], capture_output=True)
    return result.stdout.decode("utf-8")


def _run_bsdtar(
    args: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("bsdtar")
    assert executable is not None
    return subprocess.run(  # noqa: S603 - test-only static argv.
        [executable, *args],
        check=True,
        capture_output=capture_output,
        timeout=15,
    )
