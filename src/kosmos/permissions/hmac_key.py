# SPDX-License-Identifier: Apache-2.0
"""HMAC key loader / generator for the KOSMOS consent ledger (Spec 033 FR-D04).

Manages the 32-byte HMAC-SHA-256 secret stored at ``~/.kosmos/keys/ledger.key``
(configurable via ``KOSMOS_PERMISSION_KEY_PATH`` env var).

Security contract (data-model.md § 1.9, Invariant C3):
- File mode MUST be exactly ``0o400`` (owner-read only).
- If the file has any other permission bits set → raise ``HMACKeyFileModeError``
  (fail-closed; refuse to load, block all ledger appends).
- If the file does not exist → generate via ``secrets.token_bytes(32)``, write
  with ``os.open(..., O_WRONLY|O_CREAT|O_EXCL, 0o400)`` (atomic creation, no
  race window), return the 32 bytes.
- Never log or expose the raw key bytes.

Reference: NIST SP 800-107 / RFC 2104 HMAC + data-model.md § 1.9.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path

__all__ = [
    "HMACKeyFileModeError",
    "bootstrap_hmac_key",
    "load_or_generate_key",
]

_logger = logging.getLogger(__name__)

# Expected octal file mode for the HMAC key file.
_REQUIRED_MODE: int = 0o400
# Mask covering all user/group/other r/w/x bits.
_ALL_PERM_BITS: int = 0o777


class HMACKeyFileModeError(PermissionError):
    """Raised when the HMAC key file has an unexpected file mode.

    The ledger refuses to operate with a key whose file mode has drifted from
    ``0o400`` (owner-read only).  The caller must fix the file mode before any
    ledger operations can proceed.

    Attributes:
        path: The path to the key file.
        actual_mode: The actual file mode (octal) that was observed.
        expected_mode: The required file mode (always ``0o400``).
    """

    def __init__(self, path: Path, actual_mode: int) -> None:
        self.path = path
        self.actual_mode = actual_mode
        self.expected_mode = _REQUIRED_MODE
        super().__init__(
            f"HMAC key file {path!r} has mode {oct(actual_mode)} "
            f"but {oct(_REQUIRED_MODE)} is required. "
            "Fix with: chmod 0400 " + str(path)
        )


def load_or_generate_key(path: Path) -> bytes:
    """Load or generate the 32-byte HMAC key at *path*.

    Behaviour:
    - If *path* **exists**:
        1. ``os.stat(path)`` — check ``st_mode & 0o777 == 0o400``.
        2. If mode is wrong → raise ``HMACKeyFileModeError`` (fail-closed).
        3. Read and return the first 32 bytes.
    - If *path* **does not exist**:
        1. Ensure parent directory exists (created with mode ``0o700``).
        2. Generate 32 cryptographically random bytes via
           ``secrets.token_bytes(32)``.
        3. Write atomically via ``os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o400)``
           — raises ``FileExistsError`` on race condition (handled by retrying
           as a load).
        4. Return the 32 bytes.

    Args:
        path: Filesystem path for the HMAC key file.  Typically
              ``Path.home() / ".kosmos" / "keys" / "ledger.key"``.

    Returns:
        32 raw bytes of the HMAC secret.

    Raises:
        HMACKeyFileModeError: If the file exists but has wrong permissions.
        OSError: If the file cannot be read or written for OS reasons.
    """
    key = _load_existing_key(path) if path.exists() else _generate_new_key(path)
    _logger.info("kosmos.permissions.ledger - initialised at %s", path)
    return key


def _load_existing_key(path: Path) -> bytes:
    """Load the key from *path* after verifying its file mode."""
    stat = os.stat(path)
    actual_mode = stat.st_mode & _ALL_PERM_BITS
    if actual_mode != _REQUIRED_MODE:
        _logger.error(
            "HMAC key file mode drift detected: path=%s actual=%s expected=%s",
            path,
            oct(actual_mode),
            oct(_REQUIRED_MODE),
        )
        raise HMACKeyFileModeError(path, actual_mode)

    raw = path.read_bytes()
    if len(raw) < 32:
        raise ValueError(
            f"HMAC key file {path!r} is too short: got {len(raw)} bytes, expected at least 32."
        )
    _logger.debug("HMAC key loaded from %s (key_id inferred from filename)", path)
    return raw[:32]


def _generate_new_key(path: Path) -> bytes:
    """Generate a fresh 32-byte key and write it to *path* with mode 0o400."""
    # Ensure parent directory exists.
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    key_bytes = secrets.token_bytes(32)

    # Atomic creation: O_EXCL guarantees only one process creates the file.
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    except FileExistsError:
        # Race condition: another process created the file between our
        # existence check and the open() call.  Fall back to loading it.
        _logger.debug("Race condition on key generation at %s; loading instead.", path)
        return _load_existing_key(path)

    try:
        os.write(fd, key_bytes)
    finally:
        os.close(fd)

    _logger.info("Generated new HMAC key at %s (mode 0400)", path)
    return key_bytes


def bootstrap_hmac_key(
    key_path: Path,
    key_registry_path: Path,
) -> None:
    """Idempotent boot-time bootstrap: ensure key + registry exist.

    Called once during process startup (e.g. ``cli/app.py::main()``) so that
    the first ledger ``append()`` never encounters a missing key.

    Behaviour:
    - Ensures the 32-byte HMAC key exists at *key_path* (auto-generates if
      absent, validates mode if present).
    - Ensures *key_registry_path* exists with an entry for ``"k0001"``
      pointing to ``"ledger.key"``.  If the registry already exists it is
      left untouched (idempotent).

    Args:
        key_path: Absolute path to the HMAC key file (``~/.kosmos/keys/ledger.key``).
        key_registry_path: Absolute path to the key registry JSON
            (``~/.kosmos/keys/registry.json``).

    Raises:
        HMACKeyFileModeError: If the key file exists with wrong permissions.
        OSError: On unexpected filesystem errors.
    """
    # Step 1: Ensure the HMAC key exists (auto-generates with 0o400 + 0o700 dir).
    load_or_generate_key(key_path)

    # Step 2: Ensure the key registry exists with the initial k0001 entry.
    if not key_registry_path.exists():
        key_registry_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        initial_registry = [
            {
                "key_id": "k0001",
                "retired_at": None,
                "file_path": key_path.name,
            }
        ]
        key_registry_path.write_text(
            json.dumps(initial_registry, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        _logger.info(
            "Initialised HMAC key registry at %s (key_id=k0001, file=%s)",
            key_registry_path,
            key_path.name,
        )
    else:
        _logger.debug("HMAC key registry already exists at %s; skipping init.", key_registry_path)
