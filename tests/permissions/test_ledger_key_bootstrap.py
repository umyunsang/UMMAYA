# SPDX-License-Identifier: Apache-2.0
"""Tests for HMAC key auto-generation and file-permission enforcement (Spec 033 WS3).

Verifies:
  1. Key file auto-generated at the configured path (mode 0o400).
  2. Generated key is exactly 32 bytes.
  3. Boot-time info log is emitted.
  4. Existing key with wrong mode raises HMACKeyFileModeError.
  5. KOSMOS_PERMISSION_KEY_REGISTRY_PATH env var is picked up by KosmosSettings.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from kosmos.permissions.hmac_key import HMACKeyFileModeError, load_or_generate_key


# ---------------------------------------------------------------------------
# Auto-generation
# ---------------------------------------------------------------------------


def test_key_auto_generated_at_path(tmp_path: Path):
    """load_or_generate_key() creates a key file when path does not exist."""
    key_path = tmp_path / "keys" / "ledger.key"
    assert not key_path.exists()

    key = load_or_generate_key(key_path)

    assert key_path.exists(), "Key file must be created"
    assert len(key) == 32, "Key must be exactly 32 bytes"


def test_generated_key_mode_is_0400(tmp_path: Path):
    """Auto-generated key file has mode 0o400 (owner-read only)."""
    key_path = tmp_path / "keys" / "ledger.key"
    load_or_generate_key(key_path)

    actual_mode = os.stat(key_path).st_mode & 0o777
    assert actual_mode == 0o400, f"Expected 0o400, got {oct(actual_mode)}"


def test_generated_key_parent_dir_mode(tmp_path: Path):
    """Parent directory is created with mode 0o700."""
    key_path = tmp_path / "subdir" / "ledger.key"
    load_or_generate_key(key_path)

    parent_mode = os.stat(key_path.parent).st_mode & 0o777
    assert parent_mode == 0o700, f"Expected 0o700, got {oct(parent_mode)}"


# ---------------------------------------------------------------------------
# Boot-time log
# ---------------------------------------------------------------------------


def test_boot_time_log_emitted(tmp_path: Path, caplog):
    """load_or_generate_key() emits an INFO log containing the key path."""
    key_path = tmp_path / "keys" / "ledger.key"

    with caplog.at_level(logging.INFO, logger="kosmos.permissions.hmac_key"):
        load_or_generate_key(key_path)

    # The initialised log line should mention the path.
    combined = "\n".join(caplog.messages)
    assert str(key_path) in combined, (
        f"Boot log should mention key path {key_path!r}. Got:\n{combined}"
    )


def test_boot_time_log_on_load(tmp_path: Path, caplog):
    """load_or_generate_key() also emits INFO when loading an existing key."""
    key_path = tmp_path / "keys" / "ledger.key"
    # Create the key file first.
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, b"\xBE" * 32)
    finally:
        os.close(fd)

    with caplog.at_level(logging.INFO, logger="kosmos.permissions.hmac_key"):
        key = load_or_generate_key(key_path)

    assert len(key) == 32
    combined = "\n".join(caplog.messages)
    assert str(key_path) in combined


# ---------------------------------------------------------------------------
# Wrong mode raises HMACKeyFileModeError (fail-closed)
# ---------------------------------------------------------------------------


def test_wrong_mode_raises_hmac_key_file_mode_error(tmp_path: Path):
    """Key file with wrong mode raises HMACKeyFileModeError (fail-closed)."""
    key_path = tmp_path / "keys" / "ledger.key"
    key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Create with wrong mode (0o644).
    fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, b"\x00" * 32)
    finally:
        os.close(fd)

    with pytest.raises(HMACKeyFileModeError) as exc_info:
        load_or_generate_key(key_path)

    err = exc_info.value
    assert err.actual_mode == 0o644
    assert err.expected_mode == 0o400


# ---------------------------------------------------------------------------
# KosmosSettings picks up KOSMOS_PERMISSION_KEY_REGISTRY_PATH
# ---------------------------------------------------------------------------


def test_settings_key_registry_path_env(tmp_path: Path, monkeypatch):
    """KOSMOS_PERMISSION_KEY_REGISTRY_PATH overrides the default registry path."""
    custom_path = tmp_path / "custom_registry.json"
    monkeypatch.setenv("KOSMOS_PERMISSION_KEY_REGISTRY_PATH", str(custom_path))

    # Re-instantiate to pick up the env var override.
    from kosmos.settings import KosmosSettings

    s = KosmosSettings()
    assert s.permission_key_registry_path == custom_path


def test_settings_key_registry_path_default():
    """Default KOSMOS_PERMISSION_KEY_REGISTRY_PATH is ~/.kosmos/keys/registry.json."""
    from kosmos.settings import KosmosSettings

    s = KosmosSettings()
    expected = Path.home() / ".kosmos" / "keys" / "registry.json"
    assert s.permission_key_registry_path == expected
