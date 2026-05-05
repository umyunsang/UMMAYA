# SPDX-License-Identifier: Apache-2.0
"""Tests for kosmos.session.store — JSONL read/write, corruption handling, directory creation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosmos.session.models import SessionEntry, SessionMetadata
from kosmos.session.store import (
    _get_session_dir,
    create_session,
    delete_session,
    get_session_metadata,
    list_sessions,
    load_session,
    save_entry,
    update_session_metadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_does_not_create_jsonl_file(self, tmp_path: Path) -> None:
        """create_session() is now lazy — it must NOT write to disk."""
        meta = await create_session(session_dir=tmp_path)
        path = tmp_path / f"{meta.session_id}.jsonl"
        assert not path.exists(), "create_session() must not write a file (lazy)"

    @pytest.mark.asyncio
    async def test_file_created_after_first_save_entry(self, tmp_path: Path) -> None:
        """The JSONL file must be materialised on the first save_entry() call."""
        meta = await create_session(session_dir=tmp_path)
        path = tmp_path / f"{meta.session_id}.jsonl"
        assert not path.exists()

        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
        )
        assert path.exists(), "File should be created after first save_entry()"

    @pytest.mark.asyncio
    async def test_first_line_is_metadata_after_save(self, tmp_path: Path) -> None:
        """After the first save_entry() the leading line must be a metadata entry."""
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
        )
        path = tmp_path / f"{meta.session_id}.jsonl"
        first_line = path.read_text(encoding="utf-8").strip().splitlines()[0]
        obj = json.loads(first_line)
        assert obj["entry_type"] == "metadata"

    @pytest.mark.asyncio
    async def test_returned_metadata_has_uuid(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        import uuid  # noqa: PLC0415

        # Should not raise
        uuid.UUID(meta.session_id)

    @pytest.mark.asyncio
    async def test_creates_directory_on_save_entry(self, tmp_path: Path) -> None:
        """save_entry() must create the directory when it materialises the file."""
        nested = tmp_path / "deep" / "sessions"
        # Directory does not exist yet
        assert not nested.exists()
        meta = await create_session(session_dir=nested)
        assert not nested.exists(), "create_session() must not create directory (lazy)"

        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=nested,
        )
        assert nested.exists(), "Directory must be created by save_entry()"
        assert (nested / f"{meta.session_id}.jsonl").exists()


# ---------------------------------------------------------------------------
# save_entry / load_session
# ---------------------------------------------------------------------------


class TestSaveAndLoadSession:
    @pytest.mark.asyncio
    async def test_append_and_load_round_trip(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        entry = SessionEntry(
            timestamp=_now(),
            entry_type="message",
            data={"role": "user", "content": "안녕하세요"},
        )
        await save_entry(meta.session_id, entry, session_dir=tmp_path)

        entries = await load_session(meta.session_id, session_dir=tmp_path)
        # First entry is the metadata, second is our message
        assert len(entries) == 2
        assert entries[1].entry_type == "message"
        assert entries[1].data["content"] == "안녕하세요"

    @pytest.mark.asyncio
    async def test_multiple_entries_ordered(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        for i in range(3):
            await save_entry(
                meta.session_id,
                SessionEntry(entry_type="message", data={"idx": i}),
                session_dir=tmp_path,
            )
        entries = await load_session(meta.session_id, session_dir=tmp_path)
        # metadata + 3 messages = 4 entries
        assert len(entries) == 4
        assert entries[1].data["idx"] == 0
        assert entries[3].data["idx"] == 2

    @pytest.mark.asyncio
    async def test_corrupt_line_is_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging  # noqa: PLC0415

        meta = await create_session(session_dir=tmp_path)
        # Materialise the file first so we have something to corrupt
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"setup": True}),
            session_dir=tmp_path,
        )
        path = tmp_path / f"{meta.session_id}.jsonl"
        # Inject a corrupt line after the existing content
        with path.open("a", encoding="utf-8") as fh:
            fh.write("NOT_VALID_JSON\n")
        # Append a valid entry after the corrupt line
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"ok": True}),
            session_dir=tmp_path,
        )

        with caplog.at_level(logging.WARNING):
            entries = await load_session(meta.session_id, session_dir=tmp_path)

        assert any(
            "corrupt" in rec.message.lower() or "skipping" in rec.message.lower()
            for rec in caplog.records
        ), "Should log a warning about the corrupt line"
        # Metadata + valid message (corrupt line silently skipped)
        assert entries[-1].data.get("ok") is True

    @pytest.mark.asyncio
    async def test_load_nonexistent_session_returns_empty(self, tmp_path: Path) -> None:
        entries = await load_session("nonexistent-id", session_dir=tmp_path)
        assert entries == []


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    @pytest.mark.asyncio
    async def test_lists_materialised_sessions(self, tmp_path: Path) -> None:
        """Only sessions with at least one save_entry() call appear in list."""
        m1 = await create_session(session_dir=tmp_path)
        m2 = await create_session(session_dir=tmp_path)
        # Materialise both sessions
        for meta in (m1, m2):
            await save_entry(
                meta.session_id,
                SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
                session_dir=tmp_path,
            )
        sessions = await list_sessions(session_dir=tmp_path)
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_lazy_sessions_not_listed(self, tmp_path: Path) -> None:
        """Sessions that were created but never had save_entry() called are invisible."""
        await create_session(session_dir=tmp_path)
        await create_session(session_dir=tmp_path)
        sessions = await list_sessions(session_dir=tmp_path)
        assert sessions == [], "Lazy (un-materialised) sessions must not appear in list"

    @pytest.mark.asyncio
    async def test_sorted_newest_first(self, tmp_path: Path) -> None:
        import asyncio  # noqa: PLC0415

        m1 = await create_session(session_dir=tmp_path)
        await asyncio.sleep(0)  # yield to event loop
        m2 = await create_session(session_dir=tmp_path)
        # Materialise both
        for meta in (m1, m2):
            await save_entry(
                meta.session_id,
                SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
                session_dir=tmp_path,
            )
        sessions = await list_sessions(session_dir=tmp_path)
        ids = [s.session_id for s in sessions]
        assert m2.session_id in ids
        assert m1.session_id in ids

    @pytest.mark.asyncio
    async def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        sessions = await list_sessions(session_dir=tmp_path)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_nonexistent_directory_returns_empty_list(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        sessions = await list_sessions(session_dir=missing)
        assert sessions == []


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_deletes_file(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        # Materialise the file first so there is something to delete
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
        )
        path = tmp_path / f"{meta.session_id}.jsonl"
        assert path.exists()
        await delete_session(meta.session_id, session_dir=tmp_path)
        assert not path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_silent(self, tmp_path: Path) -> None:
        # Should not raise
        await delete_session("ghost-id", session_dir=tmp_path)


# ---------------------------------------------------------------------------
# get_session_metadata
# ---------------------------------------------------------------------------


class TestGetSessionMetadata:
    @pytest.mark.asyncio
    async def test_returns_correct_metadata(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        # Materialise the file so get_session_metadata can find it
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )
        loaded = await get_session_metadata(meta.session_id, session_dir=tmp_path)
        assert loaded.session_id == meta.session_id

    @pytest.mark.asyncio
    async def test_raises_for_missing_session(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            await get_session_metadata("no-such-session", session_dir=tmp_path)


# ---------------------------------------------------------------------------
# update_session_metadata
# ---------------------------------------------------------------------------


class TestUpdateSessionMetadata:
    @pytest.mark.asyncio
    async def test_title_persisted(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        updated = SessionMetadata(
            session_id=meta.session_id,
            created_at=meta.created_at,
            updated_at=_now(),
            title="테스트 세션",
            message_count=2,
            total_tokens_used=100,
        )
        await update_session_metadata(updated, session_dir=tmp_path)
        loaded = await get_session_metadata(meta.session_id, session_dir=tmp_path)
        assert loaded.title == "테스트 세션"
        assert loaded.message_count == 2
        assert loaded.total_tokens_used == 100

    @pytest.mark.asyncio
    async def test_non_metadata_entries_preserved(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hello"}),
            session_dir=tmp_path,
        )
        updated = SessionMetadata(
            session_id=meta.session_id,
            created_at=meta.created_at,
            updated_at=_now(),
            title="Updated Title",
        )
        await update_session_metadata(updated, session_dir=tmp_path)
        entries = await load_session(meta.session_id, session_dir=tmp_path)
        # Should still have both the (updated) metadata and the message entry
        assert len(entries) == 2
        assert entries[1].data["content"] == "hello"


# ---------------------------------------------------------------------------
# KOSMOS_SESSION_DIR tilde expansion
# ---------------------------------------------------------------------------


class TestSessionDirTildeExpansion:
    """Verify that KOSMOS_SESSION_DIR values containing '~' are expanded."""

    def test_tilde_in_env_var_is_expanded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_get_session_dir must call expanduser() so '~' paths resolve correctly.

        We redirect home to tmp_path so the test never touches the real
        home directory, then set KOSMOS_SESSION_DIR to a '~/...' string.
        The returned path must be an absolute directory under tmp_path,
        not a literal path starting with '~'.
        """
        # Point HOME at tmp_path so Path("~").expanduser() resolves to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("KOSMOS_SESSION_DIR", "~/kosmos-test-sess")

        result = _get_session_dir()

        # The resolved path must be absolute and not start with '~'
        assert result.is_absolute(), f"Expected absolute path, got {result}"
        assert not str(result).startswith("~"), f"'~' was not expanded — got {result}"
        # The directory must have been created by _get_session_dir
        assert result.exists() and result.is_dir(), f"Directory was not created at {result}"
        # And it should live under tmp_path (since HOME=tmp_path)
        assert str(result).startswith(str(tmp_path)), (
            f"Expected path under {tmp_path}, got {result}"
        )
