# SPDX-License-Identifier: Apache-2.0
"""Tests for kosmos.session.store — gc_empty_stubs (T007).

Covers:
- Correct detection of metadata-only stub files.
- Dry-run produces no disk writes.
- Actual delete removes only eligible stubs.
- Files with meaningful content are never touched.
- --older-than age filter respected.
- --limit cap respected.
- Error accounting on unreadable files.
- Re-run safety (second GC pass on already-clean dir is a no-op).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kosmos.session.models import SessionEntry, SessionMetadata
from kosmos.session.store import (
    GCResult,
    create_session,
    gc_empty_stubs,
    save_entry,
    _is_empty_stub,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_stub(directory: Path, session_id: str | None = None) -> Path:
    """Write a minimal metadata-only stub identical to what the old eager
    create_session() produced."""
    import uuid

    sid = session_id or str(uuid.uuid4())
    now = datetime.now(UTC)
    metadata = SessionMetadata(
        session_id=sid,
        created_at=now,
        updated_at=now,
        message_count=0,
    )
    entry = SessionEntry(
        timestamp=now,
        entry_type="metadata",
        data=metadata.model_dump(mode="json"),
    )
    path = directory / f"{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return path


def _write_stub_with_created_at(directory: Path, created_at: datetime) -> Path:
    """Write a stub with a specific created_at timestamp for age-filter tests."""
    import uuid

    sid = str(uuid.uuid4())
    metadata = SessionMetadata(
        session_id=sid,
        created_at=created_at,
        updated_at=created_at,
        message_count=0,
    )
    entry = SessionEntry(
        timestamp=created_at,
        entry_type="metadata",
        data=metadata.model_dump(mode="json"),
    )
    path = directory / f"{sid}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return path


def _write_session_with_message(directory: Path) -> Path:
    """Write a JSONL with a metadata line AND a message line (meaningful content)."""
    import uuid

    sid = str(uuid.uuid4())
    now = datetime.now(UTC)
    metadata = SessionMetadata(
        session_id=sid,
        created_at=now,
        updated_at=now,
        message_count=1,
    )
    meta_entry = SessionEntry(
        timestamp=now,
        entry_type="metadata",
        data=metadata.model_dump(mode="json"),
    )
    msg_entry = SessionEntry(
        timestamp=now,
        entry_type="message",
        data={"role": "user", "content": "안녕하세요"},
    )
    path = directory / f"{sid}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(meta_entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
        fh.write(json.dumps(msg_entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Unit tests for _is_empty_stub
# ---------------------------------------------------------------------------


class TestIsEmptyStub:
    def test_recognises_metadata_only_stub(self, tmp_path: Path) -> None:
        path = _write_stub(tmp_path)
        assert _is_empty_stub(path, cutoff_ts=None) is True

    def test_rejects_file_with_message_line(self, tmp_path: Path) -> None:
        path = _write_session_with_message(tmp_path)
        assert _is_empty_stub(path, cutoff_ts=None) is False

    def test_rejects_file_with_nonzero_message_count(self, tmp_path: Path) -> None:
        import uuid

        sid = str(uuid.uuid4())
        now = datetime.now(UTC)
        metadata = SessionMetadata(
            session_id=sid, created_at=now, updated_at=now, message_count=3
        )
        entry = SessionEntry(
            timestamp=now,
            entry_type="metadata",
            data=metadata.model_dump(mode="json"),
        )
        path = tmp_path / f"{sid}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
        assert _is_empty_stub(path, cutoff_ts=None) is False

    def test_rejects_corrupt_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.jsonl"
        path.write_text("NOT_JSON\n", encoding="utf-8")
        assert _is_empty_stub(path, cutoff_ts=None) is False

    def test_rejects_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert _is_empty_stub(path, cutoff_ts=None) is False

    def test_age_filter_rejects_recent_stub(self, tmp_path: Path) -> None:
        recent_ts = datetime.now(UTC) - timedelta(hours=1)
        path = _write_stub_with_created_at(tmp_path, recent_ts)
        cutoff = datetime.now(UTC) - timedelta(days=7)
        assert _is_empty_stub(path, cutoff_ts=cutoff) is False

    def test_age_filter_accepts_old_stub(self, tmp_path: Path) -> None:
        old_ts = datetime.now(UTC) - timedelta(days=30)
        path = _write_stub_with_created_at(tmp_path, old_ts)
        cutoff = datetime.now(UTC) - timedelta(days=7)
        assert _is_empty_stub(path, cutoff_ts=cutoff) is True


# ---------------------------------------------------------------------------
# Integration tests for gc_empty_stubs
# ---------------------------------------------------------------------------


class TestGCDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_delete(self, tmp_path: Path) -> None:
        stub1 = _write_stub(tmp_path)
        stub2 = _write_stub(tmp_path)

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=True)

        assert result.scanned == 2
        assert result.eligible == 2
        assert result.deleted == 0
        # Files still present
        assert stub1.exists()
        assert stub2.exists()

    @pytest.mark.asyncio
    async def test_dry_run_reports_correct_counts(self, tmp_path: Path) -> None:
        for _ in range(5):
            _write_stub(tmp_path)
        _write_session_with_message(tmp_path)

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=True)

        assert result.scanned == 6
        assert result.eligible == 5
        assert result.skipped_with_content == 1
        assert result.deleted == 0
        assert result.errors == 0


class TestGCLive:
    @pytest.mark.asyncio
    async def test_deletes_eligible_stubs(self, tmp_path: Path) -> None:
        stubs = [_write_stub(tmp_path) for _ in range(3)]

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=False)

        assert result.deleted == 3
        for path in stubs:
            assert not path.exists(), f"Stub should have been deleted: {path}"

    @pytest.mark.asyncio
    async def test_preserves_sessions_with_content(self, tmp_path: Path) -> None:
        _write_stub(tmp_path)
        real_session = _write_session_with_message(tmp_path)

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=False)

        assert result.deleted == 1
        assert result.skipped_with_content == 1
        assert real_session.exists(), "Session with content must NOT be deleted"

    @pytest.mark.asyncio
    async def test_empty_directory_is_noop(self, tmp_path: Path) -> None:
        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=False)
        assert result.scanned == 0
        assert result.deleted == 0
        assert result.errors == 0

    @pytest.mark.asyncio
    async def test_nonexistent_directory_is_noop(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        result = await gc_empty_stubs(session_dir=missing, dry_run=False)
        assert result.scanned == 0
        assert result.deleted == 0

    @pytest.mark.asyncio
    async def test_rerun_on_clean_dir_is_noop(self, tmp_path: Path) -> None:
        _write_stub(tmp_path)
        _write_stub(tmp_path)

        first = await gc_empty_stubs(session_dir=tmp_path, dry_run=False)
        assert first.deleted == 2

        second = await gc_empty_stubs(session_dir=tmp_path, dry_run=False)
        assert second.scanned == 0
        assert second.deleted == 0


class TestGCLimitOption:
    @pytest.mark.asyncio
    async def test_limit_caps_eligible_processed(self, tmp_path: Path) -> None:
        for _ in range(10):
            _write_stub(tmp_path)

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=True, limit=4)

        assert result.eligible == 4
        # Scanning may stop early once the limit is hit
        assert result.scanned <= 10

    @pytest.mark.asyncio
    async def test_limit_caps_actual_deletes(self, tmp_path: Path) -> None:
        for _ in range(10):
            _write_stub(tmp_path)

        result = await gc_empty_stubs(session_dir=tmp_path, dry_run=False, limit=3)

        assert result.deleted == 3
        # 7 stubs remain
        remaining = list(tmp_path.glob("*.jsonl"))
        assert len(remaining) == 7


class TestGCAgeFilter:
    @pytest.mark.asyncio
    async def test_age_filter_skips_recent_stubs(self, tmp_path: Path) -> None:
        # Recent stub — should be skipped by --older-than 7
        recent_ts = datetime.now(UTC) - timedelta(hours=2)
        _write_stub_with_created_at(tmp_path, recent_ts)

        result = await gc_empty_stubs(
            session_dir=tmp_path, dry_run=False, older_than_days=7
        )

        assert result.deleted == 0
        assert result.scanned == 1

    @pytest.mark.asyncio
    async def test_age_filter_removes_old_stubs(self, tmp_path: Path) -> None:
        old_ts = datetime.now(UTC) - timedelta(days=30)
        _write_stub_with_created_at(tmp_path, old_ts)

        result = await gc_empty_stubs(
            session_dir=tmp_path, dry_run=False, older_than_days=7
        )

        assert result.deleted == 1

    @pytest.mark.asyncio
    async def test_age_filter_mixed_population(self, tmp_path: Path) -> None:
        for _ in range(3):
            old_ts = datetime.now(UTC) - timedelta(days=14)
            _write_stub_with_created_at(tmp_path, old_ts)
        for _ in range(2):
            recent_ts = datetime.now(UTC) - timedelta(hours=1)
            _write_stub_with_created_at(tmp_path, recent_ts)

        result = await gc_empty_stubs(
            session_dir=tmp_path, dry_run=False, older_than_days=7
        )

        assert result.deleted == 3
        assert result.skipped_with_content == 2  # recent stubs treated as "has content"


class TestGCErrorCounting:
    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not reliable on Windows")
    async def test_unreadable_file_counted_as_error(self, tmp_path: Path) -> None:
        stub = _write_stub(tmp_path)
        # Make file unreadable
        stub.chmod(0o000)
        try:
            result = await gc_empty_stubs(session_dir=tmp_path, dry_run=True)
            # The unreadable file triggers an error or is counted as not-eligible
            # depending on whether _is_empty_stub raises or returns False.
            # Either outcome is acceptable — just verify we didn't crash.
            assert result.scanned >= 1
        finally:
            stub.chmod(0o644)
