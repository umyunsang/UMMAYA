# SPDX-License-Identifier: Apache-2.0
"""High-level session manager for the KOSMOS REPL.

Bridges the low-level JSONL store with the REPL, handling:
- Session creation and resumption
- Per-turn message persistence
- Auto-titling from the first user message
- Session branching from a point in history
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from kosmos.llm.models import ChatMessage, ToolCall
from kosmos.session.models import SessionEntry, SessionMetadata
from kosmos.session.store import (
    create_session,
    load_session,
    save_entry,
    update_session_metadata,
)

logger = logging.getLogger(__name__)

_AUTO_TITLE_MAX_CHARS = 50


def auto_title(messages: list[ChatMessage]) -> str:
    """Extract a session title from the first user message.

    Takes the first ``user`` role message's content and truncates it to
    :data:`_AUTO_TITLE_MAX_CHARS` characters, appending ``"…"`` if the
    content was longer.

    Args:
        messages: Ordered list of :class:`ChatMessage` objects.

    Returns:
        A short title string, or ``"Untitled"`` if no user message exists.
    """
    for msg in messages:
        if msg.role == "user" and msg.content:
            text = msg.content.strip().replace("\n", " ")
            if len(text) <= _AUTO_TITLE_MAX_CHARS:
                return text
            return text[:_AUTO_TITLE_MAX_CHARS] + "…"
    return "Untitled"


class SessionManager:
    """Manages a single KOSMOS session with JSONL persistence.

    Args:
        session_dir: Override directory (used in tests via ``tmp_path``).
    """

    def __init__(self, session_dir: Path | None = None) -> None:
        self._session_dir = session_dir
        self._metadata: SessionMetadata | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        """Return the active session ID, or ``None`` if no session is open."""
        return self._metadata.session_id if self._metadata else None

    @property
    def metadata(self) -> SessionMetadata | None:
        """Return the current session metadata snapshot."""
        return self._metadata

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def new_session(self) -> SessionMetadata:
        """Create a fresh session, activate it, and materialise the JSONL file.

        :func:`~kosmos.session.store.create_session` is now lazy — it returns
        a :class:`SessionMetadata` without writing to disk.  The SessionManager
        immediately materialises the file by writing the metadata header so
        that :meth:`resume_session` and :func:`~kosmos.session.store.list_sessions`
        work as expected for REPL-managed sessions.

        Returns:
            :class:`SessionMetadata` for the newly created session.
        """
        self._metadata = await create_session(session_dir=self._session_dir)
        logger.debug("Created new session: %s", self._metadata.session_id)

        # Materialise the JSONL file with the metadata header so the session
        # is immediately visible to list_sessions() and resume_session().
        meta_entry = SessionEntry(
            timestamp=self._metadata.created_at,
            entry_type="metadata",
            data=self._metadata.model_dump(mode="json"),
        )
        await save_entry(
            self._metadata.session_id,
            meta_entry,
            session_dir=self._session_dir,
        )
        return self._metadata

    async def resume_session(self, session_id: str) -> list[ChatMessage]:
        """Load an existing session and reconstruct its message history.

        Only entries with ``entry_type == "message"`` are reconstructed into
        :class:`ChatMessage` objects.  Tool-call and tool-result entries are
        currently skipped (they are for audit purposes only).

        Args:
            session_id: UUID string of the session to resume.

        Returns:
            Ordered list of :class:`ChatMessage` objects representing the
            conversation history.

        Raises:
            FileNotFoundError: If no session file exists for *session_id*.
            ValueError: If the session metadata cannot be parsed.
        """
        entries = await load_session(session_id, session_dir=self._session_dir)
        if not entries:
            raise FileNotFoundError(f"Session not found or empty: {session_id}")

        # Reconstruct metadata from the first entry
        meta_entry = entries[0]
        if meta_entry.entry_type == "metadata":
            try:
                self._metadata = SessionMetadata.model_validate(meta_entry.data)
            except Exception as exc:
                raise ValueError(
                    f"Could not parse metadata for session {session_id}: {exc}"
                ) from exc
        else:
            raise ValueError(
                f"Session {session_id}: expected metadata at line 1, got {meta_entry.entry_type!r}"
            )

        # Reconstruct messages (skip metadata entry at index 0)
        messages: list[ChatMessage] = []
        for entry in entries[1:]:
            if entry.entry_type == "message":
                try:
                    messages.append(ChatMessage.model_validate(entry.data))
                except Exception:  # noqa: BLE001
                    logger.warning("Could not reconstruct ChatMessage from entry: %r", entry.data)

        logger.debug("Resumed session %s (%d messages)", session_id, len(messages))
        return messages

    async def branch_session(
        self,
        messages_up_to: list[ChatMessage],
    ) -> SessionMetadata:
        """Create a new session branched from a point in the current session.

        The branch shares the message history supplied in *messages_up_to* and
        records the current session as its parent.

        Args:
            messages_up_to: Message history to carry over into the new branch.

        Returns:
            :class:`SessionMetadata` for the new branch session.
        """
        parent_id = self.session_id
        # Create a new root session
        self._metadata = await create_session(session_dir=self._session_dir)
        new_id = self._metadata.session_id
        logger.debug("Branched session %s from parent %s", new_id, parent_id)

        # Record parent linkage by rewriting metadata
        now = datetime.now(UTC)
        updated = SessionMetadata(
            session_id=new_id,
            created_at=self._metadata.created_at,
            updated_at=now,
            title=self._metadata.title,
            message_count=len(messages_up_to),
            total_tokens_used=self._metadata.total_tokens_used,
            parent_session_id=parent_id,
        )
        await update_session_metadata(updated, session_dir=self._session_dir)
        self._metadata = updated

        # Persist carried-over messages
        for msg in messages_up_to:
            await self._append_message_entry(msg)

        return self._metadata

    # ------------------------------------------------------------------
    # Turn persistence
    # ------------------------------------------------------------------

    async def save_turn(
        self,
        user_msg: ChatMessage,
        assistant_msg: ChatMessage,
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        """Persist one completed turn (user message + assistant response).

        Also appends tool-call entries for each :class:`ToolCall` in
        *tool_calls* if provided, then updates session metadata (title,
        message count, ``updated_at``).

        Args:
            user_msg: The user's message for this turn.
            assistant_msg: The assistant's response for this turn.
            tool_calls: Optional list of tool calls made during this turn.

        Raises:
            RuntimeError: If no session is currently active.
        """
        if self._metadata is None:
            raise RuntimeError("No active session — call new_session() or resume_session() first")

        session_id = self._metadata.session_id

        # Persist user message
        await self._append_message_entry(user_msg)

        # Persist tool calls (audit trail)
        if tool_calls:
            for tc in tool_calls:
                tc_entry = SessionEntry(
                    entry_type="tool_call",
                    data={
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                )
                await save_entry(session_id, tc_entry, session_dir=self._session_dir)

        # Persist assistant message
        await self._append_message_entry(assistant_msg)

        # Update metadata: title, message_count, updated_at
        await self._refresh_metadata(
            messages_delta=2,  # user + assistant
        )

    async def _append_message_entry(self, msg: ChatMessage) -> None:
        """Append a single ChatMessage as a session entry."""
        if self._metadata is None:
            raise RuntimeError("No active session")
        entry = SessionEntry(
            entry_type="message",
            data=msg.model_dump(mode="json"),
        )
        await save_entry(self._metadata.session_id, entry, session_dir=self._session_dir)

    async def _refresh_metadata(
        self,
        messages_delta: int = 0,
        title: str | None = None,
        tokens_delta: int = 0,
    ) -> None:
        """Rewrite the session's metadata line with updated counters."""
        if self._metadata is None:
            return
        now = datetime.now(UTC)
        updated = SessionMetadata(
            session_id=self._metadata.session_id,
            created_at=self._metadata.created_at,
            updated_at=now,
            title=title if title is not None else self._metadata.title,
            message_count=self._metadata.message_count + messages_delta,
            total_tokens_used=self._metadata.total_tokens_used + tokens_delta,
            parent_session_id=self._metadata.parent_session_id,
        )
        await update_session_metadata(updated, session_dir=self._session_dir)
        self._metadata = updated

    async def set_title(self, messages: list[ChatMessage]) -> None:
        """Auto-generate and persist a title from *messages* if not already set.

        A no-op when the session already has a title.

        Args:
            messages: Full message history used for title extraction.
        """
        if self._metadata is None or self._metadata.title is not None:
            return
        title = auto_title(messages)
        await self._refresh_metadata(title=title)
