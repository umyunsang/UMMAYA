# SPDX-License-Identifier: Apache-2.0
"""Pydantic v2 data models for the KOSMOS Tool System module."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosmos.tools.errors import LookupErrorReason

# Spec 025 v6 — canonical (auth_type, auth_level) consistency mapping.
# Read as: ``auth_type`` key ⇒ frozenset of ``auth_level`` values permitted
# for adapters declaring that ``auth_type``. Owned by FR-039..FR-042
# (specs/025-tool-security-v6). Imported by Spec 1636 plugin Q3 invariant
# checker (``src/kosmos/plugins/checks/q3_security.py``) which enforces V6
# at plugin install time. The matrix itself is **infrastructure-level
# consistency** (auth_type drives the upstream API auth mechanism, auth_level
# is the citizen authentication strength) and is NOT KOSMOS-invented permission
# policy — agencies declare both fields per their published policy and this
# mapping enforces that an adapter does not lie (e.g. claiming auth_type=public
# while declaring auth_level=AAL3 is impossible by design).
#
# Per Epic δ #2295 spec.md FR-006 EXCLUDE clause, this constant is one of the
# legitimate KOSMOS-needed uses of the auth_level token outside adapter metadata.
_AUTH_TYPE_LEVEL_MAPPING: Final[dict[str, frozenset[str]]] = {
    "public": frozenset({"public", "AAL1"}),
    "api_key": frozenset({"AAL1", "AAL2", "AAL3"}),
    "oauth": frozenset({"AAL1", "AAL2", "AAL3"}),
}

# Spec 1634 (P3 Tool System Wiring) — closed ministry / institution enum.
# Typed replacement for the former free-form ``provider: str`` field. New
# institutions are added by enum extension (small dedicated PR, ADR not
# required). ``OTHER`` is a transitional escape hatch for adapters whose
# institutional mapping is undecided; CI emits a warning via
# ``RoutingIndex.warnings`` (non-fatal) when any registered adapter uses it.
Ministry = Literal[
    "KOROAD",  # 도로교통공단 — road safety
    "KMA",  # 기상청 — weather
    "NMC",  # 국립중앙의료원 — emergency medical
    "HIRA",  # 건강보험심사평가원 — health insurance review
    "NFA",  # 소방청 — fire / 119
    "MOHW",  # 보건복지부 — welfare (includes SSIS adapters)
    "MOLIT",  # 국토교통부 — land/infrastructure/transport
    "MOIS",  # 행정안전부 — public administration / safety
    "KEC",  # 한국교통안전공단 — vehicle inspection / e-signature
    "MFDS",  # 식품의약품안전처 — food & drug safety
    "GOV24",  # 정부24 — citizen submission portal (OPAQUE per feedback_mock_evidence_based)
    "KOSMOS",  # harness-internal synthetic surface (resolve_location, lookup, mvp_surface)
    "OTHER",  # transitional escape hatch — CI emits warning
]


class AdapterRealDomainPolicy(BaseModel):
    """KOSMOS adapter single permission representation — cite of agency published policy.

    KOSMOS does NOT invent permission policy (.specify/memory/constitution.md § II).
    This model is the single source of truth where an adapter (a) cites the
    agency's published policy URL, (b) declares the citizen-facing gate category,
    and (c) records the last verification timestamp of the policy citation.

    References:
    - AGENTS.md § CORE THESIS — KOSMOS = AX-infrastructure callable-channel client
    - .specify/memory/constitution.md § II Fail-Closed Security (NON-NEGOTIABLE)
    - .specify/memory/constitution.md § III Pydantic v2 Strict Typing
    - specs/1979-plugin-dx-tui-integration/domain-harness-design.md § 3.2
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    real_classification_url: str = Field(
        ...,
        min_length=1,
        description="Agency published policy URL (https:// prefix recommended)",
    )
    real_classification_text: str = Field(
        ...,
        min_length=1,
        description="Korean citation from agency policy (text shown to citizen)",
    )
    citizen_facing_gate: Literal["read-only", "login", "action", "sign", "submit"] = Field(
        ...,
        description="Citizen-facing gate category — UI uses this value for PermissionRequest UX",
    )
    last_verified: datetime = Field(
        ...,
        description="Last verification timestamp of the policy URL (ISO 8601, UTC recommended)",
    )


class GovAPITool(BaseModel):
    """Government API tool definition with fail-closed security defaults.

    All boolean safety fields default to the more restrictive value
    per Constitution § II (fail-closed principle).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    id: str
    """Stable snake_case identifier (e.g. ``koroad_accident_search``)."""

    name_ko: str
    """Korean display name shown to users."""

    ministry: Ministry
    """Ministry or agency that owns the API.

    Typed closed enum (see :data:`Ministry` at module top). Replaces the
    former free-form ``provider: str`` field per Spec 1634 FR-010. New
    institutions are added by enum extension; ``OTHER`` is a transitional
    escape hatch (CI emits ``RoutingIndex.warnings`` entry — non-fatal).
    """

    category: list[str]
    """Non-empty list of topic tags."""

    endpoint: str
    """API base URL."""

    auth_type: Literal["public", "api_key", "oauth"]
    """Authentication mechanism required by the upstream API."""

    input_schema: type[BaseModel]
    """Pydantic v2 model class for request parameters."""

    output_schema: type[BaseModel]
    """Pydantic v2 model class for response data."""

    search_hint: str
    """Bilingual (Korean + English) discovery keywords for semantic search."""

    # --- Policy citation (Epic δ #2295 — replaces KOSMOS-invented security fields) ---
    # Spec 2295: AdapterRealDomainPolicy carries the agency's published policy URL
    # + citizen-facing gate category. KOSMOS does NOT invent permission policy
    # (Constitution § II). Optional during migration window (FR-028 parity).
    policy: AdapterRealDomainPolicy | None = None
    """Agency domain policy citation (Constitution § II cite-only invariant).

    Carries real_classification_url + real_classification_text +
    citizen_facing_gate + last_verified. All 18 registered adapters MUST
    populate this field (Epic δ #2295 acceptance criterion).
    None is legal only during the pre-2295 migration window.
    """

    # --- Fail-closed defaults (Constitution § II) ---
    is_concurrency_safe: bool = False
    """Safe to call concurrently. Defaults to False (fail-closed)."""

    cache_ttl_seconds: int = 0
    """Response cache lifetime in seconds. Defaults to 0 (no caching, fail-closed)."""

    rate_limit_per_minute: int = 10
    """Client-side rate limit; must be greater than zero."""

    is_core: bool = False
    """Whether the tool is included in the core prompt partition."""

    llm_description: str | None = None
    """Optional richer description shown to the LLM in the OpenAI tool definition.

    When present, ``to_openai_tool()`` emits this string as the ``description``
    field instead of ``name_ko``. Use this to communicate ordering prerequisites
    or tool-selection hints that the LLM must see *before* deciding to call the
    tool — field-level descriptions on the input schema are only seen after the
    model has already picked this tool, which is too late for ordering rules.
    """

    # Epic #2152 R6 — per-tool trigger phrase examples shown alongside each tool's
    # description in the system prompt's ``## Available tools`` block. Concrete
    # citizen-language utterances the tool covers, used to defeat Opus 4.7-class
    # tool under-triggering (Anthropic guide § "Tool use triggering"). Default
    # empty list keeps backward compatibility for adapters that have not yet
    # opted in. Capped at 5 entries to keep the system-prompt token cost bounded.
    trigger_examples: list[str] = Field(default_factory=list, max_length=5)
    """Korean citizen-utterance examples that should trigger this tool.

    Examples are emitted by ``build_system_prompt_with_tools`` as the
    ``— 예: "..."`` clause of the per-tool ``**Trigger**:`` line. Default ``[]``
    keeps the trigger line description-only when no examples are authored.
    """

    # Spec 1634 (P3 Tool System Wiring) FR-009 — runtime live/mock mode.
    # Orthogonal to ``AdapterRegistration.source_mode`` (which classifies
    # mirror fidelity: OPENAPI / OOS / HARNESS_ONLY). Default ``"live"`` is
    # fail-explicit, not fail-closed: undeclared adapters should be live;
    # mock adapters under ``src/kosmos/tools/mock/*`` MUST set this to
    # ``"mock"`` explicitly (CI consistency invariant 3 enforces declaration
    # at the filesystem layer). Documented deviation from Constitution § II
    # recorded in ``specs/1634-tool-system-wiring/plan.md`` § Complexity
    # Tracking + ``research.md`` § 5.1.
    adapter_mode: Literal["live", "mock"] = "live"
    """Runtime source. ``live`` = adapter calls the real public API.
    ``mock`` = adapter returns recorded fixture or shape-compatible synthetic.
    Distinct from ``AdapterRegistration.source_mode`` (mirror fidelity axis)."""

    # Spec 031 T032 dual-axis fields — None during pre-v1.2 compatibility window FR-028
    primitive: Literal["lookup", "resolve_location", "submit", "subscribe", "verify"] | None = None
    """Five-primitive surface this adapter binds to (Spec 031 AdapterPrimitive).

    Set to the appropriate value during Spec 031 Phase 4 (T033).
    ``None`` is legal during the pre-v1.2 compatibility window (FR-028).
    When the v12_dual_axis backstop activates (``V12_GA_ACTIVE=True``), a
    non-None value becomes mandatory for all newly-registered adapters.
    """

    published_tier_minimum: (
        Literal[
            "gongdong_injeungseo_personal_aal3",
            "gongdong_injeungseo_corporate_aal3",
            "gongdong_injeungseo_bank_only_aal2",
            "geumyung_injeungseo_personal_aal2",
            "geumyung_injeungseo_business_aal3",
            "ganpyeon_injeung_pass_aal2",
            "ganpyeon_injeung_kakao_aal2",
            "ganpyeon_injeung_naver_aal2",
            "ganpyeon_injeung_toss_aal2",
            "ganpyeon_injeung_bank_aal2",
            "ganpyeon_injeung_samsung_aal2",
            "ganpyeon_injeung_payco_aal2",
            "digital_onepass_level1_aal1",
            "digital_onepass_level2_aal2",
            "digital_onepass_level3_aal3",
            "mobile_id_mdl_aal2",
            "mobile_id_resident_aal2",
            "mydata_individual_aal2",
        ]
        | None
    ) = None
    """Minimum Korea-published auth tier required by this adapter (Spec 031 primary axis).

    ``None`` is legal during the pre-v1.2 compatibility window (FR-028).
    Mirrors ``AdapterRegistration.published_tier_minimum`` in
    ``kosmos.tools.registry``. Inline Literal avoids a circular import while
    sharing the same 18-label closed set defined in data-model.md § 4.
    """

    nist_aal_hint: Literal["AAL1", "AAL2", "AAL3"] | None = None
    """Advisory NIST SP 800-63-4 AAL hint (Spec 031 secondary axis).

    ``None`` is legal during the pre-v1.2 compatibility window (FR-028).
    This is advisory-only; enforcement gates on ``published_tier_minimum``.
    """

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        # Spec 1636 P5 ADR-007 (revised by review eval C3):
        # plugin-namespaced ids may use ONLY the four root primitives
        # (lookup / submit / verify / subscribe). resolve_location is a
        # host-reserved built-in primitive (Migration tree § L1-C C6) —
        # plugins cannot override it. The earlier regex permitted
        # resolve_location at the GovAPITool layer for symmetry with
        # AdapterRegistration; that left a registry-layer bypass for
        # Q8-NO-ROOT-OVERRIDE since direct register(GovAPITool(...))
        # calls do not run PluginManifest._v_namespace. We now reject
        # plugin.<id>.resolve_location at construction time so both
        # layers agree.
        if not re.fullmatch(
            r"^([a-z][a-z0-9_]*"
            r"|plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify|subscribe))$",
            v,
        ):
            raise ValueError(
                f"Tool id {v!r} must match ^[a-z][a-z0-9_]*$ "
                "(lowercase, start with a letter, underscores only) "
                "OR ^plugin\\.<plugin_id>\\.(lookup|submit|verify|subscribe)$ "
                "for plugin-namespaced tools (ADR-007 + Q8-NO-ROOT-OVERRIDE). "
                "resolve_location is a host-reserved primitive — plugins "
                "cannot override it."
            )
        return v

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("category must not be empty")
        return v

    @field_validator("rate_limit_per_minute")
    @classmethod
    def _validate_rate_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"rate_limit_per_minute must be > 0, got {v}")
        return v

    @field_validator("cache_ttl_seconds")
    @classmethod
    def _validate_cache_ttl(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"cache_ttl_seconds must be >= 0, got {v}")
        return v

    @field_validator("search_hint")
    @classmethod
    def _validate_search_hint(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("search_hint must not be empty or whitespace-only")
        return v

    # ------------------------------------------------------------------
    # Epic δ #2295 Path B — Spec 024/025 V1–V6 invariant chain rewritten on
    # derived ``policy.citizen_facing_gate``. Runs only when ``policy`` is set
    # (KOSMOS-internal surfaces with policy=None skip the chain).
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_policy_security_invariants(self) -> GovAPITool:
        """Enforce V3 + V6 derived from policy.citizen_facing_gate.

        Pre-2295 KOSMOS-invented chain (V1: pipa_class⇒auth_level, V2: dpa_reference,
        V4: irreversible⇒auth_level, V5: requires_auth) was tied to per-adapter
        KOSMOS-invented fields. After Path B, those fields are derived from
        ``self.policy.citizen_facing_gate`` via ``policy_derivation`` and the
        relations V1/V2/V4/V5 hold by construction (the canonical mapping
        guarantees PII-class gates derive AAL≥AAL2; sign/submit derive
        is_irreversible=True with AAL3; etc.).

        What remains as a runtime check:
        - **V3**: when ``self.id`` is in ``TOOL_MIN_AAL``, the derived AAL must
          equal that row.
        - **V6**: ``(auth_type, derived_auth_level)`` must lie in
          ``_AUTH_TYPE_LEVEL_MAPPING``.

        Skipped entirely when ``policy is None`` (KOSMOS-internal).
        """
        if self.policy is None:
            return self
        # Late import to avoid a circular dependency at module load
        # (audit imports from tools indirectly via security/__init__.py).
        from kosmos.security.audit import TOOL_MIN_AAL
        from kosmos.tools.policy_derivation import derive_min_auth_level

        derived_aal = derive_min_auth_level(self.policy.citizen_facing_gate)

        # V3 — single-source-of-truth TOOL_MIN_AAL drift detector.
        expected_aal = TOOL_MIN_AAL.get(self.id)
        if expected_aal is not None and derived_aal != expected_aal:
            raise ValueError(
                f"V3 violation (FR-001/FR-005): tool {self.id!r} cites policy "
                f"with citizen_facing_gate={self.policy.citizen_facing_gate!r} "
                f"(derived auth_level={derived_aal!r}) but TOOL_MIN_AAL "
                f"requires {expected_aal!r}."
            )

        # V6 — (auth_type, derived_auth_level) ∈ canonical mapping.
        if self.auth_type not in _AUTH_TYPE_LEVEL_MAPPING:
            raise ValueError(
                f"V6 violation (FR-048): tool {self.id!r} declares unknown "
                f"auth_type={self.auth_type!r}."
            )
        allowed = _AUTH_TYPE_LEVEL_MAPPING[self.auth_type]
        if derived_aal not in allowed:
            raise ValueError(
                f"V6 violation (FR-042): tool {self.id!r} cites policy with "
                f"citizen_facing_gate={self.policy.citizen_facing_gate!r} "
                f"(derived auth_level={derived_aal!r}), but declared "
                f"auth_type={self.auth_type!r} permits only {sorted(allowed)}."
            )
        return self

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def to_openai_tool(self) -> dict[str, object]:
        """Export as an OpenAI function-calling tool definition.

        Uses ``llm_description`` when set (richer ordering/prereq guidance),
        falling back to ``name_ko`` otherwise.

        Epic #2152 R6 — populates ``function.trigger_phrase`` from the bilingual
        ``search_hint`` plus the optional ``trigger_examples`` list. The phrase
        is consumed by ``kosmos.llm.system_prompt_builder.build_system_prompt_with_tools``
        and stripped from the OpenAI payload by ``FunctionSchema``'s
        ``exclude=True`` annotation.
        """
        description = self.llm_description or self.name_ko
        function: dict[str, object] = {
            "name": self.id,
            "description": description,
            "parameters": self.input_schema.model_json_schema(),
        }
        trigger_phrase = self._build_trigger_phrase()
        if trigger_phrase is not None:
            function["trigger_phrase"] = trigger_phrase
        return {"type": "function", "function": function}

    def _build_trigger_phrase(self) -> str | None:
        """Compose the human-readable trigger sentence + example clause.

        Format::

            <korean sentence ending with period> — 예: "<utt 1>", "<utt 2>"

        Empty ``trigger_examples`` yields the description-only variant
        (no ``— 예:`` clause). When neither a Korean ``search_hint`` nor any
        examples are available the helper returns ``None`` so callers can
        omit the trigger line entirely.
        """
        sentence = (self.search_hint or "").strip()
        if not sentence and not self.trigger_examples:
            return None
        if sentence and not sentence.endswith((".", "。", ":", "—")):
            sentence = sentence + "."
        if self.trigger_examples:
            quoted = ", ".join(f'"{ex}"' for ex in self.trigger_examples)
            sep = " — " if sentence else ""
            return f"{sentence}{sep}예: {quoted}"
        return sentence


class ToolResult(BaseModel):
    """Result returned by the tool executor after dispatching a tool call."""

    model_config = ConfigDict(frozen=True)

    tool_id: str
    """Identifier of the tool that was called."""

    success: bool
    """Whether the execution completed without error."""

    data: dict[str, object] | None = None
    """Validated output payload; populated only on success."""

    error: str | None = None
    """Human-readable error message; populated only on failure."""

    error_type: (
        Literal[
            "validation",
            "rate_limit",
            "not_found",
            "execution",
            "schema_mismatch",
            "permission_denied",
            "timeout",
            "circuit_open",
            "api_error",
            "auth_expired",
            "injection_detected",
            "content_blocked",
        ]
        | None
    ) = None
    """Structured error classification; populated only on failure."""

    @model_validator(mode="after")
    def _check_success_consistency(self) -> ToolResult:
        """Enforce invariants between success and error/data fields."""
        if self.success:
            if self.error is not None or self.error_type is not None:
                msg = "success=True must not have error or error_type set"
                raise ValueError(msg)
        else:
            if self.error is None or self.error_type is None:
                msg = "success=False must have both error and error_type set"
                raise ValueError(msg)
            if self.data is not None:
                msg = "success=False must not have data set"
                raise ValueError(msg)
        return self


class ToolSearchResult(BaseModel):
    """A ranked search result returned by ``ToolRegistry.search()``."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    tool: GovAPITool
    """The matched tool definition."""

    score: float
    """Relevance score; higher means more relevant."""

    matched_tokens: list[str]
    """Query tokens that contributed to this match."""


class SearchToolMatch(BaseModel):
    """A single lightweight match entry inside ``SearchToolsOutput``.

    Carries only the fields needed by the LLM to decide whether to call a tool,
    avoiding the heavyweight ``GovAPITool`` with embedded schema classes.
    """

    model_config = ConfigDict(frozen=True)

    tool_id: str
    """Stable snake_case tool identifier."""

    name_ko: str
    """Korean display name."""

    ministry: Ministry
    """Ministry or agency that owns the API (typed closed enum; Spec 1634 FR-010)."""

    category: list[str]
    """Topic tags."""

    description: str
    """Human-readable description derived from the tool's ``search_hint``."""

    score: float
    """Relevance score for this match."""


class SearchToolsInput(BaseModel):
    """Input schema for the ``search_tools`` meta-tool."""

    query: str
    """Search query in Korean or English keywords."""

    max_results: int = Field(default=5, gt=0)
    """Maximum number of results to return; must be greater than zero."""


class SearchToolsOutput(BaseModel):
    """Output schema for the ``search_tools`` meta-tool."""

    results: list[SearchToolMatch]
    """Ranked list of tool matches."""

    total_registered: int
    """Total number of tools currently registered in the registry."""


# ---------------------------------------------------------------------------
# T005 — ResolveLocationInput
# ---------------------------------------------------------------------------


class ResolveLocationInput(BaseModel):
    """Input to the resolve_location tool.

    Converts a free-text place query into typed location identifiers.
    Field shapes and enum values are binding per contracts/resolve_location.input.schema.json.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "자유 텍스트 위치 쿼리 (한국어 또는 영어). 시민 발화에서 그대로 추출. "
            "Examples: '서울 강남구', '동아대 하단캠퍼스', '강남역', '부산 사하구', "
            "'서울대병원'. POI / 행정동 / 도로명주소 / 지번주소 모두 허용."
        ),
    )
    want: Literal[
        "coords",
        "adm_cd",
        "coords_and_admcd",
        "road_address",
        "jibun_address",
        "poi",
        "all",
    ] = Field(
        default="coords_and_admcd",
        description=(
            "원하는 식별자 종류. 후속 도구가 요구하는 형태에 맞춤:\n"
            "- 'coords' : (lat, lon) 좌표 — 일반 위치 표시.\n"
            "- 'adm_cd' : 10자리 법정동 코드 — KOROAD accident_hazard_search 등.\n"
            "- 'coords_and_admcd' (default) : 좌표 + adm_cd 둘 다 — 가장 안전.\n"
            "- 'road_address' / 'jibun_address' : 사람용 주소 텍스트.\n"
            "- 'poi' : 관심 지점 정보 (이름 / 카테고리).\n"
            "- 'all' : 모든 위 정보. 후속 도구별 input schema 는 각 도구의 description 참조. "
            "각 도구는 self-contained — KOSMOS 가 cross-domain chain 강제하지 않음."
        ),
    )
    near: tuple[float, float] | None = Field(
        default=None,
        description=(
            "[lat, lon] tiebreaker — query 가 모호해서 동명이 여러 개 있을 때 "
            "현재 위치 좌표로 가장 가까운 결과 선택. 일반적으로 None (default)."
        ),
    )


# ---------------------------------------------------------------------------
# T006 — ResolveLocationOutput (6-variant discriminated union)
# ---------------------------------------------------------------------------


class CoordResult(BaseModel):
    """Geocoding result: latitude + longitude."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["coords"]
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    confidence: Literal["high", "medium", "low"]
    source: Literal["kakao", "juso", "sgis"]


class AdmCodeResult(BaseModel):
    """Administrative division code result (10-digit 법정동 code)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["adm_cd"]
    code: str = Field(pattern=r"^[0-9]{10}$")
    name: str
    level: Literal["sido", "sigungu", "eupmyeondong"]
    source: Literal["sgis", "juso", "kakao"]


class AddressResult(BaseModel):
    """Structured address result."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["address"]
    road_address: str | None = None
    jibun_address: str | None = None
    postal_code: str | None = None
    source: Literal["kakao", "juso"]


class POIResult(BaseModel):
    """Point of interest result."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["poi"]
    name: str
    category: str
    lat: float
    lon: float
    source: Literal["kakao"]


class ResolveBundle(BaseModel):
    """Bundle of multiple resolve results with provenance."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["bundle"]
    source: Literal["bundle"]
    coords: CoordResult | None = None
    adm_cd: AdmCodeResult | None = None
    address: AddressResult | None = None
    poi: POIResult | None = None


class ResolveError(BaseModel):
    """Location resolution error with reason and optional candidates."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["error"]
    reason: Literal[
        "not_found",
        "ambiguous",
        "upstream_unavailable",
        "invalid_query",
        "empty_query",
        "out_of_domain",
    ]
    message: str
    candidates: list[CoordResult | AdmCodeResult | AddressResult | POIResult] = Field(
        default_factory=list
    )


ResolveLocationOutputUnion = Annotated[
    CoordResult | AdmCodeResult | AddressResult | POIResult | ResolveBundle | ResolveError,
    Field(discriminator="kind"),
]
"""Discriminated union on `kind`. Binding variant names from docs/design/mvp-tools.md §4."""


# ---------------------------------------------------------------------------
# T039 — ResolveLocationOutput v4 flat model (Spec 2522 US7)
# ---------------------------------------------------------------------------
# Standardises the 4 mandatory output fields guaranteed by the Kakao backend.
# JUSO / SGIS fallbacks are optional; when not configured they are skipped
# (see resolve_location.py § _juso_adm_cd / _sgis_adm_cd).
# Evidence: /tmp/kosmos-evidence/geocoding-evidence.md (4 scenarios, Kakao only).
# ---------------------------------------------------------------------------


class ResolveLocationOutput(BaseModel):
    """Flat v4 output for resolve_location — Kakao-guaranteed 4-field standard.

    All four fields are always present when Kakao returns a document.
    ``confidence`` and ``source`` are derived from the Kakao response meta.

    Spec 2522 US7 — T039.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    lat: float = Field(ge=-90, le=90, description="WGS-84 latitude.")
    lon: float = Field(ge=-180, le=180, description="WGS-84 longitude.")
    b_code: str = Field(
        pattern=r"^[0-9]{10}$",
        description=(
            "10-digit 행정동 법정 코드 (bjdong_code). "
            "Extracted directly from the Kakao Local API 'b_code' field."
        ),
    )
    address_name: str = Field(
        min_length=1,
        description=(
            "Human-readable address name returned by Kakao "
            "(documents[0].address.address_name or documents[0].address_name)."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=("'high' if Kakao meta.total_count == 1, 'medium' if ≤ 3, 'low' otherwise."),
    )
    source: Literal["kakao", "juso", "sgis"] = Field(
        description="Backend that produced this result. Always 'kakao' for the v4 path.",
    )


# ---------------------------------------------------------------------------
# T007 — LookupInput (discriminated on `mode`)
# ---------------------------------------------------------------------------


class LookupSearchInput(BaseModel):
    """Input for lookup(mode='search'): BM25 gate over adapter registry."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["search"]
    query: str = Field(min_length=1, max_length=200)
    """Korean or English free-text describing the data you want."""

    domain: str | None = None
    """Optional facet filter (matches GovAPITool.category)."""

    top_k: int | None = Field(default=None, ge=1, le=20)
    """Per-call override; server-side clamp [1, 20]. If None, uses KOSMOS_LOOKUP_TOPK default."""


class LookupFetchInput(BaseModel):
    """Input for lookup(mode='fetch'): typed invocation of a specific adapter."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fetch"]
    tool_id: str = Field(
        # Spec 1636 P5 ADR-007: snake_case OR plugin-namespaced.
        pattern=r"^([a-z][a-z0-9_]*|plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify|subscribe|resolve_location))$",
    )
    """Must come from a previous `search` result. Never guess."""

    params: dict[str, object]
    """Validated against the target adapter's input_schema at fetch time."""

    page: int | None = Field(default=None, ge=1)


LookupInput = Annotated[
    LookupSearchInput | LookupFetchInput,
    Field(discriminator="mode"),
]
"""Discriminated union on `mode`. search → BM25; fetch → typed adapter invocation."""


# ---------------------------------------------------------------------------
# T008 — LookupOutput (5-variant discriminated union) + supporting types
# ---------------------------------------------------------------------------


class LookupMeta(BaseModel):
    """Metadata injected into every lookup(mode='fetch') response envelope."""

    model_config = ConfigDict(extra="forbid")

    source: str
    """tool_id of the adapter that handled this request."""

    fetched_at: datetime
    """UTC timestamp when the response was fetched."""

    request_id: str
    """UUID for this request, for tracing."""

    elapsed_ms: int = Field(ge=0)
    """Total elapsed time in milliseconds."""

    rate_limit_remaining: int | None = None
    """Remaining rate-limit slots for this adapter, if known."""

    freshness_status: Literal["fresh", "not_applicable"] | None = None
    """Adapter freshness signal:
    - 'fresh': adapter ran a freshness check and the data is within the SLO threshold.
    - 'not_applicable': adapter is endpoint-static (no per-record timestamp to check
      — e.g. NMC `getEgytLcinfoInqire` location endpoint, which lacks `hvidate`).
    - None: adapter does not declare a freshness signal at all."""


class AdapterCandidate(BaseModel):
    """A single search-result entry from lookup(mode='search').

    Epic ζ #2297 path B (live smoke 2026-04-30 follow-up) — extended with
    full per-domain REST schema metadata so the LLM can read each adapter's
    parameter descriptions, types, patterns, and constraints WITHOUT a
    second round-trip. Each domain API has different parameter names and
    structures (KOROAD adm_cd+year vs KMA base_date+base_time vs hometax
    delegation_context+payload); the LLM uses ``input_schema_json`` to
    judge what to fill per domain.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    score: float = Field(ge=0)
    required_params: list[str]
    search_hint: str
    why_matched: str

    # Epic ζ #2297 path B — full schema export for LLM-side per-domain reasoning
    input_schema_json: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Full Pydantic JSON Schema (Draft 2020-12) of the adapter's "
            "input_schema, including per-field description / type / pattern / "
            "examples / ge-le constraints. The LLM reads this to fill params "
            "according to the domain API's REST shape."
        ),
    )
    output_schema_json: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Full Pydantic JSON Schema of the adapter's output_schema. "
            "Helpful for the LLM to anticipate the shape of the result."
        ),
    )
    llm_description: str | None = Field(
        default=None,
        description=(
            "Adapter usage prose (rich than search_hint). "
            "Includes ordering rules, prerequisites, scope_list semantics, "
            "and worked examples when applicable."
        ),
    )
    primitive: str | None = Field(
        default=None,
        description=(
            "The primitive root this adapter binds to "
            "(lookup / verify / submit / subscribe / resolve_location)."
        ),
    )
    real_classification_url: str | None = Field(
        default=None,
        description=(
            "Agency-published policy URL the adapter cites "
            "(KOSMOS does not invent permission classifications)."
        ),
    )


class LookupSearchResult(BaseModel):
    """Result from lookup(mode='search'): ranked adapter candidates."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["search"]
    candidates: list[AdapterCandidate]
    total_registry_size: int = Field(ge=0)
    effective_top_k: int = Field(ge=0, le=20)
    reason: Literal["ok", "empty_registry", "below_threshold"] = "ok"


class LookupRecord(BaseModel):
    """Single-record fetch result."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["record"]
    item: dict[str, object]
    meta: LookupMeta


class LookupCollection(BaseModel):
    """Collection fetch result (list of records)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["collection"]
    items: list[dict[str, object]]
    total_count: int | None = None
    next_cursor: str | None = None
    meta: LookupMeta


class LookupTimeseries(BaseModel):
    """Time-series fetch result."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["timeseries"]
    points: list[dict[str, object]]
    interval: Literal["minute", "hour", "day"]
    meta: LookupMeta


class LookupError(BaseModel):  # noqa: A001
    """Structured error result from lookup operations."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["error"]
    reason: LookupErrorReason
    message: str
    upstream_code: str | None = None
    upstream_message: str | None = None
    retryable: bool = False
    meta: LookupMeta | None = None


LookupOutput = Annotated[
    LookupSearchResult | LookupRecord | LookupCollection | LookupTimeseries | LookupError,
    Field(discriminator="kind"),
]
"""Discriminated union on `kind`. Variant names are BINDING per docs/design/mvp-tools.md §5.4."""
