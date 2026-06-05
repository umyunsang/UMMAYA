# SPDX-License-Identifier: Apache-2.0
"""Playwright-captured UX evidence for local document viewers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zlib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Literal, Protocol, cast
from urllib.parse import quote
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DocumentViewerUxEvidenceError(ValueError):
    """Raised when document viewer UX evidence cannot be captured."""


class DocumentViewerViewportRect(BaseModel):
    """Viewport rectangle from a hidden document viewer manifest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float
    y: float
    width: float
    height: float


class DocumentViewerManifest(BaseModel):
    """Subset of viewer-manifest.json needed for Evidence Fabric joins."""

    model_config = ConfigDict(frozen=True, extra="allow")

    viewer_artifact_id: str
    mode: Literal["compact", "expand"]
    page_index: int = 0
    correlation_id: str | None = None
    document_diff_id: str | None = None
    source_render_artifact_id: str
    baseline_render_artifact_id: str | None = None
    viewport_rect: DocumentViewerViewportRect | None = None
    change_ids: tuple[str, ...] = Field(default_factory=tuple)
    local_only: bool = True


class DocumentViewerUxArtifact(BaseModel):
    """Join-only UX artifact record for a Playwright document viewer screenshot."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    artifact_kind: Literal["document_viewer_png"] = "document_viewer_png"
    artifact_id: str
    source_ref: str
    capture_tool: Literal["playwright"] = "playwright"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    viewer_artifact_id: str
    mode: Literal["compact", "expand"]
    correlation_id: str
    document_diff_id: str | None = None
    viewer_html_path: str
    viewer_manifest_path: str
    screenshot_path: str
    screenshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    page_index: int
    source_render_artifact_id: str
    baseline_render_artifact_id: str | None = None
    viewport_rect: DocumentViewerViewportRect | None = None
    change_ids: tuple[str, ...] = Field(default_factory=tuple)
    local_only: bool


class PlaywrightCapture(Protocol):
    """Callable boundary for Playwright screenshot capture."""

    def __call__(self, *, viewer_url: str, output_path: Path) -> None:
        """Capture ``viewer_url`` into ``output_path`` as a PNG."""


@dataclass(frozen=True)
class _PngImageData:
    width: int
    height: int
    color_type: int
    compressed_data: bytes


def capture_document_viewer_ux_artifact(
    *,
    viewer_html_path: Path,
    output_dir: Path,
    source_ref: str,
    correlation_id: str | None = None,
    document_diff_id: str | None = None,
    capture: PlaywrightCapture | None = None,
) -> DocumentViewerUxArtifact:
    """Capture a local document viewer with Playwright and return join metadata."""

    viewer_html = viewer_html_path.resolve()
    if not viewer_html.exists():
        raise DocumentViewerUxEvidenceError(f"document viewer html not found: {viewer_html}")
    manifest_path = viewer_html.parent / "viewer-manifest.json"
    manifest = _load_manifest(manifest_path)
    resolved_correlation_id = correlation_id or manifest.correlation_id
    if resolved_correlation_id is None or resolved_correlation_id.strip() == "":
        raise DocumentViewerUxEvidenceError(
            "document viewer UX evidence requires a correlation_id in the "
            "viewer manifest or CLI argument"
        )
    resolved_diff_id = document_diff_id or manifest.document_diff_id

    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = (
        output_dir / f"{manifest.viewer_artifact_id}-{manifest.mode}-playwright.png"
    ).resolve()
    capture_impl = capture or capture_with_playwright_cli
    with _serve_viewer_directory(viewer_html) as viewer_url:
        capture_impl(viewer_url=viewer_url, output_path=screenshot_path)
    if not screenshot_path.exists():
        raise DocumentViewerUxEvidenceError(
            f"Playwright did not create screenshot: {screenshot_path}"
        )
    if not _png_has_visible_nonwhite_pixel(screenshot_path):
        raise DocumentViewerUxEvidenceError(
            f"Playwright document viewer capture is blank: {screenshot_path}"
        )
    screenshot_sha256 = _sha256_file(screenshot_path)

    return DocumentViewerUxArtifact(
        artifact_id=f"ux-{manifest.viewer_artifact_id}-{screenshot_sha256[:12]}",
        source_ref=source_ref,
        viewer_artifact_id=manifest.viewer_artifact_id,
        mode=manifest.mode,
        correlation_id=resolved_correlation_id,
        document_diff_id=resolved_diff_id,
        viewer_html_path=str(viewer_html),
        viewer_manifest_path=str(manifest_path.resolve()),
        screenshot_path=str(screenshot_path),
        screenshot_sha256=screenshot_sha256,
        frame_hash=f"sha256:{screenshot_sha256}",
        page_index=manifest.page_index,
        source_render_artifact_id=manifest.source_render_artifact_id,
        baseline_render_artifact_id=manifest.baseline_render_artifact_id,
        viewport_rect=manifest.viewport_rect,
        change_ids=manifest.change_ids,
        local_only=manifest.local_only,
    )


def capture_with_playwright_cli(*, viewer_url: str, output_path: Path) -> None:
    """Capture a viewer URL through the bundled Playwright CLI wrapper."""

    wrapper = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / (
        "skills/playwright/scripts/playwright_cli.sh"
    )
    if not wrapper.exists():
        raise DocumentViewerUxEvidenceError(f"Playwright CLI wrapper not found: {wrapper}")
    session = f"udv-{uuid4().hex[:12]}"
    env = os.environ.copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commands = (
        (str(wrapper), f"-s={session}", "open", viewer_url),
        (str(wrapper), f"-s={session}", "resize", "1600", "1000"),
        (
            str(wrapper),
            f"-s={session}",
            "eval",
            "() => document.documentElement.dataset.ready || document.readyState",
        ),
        (
            str(wrapper),
            f"-s={session}",
            "screenshot",
            "--filename",
            str(output_path),
            "--full-page",
        ),
    )
    try:
        for command in commands:
            subprocess.run(  # noqa: S603 - fixed local Playwright wrapper plus typed args.
                command,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise DocumentViewerUxEvidenceError(
            f"Playwright document viewer capture failed: {detail}"
        ) from exc
    finally:
        subprocess.run(  # noqa: S603 - cleanup uses the same fixed local wrapper.
            (str(wrapper), f"-s={session}", "close"),
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )


def _load_manifest(path: Path) -> DocumentViewerManifest:
    if not path.exists():
        raise DocumentViewerUxEvidenceError(f"viewer manifest not found: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise DocumentViewerUxEvidenceError(f"viewer manifest must be a mapping: {path}")
    try:
        return DocumentViewerManifest.model_validate(cast(Mapping[str, object], loaded))
    except ValidationError as exc:
        raise DocumentViewerUxEvidenceError(str(exc)) from exc


@contextmanager
def _serve_viewer_directory(viewer_html: Path) -> Iterator[str]:
    handler = partial(
        _QuietViewerRequestHandler,
        directory=str(viewer_html.parent),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        yield f"http://127.0.0.1:{port}/{quote(viewer_html.name)}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class _QuietViewerRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, message_format: str, *args: object) -> None:
        del message_format, args


def _png_has_visible_nonwhite_pixel(path: Path) -> bool:
    image = _load_png_image_data(path)
    channels = 4 if image.color_type == 6 else 3
    stride = image.width * channels
    raw = zlib.decompress(image.compressed_data)
    previous = bytearray(stride)
    offset = 0
    for _row in range(image.height):
        filter_type, scanline, offset = _read_png_scanline(
            raw,
            offset,
            stride,
            path,
        )
        _unfilter_png_scanline(scanline, previous, channels, filter_type)
        if _scanline_has_visible_nonwhite_pixel(scanline, channels):
            return True
        previous = scanline
    return False


def _load_png_image_data(path: Path) -> _PngImageData:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DocumentViewerUxEvidenceError(f"Playwright screenshot is not a PNG: {path}")
    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    interlace = 0
    idat_chunks: list[bytes] = []
    for chunk_type, chunk_data in _iter_png_chunks(data, path):
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk_data[0:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
            interlace = chunk_data[12]
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width <= 0 or height <= 0 or not idat_chunks:
        raise DocumentViewerUxEvidenceError(f"invalid PNG screenshot: {path}")
    if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise DocumentViewerUxEvidenceError(
            f"unsupported PNG screenshot format: bit_depth={bit_depth} "
            f"color_type={color_type} interlace={interlace}"
        )
    return _PngImageData(
        width=width,
        height=height,
        color_type=color_type,
        compressed_data=b"".join(idat_chunks),
    )


def _iter_png_chunks(data: bytes, path: Path) -> Iterator[tuple[bytes, bytes]]:
    pos = 8
    while pos + 8 <= len(data):
        chunk_len = int.from_bytes(data[pos : pos + 4], "big")
        chunk_type = data[pos + 4 : pos + 8]
        chunk_start = pos + 8
        chunk_end = chunk_start + chunk_len
        if chunk_end + 4 > len(data):
            raise DocumentViewerUxEvidenceError(f"invalid PNG chunk bounds: {path}")
        yield chunk_type, data[chunk_start:chunk_end]
        pos = chunk_end + 4
        if chunk_type == b"IEND":
            break


def _read_png_scanline(
    raw: bytes,
    offset: int,
    stride: int,
    path: Path,
) -> tuple[int, bytearray, int]:
    if offset >= len(raw):
        raise DocumentViewerUxEvidenceError(f"truncated PNG scanline data: {path}")
    filter_type = raw[offset]
    next_offset = offset + 1
    scanline = bytearray(raw[next_offset : next_offset + stride])
    if len(scanline) != stride:
        raise DocumentViewerUxEvidenceError(f"truncated PNG scanline data: {path}")
    return filter_type, scanline, next_offset + stride


def _scanline_has_visible_nonwhite_pixel(scanline: bytearray, channels: int) -> bool:
    for pixel in range(0, len(scanline), channels):
        red = scanline[pixel]
        green = scanline[pixel + 1]
        blue = scanline[pixel + 2]
        alpha = scanline[pixel + 3] if channels == 4 else 255
        if alpha > 0 and (red < 250 or green < 250 or blue < 250):
            return True
    return False


def _unfilter_png_scanline(
    scanline: bytearray,
    previous: bytearray,
    bytes_per_pixel: int,
    filter_type: int,
) -> None:
    for index, value in enumerate(scanline):
        left = scanline[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index]
        up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        if filter_type == 0:
            restored = value
        elif filter_type == 1:
            restored = value + left
        elif filter_type == 2:
            restored = value + up
        elif filter_type == 3:
            restored = value + ((left + up) // 2)
        elif filter_type == 4:
            restored = value + _paeth_predictor(left, up, up_left)
        else:
            raise DocumentViewerUxEvidenceError(f"unsupported PNG filter type: {filter_type}")
        scanline[index] = restored & 0xFF


def _paeth_predictor(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    distance_left = abs(estimate - left)
    distance_up = abs(estimate - up)
    distance_up_left = abs(estimate - up_left)
    if distance_left <= distance_up and distance_left <= distance_up_left:
        return left
    if distance_up <= distance_up_left:
        return up
    return up_left


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
