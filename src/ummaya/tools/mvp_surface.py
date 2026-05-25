# SPDX-License-Identifier: Apache-2.0
"""LLM-visible core tool definitions for the MVP primitive surface.

Defines ``GovAPITool`` registrations for the 4 callable primitives:
``locate`` + ``find`` + ``check`` + ``send``.
All carry ``is_core=True`` so they appear in the core prompt partition and are
exported via ``registry.export_core_tools_openai()``.

Original Spec 022 / Spec 1634 (T028) shipped 2 tools (locate + find).
Epic η #2298 (Initiative #2290) extended the LLM-visible surface with
check / send so the citizen-OPAQUE chain
(check → find → send) the system prompt teaches is actually callable.

For ``check``, the input_schema declares ``family_hint: str`` permissively —
the system prompt's ``<check_families>`` table is the source of valid family
values (10 active families per Epic ε #2296). The dispatcher's
``_VERIFY_ADAPTERS`` registry validates the value at call time and returns
``VerifyMismatchError`` if a non-registered family is passed (FR-007 / FR-010
of Spec 031). This is the same pattern find uses — permissive ``tool_id: str``
where the prompt + BM25 search hint tells the LLM what's valid.

2026 migration note: these root primitives are high-level categories and legacy
transcript compatibility wrappers. The normal model-facing surface is a small
turn-local set of concrete adapter functions selected by ToolSearch or backend
retrieval.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from ummaya.tools.models import (
    AdapterRealDomainPolicy,
    GovAPITool,
)

# ---------------------------------------------------------------------------
# Minimal output schema placeholders
# ---------------------------------------------------------------------------
# The actual output types are discriminated unions defined in models.py.
# GovAPITool.output_schema must be a type[BaseModel]; we use RootModel wrappers
# so we can pass the full union output as-is without breaking the registry.


class _ResolveLocationOutput(RootModel[object]):
    """Placeholder output schema for locate tool registration."""


class _LookupOutput(RootModel[object]):
    """Placeholder output schema for find tool registration."""


class _LookupInputForLLM(BaseModel):
    """LLM-visible find input — fetch-only ``{tool_id, params}`` envelope.

    Spec 2521 (2026-05-01): the previous ``_LookupInput`` (RootModel union of
    LookupSearchInput | LookupFetchInput) exposed BM25 adapter discovery as
    a callable mode. That mis-modeled an *internal backend mechanism* as a
    user-visible tool: the LLM kept emitting ``find(mode='search')`` calls
    after each answer turn, painting a redundant `● find(search:)` block
    in the citizen transcript and burning agentic-loop budget.

    The corrected design (per user directive 2026-05-01):

    1. BM25 search is a backend-internal *function*, not a tool. The
       backend runs it automatically against every citizen utterance and
       injects the top-K candidates into the system prompt's
       ``<available_adapters>`` dynamic suffix (see ``stdio.py``).
    2. The LLM-visible ``find`` tool is fetch-only: pick a ``tool_id``
       from the injected suffix, supply ``params``, get a typed result.
    3. ``LookupSearchInput`` / ``LookupSearchResults`` survive as
       internal API consumed by the auto-inject path + the eval harness
       (``ummaya.eval.retrieval``); they are NOT exposed to the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(
        # Mirrors LookupFetchInput.tool_id pattern (Spec 1636 ADR-007).
        pattern=r"^([a-z][a-z0-9_]*|plugin\.[a-z][a-z0-9_]*\.(find|send|check|locate))$",
        description=(
            "Concrete adapter identifier picked from the dynamically-injected "
            "<available_adapters> block. This is not the root function name; "
            "never set tool_id to 'find', 'locate', 'check', or 'send'. "
            "Must come from the candidate list — never guess."
        ),
    )
    params: dict[str, object] = Field(
        description="Validated against the target adapter's input_schema at fetch time."
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Optional pagination cursor for adapters that return collections.",
    )


class _LocateInputForLLM(BaseModel):
    """LLM-visible locate input — provider-adapter envelope.

    Location resolution is no longer a monolithic ``query/want`` façade. The
    model chooses a provider endpoint adapter from ``<available_adapters>`` and
    fills that adapter's schema directly.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "Concrete locate adapter id from <available_adapters>; this is not "
            "the root function name. Never set tool_id to 'locate', 'find', "
            "'check', or 'send'. Examples: "
            "'kakao_keyword_search', 'kakao_address_search', "
            "'kakao_coord_to_region', 'juso_adm_cd_lookup', or "
            "'sgis_adm_cd_lookup'."
        ),
    )
    params: dict[str, object] = Field(
        description="Validated against the selected locate adapter's input_schema."
    )


# ---------------------------------------------------------------------------
# locate core tool definition (T028)
# ---------------------------------------------------------------------------

RESOLVE_LOCATION_TOOL = GovAPITool(
    id="locate",
    name_ko="위치 정보 조회",
    ministry="UMMAYA",
    category=["위치", "지오코딩", "행정구역"],
    endpoint="internal://locate",
    auth_type="public",
    input_schema=_LocateInputForLLM,
    output_schema=_ResolveLocationOutput,
    llm_description=(
        "Location primitive category and legacy wrapper. Prefer concrete locate "
        "adapter functions selected by ToolSearch or backend retrieval, and call "
        "them directly with their schema arguments. Use locate({tool_id, params}) "
        "only for old transcripts or compatibility paths. Provider endpoints are "
        "separate adapters: Kakao address search, Kakao keyword/POI search, Kakao "
        "coordinate-to-region, JUSO admCd lookup, and SGIS coordinate-to-adm_cd "
        "lookup.\n\n"
        "Do not invent coordinates or administrative codes. If the citizen gives "
        "a named place/campus/station/landmark, prefer kakao_keyword_search. If "
        "the citizen gives a structured road/jibun address or district text, "
        "prefer kakao_address_search or juso_adm_cd_lookup. If a downstream "
        "adapter needs q0/q1 region names after you have lat/lon, call "
        "kakao_coord_to_region with those coordinates.\n\n"
        "Examples:\n"
        "  kakao_keyword_search({query:'동아대학교 승학캠퍼스'})\n"
        "  kakao_coord_to_region({lat:35.115446, lon:128.967669})"
    ),
    search_hint=(
        "위치 조회 주소 변환 행정동 코드 좌표 지오코딩 POI 장소 검색 "
        "resolve location address geocode coordinates adm_cd administrative code place"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (UMMAYA 내부 geocoding 표면 — 시민 PII 미포함)"
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    is_core=True,
    primitive="locate",
    trigger_examples=[
        "강남역 어디야?",
        "서울시청 주소 알려줘",
        "근처 도서관",
    ],
)


# ---------------------------------------------------------------------------
# find core tool definition (T028)
# ---------------------------------------------------------------------------

LOOKUP_SEARCH_TOOL = GovAPITool(
    id="find",
    name_ko="데이터 조회",
    ministry="UMMAYA",
    category=["시스템", "도구검색", "데이터조회"],
    endpoint="internal://find",
    auth_type="public",
    input_schema=_LookupInputForLLM,
    output_schema=_LookupOutput,
    llm_description=(
        "Lookup primitive category and legacy wrapper for external-domain "
        "public-service data such as KMA forecasts, KMA current observations, "
        "HIRA hospital search, and KOROAD accident data. Prefer concrete adapter "
        "functions selected by ToolSearch or backend retrieval, and call them "
        "directly with their schema arguments.\n\n"
        "Use find({tool_id, params}) only for old transcripts or compatibility "
        "paths. Do not use root primitive names as tool_id values: find, locate, "
        "check, send.\n\n"
        "Example for a selected weather adapter:\n"
        "  kma_forecast_fetch({lat:35.18, lon:129.08, base_date:'20260501', "
        "base_time:'1400'})\n\n"
        "Ordering rule: select a concrete adapter, call it once with valid schema "
        "arguments, analyze the result, then answer or choose a different adapter "
        "if another official data source is needed. Do not repeat the same "
        "adapter in a turn unless validation feedback requires corrected args."
    ),
    search_hint=(
        "데이터 조회 도구 호출 검색 패치 find search fetch invoke tool adapter data query"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (UMMAYA 내부 find 메타-표면 — 시민 PII 미포함)"
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=60,
    is_core=True,
    primitive="find",
    trigger_examples=[
        "어떤 도구가 있어?",
        "공공 데이터 검색",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Epic η #2298 — check / send primitive surfaces
# ---------------------------------------------------------------------------
# These two primitives were previously registered into per-primitive sub-
# registries only (Spec 031 + Spec 2296) and were NOT visible to the LLM via
# the OpenAI tool_calls schema. The system prompt teaches the citizen-OPAQUE
# check→find→send chain pattern, but the LLM cannot follow it without
# these tools also appearing in `registry.export_core_tools_openai()`.
# Epic η registers them here as core tools to close the gap.


class _SubmitInputForLLM(BaseModel):
    """LLM-visible send input schema — `{tool_id, params}` envelope.

    Mirrors :class:`ummaya.primitives.send.SubmitInput` but lives here so the
    OpenAI tool_calls schema published to FriendliAI for the ``send`` tool
    is the send envelope, NOT the find mode-discriminated union. (Codex
    P1 #2 on PR #2480 caught the original copy-paste bug where SUBMIT_TOOL
    was declared with ``input_schema=_LookupInput``.)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "Registered send adapter id (e.g. mock_submit_module_hometax_"
            "taxreturn). MUST match a tool_id from the system prompt's "
            "<check_chain_pattern> 기본 매핑 section."
        ),
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Adapter-defined payload. MUST include 'delegation_context' "
            "(the value returned by the prior check call) plus any adapter-"
            "specific filing fields. Adapter validates against its own "
            "Pydantic model at invocation time."
        ),
    )


class _VerifyInputForLLM(BaseModel):
    """LLM-visible check input schema — accepts both citizen-shape and legacy-shape.

    **Citizen-facing shape** (emitted by K-EXAONE per ``prompts/system_v1.md``
    v2 ``<check_chain_pattern>``):

    .. code-block:: json

        {
          "tool_id": "mock_verify_module_modid",
          "params": {
            "scope_list": ["find:hometax.simplified", "send:hometax.tax-return"],
            "purpose_ko": "종합소득세 신고",
            "purpose_en": "Comprehensive income tax filing"
          }
        }

    **Legacy shape** (used by direct dispatcher callers — backward compat):

    .. code-block:: json

        {"family_hint": "modid", "session_context": {...}}

    The ``@model_validator(mode="before")`` pre-validator translates the
    citizen shape to the legacy shape before field validation.  Direct-dispatcher
    callers that already supply ``family_hint`` pass through unchanged
    (idempotent guard).

    For the LLM the OpenAI-compat schema published to FriendliAI lists
    ``tool_id`` + ``params`` as the primary citizen-facing fields.
    ``family_hint`` / ``session_context`` are retained (with ``(legacy)``
    description tags) for backward compatibility with existing integration tests.

    Fix: resolves the schema↔prompt contradiction that caused K-EXAONE to fall
    back to a conversational "no tool" response instead of emitting check().
    (Epic ζ #2297, FR-008 / FR-008a / FR-008b).

    References
    ----------
    - ``specs/2297-zeta-e2e-smoke/contracts/check-input-shape.md`` — I-V1 … I-V8
    - ``specs/2297-zeta-e2e-smoke/data-model.md § 1``
    - ``specs/2297-zeta-e2e-smoke/research.md § Decision 1 + Decision 2``
    """

    # Pydantic v2 ConfigDict — frozen for immutability; extra="allow" is
    # intentionally NOT set so unexpected fields fail loudly.
    model_config = ConfigDict(frozen=True, extra="forbid")

    # ------------------------------------------------------------------
    # Citizen-facing canonical fields (LLM-emitted shape)
    # ------------------------------------------------------------------

    tool_id: str | None = Field(
        default=None,
        description=(
            "Check adapter tool_id. MUST match a row in the system prompt's "
            "<check_families> table "
            "(e.g. 'mock_verify_module_modid'). "
            "Pre-validator translates this to family_hint."
        ),
    )
    params: dict[str, object] | None = Field(
        default=None,
        description=(
            "Adapter-specific input. Must include scope_list (list[str] of "
            "'<verb>:<adapter_family>.<action>' scopes), purpose_ko, "
            "purpose_en. Optional session_id belongs directly in params "
            "(params['session_id']), not nested under params['session_context']. "
            "Pre-validator packs this into session_context."
        ),
    )

    # ------------------------------------------------------------------
    # Legacy fields (preserved for backward compatibility)
    # ------------------------------------------------------------------

    family_hint: str = Field(
        default="",
        description=(
            "(legacy) Authentication family identifier. One of the 10 active "
            "values documented in the system prompt's <check_families> table: "
            "gongdong_injeungseo / geumyung_injeungseo / ganpyeon_injeung / "
            "mobile_id / mydata / simple_auth_module / modid / kec / "
            "geumyung_module / any_id_sso. "
            "Set automatically from tool_id by the pre-validator when "
            "citizen-shape input is supplied."
        ),
    )
    session_context: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "(legacy) Adapter-specific session evidence. For Mock-mode chains "
            "the LLM passes scope_list (list[str] of "
            "'<verb>:<adapter_family>.<action>' scopes), purpose_ko, "
            "purpose_en. Set automatically from params by the pre-validator "
            "when citizen-shape input is supplied. This is a top-level legacy "
            "field; citizen-shape callers must not nest it under params."
        ),
    )

    # ------------------------------------------------------------------
    # Pre-validator (FR-008a / I-V1 … I-V8)
    # ------------------------------------------------------------------

    @model_validator(mode="before")
    @classmethod
    def translate_tool_id_shape(cls, data: dict[str, object]) -> dict[str, object]:
        """Translate citizen-shape ``{tool_id, params}`` → legacy-shape.

        Idempotent — if *data* already has ``family_hint`` set (non-empty),
        the citizen-shape fields are ignored (I-V2 / I-V5).

        Raises ``ValueError`` for an unknown ``tool_id`` (I-V3 / FR-010).
        """
        if not isinstance(data, dict):
            return data

        # Idempotency guard: already in legacy shape (I-V2 / I-V5)
        if data.get("family_hint"):
            return data

        # Citizen shape: translate tool_id → family_hint (I-V1)
        tool_id = data.get("tool_id")
        if tool_id:
            from ummaya.tools.verify_canonical_map import (  # noqa: PLC0415
                resolve_family,
            )

            family = resolve_family(str(tool_id))
            if family is None:
                raise ValueError(f"unknown verify tool_id: {tool_id!r}")

            # Build a fresh dict — never mutate caller's original (I-V8)
            data = dict(data)
            data["family_hint"] = family

            # Pack params → session_context (merge; citizen params win on conflict)
            params = data.get("params")
            existing_ctx: dict[str, object] = {}
            raw_ctx = data.get("session_context")
            if isinstance(raw_ctx, dict):
                existing_ctx = {str(k): v for k, v in raw_ctx.items()}
            if isinstance(params, dict):
                nested_ctx: dict[str, object] = {}
                raw_nested_ctx = params.get("session_context")
                if isinstance(raw_nested_ctx, dict):
                    nested_ctx = {str(k): v for k, v in raw_nested_ctx.items()}
                flat_params = {str(k): v for k, v in params.items() if k != "session_context"}
                data["session_context"] = {**existing_ctx, **nested_ctx, **flat_params}
            elif params is None:
                data.setdefault("session_context", existing_ctx)

        return data

    @model_validator(mode="after")
    def _enforce_selector_present(self) -> _VerifyInputForLLM:
        """Codex P1 fail-closed gate (Epic ζ #2297 PR #2517 review).

        After the pre-validator runs, at least ONE of {``tool_id``,
        non-empty ``family_hint``} MUST be present. The default ``family_hint=""``
        + optional ``tool_id`` combination would otherwise let the LLM emit
        ``check({})`` and pass schema validation, after which the dispatcher
        would silently call ``check(family_hint="")`` and return a
        no-adapter error. Reject empty-everything at the schema boundary so
        the LLM gets a typed validation failure on the same turn.
        """
        if not self.tool_id and not self.family_hint:
            raise ValueError(
                "check requires at least one selector — either citizen-shape "
                "'tool_id' (e.g. 'mock_verify_module_modid') OR legacy-shape "
                "non-empty 'family_hint'. Both were empty."
            )
        return self


VERIFY_TOOL = GovAPITool(
    id="check",
    name_ko="인증 및 위임",
    ministry="UMMAYA",
    category=["인증", "위임토큰", "primitive"],
    endpoint="internal://check",
    # api_key auth type required for citizen_facing_gate=login (AAL2) per V6
    # invariant — the delegation ceremony establishes session-bound credentials.
    auth_type="api_key",
    input_schema=_VerifyInputForLLM,
    output_schema=_LookupOutput,  # opaque envelope wrapper (RootModel[object])
    llm_description=(
        "Authentication-ceremony primitive category and legacy wrapper. Prefer "
        "concrete check adapter functions selected by ToolSearch or backend "
        "retrieval, and call them directly with their schema arguments. A check "
        "adapter issues a scope-bound DelegationContext or IdentityAssertion. "
        "Call an appropriate check adapter first when the citizen requests an "
        "OPAQUE-domain send-class action (홈택스 신고 / 정부24 민원 / 마이데이터 액션). "
        "Pass the scope_list covering all downstream lookup and send adapters in "
        "one check invocation. The returned DelegationContext is then passed as a "
        "param into subsequent concrete lookup/send adapter calls.\n\n"
        "Use check({tool_id, params}) only for old transcripts or compatibility "
        "paths. The LLM defaults to the lowest AAL satisfying the citizen's "
        "stated purpose.\n\n"
        "Exception: family_hint='any_id_sso' returns an IdentityAssertion "
        "with no DelegationToken — do NOT chain a send after this check."
    ),
    search_hint=(
        "인증 위임 토큰 check 모바일ID 공동인증서 금융인증서 간편인증 "
        "마이데이터 KEC SSO delegation token authentication ceremony"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (UMMAYA 내부 check primitive — "
            "각 family adapter 가 기관 자체 정책 citation; UMMAYA 권한 발명 X)"
        ),
        citizen_facing_gate="login",
        last_verified=datetime(2026, 4, 30, tzinfo=UTC),
    ),
    is_concurrency_safe=False,  # ceremony establishes session-bound state
    cache_ttl_seconds=0,
    rate_limit_per_minute=30,
    is_core=True,
    primitive="check",
    trigger_examples=[
        "내 종합소득세 신고해줘",
        "정부24 민원 하나 신청해줘",
        "사업자 등록증 발급해줘",
    ],
)


SUBMIT_TOOL = GovAPITool(
    id="send",
    name_ko="행정 모듈 제출",
    ministry="UMMAYA",
    category=["제출", "신고", "primitive"],
    endpoint="internal://send",
    # api_key auth type required for citizen_facing_gate=send (AAL3) per V6.
    auth_type="api_key",
    input_schema=_SubmitInputForLLM,
    output_schema=_LookupOutput,
    llm_description=(
        "Send primitive category and legacy wrapper for write-transaction "
        "adapters (홈택스 신고, 정부24 민원, mydata 액션 등). Prefer concrete send "
        "adapter functions selected by ToolSearch or backend retrieval, and call "
        "them directly with their schema arguments. A send adapter requires a "
        "valid DelegationContext from a prior check adapter with matching scope. "
        "Use send({tool_id, params}) only for old transcripts or compatibility "
        "paths. params must include the returned DelegationContext and the "
        "adapter-specific payload.\n\n"
        "On success: returns transaction_id (deterministic URN) + adapter_"
        "receipt with the agency's 접수번호 (e.g. 'hometax-2026-MM-DD-RX-XXXXX'). "
        "Cite the receipt in the citizen-facing Korean response.\n\n"
        "Failure modes: scope_violation / expired / session_violation / "
        "revoked / DelegationGrantMissing (after any_id_sso check). Each "
        "failure surfaces a typed error; do NOT silently retry."
    ),
    search_hint=(
        "제출 신고 민원 홈택스 정부24 마이데이터 send transaction receipt "
        "delegation hometax 접수번호 minwon application filing"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (UMMAYA 내부 send primitive — "
            "각 adapter 가 기관 자체 정책 citation; UMMAYA 권한 발명 X)"
        ),
        citizen_facing_gate="send",
        last_verified=datetime(2026, 4, 30, tzinfo=UTC),
    ),
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=30,
    is_core=True,
    primitive="send",
    trigger_examples=[
        "신고 제출",
        "민원 신청 마무리",
    ],
)


def register_mvp_surface(registry: object) -> None:
    """Register the MVP LLM-visible core tools — 4-primitive surface.

    Spec 022 / Spec 1634 shipped locate + find. Epic η #2298 added
    check and send so the citizen-OPAQUE chain the system prompt teaches is
    actually callable from the OpenAI tool_calls schema sent to the LLM.

    These tools are NOT bound to executor adapters — their invocation is
    handled directly by the UMMAYA orchestrator loop (or its primitive sub-
    dispatcher), not via ``ToolExecutor.invoke()``. Registration here ensures
    they appear in ``registry.core_tools()`` and
    ``registry.export_core_tools_openai()``.

    Args:
        registry: A ToolRegistry instance.
    """
    from ummaya.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)

    registry.register(RESOLVE_LOCATION_TOOL)
    registry.register(LOOKUP_SEARCH_TOOL)
    registry.register(VERIFY_TOOL)
    registry.register(SUBMIT_TOOL)
