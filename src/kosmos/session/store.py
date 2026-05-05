# SPDX-License-Identifier: Apache-2.0
"""Append-only JSONL session store for KOSMOS session persistence.

Session files live at ``~/.kosmos/memdir/user/sessions/{session_id}.jsonl``.
Each line is a JSON-serialised :class:`~kosmos.session.models.SessionEntry`.
The first line is always a ``"metadata"`` entry so that :func:`list_sessions`
can cheaply read metadata without loading the full history.

**Lazy file creation**: :func:`create_session` no longer writes a file on
disk immediately.  The session JSONL is created on the first
:func:`save_entry` call for that session — this eliminates the "metadata-only
stub" problem where IPC boot created thousands of zero-message files.

File I/O is dispatched via :func:`asyncio.to_thread` so that the async event
loop is never blocked — no additional dependencies are required.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from kosmos.session.models import SessionEntry, SessionMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default session directory
# ---------------------------------------------------------------------------

def _get_default_session_dir() -> Path:
    """Compute the default session directory.

    Respects ``KOSMOS_MEMDIR_USER`` (canonical Spec 027 env var) first, then
    falls back to ``~/.kosmos/memdir/user``.  The sessions sub-directory is
    always appended.

    Legacy ``KOSMOS_SESSION_DIR`` is retained as a lower-priority override for
    test isolation when the caller cannot set ``KOSMOS_MEMDIR_USER``.
    """
    memdir_user = os.environ.get("KOSMOS_MEMDIR_USER", "").strip()
    if memdir_user:
        return Path(memdir_user).expanduser() / "sessions"
    return Path.home() / ".kosmos" / "memdir" / "user" / "sessions"


def _get_session_dir() -> Path:
    """Return the session directory, creating it if necessary.

    Priority order (first non-empty wins):
    1. ``KOSMOS_MEMDIR_USER`` env var — Spec 027 canonical.  Points to the
       memdir user-tier root; ``sessions/`` sub-dir is appended automatically.
    2. ``KOSMOS_SESSION_DIR`` env var — legacy test-isolation override.
       Treated as a full path (no sub-dir appended).
    3. Hard-coded default: ``~/.kosmos/memdir/user/sessions/``.
    """
    memdir_user = os.environ.get("KOSMOS_MEMDIR_USER", "").strip()
    if memdir_user:
        session_dir = Path(memdir_user).expanduser() / "sessions"
    else:
        legacy_override = os.environ.get("KOSMOS_SESSION_DIR", "").strip()
        if legacy_override:
            session_dir = Path(legacy_override).expanduser()
        else:
            session_dir = _get_default_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _session_path(session_id: str, session_dir: Path | None = None) -> Path:
    """Return the JSONL file path for a given session ID."""
    base = session_dir if session_dir is not None else _get_session_dir()
    return base / f"{session_id}.jsonl"


# ---------------------------------------------------------------------------
# Sync helpers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------


def _sync_write_line(path: Path, obj: dict[str, object]) -> None:
    """Append a single JSON line to *path* (sync, for use in to_thread)."""
    line = json.dumps(obj, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _sync_read_lines(path: Path) -> list[dict[str, object]]:
    """Read all valid JSON lines from *path*, skipping corrupt ones (sync)."""
    results: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    results.append(json.loads(raw))
                except json.JSONDecodeError:
                    logger.warning("Skipping corrupt JSONL line %d in %s", lineno, path)
    except FileNotFoundError:
        pass
    return results


def _sync_read_first_line(path: Path) -> dict[str, object] | None:
    """Read only the first non-empty JSON line from *path* (sync)."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    result: dict[str, object] = json.loads(raw)
                    return result
                except json.JSONDecodeError:
                    logger.warning("Corrupt first line in %s — cannot read metadata", path)
                    return None
    except FileNotFoundError:
        pass
    return None


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def create_session(
    session_dir: Path | None = None,
) -> SessionMetadata:
    """Create a new session identity WITHOUT writing anything to disk.

    The JSONL file is created lazily on the first :func:`save_entry` call so
    that IPC boot no longer produces metadata-only stub files.  Callers that
    need the file to exist immediately should call :func:`save_entry` right
    after with an initial metadata or message entry.

    Args:
        session_dir: Override directory (used in tests via ``tmp_path``).

    Returns:
        :class:`SessionMetadata` for the newly created session.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    return SessionMetadata(
        session_id=session_id,
        created_at=now,
        updated_at=now,
    )


async def save_entry(
    session_id: str,
    entry: SessionEntry,
    session_dir: Path | None = None,
    *,
    session_metadata: SessionMetadata | None = None,
) -> None:
    """Append *entry* to the session JSONL file.

    If the file does not yet exist (lazy-created session) and *entry* is not
    itself a metadata entry, a synthetic metadata header is written first so
    that the file invariant (first line = metadata) is preserved.  Pass
    *session_metadata* to supply accurate ``created_at`` / ``title`` values;
    otherwise a minimal header is derived from the session_id.

    Args:
        session_id: UUID string identifying the target session.
        entry: The :class:`SessionEntry` to persist.
        session_dir: Override directory (used in tests via ``tmp_path``).
        session_metadata: Optional metadata to use as the header when creating
            the file for the first time.  Ignored if the file already exists
            or if *entry* is itself a metadata entry.
    """
    path = _session_path(session_id, session_dir)
    payload = entry.model_dump(mode="json")

    def _write() -> None:
        # Ensure parent directory exists (handles first write for new sessions)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists() and entry.entry_type != "metadata":
            # Write synthetic metadata header so the file invariant holds
            now = datetime.now(UTC)
            if session_metadata is not None:
                meta_obj = session_metadata
            else:
                meta_obj = SessionMetadata(
                    session_id=session_id,
                    created_at=now,
                    updated_at=now,
                )
            meta_entry = SessionEntry(
                timestamp=meta_obj.created_at,
                entry_type="metadata",
                data=meta_obj.model_dump(mode="json"),
            )
            _sync_write_line(path, meta_entry.model_dump(mode="json"))

        _sync_write_line(path, payload)

    await asyncio.to_thread(_write)


async def load_session(
    session_id: str,
    session_dir: Path | None = None,
) -> list[SessionEntry]:
    """Load all entries for a session.

    Corrupt lines are silently skipped (a warning is logged).

    Args:
        session_id: UUID string identifying the session.
        session_dir: Override directory (used in tests via ``tmp_path``).

    Returns:
        Ordered list of :class:`SessionEntry` objects (including the leading
        metadata entry).
    """
    path = _session_path(session_id, session_dir)
    raw_lines = await asyncio.to_thread(_sync_read_lines, path)
    entries: list[SessionEntry] = []
    for raw in raw_lines:
        try:
            entries.append(SessionEntry.model_validate(raw))
        except Exception:  # noqa: BLE001
            logger.warning("Could not deserialise session entry: %r", raw)
    return entries


async def list_sessions(
    session_dir: Path | None = None,
) -> list[SessionMetadata]:
    """Return metadata for all persisted sessions, sorted newest-first.

    Only the first line of each JSONL file is read to keep this O(n) with
    respect to the number of sessions rather than the total history size.

    Args:
        session_dir: Override directory (used in tests via ``tmp_path``).

    Returns:
        List of :class:`SessionMetadata`, sorted by ``updated_at`` descending.
    """
    base = session_dir if session_dir is not None else _get_session_dir()

    def _collect() -> list[SessionMetadata]:
        metas: list[SessionMetadata] = []
        if not base.exists():
            return metas
        for jsonl_path in base.glob("*.jsonl"):
            first = _sync_read_first_line(jsonl_path)
            if first is None:
                continue
            # The first line is a SessionEntry whose data holds the metadata
            try:
                entry = SessionEntry.model_validate(first)
                if entry.entry_type == "metadata":
                    metas.append(SessionMetadata.model_validate(entry.data))
            except Exception:  # noqa: BLE001
                logger.warning("Could not parse metadata from %s", jsonl_path)
        metas.sort(key=lambda m: m.updated_at, reverse=True)
        return metas

    return await asyncio.to_thread(_collect)


async def delete_session(
    session_id: str,
    session_dir: Path | None = None,
) -> None:
    """Delete a session JSONL file.

    Silently succeeds if the file does not exist.

    Args:
        session_id: UUID string identifying the session to remove.
        session_dir: Override directory (used in tests via ``tmp_path``).
    """
    path = _session_path(session_id, session_dir)

    def _remove() -> None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()

    await asyncio.to_thread(_remove)


async def get_session_metadata(
    session_id: str,
    session_dir: Path | None = None,
) -> SessionMetadata:
    """Read the metadata entry for a specific session.

    Args:
        session_id: UUID string identifying the session.
        session_dir: Override directory (used in tests via ``tmp_path``).

    Returns:
        :class:`SessionMetadata` parsed from the first JSONL line.

    Raises:
        FileNotFoundError: If no session file exists for *session_id*.
        ValueError: If the first line cannot be parsed as valid metadata.
    """
    path = _session_path(session_id, session_dir)
    first = await asyncio.to_thread(_sync_read_first_line, path)
    if first is None:
        raise FileNotFoundError(f"Session not found: {session_id}")
    try:
        entry = SessionEntry.model_validate(first)
        if entry.entry_type != "metadata":
            raise ValueError(
                f"Expected metadata entry at line 1 of {path}, got {entry.entry_type!r}"
            )
        return SessionMetadata.model_validate(entry.data)
    except Exception as exc:
        raise ValueError(f"Could not parse metadata for session {session_id}: {exc}") from exc


async def update_session_metadata(
    metadata: SessionMetadata,
    session_dir: Path | None = None,
) -> None:
    """Rewrite the first line of a session file with updated metadata.

    This reads all lines, replaces line 0, and rewrites the file atomically
    (write to a ``.tmp`` file then rename).

    Args:
        metadata: Updated :class:`SessionMetadata` to persist.
        session_dir: Override directory (used in tests via ``tmp_path``).
    """
    path = _session_path(metadata.session_id, session_dir)
    entry = SessionEntry(
        timestamp=metadata.updated_at,
        entry_type="metadata",
        data=metadata.model_dump(mode="json"),
    )

    def _rewrite() -> None:
        raw_lines = _sync_read_lines(path)
        if not raw_lines:
            # File was empty — just create it fresh
            _sync_write_line(path, entry.model_dump(mode="json"))
            return
        # Replace the first line (metadata) and keep the rest
        raw_lines[0] = entry.model_dump(mode="json")
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            for obj in raw_lines:
                fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        tmp_path.replace(path)

    await asyncio.to_thread(_rewrite)


# ---------------------------------------------------------------------------
# Garbage collection — remove metadata-only stub files
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class GCResult:
    """Summary returned by :func:`gc_empty_stubs`."""

    scanned: int = 0
    """Total JSONL files examined."""

    eligible: int = 0
    """Files that qualify as empty stubs (metadata-only, message_count=0)."""

    deleted: int = 0
    """Files actually removed from disk (0 when *dry_run=True*)."""

    skipped_with_content: int = 0
    """Files that had more than one line or a non-zero message_count."""

    errors: int = 0
    """Files that could not be read or deleted due to I/O errors."""


def _is_empty_stub(path: Path, cutoff_ts: datetime | None) -> bool:
    """Return True if *path* is a metadata-only stub with message_count == 0.

    The check is conservative:
    - The file must contain exactly one non-empty line.
    - That line must parse as a SessionEntry with entry_type="metadata".
    - The embedded metadata must have message_count == 0.
    - If *cutoff_ts* is provided the session's ``created_at`` must be older.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = [l.rstrip("\n") for l in fh if l.strip()]
    except OSError:
        return False

    if len(lines) != 1:
        return False

    try:
        obj = json.loads(lines[0])
    except json.JSONDecodeError:
        return False

    if obj.get("entry_type") != "metadata":
        return False

    data = obj.get("data", {})
    if not isinstance(data, dict):
        return False

    if int(data.get("message_count", 0)) != 0:
        return False

    if cutoff_ts is not None:
        created_at_raw = data.get("created_at")
        if created_at_raw is not None:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
                # Ensure timezone-aware comparison
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                if created_at >= cutoff_ts:
                    return False
            except (ValueError, TypeError):
                pass  # Cannot parse timestamp — be conservative and allow GC

    return True


def _sync_gc_empty_stubs(
    session_dir: Path,
    dry_run: bool,
    limit: int | None,
    older_than_days: int | None,
) -> GCResult:
    """Synchronous implementation of stub GC (runs inside asyncio.to_thread)."""
    result = GCResult()

    if not session_dir.exists():
        return result

    cutoff_ts: datetime | None = None
    if older_than_days is not None:
        cutoff_ts = datetime.now(UTC) - timedelta(days=older_than_days)

    for jsonl_path in sorted(session_dir.glob("*.jsonl")):
        result.scanned += 1

        try:
            eligible = _is_empty_stub(jsonl_path, cutoff_ts)
        except Exception:  # noqa: BLE001
            logger.warning("GC: could not inspect %s", jsonl_path)
            result.errors += 1
            continue

        if not eligible:
            result.skipped_with_content += 1
            continue

        result.eligible += 1

        if not dry_run:
            try:
                jsonl_path.unlink()
                result.deleted += 1
                logger.debug("GC: deleted stub %s", jsonl_path)
            except OSError as exc:
                logger.warning("GC: could not delete %s — %s", jsonl_path, exc)
                result.errors += 1

        if limit is not None and result.eligible >= limit:
            # Reached the caller-imposed cap — stop scanning
            break

    return result


async def gc_empty_stubs(
    session_dir: Path | None = None,
    *,
    dry_run: bool = True,
    limit: int | None = None,
    older_than_days: int | None = None,
) -> GCResult:
    """Remove metadata-only stub JSONL files from the session directory.

    A file is considered an empty stub when it contains exactly one JSON line
    whose ``entry_type`` is ``"metadata"`` and whose embedded
    ``message_count`` is ``0``.  This matches the pattern created by the old
    eager :func:`create_session` implementation during IPC boot.

    Safety guarantees:

    - By default *dry_run* is ``True`` — no disk writes occur.
    - Each file is inspected individually before deletion (no bulk rm).
    - Files with any non-metadata content are never touched.
    - The *limit* parameter caps the number of eligible files processed so
      the caller can batch the operation.

    Args:
        session_dir: Override directory (tests / alternative install paths).
        dry_run: When ``True`` (default) log eligible files but do not delete.
        limit: Maximum number of eligible stubs to process in one call.
            ``None`` means process all eligible files found.
        older_than_days: Only consider stubs whose ``created_at`` metadata
            timestamp is older than this many days.  ``None`` means no
            age filter.

    Returns:
        :class:`GCResult` summary with counts for scanned / eligible /
        deleted / skipped / error files.
    """
    base = session_dir if session_dir is not None else _get_session_dir()
    return await asyncio.to_thread(
        _sync_gc_empty_stubs,
        base,
        dry_run,
        limit,
        older_than_days,
    )
