# SPDX-License-Identifier: Apache-2.0
"""Tests for the lazy create_session() behaviour (T007).

After the lazy-creation fix, create_session() must:
- Return a valid SessionMetadata with a UUID session_id.
- NOT write any file to disk.

The first save_entry() call must then materialise the file with:
- A metadata header as line 1 (preserving the invariant).
- The actual entry as line 2.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosmos.session.models import SessionEntry, SessionMetadata
from kosmos.session.store import (
    create_session,
    load_session,
    save_entry,
    get_session_metadata,
    list_sessions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Lazy creation — no disk write on create_session
# ---------------------------------------------------------------------------


class TestCreateSessionLazy:
    @pytest.mark.asyncio
    async def test_no_file_written_on_create(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        jsonl = tmp_path / f"{meta.session_id}.jsonl"
        assert not jsonl.exists(), (
            "create_session() must not write a file — lazy creation expected"
        )

    @pytest.mark.asyncio
    async def test_returns_valid_uuid(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        # uuid.UUID() raises ValueError if not a valid UUID
        uuid.UUID(meta.session_id)

    @pytest.mark.asyncio
    async def test_returned_metadata_has_zero_message_count(
        self, tmp_path: Path
    ) -> None:
        meta = await create_session(session_dir=tmp_path)
        assert meta.message_count == 0

    @pytest.mark.asyncio
    async def test_multiple_creates_produce_unique_ids(
        self, tmp_path: Path
    ) -> None:
        metas = [await create_session(session_dir=tmp_path) for _ in range(5)]
        ids = [m.session_id for m in metas]
        assert len(set(ids)) == 5, "Each create_session call must produce a unique id"

    @pytest.mark.asyncio
    async def test_lazy_create_produces_no_stubs(self, tmp_path: Path) -> None:
        """100 concurrent create_session calls must leave the directory empty."""
        import asyncio

        await asyncio.gather(*[create_session(session_dir=tmp_path) for _ in range(100)])
        stubs = list(tmp_path.glob("*.jsonl"))
        assert stubs == [], (
            f"Expected 0 files after 100 lazy creates, found {len(stubs)}"
        )


# ---------------------------------------------------------------------------
# File materialised on first save_entry
# ---------------------------------------------------------------------------


class TestSaveEntryMaterialisesFile:
    @pytest.mark.asyncio
    async def test_file_created_on_first_save(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        jsonl = tmp_path / f"{meta.session_id}.jsonl"
        assert not jsonl.exists()

        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        assert jsonl.exists(), "File must be created after the first save_entry()"

    @pytest.mark.asyncio
    async def test_first_line_is_metadata_header(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hi"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        jsonl = tmp_path / f"{meta.session_id}.jsonl"
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        first = json.loads(lines[0])
        assert first["entry_type"] == "metadata", (
            "First line must be the metadata header after lazy materialisation"
        )

    @pytest.mark.asyncio
    async def test_message_is_second_line(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "hello"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        jsonl = tmp_path / f"{meta.session_id}.jsonl"
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        second = json.loads(lines[1])
        assert second["entry_type"] == "message"
        assert second["data"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_round_trip_load_session(self, tmp_path: Path) -> None:
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "world"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        entries = await load_session(meta.session_id, session_dir=tmp_path)
        assert len(entries) == 2
        assert entries[0].entry_type == "metadata"
        assert entries[1].data["content"] == "world"

    @pytest.mark.asyncio
    async def test_second_save_appends_without_double_metadata(
        self, tmp_path: Path
    ) -> None:
        meta = await create_session(session_dir=tmp_path)
        for i in range(3):
            await save_entry(
                meta.session_id,
                SessionEntry(entry_type="message", data={"idx": i}),
                session_dir=tmp_path,
                session_metadata=meta,
            )

        entries = await load_session(meta.session_id, session_dir=tmp_path)
        # 1 metadata + 3 messages = 4 lines
        assert len(entries) == 4
        metadata_entries = [e for e in entries if e.entry_type == "metadata"]
        assert len(metadata_entries) == 1, "Must have exactly one metadata header"

    @pytest.mark.asyncio
    async def test_save_metadata_entry_directly(self, tmp_path: Path) -> None:
        """save_entry with entry_type='metadata' must not prepend a second header."""
        meta = await create_session(session_dir=tmp_path)
        now = _now()
        meta_entry = SessionEntry(
            timestamp=now,
            entry_type="metadata",
            data=meta.model_dump(mode="json"),
        )
        await save_entry(
            meta.session_id,
            meta_entry,
            session_dir=tmp_path,
        )

        entries = await load_session(meta.session_id, session_dir=tmp_path)
        assert len(entries) == 1
        assert entries[0].entry_type == "metadata"

    @pytest.mark.asyncio
    async def test_get_session_metadata_after_lazy_materialise(
        self, tmp_path: Path
    ) -> None:
        meta = await create_session(session_dir=tmp_path)
        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "assistant", "content": "Hi!"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        loaded = await get_session_metadata(meta.session_id, session_dir=tmp_path)
        assert loaded.session_id == meta.session_id

    @pytest.mark.asyncio
    async def test_list_sessions_includes_materialised_session(
        self, tmp_path: Path
    ) -> None:
        meta = await create_session(session_dir=tmp_path)
        # Before any save_entry, create_session is lazy — no file on disk
        sessions_before = await list_sessions(session_dir=tmp_path)
        assert not any(s.session_id == meta.session_id for s in sessions_before)

        await save_entry(
            meta.session_id,
            SessionEntry(entry_type="message", data={"role": "user", "content": "test"}),
            session_dir=tmp_path,
            session_metadata=meta,
        )

        sessions_after = await list_sessions(session_dir=tmp_path)
        assert any(s.session_id == meta.session_id for s in sessions_after), (
            "Session must appear in list after first save_entry"
        )
