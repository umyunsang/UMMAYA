# SPDX-License-Identifier: Apache-2.0
"""Central registry for KOSMOS government API tools."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from kosmos.tools.bm25_index import BM25Index
from kosmos.tools.errors import (
    AdapterIdCollisionError,
    RegistrationError,
    ToolNotFoundError,
)
from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool, ToolSearchResult
from kosmos.tools.policy_derivation import (
    AALLevel,
    PIPAClass,
    derive_is_irreversible,
    derive_min_auth_level,
    derive_pipa_class_default,
)
from kosmos.tools.rate_limiter import RateLimiter
from kosmos.tools.retrieval.backend import Retriever, build_retriever_from_env
from kosmos.tools.retrieval.bm25_backend import BM25Backend
from kosmos.tools.retrieval.degrade import DegradationRecord
from kosmos.tools.retrieval.dense_backend import DenseBackendLoadError
from kosmos.tools.search import search_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spec 031 Phase 2 — active primitive registry metadata (T007–T009).
# ---------------------------------------------------------------------------


class AdapterPrimitive(StrEnum):
    """T007 — active primitive surfaces every registered adapter binds to.

    Matches data-model.md § 4 verbatim.
    """

    lookup = "lookup"
    resolve_location = "resolve_location"
    submit = "submit"
    verify = "verify"


class AdapterSourceMode(StrEnum):
    """T009 — how faithfully the adapter mirrors its external source.

    OPENAPI: byte-mirrored from a public OpenAPI spec.
    OOS: shape-mirrored from an open-source SDK / reference implementation.
    HARNESS_ONLY: net-new; no external byte- or shape-mirror exists (per FR-026).
    """

    OPENAPI = "OPENAPI"
    OOS = "OOS"
    HARNESS_ONLY = "harness-only"


# T008 — 18-label closed enum of Korea-published auth tiers (primary axis).
PublishedTier = Literal[
    # gongdong_injeungseo — 3 labels
    "gongdong_injeungseo_personal_aal3",
    "gongdong_injeungseo_corporate_aal3",
    "gongdong_injeungseo_bank_only_aal2",
    # geumyung_injeungseo — 2 labels
    "geumyung_injeungseo_personal_aal2",
    "geumyung_injeungseo_business_aal3",
    # ganpyeon_injeung — 7 labels
    "ganpyeon_injeung_pass_aal2",
    "ganpyeon_injeung_kakao_aal2",
    "ganpyeon_injeung_naver_aal2",
    "ganpyeon_injeung_toss_aal2",
    "ganpyeon_injeung_bank_aal2",
    "ganpyeon_injeung_samsung_aal2",
    "ganpyeon_injeung_payco_aal2",
    # digital_onepass — 3 labels
    "digital_onepass_level1_aal1",
    "digital_onepass_level2_aal2",
    "digital_onepass_level3_aal3",
    # mobile_id — 2 labels
    "mobile_id_mdl_aal2",
    "mobile_id_resident_aal2",
    # mydata — 1 label
    "mydata_individual_aal2",
    # Spec 2296 Epic ε — AX-infrastructure callable-channel verify modules.
    # Five new tier values for the mock_verify_module_* family. Each tier
    # encodes (a) the AX-channel family name and (b) the NIST AAL hint
    # the channel is expected to attest to once a real backend ships.
    "simple_auth_module_aal2",  # 간편인증 AX-channel
    "modid_aal3",  # 모바일ID OID4VP + DID-resolved RP (AAL3 by KOMSCO design)
    "kec_aal3",  # 공동인증서 AX-channel (AAL3, joint-cert legacy)
    "geumyung_module_aal3",  # 금융인증서 AX-channel (AAL3, FNS managed)
    "any_id_sso_aal2",  # Any-ID SSO (identity-only — no delegation grant)
]

# T008 — advisory secondary axis; hint for external consumers only.
NistAalHint = Literal["AAL1", "AAL2", "AAL3"]


class AdapterRegistration(BaseModel):
    """T009 — registry metadata for active primitive adapters.

    Mirrors data-model.md § 4 verbatim. Spec 024 V1–V4 (applied via pydantic
    ``@model_validator`` on :class:`GovAPITool`) and Spec 025 V6 + the Spec 031
    v1.2 dual-axis invariant (applied via ``@model_validator`` on this class at
    construction time; see :mod:`kosmos.security.v12_dual_axis`) remain the
    authoritative enforcement points; :meth:`ToolRegistry.register` only
    additionally validates :class:`GovAPITool` instances passed to it.
    ``published_tier_minimum`` / ``nist_aal_hint`` are optional during the
    pre-v1.2 compatibility window (FR-028) and become mandatory when the
    :mod:`kosmos.security.v12_dual_axis` backstop flips ``V12_GA_ACTIVE = True``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        max_length=128,
        # Spec 1636 P5 ADR-007 (revised by review eval C3): tool_id may be
        # either snake_case (built-in adapters from Spec 022/031) OR
        # plugin-namespaced ``plugin.<plugin_id>.<verb>`` (Migration tree
        # § L1-C C7) where <verb> is one of the active plugin primitives.
        # resolve_location is host-reserved (Q8-NO-ROOT-OVERRIDE) and
        # cannot be overridden by plugins; the regex enforces that on
        # both AdapterRegistration and GovAPITool to keep the layers
        # drift-free.
        pattern=r"^([a-z][a-z0-9_]*|plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify))$",
    )
    primitive: AdapterPrimitive
    module_path: str
    input_model_ref: str
    source_mode: AdapterSourceMode

    # Dual-axis auth (Spec 031 § 6). Pre-v1.2 may ship None on either field;
    # v1.2 GA enforces both non-None via v12_dual_axis.enforce().
    published_tier_minimum: PublishedTier | None = None
    nist_aal_hint: NistAalHint | None = None

    # Spec 024 / 025 invariants preserved (FR-028)
    is_concurrency_safe: bool = False
    cache_ttl_seconds: int = 0
    rate_limit_per_minute: int = 10
    search_hint: dict[Literal["ko", "en"], list[str]] = Field(default_factory=dict)

    # Spec 024 security extensions — auth_type preserved for routing
    auth_type: Literal["public", "api_key", "oauth"]

    # Epic δ #2295 Path B — AdapterRealDomainPolicy nested cite. Pre-2295 adapters
    # may register without a policy (None allowed during migration); the V6
    # backstop in ``ToolRegistry.register`` skips invariant enforcement when
    # policy is None. New registrations SHOULD populate this field; KOSMOS-internal
    # synthetic surfaces (resolve_location / lookup / search_tools) carry None.
    policy: AdapterRealDomainPolicy | None = None

    # Spec 031 T023 — optional per-adapter nonce used to namespace the
    # deterministic ``transaction_id`` emitted by the ``submit`` dispatcher
    # (see :func:`kosmos.primitives.submit.derive_transaction_id`). Adapters
    # that participate in the ``submit`` primitive declare a stable nonce
    # string so the dispatcher and the adapter body compute byte-identical
    # transaction ids (FR-004). ``None`` is valid for non-submit primitives
    # and for submit adapters that explicitly opt out of nonce namespacing.
    nonce: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _enforce_v12_dual_axis(self) -> AdapterRegistration:
        """Spec 031 FR-030 v1.2 GA backstop.

        Delegates to :func:`kosmos.security.v12_dual_axis.enforce`. No-op while
        ``V12_GA_ACTIVE`` is ``False`` (pre-v1.2 compatibility window, FR-028).
        Once flipped, raises ``DualAxisMissingError`` if either dual-axis field
        is ``None``. Imported inline to avoid a circular import at module load.
        """
        from kosmos.security.v12_dual_axis import enforce as _enforce_v12

        _enforce_v12(self)
        return self

    # Epic δ #2295 Path B — backward-compat computed properties derived from
    # ``policy.citizen_facing_gate``. External readers (``ipc/tx_cache``,
    # ``ipc/demo/register_irreversible_fixture``) continue to consume
    # ``registration.is_irreversible`` / ``.auth_level`` / ``.pipa_class``
    # without code changes; the values are now derived from the cited agency
    # policy via ``policy_derivation`` instead of stored as KOSMOS-invented
    # fields. Returns conservative defaults when policy is None.

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_irreversible(self) -> bool:
        """Derived from ``policy.citizen_facing_gate`` (sign/submit ⇒ True)."""
        if self.policy is None:
            return False
        return derive_is_irreversible(self.policy.citizen_facing_gate)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def auth_level(self) -> AALLevel:
        """Derived minimum NIST AAL required for this adapter's gate.

        Returns ``"AAL1"`` (the safest default for read-only) when policy is
        None — KOSMOS-internal synthetic surfaces (resolve_location, lookup).
        """
        if self.policy is None:
            return "AAL1"
        return derive_min_auth_level(self.policy.citizen_facing_gate)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pipa_class(self) -> PIPAClass:
        """Derived default PIPA classification for this adapter's gate.

        Returns ``"non_personal"`` when policy is None.
        """
        if self.policy is None:
            return "non_personal"
        return derive_pipa_class_default(self.policy.citizen_facing_gate)


class ToolRegistry:
    """Central registry for government API tools."""

    def __init__(self) -> None:
        self._tools: dict[str, GovAPITool] = {}
        self._rate_limiters: dict[str, RateLimiter] = {}
        # Spec 1979 R-3+R-4 — in-memory enable/disable shadow set.
        # Reserved for backend support; not exposed via IPC in Spec 1979
        # (runtime toggle via plugin_op_request:activate/deactivate is
        # deferred to a follow-up Epic per Spec 032 envelope-bump scope).
        self._inactive: set[str] = set()

        # Spec 026: dependency-injection seam. The registry no longer
        # depends on a concrete BM25Index; it depends on the Retriever
        # protocol and lets the environment (via KOSMOS_RETRIEVAL_BACKEND)
        # pick the implementation. Default path is bm25 — byte-identical
        # to pre-#585 behaviour (FR-009, SC-04).
        default_bm25_index = BM25Index({})
        self._degradation_record = DegradationRecord()
        self._retriever: Retriever = build_retriever_from_env(
            bm25_index_factory=lambda: default_bm25_index,
            degradation_record=self._degradation_record,
        )

        # FR-009 compatibility alias: external call sites that read the
        # legacy ``bm25_index`` attribute (e.g., kosmos.tools.search) keep
        # working while we migrate them. The alias is retired in a
        # follow-on spec; during #585 it always references the BM25Index
        # owned by the active retriever when the active backend is BM25.
        if isinstance(self._retriever, BM25Backend):
            self.bm25_index: BM25Index = self._retriever._index
        else:
            self.bm25_index = default_bm25_index

    def register(self, tool: GovAPITool) -> None:
        """Register a tool.

        Raises:
            AdapterIdCollisionError: If ``tool.id`` is already registered
                (Spec 031 FR-020 — first-wins semantics). Subclasses
                :class:`DuplicateToolError`, so existing call sites that catch
                the parent keep working.
        """
        if tool.id in self._tools:
            existing = self._tools[tool.id]
            raise AdapterIdCollisionError(
                tool.id,
                existing_module=type(existing).__module__,
            )

        # Epic δ #2295 Path B — V6 invariant rewritten on derived auth_level.
        # When ``tool.policy`` is set, derive the AAL via policy_derivation and
        # verify it is permitted under the canonical (auth_type → auth_level)
        # mapping (``_AUTH_TYPE_LEVEL_MAPPING``). KOSMOS-internal synthetic
        # surfaces (policy=None) skip this check.
        if tool.policy is not None:
            from kosmos.tools.models import _AUTH_TYPE_LEVEL_MAPPING

            derived_aal = derive_min_auth_level(tool.policy.citizen_facing_gate)
            if tool.auth_type not in _AUTH_TYPE_LEVEL_MAPPING:
                logger.error(
                    "V6 violation at registry.register: tool_id=%s auth_type=%s (unknown)",
                    tool.id,
                    tool.auth_type,
                )
                raise RegistrationError(
                    tool.id,
                    f"V6 violation (FR-048): unknown auth_type={tool.auth_type!r}.",
                )
            allowed = _AUTH_TYPE_LEVEL_MAPPING[tool.auth_type]
            if derived_aal not in allowed:
                logger.error(
                    "V6 violation at registry.register: tool_id=%s auth_type=%s "
                    "derived_auth_level=%s (from gate=%s) allowed=%s",
                    tool.id,
                    tool.auth_type,
                    derived_aal,
                    tool.policy.citizen_facing_gate,
                    sorted(allowed),
                )
                raise RegistrationError(
                    tool.id,
                    f"V6 violation (FR-042): tool {tool.id!r} cites policy with "
                    f"citizen_facing_gate={tool.policy.citizen_facing_gate!r} "
                    f"(derived auth_level={derived_aal!r}), but declared "
                    f"auth_type={tool.auth_type!r} permits only {sorted(allowed)}.",
                )

        self._tools[tool.id] = tool
        self._rate_limiters[tool.id] = RateLimiter(
            limit=tool.rate_limit_per_minute,
        )

        # Spec 026: rebuild via the injected Retriever. The BM25 default
        # path delegates straight to BM25Index.rebuild, preserving the
        # legacy behaviour; Dense / Hybrid backends recompute embeddings
        # here. Using the instance-owned retriever keeps cross-registry
        # isolation intact (parallel pytest workers see independent
        # state).
        corpus = {tid: t.search_hint for tid, t in self._tools.items()}
        try:
            self._retriever.rebuild(corpus)
        except (DenseBackendLoadError, ImportError, RuntimeError, OSError) as exc:
            # FR-002 fail-open: dense/hybrid model load failed at first real
            # rebuild. Degrade to pure BM25 and emit exactly one WARN via the
            # registry-scoped DegradationRecord latch.
            #
            # The retriever may be a wrapper (``_DenseFailOpenWrapper``)
            # whose type name does not match the user-facing backend
            # label. Prefer the wrapper's declared ``_requested_backend_label``
            # when present, otherwise fall back to the class name heuristic.
            requested = getattr(
                self._retriever,
                "_requested_backend_label",
                type(self._retriever).__name__.lower().replace("backend", ""),
            )
            self._degradation_record.emit_if_needed(
                logger,
                requested_backend=requested,
                effective_backend="bm25",
                reason=f"dense load failed: {type(exc).__name__}: {exc}",
            )
            fallback = BM25Backend(BM25Index({}))
            fallback.rebuild(corpus)
            self._retriever = fallback
            self.bm25_index = fallback._index

        logger.info("Registered tool: %s", tool.id)

    def lookup(self, tool_id: str) -> GovAPITool:
        """Look up tool by id. Raises ToolNotFoundError if not found."""
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ToolNotFoundError(tool_id) from None

    def all_tools(self) -> list[GovAPITool]:
        """Return all active registered tools (filters Spec 1979 _inactive set)."""
        return [t for tid, t in self._tools.items() if tid not in self._inactive]

    def search(self, query: str, max_results: int = 5) -> list[ToolSearchResult]:
        """Search tools by Korean or English keywords in search_hint."""
        return search_tools(self.all_tools(), query, max_results)

    def core_tools(self) -> list[GovAPITool]:
        """Return core, active tools sorted by id (deterministic for prompt caching)."""
        return sorted(
            [t for tid, t in self._tools.items() if t.is_core and tid not in self._inactive],
            key=lambda t: t.id,
        )

    def situational_tools(self) -> list[GovAPITool]:
        """Return non-core, active tools."""
        return [t for tid, t in self._tools.items() if not t.is_core and tid not in self._inactive]

    def export_core_tools_openai(self) -> list[dict[str, object]]:
        """Export core tools as OpenAI function-calling definitions.

        Output is deterministic (sorted by id) for prompt cache stability.
        Filters Spec 1979 _inactive set so disabled plugins are not
        surfaced to the LLM.
        """
        return [t.to_openai_tool() for t in self.core_tools()]

    # ------------------------------------------------------------------
    # Spec 1979 lifecycle methods (data-model.md § E4)
    # ------------------------------------------------------------------

    def deregister(self, tool_id: str) -> None:
        """Remove a tool from the registry entirely.

        Used by :func:`kosmos.plugins.uninstall.uninstall_plugin` to fully
        remove a plugin's adapter from the in-process registry. Rebuilds
        the BM25 corpus over the remaining tools.

        Raises:
            ToolNotFoundError: If ``tool_id`` is not registered.
        """
        if tool_id not in self._tools:
            raise ToolNotFoundError(tool_id)
        del self._tools[tool_id]
        self._rate_limiters.pop(tool_id, None)
        self._inactive.discard(tool_id)
        # Rebuild BM25 over the surviving tools so the deregistered tool
        # never surfaces in lookup() results again.
        corpus = {tid: t.search_hint for tid, t in self._tools.items()}
        self._retriever.rebuild(corpus)
        logger.info("Deregistered tool: %s", tool_id)

    def set_active(self, tool_id: str, active: bool) -> None:
        """Mark a tool active or inactive without removing it from the registry.

        Active tools surface in BM25 + LLM tool inventory; inactive tools
        stay registered (consent receipt + install root preserved) but are
        filtered from discovery + dispatch.

        Raises:
            ToolNotFoundError: If ``tool_id`` is not registered.
        """
        if tool_id not in self._tools:
            raise ToolNotFoundError(tool_id)
        if active:
            self._inactive.discard(tool_id)
        else:
            self._inactive.add(tool_id)
        # Rebuild BM25 corpus to reflect the new active set.
        corpus = {tid: t.search_hint for tid, t in self._tools.items() if tid not in self._inactive}
        self._retriever.rebuild(corpus)

    def is_active(self, tool_id: str) -> bool:
        """Return True iff the tool is registered AND not in the inactive set."""
        return tool_id in self._tools and tool_id not in self._inactive

    def get_rate_limiter(self, tool_id: str) -> RateLimiter:
        """Get the rate limiter for a tool.

        Raises ToolNotFoundError if tool_id is not registered.
        """
        if tool_id not in self._rate_limiters:
            raise ToolNotFoundError(tool_id)
        return self._rate_limiters[tool_id]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_id: str) -> bool:
        return tool_id in self._tools


# ---------------------------------------------------------------------------
# Plugin shim (Epic #1636 P5 / T010)
# ---------------------------------------------------------------------------


def register_plugin_adapter(
    manifest: object,
    *,
    registry: ToolRegistry,
    executor: object,
    plugin_root: object | None = None,
) -> object:
    """Plugin-adapter registration shim deferring to :mod:`kosmos.plugins.registry`.

    The real implementation lives in ``kosmos.plugins.registry`` so the plugin
    module owns its OTEL emission and module-import glue. This shim exists at
    the canonical ``kosmos.tools.registry`` import path that downstream code
    already consumes (Spec 022/024/025/031 callers) so they can register a
    plugin without learning a new module name. The shim preserves the
    existing V1-V6 invariant chain by routing through
    :meth:`ToolRegistry.register` — there is no parallel registration path.

    Args:
        manifest: A validated :class:`kosmos.plugins.manifest_schema.PluginManifest`.
        registry: Central :class:`ToolRegistry`.
        executor: :class:`kosmos.tools.executor.ToolExecutor` instance.
        plugin_root: Optional filesystem root for installed-bundle adapter
            module loading. ``None`` means import via the standard import
            system (development workflow with ``pip install -e``).

    Returns:
        The registered :class:`kosmos.tools.models.GovAPITool`.

    Raises:
        kosmos.plugins.exceptions.PluginRegistrationError: On any failure
            in module import, symbol resolution, or invariant violation.
    """
    # Inline import to avoid a load-order cycle: kosmos.plugins.registry
    # imports kosmos.tools.registry (ToolRegistry). The shim lives at the
    # bottom of this module so a top-level import would re-enter before the
    # ToolRegistry class object is bound.
    from kosmos.plugins.registry import (  # noqa: PLC0415
        register_plugin_adapter as _impl,
    )

    return _impl(
        manifest,  # type: ignore[arg-type]
        registry=registry,
        executor=executor,  # type: ignore[arg-type]
        plugin_root=plugin_root,  # type: ignore[arg-type]
    )
