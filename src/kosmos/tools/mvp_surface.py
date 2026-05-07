# SPDX-License-Identifier: Apache-2.0
"""LLM-visible core tool definitions for the MVP primitive surface.

Defines ``GovAPITool`` registrations for the 4 callable primitives:
``resolve_location`` + ``lookup`` + ``verify`` + ``submit``.
All carry ``is_core=True`` so they appear in the core prompt partition and are
exported via ``registry.export_core_tools_openai()``.

Original Spec 022 / Spec 1634 (T028) shipped 2 tools (resolve_location + lookup).
Epic η #2298 (Initiative #2290) extended the LLM-visible surface with
verify / submit so the citizen-OPAQUE chain
(verify → lookup → submit) the system prompt teaches is actually callable.

For ``verify``, the input_schema declares ``family_hint: str`` permissively —
the system prompt's ``<verify_families>`` table is the source of valid family
values (10 active families per Epic ε #2296). The dispatcher's
``_VERIFY_ADAPTERS`` registry validates the value at call time and returns
``VerifyMismatchError`` if a non-registered family is passed (FR-007 / FR-010
of Spec 031). This is the same pattern lookup uses — permissive ``tool_id: str``
where the prompt + BM25 search hint tells the LLM what's valid.

FR-001 (Epic η updated): The LLM sees exactly four tools: resolve_location,
lookup, verify, submit. Subscribe is deferred until KOSMOS has a real
app/push-notification runtime rather than a CLI-only subscription surface.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from kosmos.tools.models import (
    AdapterRealDomainPolicy,
    GovAPITool,
    ResolveLocationInput,
)

# ---------------------------------------------------------------------------
# Minimal output schema placeholders
# ---------------------------------------------------------------------------
# The actual output types are discriminated unions defined in models.py.
# GovAPITool.output_schema must be a type[BaseModel]; we use RootModel wrappers
# so we can pass the full union output as-is without breaking the registry.


class _ResolveLocationOutput(RootModel[object]):
    """Placeholder output schema for resolve_location tool registration."""


class _LookupOutput(RootModel[object]):
    """Placeholder output schema for lookup tool registration."""


class _LookupInputForLLM(BaseModel):
    """LLM-visible lookup input — fetch-only ``{tool_id, params}`` envelope.

    Spec 2521 (2026-05-01): the previous ``_LookupInput`` (RootModel union of
    LookupSearchInput | LookupFetchInput) exposed BM25 adapter discovery as
    a callable mode. That mis-modeled an *internal backend mechanism* as a
    user-visible tool: the LLM kept emitting ``lookup(mode='search')`` calls
    after each answer turn, painting a redundant `● lookup(search:)` block
    in the citizen transcript and burning agentic-loop budget.

    The corrected design (per user directive 2026-05-01):

    1. BM25 search is a backend-internal *function*, not a tool. The
       backend runs it automatically against every citizen utterance and
       injects the top-K candidates into the system prompt's
       ``<available_adapters>`` dynamic suffix (see ``stdio.py``).
    2. The LLM-visible ``lookup`` tool is fetch-only: pick a ``tool_id``
       from the injected suffix, supply ``params``, get a typed result.
    3. ``LookupSearchInput`` / ``LookupSearchResults`` survive as
       internal API consumed by the auto-inject path + the eval harness
       (``kosmos.eval.retrieval``); they are NOT exposed to the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str = Field(
        # Mirrors LookupFetchInput.tool_id pattern (Spec 1636 ADR-007).
        pattern=r"^([a-z][a-z0-9_]*|plugin\.[a-z][a-z0-9_]*\.(lookup|submit|verify|resolve_location))$",
        description=(
            "Adapter identifier picked from the dynamically-injected "
            "<available_adapters> block. Must come from the candidate "
            "list — never guess."
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


# ---------------------------------------------------------------------------
# resolve_location core tool definition (T028)
# ---------------------------------------------------------------------------

RESOLVE_LOCATION_TOOL = GovAPITool(
    id="resolve_location",
    name_ko="위치 정보 조회",
    ministry="KOSMOS",
    category=["위치", "지오코딩", "행정구역"],
    endpoint="internal://resolve_location",
    auth_type="public",
    input_schema=ResolveLocationInput,
    output_schema=_ResolveLocationOutput,
    llm_description=(
        "Convert a free-text Korean place name, address, or landmark into structured "
        "location identifiers (coordinates, 10-digit 행정동 code, road address, POI).\n\n"
        "ALWAYS call this tool first before calling lookup(mode='fetch') on any "
        "location-dependent adapter such as koroad_accident_hazard_search.\n\n"
        "QUERY DISCIPLINE — pass ONLY a place/location noun. Do NOT splice the "
        "service the citizen asked about into the query: split '동아대학교 근처 병원' "
        "into resolve_location(query='동아대학교') first, then hira_hospital_search "
        "with the returned coordinates. NEVER call resolve_location(query='X 병원') / "
        "(query='X 식당') / (query='X 주변 약국') — those collapse the citizen's "
        "two-step intent into a single keyword that Kakao matches as 'X병원' "
        "(institution name), bringing back the institution's address rather than "
        "the campus/landmark the citizen referenced. Examples of the right shape: "
        "query='동아대학교' / '강남역' / '부산 사하구 다대1동' / '경복궁'.\n\n"
        "want options:\n"
        "  - 'coords_and_admcd' (default): returns lat/lon + 10-digit adm_cd bundle\n"
        "  - 'adm_cd': returns only the 10-digit 행정동 administrative code\n"
        "  - 'coords': returns lat/lon with confidence level\n"
        "  - 'road_address' / 'jibun_address': returns structured address\n"
        "  - 'poi': returns the nearest point-of-interest match\n"
        "  - 'all': returns all of the above in a ResolveBundle\n\n"
        "Examples: query='서울 강남구', want='adm_cd' → '1168000000'"
    ),
    search_hint=(
        "위치 조회 주소 변환 행정동 코드 좌표 지오코딩 POI 장소 검색 "
        "resolve location address geocode coordinates adm_cd administrative code place"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (KOSMOS 내부 geocoding 표면 — 시민 PII 미포함)"
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=300,
    rate_limit_per_minute=60,
    is_core=True,
    primitive="lookup",
    trigger_examples=[
        "강남역 어디야?",
        "서울시청 주소 알려줘",
        "근처 도서관",
    ],
)


# ---------------------------------------------------------------------------
# lookup core tool definition (T028)
# ---------------------------------------------------------------------------

LOOKUP_SEARCH_TOOL = GovAPITool(
    id="lookup",
    name_ko="데이터 조회",
    ministry="KOSMOS",
    category=["시스템", "도구검색", "데이터조회"],
    endpoint="internal://lookup",
    auth_type="public",
    input_schema=_LookupInputForLLM,
    output_schema=_LookupOutput,
    llm_description=(
        "외부 도메인 API (기상청 단기예보, HIRA 병원 검색, KOROAD 사고 데이터, "
        "KMA 현재 관측 등) 를 조회하는 추상 도구. 시스템 프롬프트의 "
        "<available_adapters> 블록에 백엔드가 매 사용자 발화마다 후보 어댑터를 "
        "자동으로 inject 합니다 — LLM 은 그 목록의 tool_id 중 하나를 선택해 "
        "이 lookup 도구를 호출하면 됩니다.\n\n"
        "사용법:\n"
        '  {"tool_id": "<후보 목록의 tool_id>", "params": {...}}\n\n'
        "예시 (시민: '오늘 부산 날씨'):\n"
        "  {\n"
        '    "tool_id": "kma_forecast_fetch",\n'
        '    "params": {"lat": 35.18, "lon": 129.08,\n'
        '               "base_date": "20260501", "base_time": "1400"}\n'
        "  }\n\n"
        "ORDERING RULE: <available_adapters> 에서 tool_id 선택 → 호출 → 결과 "
        "분석 → 다음 도구 또는 답변. 동일 tool_id 를 한 turn 안에서 반복 호출하지 "
        "않습니다 — 결과를 바탕으로 답변하거나, 필요하면 다른 tool_id 로 보완 호출."
    ),
    search_hint=(
        "데이터 조회 도구 호출 검색 패치 lookup search fetch invoke tool adapter data query"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (KOSMOS 내부 lookup 메타-표면 — 시민 PII 미포함)"
        ),
        citizen_facing_gate="read-only",
        last_verified=datetime(2026, 4, 29, tzinfo=UTC),
    ),
    is_concurrency_safe=True,
    cache_ttl_seconds=0,
    rate_limit_per_minute=60,
    is_core=True,
    primitive="lookup",
    trigger_examples=[
        "어떤 도구가 있어?",
        "공공 데이터 검색",
    ],
)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Epic η #2298 — verify / submit primitive surfaces
# ---------------------------------------------------------------------------
# These two primitives were previously registered into per-primitive sub-
# registries only (Spec 031 + Spec 2296) and were NOT visible to the LLM via
# the OpenAI tool_calls schema. The system prompt teaches the citizen-OPAQUE
# verify→lookup→submit chain pattern, but the LLM cannot follow it without
# these tools also appearing in `registry.export_core_tools_openai()`.
# Epic η registers them here as core tools to close the gap.


class _SubmitInputForLLM(BaseModel):
    """LLM-visible submit input schema — `{tool_id, params}` envelope.

    Mirrors :class:`kosmos.primitives.submit.SubmitInput` but lives here so the
    OpenAI tool_calls schema published to FriendliAI for the ``submit`` tool
    is the submit envelope, NOT the lookup mode-discriminated union. (Codex
    P1 #2 on PR #2480 caught the original copy-paste bug where SUBMIT_TOOL
    was declared with ``input_schema=_LookupInput``.)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "Registered submit adapter id (e.g. mock_submit_module_hometax_"
            "taxreturn). MUST match a tool_id from the system prompt's "
            "<verify_chain_pattern> 기본 매핑 section."
        ),
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        description=(
            "Adapter-defined payload. MUST include 'delegation_context' "
            "(the value returned by the prior verify call) plus any adapter-"
            "specific filing fields. Adapter validates against its own "
            "Pydantic model at invocation time."
        ),
    )


class _VerifyInputForLLM(BaseModel):
    """LLM-visible verify input schema — accepts both citizen-shape and legacy-shape.

    **Citizen-facing shape** (emitted by K-EXAONE per ``prompts/system_v1.md``
    v2 ``<verify_chain_pattern>``):

    .. code-block:: json

        {
          "tool_id": "mock_verify_module_modid",
          "params": {
            "scope_list": ["lookup:hometax.simplified", "submit:hometax.tax-return"],
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
    back to a conversational "no tool" response instead of emitting verify().
    (Epic ζ #2297, FR-008 / FR-008a / FR-008b).

    References
    ----------
    - ``specs/2297-zeta-e2e-smoke/contracts/verify-input-shape.md`` — I-V1 … I-V8
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
            "Verify adapter tool_id. MUST match a row in the system prompt's "
            "<verify_families> table "
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
            "values documented in the system prompt's <verify_families> table: "
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
            from kosmos.tools.verify_canonical_map import (  # noqa: PLC0415
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
        ``verify({})`` and pass schema validation, after which the dispatcher
        would silently call ``verify(family_hint="")`` and return a
        no-adapter error. Reject empty-everything at the schema boundary so
        the LLM gets a typed validation failure on the same turn.
        """
        if not self.tool_id and not self.family_hint:
            raise ValueError(
                "verify requires at least one selector — either citizen-shape "
                "'tool_id' (e.g. 'mock_verify_module_modid') OR legacy-shape "
                "non-empty 'family_hint'. Both were empty."
            )
        return self


VERIFY_TOOL = GovAPITool(
    id="verify",
    name_ko="인증 및 위임",
    ministry="KOSMOS",
    category=["인증", "위임토큰", "primitive"],
    endpoint="internal://verify",
    # api_key auth type required for citizen_facing_gate=login (AAL2) per V6
    # invariant — the delegation ceremony establishes session-bound credentials.
    auth_type="api_key",
    input_schema=_VerifyInputForLLM,
    output_schema=_LookupOutput,  # opaque envelope wrapper (RootModel[object])
    llm_description=(
        "Authentication-ceremony primitive that issues a scope-bound "
        "DelegationContext (or IdentityAssertion for any_id_sso). Call this "
        "FIRST when the citizen requests any OPAQUE-domain submit-class action "
        "(홈택스 신고 / 정부24 민원 / 마이데이터 액션). Pass the scope_list "
        "covering ALL downstream lookup + submit calls in a single verify "
        "invocation. The returned DelegationContext is then passed as a "
        "param into the subsequent lookup(mode='fetch', params={'delegation_"
        "context': ctx}) and submit(delegation_context=ctx) calls.\n\n"
        "family_hint values + canonical AAL hints are documented in the "
        "system prompt's <verify_families> table. The LLM defaults to the "
        "lowest AAL satisfying the citizen's stated purpose.\n\n"
        "Exception: family_hint='any_id_sso' returns an IdentityAssertion "
        "with no DelegationToken — do NOT chain a submit after this verify."
    ),
    search_hint=(
        "인증 위임 토큰 verify 모바일ID 공동인증서 금융인증서 간편인증 "
        "마이데이터 KEC SSO delegation token authentication ceremony"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (KOSMOS 내부 verify primitive — "
            "각 family adapter 가 기관 자체 정책 citation; KOSMOS 권한 발명 X)"
        ),
        citizen_facing_gate="login",
        last_verified=datetime(2026, 4, 30, tzinfo=UTC),
    ),
    is_concurrency_safe=False,  # ceremony establishes session-bound state
    cache_ttl_seconds=0,
    rate_limit_per_minute=30,
    is_core=True,
    primitive="verify",
    trigger_examples=[
        "내 종합소득세 신고해줘",
        "정부24 민원 하나 신청해줘",
        "사업자 등록증 발급해줘",
    ],
)


SUBMIT_TOOL = GovAPITool(
    id="submit",
    name_ko="행정 모듈 제출",
    ministry="KOSMOS",
    category=["제출", "신고", "primitive"],
    endpoint="internal://submit",
    # api_key auth type required for citizen_facing_gate=submit (AAL3) per V6.
    auth_type="api_key",
    input_schema=_SubmitInputForLLM,
    output_schema=_LookupOutput,
    llm_description=(
        "Submit primitive — invokes a write-transaction adapter (홈택스 신고, "
        "정부24 민원, mydata 액션 등). REQUIRES a valid DelegationContext "
        "from a prior verify call with matching scope. tool_id MUST be one of "
        "the registered submit adapters (e.g. mock_submit_module_hometax_"
        "taxreturn). params MUST include 'delegation_context' (the value "
        "returned by verify) and the adapter-specific payload.\n\n"
        "On success: returns transaction_id (deterministic URN) + adapter_"
        "receipt with the agency's 접수번호 (e.g. 'hometax-2026-MM-DD-RX-XXXXX'). "
        "Cite the receipt in the citizen-facing Korean response.\n\n"
        "Failure modes: scope_violation / expired / session_violation / "
        "revoked / DelegationGrantMissing (after any_id_sso verify). Each "
        "failure surfaces a typed error; do NOT silently retry."
    ),
    search_hint=(
        "제출 신고 민원 홈택스 정부24 마이데이터 submit transaction receipt "
        "delegation hometax 접수번호 minwon application filing"
    ),
    policy=AdapterRealDomainPolicy(
        real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
        real_classification_text=(
            "공공데이터포털 개인정보처리방침 (KOSMOS 내부 submit primitive — "
            "각 adapter 가 기관 자체 정책 citation; KOSMOS 권한 발명 X)"
        ),
        citizen_facing_gate="submit",
        last_verified=datetime(2026, 4, 30, tzinfo=UTC),
    ),
    is_concurrency_safe=False,
    cache_ttl_seconds=0,
    rate_limit_per_minute=30,
    is_core=True,
    primitive="submit",
    trigger_examples=[
        "신고 제출",
        "민원 신청 마무리",
    ],
)


def register_mvp_surface(registry: object) -> None:
    """Register the MVP LLM-visible core tools — 4-primitive surface.

    Spec 022 / Spec 1634 shipped resolve_location + lookup. Epic η #2298 added
    verify and submit so the citizen-OPAQUE chain the system prompt teaches is
    actually callable from the OpenAI tool_calls schema sent to the LLM.

    These tools are NOT bound to executor adapters — their invocation is
    handled directly by the KOSMOS orchestrator loop (or its primitive sub-
    dispatcher), not via ``ToolExecutor.invoke()``. Registration here ensures
    they appear in ``registry.core_tools()`` and
    ``registry.export_core_tools_openai()``.

    Args:
        registry: A ToolRegistry instance.
    """
    from kosmos.tools.registry import ToolRegistry

    assert isinstance(registry, ToolRegistry)

    registry.register(RESOLVE_LOCATION_TOOL)
    registry.register(LOOKUP_SEARCH_TOOL)
    registry.register(VERIFY_TOOL)
    registry.register(SUBMIT_TOOL)
