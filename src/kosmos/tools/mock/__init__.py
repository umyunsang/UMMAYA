"""Mock adapter tree for Spec 031 Five-Primitive Harness.

Six mock system sub-packages (byte- or shape-mirror-able public systems):
- data_go_kr: openapi.data.go.kr REST surface (byte mirror)
- omnione: OpenDID reference stack (byte mirror, Apache-2.0)
- barocert: developers.barocert.com SDK docs (shape mirror)
- mydata: KFTC MyData v240930 (shape mirror, mTLS/OAuth profile)
- npki_crypto: PyPinkSign crypto layer (PKCS#7/#12 only; portal session is OPAQUE)
- cbs: 3GPP TS 23.041 broadcast (byte mirror)

OPAQUE internals (KEC XML signature, NPKI portal session handshake, and private
Government24 live submit schemas) stay scenario-only unless a mock mirrors a
publicly documented workflow boundary and keeps the private endpoint shape
declared as inferred.

Spec 031 US1 submit adapters (T027) — registered with kosmos.primitives.submit
on import:
- data_go_kr.fines_pay
- mydata.welfare_application

Spec 031 US2 verify adapters (T043) — one per family, registered on import:
- verify_gongdong_injeungseo: 공동인증서 / KOSCOM Joint Certificate
- verify_geumyung_injeungseo: 금융인증서 / Financial Certificate (KFTC)
- verify_ganpyeon_injeung: 간편인증 — Kakao/Naver/Toss/PASS/etc.
- verify_mobile_id: 모바일 신분증 (mdl | resident)
- verify_mydata: 마이데이터 OAuth 2.0 + mTLS
NOTE: verify_digital_onepass DELETED — FR-004 (서비스 종료 2025-12-30).

Epic ε #2296 US1 new verify adapters — registered on import:
- verify_module_simple_auth: 간편인증 AX-channel (Japan マイナポータル API analog)
- verify_module_modid: 모바일ID AX-channel (EU EUDI Wallet analog)
- verify_module_kec: KEC 공동인증서 AX-channel (Singapore APEX analog)
- verify_module_geumyung: 금융인증서 AX-channel (Singapore Myinfo analog)
- verify_module_any_id_sso: Any-ID SSO — returns IdentityAssertion only (UK GOV.UK One Login analog)

Spec 031 US3 subscribe adapters (T058–T060) — registered with
kosmos.primitives.subscribe on import:
- cbs.disaster_feed.MOCK_CBS_DISASTER_TOOL (tool_id="mock_cbs_disaster_v1")
- data_go_kr.rest_pull_tick.MOCK_REST_PULL_TICK_TOOL (tool_id="mock_rest_pull_tick_v1")
- data_go_kr.rss_notices.MOCK_RSS_PUBLIC_NOTICES_TOOL (tool_id="mock_rss_public_notices_v1")
"""

# T027 (Spec 031) + Epic ε #2296 T026 — existing submit adapters (transparency-retrofitted).
# Import triggers self-registration in kosmos.primitives.submit._ADAPTER_REGISTRY.
# APPEND ONLY — do not remove or reorder existing entries.
import kosmos.tools.mock.data_go_kr.fines_pay  # noqa: F401, E402
import kosmos.tools.mock.koroad.driver_fitness_reservation  # noqa: F401, E402
import kosmos.tools.mock.mydata.welfare_application  # noqa: F401, E402

# Epic ε #2296 T023–T025 — new delegation-aware submit adapters.
# Import triggers self-registration; each enforces DelegationContext scope validation.
import kosmos.tools.mock.submit_module_gov24_minwon  # noqa: F401, E402
import kosmos.tools.mock.submit_module_hometax_taxreturn  # noqa: F401, E402
import kosmos.tools.mock.submit_module_public_mydata_action  # noqa: F401, E402

# T043 — US2 verify adapters (Spec 031). Import side-effect registers each family's
# adapter via register_verify_adapter(); imports are order-independent.
# NOTE: verify_digital_onepass was REMOVED — FR-004 (서비스 종료 2025-12-30).
# Epic ε #2296 — T016-T020 new verify adapters. Import side-effect registers
# each adapter's family via register_verify_adapter().
from kosmos.tools.mock import (  # noqa: F401, E402  # noqa: F401, E402
    verify_ganpyeon_injeung,
    verify_geumyung_injeungseo,
    verify_gongdong_injeungseo,
    verify_mobile_id,
    verify_module_any_id_sso,
    verify_module_geumyung,
    verify_module_kec,
    verify_module_modid,
    verify_module_simple_auth,
    verify_mydata,
)

# T058–T060 — US3 subscribe adapters. Import side-effect registers each
# tool via register_subscribe_adapter().
from kosmos.tools.mock.cbs.disaster_feed import MOCK_CBS_DISASTER_TOOL  # noqa: F401, E402
from kosmos.tools.mock.data_go_kr.rest_pull_tick import MOCK_REST_PULL_TICK_TOOL  # noqa: F401, E402
from kosmos.tools.mock.data_go_kr.rss_notices import (
    MOCK_RSS_PUBLIC_NOTICES_TOOL,  # noqa: F401, E402
)
