# SPDX-License-Identifier: Apache-2.0
"""Discovery bridge — Epic ζ #2297 path B fix (live smoke 2026-04-30 follow-up).

The KOSMOS 5-primitive design isolates verify / submit / subscribe mock adapters
in per-primitive ``_ADAPTER_REGISTRY`` dicts (``kosmos.primitives.{verify,
submit,subscribe}``). The main :class:`kosmos.tools.registry.ToolRegistry` and
its BM25 corpus only see lookup-class adapters, so when the LLM emits
``lookup(mode="search", query="종합소득세 신고")`` the search returns no
verify/submit candidates — the citizen-facing chain never starts.

This module bridges the per-primitive registries into the main ToolRegistry by
synthesising lightweight :class:`kosmos.tools.models.GovAPITool` wrappers for
each registered mock and registering them with ``is_core=False`` (so they
participate in BM25 search but do NOT appear in the LLM-visible primary tool
list — that surface stays as the 5 primitives + lookup-class Live adapters).

The wrapped tools surface (per :class:`AdapterCandidate`):
- input_schema (Pydantic) — the citizen-shape params model the LLM should fill
- search_hint (bilingual ko/en) — BM25 indexable keyword phrase
- llm_description — adapter usage prose
- policy URL — agency-cited classification URL
- adapter_mode — mock/live transparency surfaced in AdapterCandidate

Called once from :func:`kosmos.tools.register_all.register_all_tools`
immediately after ``import kosmos.tools.mock`` so all per-primitive registries
are populated.
"""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kosmos.tools.models import AdapterRealDomainPolicy, GovAPITool

if TYPE_CHECKING:
    from kosmos.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight params shells for verify/subscribe (LLM-facing input schemas)
# ---------------------------------------------------------------------------


class _VerifyParamsShell(BaseModel):
    """LLM-facing verify params — citizen-shape `{scope_list, purpose_ko, purpose_en}`."""

    model_config = ConfigDict(extra="allow")

    scope_list: list[str] = Field(
        default_factory=list,
        description=(
            "List of '<verb>:<adapter_family>.<action>' scope strings the "
            "downstream lookup/submit calls will need. The verify ceremony "
            "issues a DelegationToken bound to exactly this scope set."
        ),
    )
    purpose_ko: str = Field(
        default="",
        description=(
            "Korean-language one-line purpose statement shown to the citizen "
            "during the consent prompt. Example: '종합소득세 신고'."
        ),
    )
    purpose_en: str = Field(
        default="",
        description=("English-language one-line purpose statement (for audit logs)."),
    )


class _SubscribeParamsShell(BaseModel):
    """LLM-facing subscribe params — opaque per-adapter dict."""

    model_config = ConfigDict(extra="allow")


class _OpaqueOutput(RootModel[dict[str, Any]]):
    """Generic envelope wrapper for bridge-registered tools' outputs."""


# ---------------------------------------------------------------------------
# Verify family metadata table (hand-rolled — verify mocks register by family
# name into kosmos.primitives.verify._ADAPTER_REGISTRY without an
# AdapterRegistration object, so we capture metadata declaratively here).
#
# Each entry mirrors the constants exposed by the corresponding mock module
# (`_TOOL_ID`, `SEARCH_HINT`, `_ACTUAL_ENDPOINT`, `_POLICY_AUTHORITY`).
# Drift detection: tests/integration/test_discovery_bridge_verify_table.py
# imports the mock modules and asserts the table matches.
# ---------------------------------------------------------------------------


_VERIFY_FAMILIES: list[dict[str, Any]] = [
    {
        "tool_id": "mock_verify_module_modid",
        "family": "modid",
        "name_ko": "모바일ID 모듈 (AX-channel)",
        "search_hint_ko": ["모바일ID", "모바일신분증", "행정안전부", "DID", "디지털신원"],
        "search_hint_en": [
            "mobile ID",
            "mobile identity",
            "mobile resident card",
            "MOIS digital ID",
        ],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/modid",
        "policy_authority": "https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000016&nttId=104637",
    },
    {
        "tool_id": "mock_verify_module_kec",
        "family": "kec",
        "name_ko": "KEC 공동인증서 모듈 (AX)",
        "search_hint_ko": ["KEC", "공동인증서", "사업자등록증", "법인", "전자서명"],
        "search_hint_en": [
            "KEC",
            "joint certificate",
            "corporate certificate",
            "business registration",
        ],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/kec",
        "policy_authority": "https://www.kec.co.kr/",
    },
    {
        "tool_id": "mock_verify_module_geumyung",
        "family": "geumyung_module",
        "name_ko": "금융인증서 모듈 (AX-channel)",
        "search_hint_ko": ["금융인증서", "금융결제원", "신용정보", "마이데이터금융"],
        "search_hint_en": ["financial certificate", "KFTC", "credit info", "financial mydata"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/geumyung",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_module_simple_auth",
        "family": "simple_auth_module",
        "name_ko": "간편인증 모듈 (AX-channel)",
        "search_hint_ko": ["간편인증", "PASS", "카카오인증", "네이버인증", "토스인증"],
        "search_hint_en": ["simple auth", "PASS", "Kakao", "Naver", "Toss"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/simple",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_module_any_id_sso",
        "family": "any_id_sso",
        "name_ko": "Any-ID SSO",
        "search_hint_ko": [
            "SSO",
            "통합로그인",
            "신원확인",
            "IdentityAssertion",
        ],
        "search_hint_en": ["SSO", "single sign-on", "identity assertion", "GOV.UK One Login"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/sso",
        "policy_authority": "https://www.gov.kr/",
    },
    {
        "tool_id": "mock_verify_gongdong_injeungseo",
        "family": "gongdong_injeungseo",
        "name_ko": "공동인증서 (구 공인인증서)",
        "search_hint_ko": ["공동인증서", "공인인증서", "KOSCOM", "전자서명", "인증서로그인"],
        "search_hint_en": ["joint certificate", "KOSCOM", "digital signature", "PKI"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/gongdong",
        "policy_authority": "https://www.rootca.or.kr/",
    },
    {
        "tool_id": "mock_verify_geumyung_injeungseo",
        "family": "geumyung_injeungseo",
        "name_ko": "금융인증서",
        "search_hint_ko": ["금융인증서", "금융결제원", "은행인증", "통장인증"],
        "search_hint_en": ["financial certificate", "KFTC", "bank authentication"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/geumyung-injeungseo",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_ganpyeon_injeung",
        "family": "ganpyeon_injeung",
        "name_ko": "간편인증 (PASS·카카오·네이버)",
        "search_hint_ko": [
            "간편인증",
            "PASS",
            "카카오",
            "네이버",
            "토스",
            "대리확인",
            "대신확인",
            "보호자확인",
        ],
        "search_hint_en": ["simple auth", "PASS", "Kakao Pay", "Naver", "Toss"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/ganpyeon",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_mobile_id",
        "family": "mobile_id",
        "name_ko": "모바일 신분증 (mDL)",
        "search_hint_ko": ["모바일 신분증", "모바일 운전면허증", "mDL", "ISO/IEC 18013-5"],
        "search_hint_en": ["mobile ID", "mobile DL", "mDL", "ISO/IEC 18013-5"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/mobile-id",
        "policy_authority": "https://www.mobileid.go.kr/",
    },
    {
        "tool_id": "mock_verify_mydata",
        "family": "mydata",
        "name_ko": "마이데이터 (KFTC)",
        "search_hint_ko": ["마이데이터", "거래내역", "신용카드", "은행거래", "자산조회"],
        "search_hint_en": ["mydata", "transaction history", "open banking", "credit info"],
        "endpoint": "https://api.gateway.kosmos.gov.kr/v1/verify/mydata",
        "policy_authority": "https://www.mydatacenter.or.kr:3441/",
    },
]


def _build_verify_search_hint(entry: dict[str, Any]) -> str:
    """Compose the BM25-indexable bilingual phrase from ko + en lists."""
    ko = " ".join(entry["search_hint_ko"])
    en = " ".join(entry["search_hint_en"])
    return f"{ko} {en} verify 인증 인증서 위임 delegation"


def _verify_to_govapitool(entry: dict[str, Any]) -> GovAPITool:
    """Build a GovAPITool wrapper for one verify family mock adapter."""
    return GovAPITool(
        id=entry["tool_id"],
        name_ko=entry["name_ko"],
        ministry="KOSMOS",
        category=["verify", "mock", "delegation"],
        endpoint=entry["endpoint"],
        auth_type="api_key",
        input_schema=_VerifyParamsShell,
        output_schema=_OpaqueOutput,
        llm_description=(
            f"Verify ceremony for {entry['name_ko']}. Issues a DelegationToken bound to "
            "the citizen's session and the requested scope_list. Returns the DelegationContext "
            "that downstream lookup/submit calls pass via params['delegation_context'].\n\n"
            "Citizen-shape input: {tool_id, params={scope_list, purpose_ko, purpose_en}}. "
            "The verify primitive (registered separately as a core 'verify' tool) "
            "translates this to the dispatcher's family_hint via the canonical map "
            "in prompts/system_v1.md <verify_families>."
        ),
        search_hint=_build_verify_search_hint(entry),
        policy=AdapterRealDomainPolicy(
            real_classification_url=entry["policy_authority"],
            real_classification_text=(
                f"{entry['name_ko']} — agency-published policy citation "
                "(KOSMOS does not invent permission classifications; "
                "see AGENTS.md § Hard rules)."
            ),
            citizen_facing_gate="login",
            last_verified=datetime(2026, 4, 30, tzinfo=UTC),
        ),
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=30,
        is_core=False,  # Discoverable via lookup search; NOT in primary LLM tool list
        primitive="verify",
        adapter_mode="mock",
    )


# ---------------------------------------------------------------------------
# Submit / subscribe — read AdapterRegistration from per-primitive registries
# ---------------------------------------------------------------------------


def _delegation_source_from_published_tier(tier: object) -> str | None:
    """Derive the compatible verify adapter from declared auth-tier metadata.

    This keeps the routing hint metadata-driven: submit registrations already
    declare the minimum published tier they accept, and the bridge projects
    that into the discoverable GovAPITool so the LLM can pick one verify module
    instead of cycling over unrelated auth families.
    """
    value = str(tier or "")
    if value.startswith(("mobile_id_", "modid_")):
        return "mock_verify_module_modid"
    if value.startswith("ganpyeon_injeung_"):
        return "mock_verify_ganpyeon_injeung"
    if value.startswith("simple_auth_module_"):
        return "mock_verify_module_simple_auth"
    if value.startswith(("kec_", "gongdong_injeungseo_")):
        return "mock_verify_module_kec"
    if value.startswith(("geumyung_module_", "geumyung_injeungseo_")):
        return "mock_verify_module_geumyung"
    if value.startswith("mydata_"):
        return "mock_verify_mydata"
    return None


def _required_scope_from_registration(registration: Any) -> str | None:
    """Read an adapter-declared required delegation scope, when present."""
    try:
        module = importlib.import_module(str(registration.module_path))
    except Exception:  # noqa: BLE001
        logger.debug("submit bridge: failed to import %s", registration.module_path)
        return None
    scope = getattr(module, "_REQUIRED_SCOPE", None)
    return scope if isinstance(scope, str) and scope else None


def _submit_to_govapitool(
    tool_id: str, registration: Any, input_model: type[BaseModel]
) -> GovAPITool:
    """Build a GovAPITool wrapper from a submit AdapterRegistration."""
    sh_ko = " ".join(registration.search_hint.get("ko", []))
    sh_en = " ".join(registration.search_hint.get("en", []))
    delegation_source = _delegation_source_from_published_tier(
        registration.published_tier_minimum
    )
    required_scope = _required_scope_from_registration(registration)
    verify_instruction = (
        f" Use verify(tool_id='{delegation_source}', params={{'scope_list': "
        f"['{required_scope}'], 'purpose_ko': '<citizen purpose>', "
        f"'purpose_en': '<English purpose>'}}) first."
        if delegation_source and required_scope
        else ""
    )
    return GovAPITool(
        id=tool_id,
        name_ko=tool_id.replace("mock_submit_module_", "").replace("_", " "),
        ministry="KOSMOS",
        category=["submit", "mock"],
        endpoint=f"internal://mock-submit/{tool_id}",
        auth_type=registration.auth_type,
        input_schema=input_model,
        output_schema=_OpaqueOutput,
        llm_description=(
            f"Submit primitive — {tool_id}. REQUIRES a DelegationContext from a prior "
            "verify call with matching scope. Pass the verify result's "
            "'delegation_context' in params; the backend also mirrors the latest "
            "DelegationContext when the model omits it. Never ask the citizen for "
            "raw session_id or identity numbers in chat. Fill only adapter-specific "
            "payload fields declared in this tool's input_schema; optional Mock "
            "fields may be omitted. For tax payment without explicit payment "
            "confirmation, use an action_type that creates a reminder rather than "
            "executing payment. On success: returns transaction_id (deterministic "
            "URN) + adapter_receipt with the agency's 접수번호."
            f"{verify_instruction}\n\n"
            "Failure modes: scope_violation / expired / session_violation / revoked / "
            "DelegationGrantMissing. Each failure surfaces a typed error; do NOT silently retry."
        ),
        search_hint=f"{sh_ko} {sh_en}",
        policy=registration.policy,
        is_concurrency_safe=registration.is_concurrency_safe,
        cache_ttl_seconds=registration.cache_ttl_seconds,
        rate_limit_per_minute=registration.rate_limit_per_minute,
        is_core=False,  # Discoverable via lookup search; NOT in primary LLM tool list
        primitive="submit",
        published_tier_minimum=registration.published_tier_minimum,
        nist_aal_hint=registration.nist_aal_hint,
        adapter_mode="mock",
        delegation_source_tool_id=delegation_source,
    )


def _subscribe_to_govapitool(tool_id: str, search_hint_str: str) -> GovAPITool:
    """Build a GovAPITool wrapper for a subscribe mock (registry has tool_id only)."""
    return GovAPITool(
        id=tool_id,
        name_ko=tool_id.replace("mock_", "").replace("_", " "),
        ministry="KOSMOS",
        category=["subscribe", "mock", "stream"],
        endpoint=f"internal://mock-subscribe/{tool_id}",
        auth_type="public",
        input_schema=_SubscribeParamsShell,
        output_schema=_OpaqueOutput,
        llm_description=(
            f"Subscribe primitive — {tool_id}. Opens a session-lifetime stream "
            "of events from the registered data source (CBS broadcast / REST-pull / RSS). "
            "Returns a SubscriptionHandle; subsequent events arrive as backend tool_result "
            "frames during the session."
        ),
        search_hint=search_hint_str,
        policy=AdapterRealDomainPolicy(
            real_classification_url="https://www.data.go.kr/policy/privacyPolicy.do",
            real_classification_text=(
                "공공데이터포털 개인정보처리방침 (KOSMOS subscribe mock — "
                "session-lifetime event stream; no persistent state)."
            ),
            citizen_facing_gate="read-only",
            last_verified=datetime(2026, 4, 30, tzinfo=UTC),
        ),
        is_concurrency_safe=True,
        cache_ttl_seconds=0,
        rate_limit_per_minute=30,
        is_core=False,
        primitive="subscribe",
        adapter_mode="mock",
    )


# Subscribe search hints — hardcoded since the per-tool registry doesn't carry them.
_SUBSCRIBE_HINTS: dict[str, str] = {
    "mock_cbs_disaster_v1": (
        "재난방송 CBS 긴급재난문자 cell broadcast disaster alert "
        "폭염 미세먼지 정전 단수 재난 알림 부모님 지역 위험 확인 "
        "emergency flood heatwave fine dust outage water shutdown safety "
        "case status relief temporary housing inspection road risk weather "
        "3GPP TS 23.041 subscribe 구독 알림 추적 상태 기한"
    ),
    "mock_rest_pull_tick_v1": (
        "REST-pull 폴링 polling 데이터고닷케이알 data.go.kr periodic subscribe 구독 "
        "민원 처리상태 신청 결과 납부기한 갱신기한 예약기한 제출기한 "
        "복지 심사 장학금 서류 고용센터 이민 체류기간 응급실 야간진료 병원 보험 "
        "deadline status tracker"
    ),
    "mock_rss_public_notices_v1": (
        "RSS 공공 공지 정부 announcement notice government subscribe 구독 "
        "정부24 홈택스 위택스 워크넷 장학금 고용 복지 세금 민원 공지 "
        "due date reminder alert follow-up milestone deadline notice"
    ),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def bridge_per_primitive_registries(registry: ToolRegistry) -> int:
    """Bridge verify/submit/subscribe mock adapters into the main ToolRegistry.

    Idempotent — already-registered tool_ids are skipped (logged at DEBUG).
    Must be called AFTER ``import kosmos.tools.mock`` so all per-primitive
    registries are populated.

    Returns the number of newly-registered tools.
    """
    return _bridge_verify(registry) + _bridge_submit(registry) + _bridge_subscribe(registry)


def _bridge_verify(registry: ToolRegistry) -> int:
    count = 0
    for entry in _VERIFY_FAMILIES:
        if entry["tool_id"] in registry._tools:  # noqa: SLF001
            continue
        try:
            registry.register(_verify_to_govapitool(entry))
            count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "discovery_bridge: failed to register verify %s: %s",
                entry["tool_id"],
                exc,
            )
    return count


def _bridge_submit(registry: ToolRegistry) -> int:
    try:
        from kosmos.primitives.submit import _ADAPTER_REGISTRY as _SUBMIT_REG_LOCAL
    except ImportError:
        return 0

    count = 0
    for tool_id, payload in _SUBMIT_REG_LOCAL.items():
        if tool_id in registry._tools:  # noqa: SLF001
            continue
        registration = payload[0] if isinstance(payload, tuple) else payload
        try:
            module_name, model_name = registration.input_model_ref.rsplit(".", 1)
            module = importlib.import_module(module_name)
            input_model = getattr(module, model_name)
            registry.register(_submit_to_govapitool(tool_id, registration, input_model))
            count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "discovery_bridge: failed to register submit %s: %s",
                tool_id,
                exc,
            )
    return count


def _bridge_subscribe(registry: ToolRegistry) -> int:
    try:
        from kosmos.primitives.subscribe import (
            _SUBSCRIBE_ADAPTERS as _SUBSCRIBE_REG_LOCAL,
        )
    except ImportError:
        return 0

    count = 0
    for tool_id in _SUBSCRIBE_REG_LOCAL:
        if tool_id in registry._tools:  # noqa: SLF001
            continue
        search_hint = _SUBSCRIBE_HINTS.get(tool_id, f"{tool_id} subscribe stream")
        try:
            registry.register(_subscribe_to_govapitool(tool_id, search_hint))
            count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "discovery_bridge: failed to register subscribe %s: %s",
                tool_id,
                exc,
            )
    return count


__all__ = [
    "_VERIFY_FAMILIES",
    "_VerifyParamsShell",
    "_SubscribeParamsShell",
    "_OpaqueOutput",
    "bridge_per_primitive_registries",
]
