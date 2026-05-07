# SPDX-License-Identifier: Apache-2.0
"""Exception types raised by the plugin DX module.

All exceptions inherit from :class:`PluginError` so callers can
``except PluginError`` without enumerating subclasses.
"""

from __future__ import annotations


class PluginError(Exception):
    """Base class for all plugin DX exceptions."""


class PluginRegistrationError(PluginError):
    """Raised when a plugin cannot be registered into the running tool registry.

    Examples include duplicate ``plugin_id``, namespace conflicts with
    reserved active plugin primitives, or invariant violations propagated from
    Spec 022/024/025/031 validators on the embedded ``AdapterRegistration``.
    """


class ManifestValidationError(PluginError):
    """Raised when a ``PluginManifest`` fails Pydantic v2 validation.

    Carries the underlying :class:`pydantic.ValidationError` if applicable
    so the caller can render structured errors back to the contributor.
    """


class AcknowledgmentMismatchError(PluginError):
    """Raised when ``pipa_trustee_acknowledgment.acknowledgment_sha256``
    does not match the canonical SHA-256 computed from
    ``docs/plugins/security-review.md``.

    Carries both ``expected`` and ``actual`` hash values so the caller can
    surface the diff to the contributor with a re-acknowledgment hint.
    """

    def __init__(self, *, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"acknowledgment_sha256 mismatch: expected {expected}, got {actual}. "
            "Re-read docs/plugins/security-review.md and update the manifest."
        )
