# SPDX-License-Identifier: Apache-2.0
"""Discovery bridge — Epic ζ #2297 path B fix (live smoke 2026-04-30 follow-up).

The UMMAYA primitive design isolates verify / submit mock adapters
in per-primitive ``_ADAPTER_REGISTRY`` dicts (``ummaya.primitives.{verify,
submit}``). The main :class:`ummaya.tools.registry.ToolRegistry` and
its BM25 corpus only see lookup-class adapters, so when the LLM emits
``lookup(mode="search", query="종합소득세 신고")`` the search returns no
verify/submit candidates — the citizen-facing chain never starts.

This module bridges the per-primitive registries into the main ToolRegistry by
synthesising lightweight :class:`ummaya.tools.models.GovAPITool` wrappers for
each registered mock and registering them with ``is_core=False`` (so they
participate in BM25 search but do NOT appear in the LLM-visible primary tool
list — that surface stays as the active primitives + lookup-class Live adapters).

The wrapped tools surface (per :class:`AdapterCandidate`):
- input_schema (Pydantic) — the citizen-shape params model the LLM should fill
- search_hint (bilingual ko/en) — BM25 indexable keyword phrase
- llm_description — adapter usage prose
- policy URL — agency-cited classification URL

Called once from :func:`ummaya.tools.register_all.register_all_tools`
immediately after ``import ummaya.tools.mock`` so all per-primitive registries
are populated.
"""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, RootModel

from ummaya.tools.models import AdapterRealDomainPolicy, GovAPITool

if TYPE_CHECKING:
    from ummaya.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight params shell for check (LLM-facing input schema)
# ---------------------------------------------------------------------------


class _VerifyParamsShell(BaseModel):
    """LLM-facing check params — citizen-shape `{scope_list, purpose_ko, purpose_en}`."""

    model_config = ConfigDict(extra="allow")

    scope_list: list[str] = Field(
        default_factory=list,
        description=(
            "List of '<verb>:<adapter_family>.<action>' scope strings the "
            "downstream find/send calls will need. The check ceremony "
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


class _OpaqueOutput(RootModel[dict[str, Any]]):
    """Generic envelope wrapper for bridge-registered tools' outputs."""


# ---------------------------------------------------------------------------
# Verify family metadata table (hand-rolled — verify adapters register by family
# name into ummaya.primitives.verify._ADAPTER_REGISTRY without an
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
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/modid",
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
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/kec",
        "policy_authority": "https://www.kec.co.kr/",
    },
    {
        "tool_id": "mock_verify_module_geumyung",
        "family": "geumyung_module",
        "name_ko": "금융인증서 모듈 (AX-channel)",
        "search_hint_ko": ["금융인증서", "금융결제원", "신용정보", "마이데이터금융"],
        "search_hint_en": ["financial certificate", "KFTC", "credit info", "financial mydata"],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/geumyung",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_module_simple_auth",
        "family": "simple_auth_module",
        "name_ko": "간편인증 모듈 (AX-channel)",
        "search_hint_ko": [
            "간편인증",
            "PASS",
            "카카오인증",
            "네이버인증",
            "토스인증",
            "정부24",
            "민원",
            "주민등록등본",
            "발급",
        ],
        "search_hint_en": [
            "simple auth",
            "PASS",
            "Kakao",
            "Naver",
            "Toss",
            "gov24",
            "civil petition",
            "resident registration certificate",
            "issuance",
        ],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/simple",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_module_any_id_sso",
        "family": "any_id_sso",
        "name_ko": "Any-ID SSO",
        "search_hint_ko": ["통합SSO", "통합로그인", "Any-ID", "단일인증", "공공통합인증"],
        "search_hint_en": [
            "any id sso",
            "unified login",
            "single sign on",
            "public SSO",
            "government sso",
        ],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/sso",
        "policy_authority": "https://www.gov.kr/",
    },
    {
        "tool_id": "mock_verify_gongdong_injeungseo",
        "family": "gongdong_injeungseo",
        "name_ko": "공동인증서 (구 공인인증서)",
        "search_hint_ko": ["공동인증서", "공인인증서", "KOSCOM", "전자서명", "인증서로그인"],
        "search_hint_en": ["joint certificate", "KOSCOM", "digital signature", "PKI"],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/gongdong",
        "policy_authority": "https://www.rootca.or.kr/",
    },
    {
        "tool_id": "mock_verify_geumyung_injeungseo",
        "family": "geumyung_injeungseo",
        "name_ko": "금융인증서",
        "search_hint_ko": ["금융인증서", "금융결제원", "은행인증", "통장인증"],
        "search_hint_en": ["financial certificate", "KFTC", "bank authentication"],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/geumyung-injeungseo",
        "policy_authority": "https://www.kftc.or.kr/",
    },
    {
        "tool_id": "mock_verify_ganpyeon_injeung",
        "family": "ganpyeon_injeung",
        "name_ko": "간편인증 (PASS·카카오·네이버)",
        "search_hint_ko": [
            "간편인증 로그인 행정서비스 이용 권한 확인 본인확인 check:ganpyeon.identity",
            "간편인증",
            "PASS",
            "카카오",
            "네이버",
            "토스",
        ],
        "search_hint_en": ["simple auth", "PASS", "Kakao Pay", "Naver", "Toss"],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/ganpyeon",
        "policy_authority": "https://www.kftc.or.kr/",
        "scope_rules": (
            "Scope rule: simple-auth login uses exactly scope_list "
            "['check:ganpyeon.identity']; do not use Any-ID SSO, "
            "admin_service scopes, or submit scopes for identity-only 간편인증."
        ),
    },
    {
        "tool_id": "mock_verify_mobile_id",
        "family": "mobile_id",
        "name_ko": "모바일 신분증 (mDL)",
        "search_hint_ko": ["모바일 신분증", "모바일 운전면허증", "mDL", "ISO/IEC 18013-5"],
        "search_hint_en": ["mobile ID", "mobile DL", "mDL", "ISO/IEC 18013-5"],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/mobile-id",
        "policy_authority": "https://www.mobileid.go.kr/",
        "scope_rules": (
            "Scope rule: mobile ID identity verification uses exactly scope_list "
            "['check:mobile_id.identity']; do not invent find:identity.info "
            "or find:identity.verify scopes."
        ),
    },
    {
        "tool_id": "mock_verify_mydata",
        "family": "mydata",
        "name_ko": "마이데이터 (KFTC)",
        "search_hint_ko": [
            "복지신청 scope_list send:mydata.welfare_application 전용",
            "공공마이데이터 제공동의 scope_list send:public_mydata.action 전용",
            "find:mohw.welfare_eligibility_search 제외",
            "send:mock.welfare_application_submit_v1 금지",
            "마이데이터",
            "공공 마이데이터",
            "마이데이터 동의",
            "제공 동의",
            "동의 상태",
            "데이터이동권",
            "마이데이터 액션",
            "거래내역",
            "신용카드",
            "은행거래",
            "자산조회",
            "복지",
            "복지신청",
            "복지급여신청",
            "사회보장",
            "한부모가족",
            "한부모",
            "아동양육비",
        ],
        "search_hint_en": [
            "mydata",
            "public mydata",
            "mydata consent",
            "consent status",
            "data portability",
            "mydata action",
            "transaction history",
            "open banking",
            "credit info",
            "welfare",
            "welfare application",
            "benefit application",
            "social assistance",
        ],
        "endpoint": "https://api.gateway.ummaya.gov.kr/v1/verify/mydata",
        "policy_authority": "https://www.mydatacenter.or.kr:3441/",
        "scope_rules": (
            "Scope rule: for '마이데이터 제공 동의' or '동의 상태 확인하고 ... 제공 동의', "
            "use exactly scope_list ['send:public_mydata.action']; pure MyData "
            "authentication uses ['check:mydata.consent']; welfare application verify uses "
            "exactly ['send:mydata.welfare_application'] because MOHW eligibility lookup "
            "is public and already ran before verify; never include "
            "find:mohw.welfare_eligibility_search, send:mock.welfare_application_submit_v1, "
            "or find:mydata.public.consent; never invent find:mydata.public.consent."
        ),
    },
    {
        "tool_id": "live_verify_kb_identity",
        "family": "kb_identity",
        "name_ko": "KB국민인증서 본인확인",
        "search_hint_ko": [
            "KB국민인증서",
            "국민인증서",
            "KB 인증서",
            "KB스타뱅킹",
            "본인확인",
            "신원검증",
        ],
        "search_hint_en": [
            "KB certificate",
            "Kookmin certificate",
            "KB identity",
            "KB Star Banking",
            "identity verification",
        ],
        "endpoint": "https://stg-openapi.kbstar.com:8443/kbsign/api",
        "policy_authority": "https://cert.kbstar.com/quics?page=C112279",
        "category": ["check", "live", "identity"],
        "adapter_mode": "live",
        "rate_limit_per_minute": 10,
        "scope_rules": (
            "Scope rule: KB identity verification uses exactly scope_list "
            "['check:kb_identity.identity']. This live check returns only a sanitized "
            "AuthContext external_session_ref based on reqTxId/certTxId; do not expect "
            "a DelegationToken and do not persist CI, DI, name, birthdate, gender, "
            "nationality, or encrypted identity payloads."
        ),
        "llm_result_description": (
            "Returns a KbIdentityContext with provider='kb' and an opaque "
            "external_session_ref. It never returns raw identity attributes."
        ),
        "last_verified": datetime(2026, 5, 18, tzinfo=UTC),
    },
]


def _build_verify_search_hint(entry: dict[str, Any]) -> str:
    """Compose the BM25-indexable bilingual phrase from ko + en lists."""
    ko = " ".join(entry["search_hint_ko"])
    en = " ".join(entry["search_hint_en"])
    return f"{ko} {en} verify 인증 인증서 위임 delegation"


def _verify_to_govapitool(entry: dict[str, Any]) -> GovAPITool:
    """Build a GovAPITool wrapper for one check-family adapter."""
    scope_rules = str(entry.get("scope_rules", "")).strip()
    scope_clause = f"{scope_rules}\n\n" if scope_rules else ""
    auth_type = cast(Literal["public", "api_key", "oauth"], entry.get("auth_type", "api_key"))
    adapter_mode = cast(Literal["live", "mock"], entry.get("adapter_mode", "mock"))
    result_description = str(
        entry.get(
            "llm_result_description",
            "Returns the DelegationContext that downstream find/send calls pass via "
            "params['delegation_context'].",
        )
    )
    return GovAPITool(
        id=entry["tool_id"],
        name_ko=entry["name_ko"],
        ministry="UMMAYA",
        category=list(entry.get("category", ["check", "mock", "delegation"])),
        endpoint=entry["endpoint"],
        auth_type=auth_type,
        input_schema=_VerifyParamsShell,
        output_schema=_OpaqueOutput,
        llm_description=(
            "Use only through the core check primitive: "
            f"check(tool_id='{entry['tool_id']}', params={{...}}). "
            "Do not call this adapter through find.\n\n"
            f"{scope_clause}"
            f"Verify ceremony for {entry['name_ko']}. Binds the result to the citizen's "
            "session and requested scope_list. Providers that support delegation issue "
            f"a DelegationToken; identity-only providers return a sanitized AuthContext. "
            f"{result_description}\n\n"
            "Citizen-shape input: {tool_id, params={scope_list, purpose_ko, purpose_en}}. "
            "The check primitive translates this to the dispatcher's family_hint via "
            "adapter metadata, not via the system prompt."
        ),
        search_hint=_build_verify_search_hint(entry),
        policy=AdapterRealDomainPolicy(
            real_classification_url=entry["policy_authority"],
            real_classification_text=(
                f"{entry['name_ko']} — agency-published policy citation "
                "(UMMAYA does not invent permission classifications; "
                "see AGENTS.md § Hard rules)."
            ),
            citizen_facing_gate="login",
            last_verified=entry.get("last_verified", datetime(2026, 4, 30, tzinfo=UTC)),
        ),
        is_concurrency_safe=False,
        cache_ttl_seconds=0,
        rate_limit_per_minute=int(entry.get("rate_limit_per_minute", 30)),
        is_core=False,  # Discoverable via lookup search; NOT in primary LLM tool list
        primitive="check",
        adapter_mode=adapter_mode,
    )


# ---------------------------------------------------------------------------
# Submit — read AdapterRegistration from the per-primitive registry
# ---------------------------------------------------------------------------


def _submit_to_govapitool(
    tool_id: str, registration: Any, input_model: type[BaseModel]
) -> GovAPITool:
    """Build a GovAPITool wrapper from a submit AdapterRegistration."""
    sh_ko = " ".join(registration.search_hint.get("ko", []))
    sh_en = " ".join(registration.search_hint.get("en", []))
    return GovAPITool(
        id=tool_id,
        name_ko=tool_id.replace("mock_submit_module_", "").replace("_", " "),
        ministry="UMMAYA",
        category=["send", "mock"],
        endpoint=f"internal://mock-submit/{tool_id}",
        auth_type=registration.auth_type,
        input_schema=input_model,
        output_schema=_OpaqueOutput,
        llm_description=(
            f"send primitive — {tool_id}. REQUIRES a DelegationContext from a prior "
            "check call with matching scope. params MUST include 'delegation_context' "
            "(returned by check) plus the adapter-specific payload defined in this "
            "tool's input_schema. On success: returns transaction_id (deterministic URN) "
            "+ adapter_receipt with the agency's 접수번호.\n\n"
            "Failure modes: scope_violation / expired / session_violation / revoked / "
            "DelegationGrantMissing. Each failure surfaces a typed error; do NOT silently retry."
        ),
        search_hint=f"{sh_ko} {sh_en} submit 제출 신고 민원",
        policy=registration.policy,
        is_concurrency_safe=registration.is_concurrency_safe,
        cache_ttl_seconds=registration.cache_ttl_seconds,
        rate_limit_per_minute=registration.rate_limit_per_minute,
        is_core=False,  # Discoverable via lookup search; NOT in primary LLM tool list
        primitive="send",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def bridge_per_primitive_registries(registry: ToolRegistry) -> int:
    """Bridge verify/submit mock adapters into the main ToolRegistry.

    Idempotent — already-registered tool_ids are skipped (logged at DEBUG).
    Must be called AFTER ``import ummaya.tools.mock`` so all per-primitive
    registries are populated.

    Returns the number of newly-registered tools.
    """
    return _bridge_verify(registry) + _bridge_submit(registry)


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
        from ummaya.primitives.submit import _ADAPTER_REGISTRY as _SUBMIT_REG_LOCAL
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


__all__ = [
    "_VERIFY_FAMILIES",
    "_VerifyParamsShell",
    "_OpaqueOutput",
    "bridge_per_primitive_registries",
]
