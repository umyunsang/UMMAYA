# SPDX-License-Identifier: Apache-2.0
"""Runtime package version helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

_PACKAGE_NAME = "ummaya"
_LOCAL_VERSION = "0.0.0+local"


def get_version() -> str:
    """Return the installed package version, or a local-dev sentinel."""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _LOCAL_VERSION


__version__ = get_version()
