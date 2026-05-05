# SPDX-License-Identifier: Apache-2.0
"""Append-only PIPA consent ledger for KOSMOS (Spec 033 FR-D01, FR-D04).

Provides a single public function:

    append(record_data, ledger_path, key_path, key_registry_path) -> ConsentLedgerRecord

The append operation is:
  1. Exclusively locked via ``fcntl.LOCK_EX`` for the duration of
     ``read_last_line + compute_hashes + write_line + fsync``.
  2. Hash-chained: ``prev_hash = SHA-256(canonical(previous_record_without_hash))``.
  3. HMAC-sealed: ``hmac_seal = HMAC-SHA-256(key, record_hash)``.
  4. Written as NDJSON (UTF-8, ``\\n`` terminated).

Security invariants enforced here:
  L1 (genesis): first record ``prev_hash == "0" * 64``.
  L2 (chain):   ``record_hash = SHA-256(canonical(record_without_record_hash_and_hmac_seal))``.
  L3 (HMAC):    ``hmac_seal = HMAC-SHA-256(key, record_hash_bytes)``.
  L4 (key-ID):  ``key_id`` preserved in record; key registry tracks all keys.
  L5 (WORM):    O_WRONLY | O_APPEND — no rewrite, no truncate, no delete.
  C4 (receipt): ``consent_receipt_id`` is UUIDv7 when provided.

References:
  - specs/033-permission-v2-spectrum/spec.md §US1 §US2 FR-D01..FR-D05
  - specs/033-permission-v2-spectrum/data-model.md § 2.1 L1–L5
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac as hmac_lib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kosmos.permissions.canonical_json import canonicalize
from kosmos.permissions.hmac_key import HMACKeyFileModeError, load_or_generate_key
from kosmos.permissions.models import ConsentLedgerRecord

__all__ = [
    "LedgerFilePermissionsError",
    "LedgerKeyMissingError",
    "append",
    "read_last_record",
]

_logger = logging.getLogger(__name__)

# Genesis sentinel: 64 hex zeros (Invariant L1).
_GENESIS_PREV_HASH = "0" * 64

# Required octal file mode for the ledger JSONL file.
_REQUIRED_LEDGER_MODE: int = 0o600
_ALL_PERM_BITS: int = 0o777


class LedgerFilePermissionsError(PermissionError):
    """Raised when the ledger file has an unexpected file mode.

    The ledger loader refuses to operate when the JSONL file's permission
    bits have drifted from ``0o600``.  This prevents other OS users from
    reading or appending to the consent ledger.

    Attributes:
        path: Path to the ledger file.
        actual_mode: Observed file mode (octal).
        expected_mode: Required file mode (``0o600``).
    """

    def __init__(self, path: Path, actual_mode: int) -> None:
        self.path = path
        self.actual_mode = actual_mode
        self.expected_mode = _REQUIRED_LEDGER_MODE
        super().__init__(
            f"Ledger file {path!r} has mode {oct(actual_mode)} "
            f"but {oct(_REQUIRED_LEDGER_MODE)} is required. "
            "Fix with: chmod 0600 " + str(path)
        )


class LedgerKeyMissingError(FileNotFoundError):
    """Raised when no HMAC key exists and cannot be created.

    The ledger refuses to operate without a valid HMAC key.  This prevents
    unprotected records from being silently appended.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            f"HMAC key not found at {path!r}. "
            "Run ``kosmos-permissions rotate-key`` to initialise a key."
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_record_hash(record_dict: dict[str, Any]) -> str:
    """Compute SHA-256 over canonical(record) excluding ``record_hash``/``hmac_seal``.

    Invariant L2: deterministic hash using RFC 8785 JCS canonical encoding.
    The fields ``record_hash`` and ``hmac_seal`` are excluded (zeroed in a copy)
    so the hash does not depend on its own value.

    Returns:
        64-character lowercase hex string.
    """
    hashable = {k: v for k, v in record_dict.items() if k not in ("record_hash", "hmac_seal")}
    canonical_bytes = canonicalize(hashable)
    return hashlib.sha256(canonical_bytes).hexdigest()


def _compute_hmac_seal(key: bytes, record_hash: str) -> str:
    """Compute HMAC-SHA-256 over the record_hash hex string (Invariant L3).

    Using the record_hash (already a deterministic 64-char hex string) as the
    HMAC message means the seal is independent of the hash chain relationship —
    providing two independent integrity checks (chain + HMAC).

    Args:
        key: 32-byte HMAC secret loaded from key file.
        record_hash: 64-character hex string from ``_compute_record_hash``.

    Returns:
        64-character lowercase hex string.
    """
    return hmac_lib.new(key, record_hash.encode("ascii"), "sha256").hexdigest()


def _read_last_line_locked(fd: int) -> bytes | None:
    """Read the last non-empty line from an open file descriptor.

    The file is seeked from current append position.  Called while holding
    ``LOCK_EX`` so the read is consistent with the subsequent write.

    Reads the tail of the file in 1 MiB chunks from EOF backward so that
    ledgers larger than 64 MiB still return the true last record (preserving
    chain integrity — Invariant L3 / L4).

    Args:
        fd: Open file descriptor in O_RDONLY mode on the same path.

    Returns:
        Last non-empty line bytes without trailing newline, or ``None`` if
        the file is empty.

    Raises:
        OSError: Propagated to the caller so a tail-read failure on a
            non-empty ledger fails closed instead of silently re-seeding
            the chain at genesis.
    """
    chunk_size = 1024 * 1024
    file_size = os.lseek(fd, 0, os.SEEK_END)
    if file_size == 0:
        return None

    offset = file_size
    buffer = b""
    while offset > 0:
        read_size = min(chunk_size, offset)
        offset -= read_size
        os.lseek(fd, offset, os.SEEK_SET)
        chunk = os.read(fd, read_size)
        buffer = chunk + buffer
        # Keep reading until we have at least one newline that isn't the
        # trailing one — otherwise the final record may span the chunk
        # boundary.
        stripped = buffer.rstrip(b"\n")
        if b"\n" in stripped:
            _, _, last = stripped.rpartition(b"\n")
            candidate = last.strip()
            if candidate:
                return candidate
    # Whole file is a single line.
    stripped = buffer.rstrip(b"\n")
    candidate = stripped.strip()
    return candidate or None


def _parse_prev_hash(last_line: bytes | None) -> str:
    """Extract ``record_hash`` from the last ledger line to use as ``prev_hash``.

    Args:
        last_line: Raw bytes of the last NDJSON line, or ``None`` for genesis.

    Returns:
        64-char hex string: ``"0" * 64`` for genesis, or last record's hash.

    Raises:
        ValueError: If the last line is not valid JSON or lacks ``record_hash``.
    """
    if last_line is None:
        return _GENESIS_PREV_HASH
    try:
        obj = json.loads(last_line.decode("utf-8"))
        record_hash: str = obj["record_hash"]
        return record_hash
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Ledger corruption: failed to parse prev_hash from last line: {exc}"
        ) from exc


def _get_key_id(key_registry_path: Path) -> str:
    """Return the active key_id from the key registry.

    Registry format (``keys/registry.json``):
    ``[{"key_id": "k0001", "retired_at": null, "file_path": "ledger.key"}, ...]``

    The active key is the last entry with ``retired_at == null``.  If no
    registry exists yet, returns ``"k0001"`` (initial key_id).

    Args:
        key_registry_path: Absolute path to ``keys/registry.json``.

    Returns:
        Active key_id string (e.g. ``"k0001"``).
    """
    if not key_registry_path.exists():
        return "k0001"
    try:
        entries = json.loads(key_registry_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # Fail closed: silently using "k0001" here would tag new records with
        # a key_id unrelated to the actual signing key bytes, producing rows
        # that verify() would later reject.
        raise RuntimeError(
            f"Failed to read/parse key registry at {key_registry_path}. "
            "Ledger append aborted to preserve HMAC verification continuity. "
            f"Root cause: {exc!r}"
        ) from exc
    if not isinstance(entries, list) or not entries:
        return "k0001"
    # Active key = last entry with retired_at == null.
    for entry in reversed(entries):
        if entry.get("retired_at") is None:
            try:
                key_id: str = entry["key_id"]
            except KeyError as exc:
                raise RuntimeError(
                    f"Key registry entry is missing 'key_id' at {key_registry_path}."
                ) from exc
            return key_id
    # Fallback if all entries are retired (should not happen normally).
    try:
        fallback_key_id: str = entries[-1]["key_id"]
    except KeyError as exc:
        raise RuntimeError(
            f"Key registry tail entry is missing 'key_id' at {key_registry_path}."
        ) from exc
    return fallback_key_id


def _ensure_ledger_file(ledger_path: Path) -> None:
    """Create the ledger file with mode 0o600 if it does not exist."""
    if not ledger_path.exists():
        ledger_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        _logger.info("Created new consent ledger at %s (mode 0600)", ledger_path)
    else:
        # Verify existing file has the correct mode.
        stat = os.stat(ledger_path)
        actual_mode = stat.st_mode & _ALL_PERM_BITS
        if actual_mode != _REQUIRED_LEDGER_MODE:
            raise LedgerFilePermissionsError(ledger_path, actual_mode)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_last_record(ledger_path: Path) -> dict[str, Any] | None:
    """Read and parse the last record from the ledger without locking.

    Used by tests and the verifier for non-append operations.

    Args:
        ledger_path: Path to the consent ledger JSONL file.

    Returns:
        Parsed last record dict, or ``None`` if the ledger is empty.
    """
    if not ledger_path.exists() or ledger_path.stat().st_size == 0:
        return None
    content = ledger_path.read_bytes()
    lines = content.rstrip(b"\n").split(b"\n")
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            try:
                record: dict[str, Any] = json.loads(stripped.decode("utf-8"))
                return record
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    return None


def append(  # noqa: C901 — linear 4-step WORM append; splitting hides atomicity
    *,
    tool_id: str,
    mode: str,
    granted: bool,
    action_digest: str,
    version: str = "1.0.0",
    sequence: int | None = None,
    consent_receipt_id: str | None = None,
    purpose: str | None = None,
    data_items: tuple[str, ...] | None = None,
    retention_period: str | None = None,
    refusal_right: str | None = None,
    pipa_class: str | None = None,
    auth_level: str | None = None,
    session_id: str | None = None,
    correlation_id: str | None = None,
    action: str = "allow",
    scope_receipt_id: str | None = None,
    withdrawn_at: datetime | None = None,
    ledger_path: Path,
    key_path: Path,
    key_registry_path: Path,
) -> ConsentLedgerRecord:
    """Append a consent decision record to the PIPA consent ledger.

    This function is the ONLY write path to the ledger.  It enforces:
    - Exclusive file locking (fcntl.LOCK_EX) for the entire
      read-last-line → compute-hashes → write-line → fsync sequence.
    - Hash chaining (L1, L2).
    - HMAC sealing (L3).
    - WORM semantics (L5): uses O_WRONLY | O_APPEND | O_CREAT.
    - Ledger file mode 0o600 enforcement.

    Args:
        tool_id: Canonical adapter identifier.
        mode: PermissionMode string active at time of decision.
        granted: True if citizen granted consent.
        action_digest: SHA-256 hex of canonical(tool_id, args, nonce). 64 chars.
        version: Schema version (default ``"1.0.0"``).
        sequence: Record sequence number.  If ``None``, derived from prev record + 1.
        consent_receipt_id: Optional Kantara CR receipt UUID.
        action: One of ``"allow"`` / ``"deny"`` / ``"withdraw"`` (default ``"allow"``).
        scope_receipt_id: Receipt ID being revoked (non-null when action=="withdraw").
        withdrawn_at: UTC timestamp of withdrawal decision (non-null when action=="withdraw").
        ledger_path: Absolute path to the consent ledger JSONL file.
        key_path: Absolute path to the HMAC key file (mode 0o400).
        key_registry_path: Absolute path to ``keys/registry.json``.

    Returns:
        The fully-populated and sealed ``ConsentLedgerRecord``.

    Raises:
        LedgerFilePermissionsError: If the ledger file has wrong permissions.
        HMACKeyFileModeError: If the HMAC key file has wrong permissions.
        LedgerKeyMissingError: If the HMAC key cannot be loaded or generated.
        ValueError: If ledger data is corrupt.
    """
    # Step 1: Ensure ledger file exists with correct permissions.
    _ensure_ledger_file(ledger_path)

    # Step 2: Load HMAC key (fail-closed on mode error).
    try:
        hmac_key = load_or_generate_key(key_path)
    except HMACKeyFileModeError:
        raise
    except FileNotFoundError as exc:
        raise LedgerKeyMissingError(key_path) from exc

    # Step 3: Determine active key_id.
    key_id = _get_key_id(key_registry_path)

    # Step 4: Open ledger for append + open read-only for last-line.
    # Use O_APPEND to guarantee POSIX atomic append position.
    # Use a separate read fd for reading the last line.
    append_fd = os.open(str(ledger_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    read_fd = os.open(str(ledger_path), os.O_RDONLY)

    try:
        # Step 5: Acquire exclusive lock (wraps read + write + fsync).
        fcntl.flock(append_fd, fcntl.LOCK_EX)
        try:
            # Step 6: Read last line to derive prev_hash and sequence.
            last_line = _read_last_line_locked(read_fd)
            prev_hash = _parse_prev_hash(last_line)

            # Derive sequence number.
            if sequence is None:
                if last_line is None:
                    sequence = 0
                else:
                    try:
                        last_obj = json.loads(last_line.decode("utf-8"))
                        sequence = last_obj.get("sequence", -1) + 1
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        sequence = 0

            # Step 7: Build the record dict for hash computation.
            now = datetime.now(tz=UTC)
            record_dict: dict[str, Any] = {
                "version": version,
                "sequence": sequence,
                "recorded_at": now.isoformat(),
                "tool_id": tool_id,
                "mode": mode,
                "granted": granted,
                "action_digest": action_digest,
                "prev_hash": prev_hash,
                # Placeholders — computed next.
                "record_hash": _GENESIS_PREV_HASH,  # will be replaced
                "hmac_seal": _GENESIS_PREV_HASH,  # will be replaced
                "key_id": key_id,
            }
            if consent_receipt_id is not None:
                record_dict["consent_receipt_id"] = consent_receipt_id
            if purpose is not None:
                record_dict["purpose"] = purpose
            if data_items is not None:
                record_dict["data_items"] = list(data_items)
            if retention_period is not None:
                record_dict["retention_period"] = retention_period
            if refusal_right is not None:
                record_dict["refusal_right"] = refusal_right
            if pipa_class is not None:
                record_dict["pipa_class"] = pipa_class
            if auth_level is not None:
                record_dict["auth_level"] = auth_level
            if session_id is not None:
                record_dict["session_id"] = session_id
            if correlation_id is not None:
                record_dict["correlation_id"] = correlation_id
            # Withdrawal action fields (WS3 extension — always include action so
            # the field participates in the hash even for "allow"/"deny" records).
            record_dict["action"] = action
            if scope_receipt_id is not None:
                record_dict["scope_receipt_id"] = scope_receipt_id
            if withdrawn_at is not None:
                record_dict["withdrawn_at"] = withdrawn_at.isoformat()

            # Step 8: Compute record_hash over record_dict with
            #         record_hash + hmac_seal excluded (L2).
            record_hash = _compute_record_hash(record_dict)

            # Step 9: Compute HMAC seal over record_hash (L3).
            hmac_seal = _compute_hmac_seal(hmac_key, record_hash)

            # Step 10: Fill in the computed values.
            record_dict["record_hash"] = record_hash
            record_dict["hmac_seal"] = hmac_seal

            # Step 11: Serialize to NDJSON.  We serialize BEFORE writing so we
            # can validate the schema while the lock is still held — this
            # guarantees that a schema violation raises before any bytes hit
            # disk (fail-closed for integrity-sensitive storage).
            serialized = json.dumps(record_dict, ensure_ascii=False, separators=(",", ":"))
            record_model = ConsentLedgerRecord.model_validate_json(serialized)
            line_bytes = (serialized + "\n").encode("utf-8")
            os.write(append_fd, line_bytes)

            # Step 12: fsync to ensure durability before releasing the lock.
            os.fsync(append_fd)

        finally:
            # Release the lock even on error.
            fcntl.flock(append_fd, fcntl.LOCK_UN)

    finally:
        os.close(append_fd)
        os.close(read_fd)

    _logger.info(
        "Ledger record appended: sequence=%d tool_id=%s key_id=%s hash=%.16s",
        sequence,
        tool_id,
        key_id,
        record_hash,
    )

    return record_model
