# SPDX-License-Identifier: Apache-2.0
"""Pydantic v2 manifest schema for KOSMOS plugins.

Source-of-truth: ``specs/1636-plugin-dx-5tier/data-model.md`` § 1 + § 2.
JSON Schema parity contract: ``specs/1636-plugin-dx-5tier/contracts/manifest.schema.json``
(parity enforced by ``tests/test_schema_parity.py`` — drift fails CI per T008).

The manifest is the *contract* an external developer authors as
``manifest.yaml`` and the registry consumes. It composes (embeds) the
existing Spec 022/031 :class:`~kosmos.tools.registry.AdapterRegistration`
so the same V1-V6 invariant chain (Spec 024/025) and the v1.2 dual-axis
backstop (Spec 031) cover plugin adapters automatically. Plugin-only
fields layered on top: ``plugin_id`` / ``version`` / ``tier`` /
``processes_pii`` / ``pipa_trustee_acknowledgment`` /
``slsa_provenance_url`` / ``otel_attributes`` /
``search_hint_{ko,en}`` / ``permission_layer``.

The 5 cross-field validators below encode the hard invariants the spec
asks the schema to enforce:

* ``_v_mock_source`` — tier ↔ ``mock_source_spec`` consistency (FR-019,
  R-1 Q7-MOCK-SOURCE).
* ``_v_pipa_required`` — ``processes_pii`` ↔
  ``pipa_trustee_acknowledgment`` symmetry (FR-014).
* ``_v_pipa_hash`` — ``acknowledgment_sha256`` byte-equals the canonical
  hash from :mod:`kosmos.plugins.canonical_acknowledgment`
  (FR-014, R-1 Q6-PIPA-HASH).
* ``_v_otel_attribute`` — ``otel_attributes["kosmos.plugin.id"]``
  equals ``plugin_id`` (FR-021, Spec 021 attribute).
* ``_v_namespace`` — ``adapter.tool_id`` follows
  ``plugin.<plugin_id>.<verb>`` with ``<verb>`` in the active plugin
  primitive verbs
  (R-1 Q8-NAMESPACE / Q8-NO-ROOT-OVERRIDE / Q8-VERB-IN-PRIMITIVES,
  ADR-007).

Both models are ``frozen=True`` and ``extra="forbid"``. A successfully
constructed :class:`PluginManifest` is therefore the immutable bundle
contract for a single release; transitions (catalogued / verified /
installed / uninstalled) happen at the *bundle* level — the manifest
itself never mutates.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosmos.plugins import canonical_acknowledgment
from kosmos.tools.models import AdapterRealDomainPolicy  # noqa: F401 — re-exported via __all__
from kosmos.tools.registry import AdapterRegistration

# H5 (review eval): tool_id MUST be ASCII to prevent Unicode confusable
# attacks (e.g. Cyrillic 'о' replacing Latin 'o' in plugin_id).
_TOOL_ID_ASCII_RE: Final = re.compile(
    r"^plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify)$",
    flags=re.ASCII,
)

_ROOT_PRIMITIVE_VERBS: Final[frozenset[str]] = frozenset({"lookup", "submit", "verify"})
"""The active reserved plugin primitive verbs.

Plugin namespaces extend the registry via ``plugin.<id>.<verb>``; ADR-007
permits exactly these suffixes. ``resolve_location`` is intentionally
NOT in this set — it is a built-in primitive a plugin cannot override
(Q8-NO-ROOT-OVERRIDE). ``subscribe`` is deferred until KOSMOS has a real
app/push-notification runtime to own delivery.
"""


class PIPATrusteeAcknowledgment(BaseModel):
    """Nested manifest block required when ``processes_pii=True``.

    Mirrors data-model.md § 2 verbatim. Encodes the PIPA §26 trustee chain
    (위탁자 / 수탁자 / 처리목적 / 처리범위 / 보유기간) so the validation
    workflow can mechanically reject missing or hash-tampered
    acknowledgments. The actual hash equality check is enforced by the
    parent :meth:`PluginManifest._v_pipa_hash`; this model only carries
    field-level shape constraints.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    trustee_org_name: str = Field(
        min_length=1,
        description="Trustee 수탁자 organisation legal name.",
    )
    trustee_contact: str = Field(
        min_length=1,
        description="Trustee contact (email or phone).",
    )
    pii_fields_handled: list[str] = Field(
        min_length=1,
        description=(
            "List of PII field identifiers the adapter handles "
            "(e.g. resident_registration_number, phone_number)."
        ),
    )
    legal_basis: str = Field(
        min_length=1,
        description="PIPA article reference (e.g. 'PIPA §15-1-2').",
    )
    acknowledgment_sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description=(
            "Lowercase hex SHA-256 of the canonical PIPA §26 text from "
            "docs/plugins/security-review.md. Must equal "
            "kosmos.plugins.canonical_acknowledgment.CANONICAL_ACKNOWLEDGMENT_SHA256."
        ),
    )


class PluginManifest(BaseModel):
    """Top-level Pydantic v2 manifest contract for a KOSMOS plugin release.

    Mirrors data-model.md § 1 verbatim. A successfully constructed
    instance is byte-equivalent to a valid ``manifest.yaml``; the JSON
    Schema export :data:`PluginManifest.model_json_schema` is contract-
    pinned to ``contracts/manifest.schema.json`` (parity test in T008).

    See module docstring for the 5 cross-field validators and ADR-007 for
    the namespacing rule rationale.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        max_length=64,
        description=(
            "snake_case plugin identifier; immutable across versions. "
            "Used as the namespace prefix in adapter.tool_id."
        ),
    )
    version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="SemVer major.minor.patch (no pre-release suffix).",
    )
    adapter: AdapterRegistration = Field(
        description=(
            "Embedded Spec 022/031 AdapterRegistration. The full V1-V6 "
            "invariant chain plus the v1.2 dual-axis backstop run on this "
            "field at construction time — there is no separate plugin "
            "validation path."
        ),
    )
    tier: Literal["live", "mock"] = Field(
        description=(
            "Plugin distribution tier. 'live' adapters call the real "
            "external API at runtime; 'mock' adapters replay recorded "
            "fixtures and MUST set mock_source_spec."
        ),
    )
    mock_source_spec: str | None = Field(
        default=None,
        description=(
            "Required (non-empty) when tier='mock'; MUST be None when "
            "tier='live'. URL or attribution string pointing to the "
            "public spec the mock mirrors (memory feedback_mock_evidence_based)."
        ),
    )
    processes_pii: bool = Field(
        default=True,
        description=(
            "Fail-closed default per Constitution §II. Set False only "
            "when the adapter has been audited and confirmed PII-free."
        ),
    )
    pipa_trustee_acknowledgment: PIPATrusteeAcknowledgment | None = Field(
        default=None,
        description=(
            "Required (non-null) when processes_pii=True. PIPA §26 "
            "trustee chain. Hash equality vs canonical text is enforced "
            "by _v_pipa_hash."
        ),
    )
    slsa_provenance_url: str = Field(
        pattern=r"^https://github\.com/",
        description=(
            "URL to the SLSA v1.0 provenance attestation (.intoto.jsonl) "
            "produced by slsa-framework/slsa-github-generator on tag push. "
            "Verified by slsa-verifier at install time (R-3)."
        ),
    )
    otel_attributes: dict[str, str] = Field(
        description=(
            "OTEL span attributes emitted on every plugin tool invocation "
            "(Spec 021 extension). MUST contain key 'kosmos.plugin.id' "
            "with value equal to plugin_id (enforced by _v_otel_attribute)."
        ),
    )
    search_hint_ko: str = Field(
        min_length=1,
        description=(
            "Korean search hint indexed by BM25 (Spec 022). Recommended "
            "≥ 3 Korean nouns extractable by Kiwipiepy "
            "(R-1 Q4-HINT-NOUNS)."
        ),
    )
    search_hint_en: str = Field(
        min_length=1,
        description="English search hint indexed alongside the Korean hint.",
    )
    permission_layer: Literal[1, 2, 3] = Field(
        description=(
            "Informational permission tier (1=green / 2=orange / 3=red, "
            "Migration tree § UI-C). Spec 033 is the actual enforcement "
            "point — this field drives the TUI consent overlay copy."
        ),
    )
    dpa_reference: str | None = Field(
        default=None,
        description=(
            "PIPA §26 data processing trustee reference URL or citation. "
            "Required (non-null) when adapter.policy derives pipa_class != 'non_personal' "
            "(Spec 024 V2 invariant). Distinct from pipa_trustee_acknowledgment — "
            "this is the agency-published policy URL the adapter cites for the "
            "data processing trustee relationship."
        ),
    )

    @field_validator("otel_attributes")
    @classmethod
    def _v_otel_required_key(cls, value: dict[str, str]) -> dict[str, str]:
        if "kosmos.plugin.id" not in value:
            raise ValueError(
                "otel_attributes must contain key 'kosmos.plugin.id' (Spec 021 KOSMOS extension)."
            )
        return value

    @model_validator(mode="after")
    def _v_mock_source(self) -> PluginManifest:
        """tier ↔ mock_source_spec must be consistent (R-1 Q7-MOCK-SOURCE)."""
        if self.tier == "mock" and not self.mock_source_spec:
            raise ValueError("mock_source_spec is required (non-empty) when tier='mock'")
        if self.tier == "live" and self.mock_source_spec is not None:
            raise ValueError("mock_source_spec must be None when tier='live'")
        return self

    @model_validator(mode="after")
    def _v_pipa_required(self) -> PluginManifest:
        """processes_pii ↔ pipa_trustee_acknowledgment symmetry (FR-014)."""
        if self.processes_pii and self.pipa_trustee_acknowledgment is None:
            raise ValueError(
                "pipa_trustee_acknowledgment required when processes_pii=True (PIPA §26)"
            )
        if not self.processes_pii and self.pipa_trustee_acknowledgment is not None:
            raise ValueError("pipa_trustee_acknowledgment must be None when processes_pii=False")
        return self

    @model_validator(mode="after")
    def _v_pipa_hash(self) -> PluginManifest:
        """acknowledgment_sha256 must equal canonical hash (R-1 Q6-PIPA-HASH)."""
        if self.pipa_trustee_acknowledgment is None:
            return self
        expected = canonical_acknowledgment.CANONICAL_ACKNOWLEDGMENT_SHA256
        actual = self.pipa_trustee_acknowledgment.acknowledgment_sha256
        if actual != expected:
            raise ValueError(
                f"acknowledgment_sha256 mismatch: expected {expected}, "
                f"got {actual}. Re-read docs/plugins/security-review.md "
                "and update."
            )
        return self

    @model_validator(mode="after")
    def _v_otel_attribute(self) -> PluginManifest:
        """otel_attributes['kosmos.plugin.id'] must equal plugin_id (FR-021)."""
        observed = self.otel_attributes.get("kosmos.plugin.id")
        if observed != self.plugin_id:
            raise ValueError(
                f'otel_attributes["kosmos.plugin.id"] must equal plugin_id '
                f"({self.plugin_id!r}); got {observed!r}"
            )
        return self

    @model_validator(mode="after")
    def _v_namespace(self) -> PluginManifest:
        """adapter.tool_id must be plugin.<plugin_id>.<root-primitive> (ADR-007).

        H5 (review eval): use a re.ASCII regex full-match so Unicode
        confusables (Cyrillic 'о', Greek 'ο' …) cannot slip past the
        prefix check via :py:meth:`str.startswith`.
        """
        if not _TOOL_ID_ASCII_RE.fullmatch(self.adapter.tool_id):
            raise ValueError(
                f"adapter.tool_id must match {_TOOL_ID_ASCII_RE.pattern} "
                f"(ASCII only, ADR-007); got {self.adapter.tool_id!r}"
            )
        expected_prefix = f"plugin.{self.plugin_id}."
        if not self.adapter.tool_id.startswith(expected_prefix):
            raise ValueError(
                f"adapter.tool_id must start with {expected_prefix!r} "
                f"(got {self.adapter.tool_id!r})"
            )
        suffix = self.adapter.tool_id[len(expected_prefix) :]
        if suffix not in _ROOT_PRIMITIVE_VERBS:
            raise ValueError(
                "adapter.tool_id verb suffix must be one of "
                f"{sorted(_ROOT_PRIMITIVE_VERBS)} (got {suffix!r})"
            )
        return self


__all__ = [
    "AdapterRealDomainPolicy",
    "PIPATrusteeAcknowledgment",
    "PluginManifest",
]
