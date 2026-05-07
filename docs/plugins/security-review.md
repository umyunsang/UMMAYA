# Security Review · PIPA §26 Trustee Acknowledgment · L3 Gate

> 본 문서는 UMMAYA 플러그인이 PII 를 처리할 때 따라야 하는 「개인정보 보호법」 제26조 수탁자 의무와
> Layer 2+ / Layer 3 어댑터의 보안 격리 가이드라인을 정의합니다.
>
> 참고: [Migration tree § B8](../requirements/ummaya-migration-tree.md), [Spec 033 permission v2](../../specs/033-permission-v2-spectrum/spec.md), [Memory `project_pipa_role`](../../specs/1636-plugin-dx-5tier/research.md), [contracts/pipa-acknowledgment.md](../../specs/1636-plugin-dx-5tier/contracts/pipa-acknowledgment.md), [Spec 1636 manifest_schema._v_pipa_hash](../../src/ummaya/plugins/manifest_schema.py).

## Current canonical SHA-256

| | |
|---|---|
| Hash | `1f37e43eda5dd3291ca18a5ff68e7acbc42d6d08dc31dd2c6b3705311c1079ef` |
| Source-of-truth | 본 문서의 `<!-- CANONICAL-PIPA-ACK-START -->` ↔ `<!-- CANONICAL-PIPA-ACK-END -->` 사이 텍스트 |
| 산출 모듈 | [`src/ummaya/plugins/canonical_acknowledgment.py`](../../src/ummaya/plugins/canonical_acknowledgment.py) (`CANONICAL_ACKNOWLEDGMENT_SHA256`) |
| 정규화 | UTF-8 + CRLF→LF + 양끝 whitespace strip 후 SHA-256 |
| 길이 | 540자 (BMP 한글 + ASCII 혼용) |

플러그인의 `manifest.yaml` 의 `pipa_trustee_acknowledgment.acknowledgment_sha256` 은 위 hash 와 byte-equal 해야 합니다 (`PluginManifest._v_pipa_hash` validator). 다르면 **install 자체가 차단** 되며 50-item 검증 워크플로의 Q6-PIPA-HASH 가 실패합니다.

### Version history

| Version | Date | Hash | 변경 사유 |
|---|---|---|---|
| v1 | 2026-04-25 | `321d518f4bda3bf748352603131b6ca23eb3b37e4dc432ff25ac6e938378c0aa` | Spec 1636 P5 초안. 「개인정보 보호법」 제26조 + 시행령 제28조 의 수탁자 7대 의무 정문화. |
| v2 | 2026-05-08 | `1f37e43eda5dd3291ca18a5ff68e7acbc42d6d08dc31dd2c6b3705311c1079ef` | Project rename: KOSAX → UMMAYA in canonical acknowledgment text. |

> **변경 정책**: canonical 텍스트가 변경되면 hash 가 바뀌고 모든 기존 플러그인이 hash mismatch 로 거부됩니다. 변경은 다음 절차로만 허용:
> 1. 법무 검토 + UMMAYA 운영자 합의로 새 텍스트 확정.
> 2. 본 문서의 마커 사이 텍스트 + 위 history 표 갱신을 단일 PR 에 묶음.
> 3. PR 머지 후 모든 published plugin 이 새 hash 로 manifest 재발행 필요.
> 4. drift-audit workflow (#1926, deferred) 가 머지된 plugin 의 hash 를 일제 점검.

## Canonical PIPA §26 Trustee Acknowledgment Text

아래 마커 사이의 본문은 **수탁자 동의문 canonical text** 입니다.
플러그인 매니페스트의 `pipa_trustee_acknowledgment.acknowledgment_sha256` 필드는
이 텍스트의 SHA-256 (UTF-8 인코딩, `\n` 정규화, leading/trailing whitespace strip 후)
과 정확히 일치해야 합니다.

마커는 절대 변경하지 마십시오. 본문 변경 시 모든 기존 플러그인이 hash mismatch 로
거부됩니다 (drift-audit workflow 는 #1926 deferred).

<!-- CANONICAL-PIPA-ACK-START -->

본 플러그인의 기여 조직(이하 "수탁자")은 「개인정보 보호법」 제26조 및 같은 법
시행령 제28조에 따른 개인정보 처리 위탁의 수탁자로서 다음 의무를 인지하고
이행하기로 동의합니다.

1. 위탁업무의 목적과 범위 내에서만 개인정보를 처리합니다.
2. 위탁업무 처리 목적 달성에 필요한 최소한의 개인정보만을 수집·이용합니다.
3. 개인정보의 안전성 확보를 위한 기술적·관리적 조치를 이행합니다.
4. 재위탁(下수탁)은 UMMAYA 운영자(위탁자)의 사전 서면 동의 없이 수행하지 않습니다.
5. 개인정보의 처리 현황 및 안전성 확보 조치 이행 여부에 대한 UMMAYA 운영자의
   감독에 협조합니다.
6. 위탁업무 종료 시 개인정보를 지체 없이 파기하고 그 결과를 UMMAYA 운영자에게
   서면으로 통보합니다.
7. 본 의무를 위반하여 정보주체에게 손해가 발생한 경우 그 손해를 배상할 책임이
   있음을 확인합니다.

수탁자는 본 acknowledgment 의 SHA-256 해시값을 플러그인 manifest 에 기록함으로써
위 의무에 동의함을 표시합니다.

<!-- CANONICAL-PIPA-ACK-END -->

## Trustee Acknowledgment Procedure

`processes_pii: true` 인 어댑터는 **반드시** 다음 5단계를 따릅니다:

### 1단계 · Canonical 텍스트 정독

본 문서의 `<!-- CANONICAL-PIPA-ACK-START -->` ↔ `<!-- CANONICAL-PIPA-ACK-END -->` 사이 7개 의무 항목을 정독합니다. 본 의무는 「개인정보 보호법」 제26조 (개인정보의 처리 위탁) + 시행령 제28조 (위탁자의 관리·감독 의무) 에 근거합니다.

### 2단계 · canonical hash 재확인

Python 한 줄 또는 TUI 슬래시 커맨드 두 경로 중 하나를 사용합니다.

```bash
uv run python -c "
from ummaya.plugins import CANONICAL_ACKNOWLEDGMENT_SHA256
print(CANONICAL_ACKNOWLEDGMENT_SHA256)
"
# → 1f37e43eda5dd3291ca18a5ff68e7acbc42d6d08dc31dd2c6b3705311c1079ef
```

또는 TUI 에서 `/plugin pipa-text` 슬래시 커맨드 (canonical 본문 + hash 를 그대로 출력).
**수동으로 hash 를 복사하지 말고** 위 두 명령 중 하나의 출력을 사용하세요. 잘못 복사한
hash 는 install 시점 + PR 의 plugin-validation 워크플로 양쪽에서 차단됩니다.

### 3단계 · `manifest.yaml` 의 `pipa_trustee_acknowledgment` 블록 작성

```yaml
processes_pii: true
pipa_trustee_acknowledgment:
  trustee_org_name: "<수탁자 조직 법적 명칭, 예: 부산광역시청>"
  trustee_contact: "<연락처: 이메일 또는 대표 전화>"
  pii_fields_handled:
    - resident_registration_number   # 주민등록번호 — pipa_class=personal_unique_id
    - phone_number                   # 휴대전화번호 — pipa_class=personal_standard
  legal_basis: "「개인정보 보호법」 제15조 제1항 제2호"
  acknowledgment_sha256: "1f37e43eda5dd3291ca18a5ff68e7acbc42d6d08dc31dd2c6b3705311c1079ef"
```

규칙 (50-item 검증의 Q6 4 항목 + Spec 024 V2 가 enforce):
- **`trustee_org_name`** — 법적 명칭. 약어 / 단축형 금지. 예: "부산광역시" 가 아니라 "부산광역시청".
- **`trustee_contact`** — 정보주체 (시민) 가 연락 가능한 통로. 개인 이메일 ❌, 부서/팀 단위 대표 연락처 ✓.
- **`pii_fields_handled`** — UMMAYA 의 `pipa_class` 분류 (`personal_standard` / `personal_sensitive` / `personal_unique_id`) 와 정합하는 식별자 목록. 빈 배열 금지.
- **`legal_basis`** — PIPA 의 동의 근거 조항. 「개인정보 보호법」 제15조 (수집·이용) 또는 제17조 (제공) 또는 제18조 (목적 외 이용) + 해당 항/호 표기.
- **`acknowledgment_sha256`** — 본 문서 상단의 hash. 64자 lowercase hex.

> **`pipa_class` 두 enum 표기**: 위 예시의 `pipa_class: personal_standard` 는 `manifest.yaml` 의 `AdapterRegistration` enum 입니다. 같은 plugin 의 `adapter.py` 안에서 `GovAPITool(...)` 인스턴스를 만들 때는 별도의 단축 enum (`personal` / `sensitive` / `identifier`) 을 씁니다. 자세한 mapping 은 [`docs/plugins/permission-tier.md`](permission-tier.md) Layer 1 섹션의 "두 개의 `pipa_class` enum 표기" 박스를 참고.

### 4단계 · `dpa_reference` (Spec 024 V2)

`pipa_class != non_personal` 인 모든 어댑터는 `dpa_reference` (Data Processing Agreement 식별자) 가 manifest 에 명시되어야 합니다 (Q3-V2-DPA). 예:

```yaml
adapter:
  ...
  pipa_class: personal_standard
  dpa_reference: "DPA-busan-bts-2026-04"  # 자유 형식 식별자; 내부 추적용.
```

`non_personal` 인 경우 `dpa_reference: null` 허용.

### 5단계 · 50-item 워크플로 녹색 확인

```bash
# 외부 plugin repo 의 plugin-validation.yml 가 자동 실행.
# 로컬에서도 직접 가능:
uv run python scripts/render_checklist.py --check  # 매트릭스 drift 가드
```

Q6 4 항목 (PIPA-PRESENT / PIPA-HASH / PIPA-ORG / PIPA-FIELDS-LIST) 모두 ✓ 가 떠야 PR merge 가능.

---

## L3 Gate Procedure

`permission_layer: 3` (red) 어댑터는 **시민 동의 없이 호출 불가능** + **AAL2 이상 인증 필수**. Spec 033 permission gauntlet 가 enforce 하며 plugin 측은 다음을 추가로 준수:

### L3 정의

- 정부24 민원 제출 (`submit` primitive 가 irreversible)
- 신고 / 신청 / 결제 / 발급 등 **시민 행위가 외부 시스템 상태를 변경** 하는 모든 동작
- KEC 차량검사 결과 read-back, NPKI 본인인증 후 read-only 도 AAL2 정책상 L3.

### L3 manifest 요건

```yaml
adapter:
  ...
  is_irreversible: true
  auth_level: AAL2  # 또는 AAL3 (Q3-V4-IRREVERSIBLE-AAL)
  pipa_class: personal_standard  # 또는 더 강한 분류
  dpa_reference: "DPA-..."

permission_layer: 3
```

추가 invariant (Spec 024 V4): `is_irreversible: true ⇒ auth_level ≥ AAL2`. 위반 시 manifest 자체가 거부됩니다.

### L3 release gate

L3 어댑터는 단순 plugin-validation 외에 maintainer 의 보안 리뷰가 필수:
- `submit` primitive 가 호출하는 외부 endpoint 의 **idempotency key** 처리 검토.
- `transaction_id` 발산 (Spec 031) 을 통한 중복 제출 방어 검토.
- 실패 경로의 시민 통보 메시지 검토 (한국어 명확성).
- SLSA provenance 가 UMMAYA 운영자 + plugin 작성자 양쪽 서명을 가지는지 확인.

### L3 release-with-slsa 변경

기본 `release-with-slsa.yml` 외에 `slsa-framework/slsa-github-generator` 의 `provenance` step 을 거쳐 발산된 `.intoto.jsonl` 이 install 시점 `slsa-verifier` 통과해야 합니다. L3 어댑터는 이 verification 을 절대 skip 할 수 없으며 `UMMAYA_PLUGIN_SLSA_SKIP=1` 은 dev 모드에서도 L3 install 시 거부됩니다 (향후 enforcement 추가 예정 — 현재는 정책상 약속).

---

## L2+ Sandboxing Guidelines (FR-024)

`permission_layer ∈ {2, 3}` 어댑터의 실행 환경 격리 권장사항. UMMAYA host 가 install 시점에 강제하지는 않지만 (FR-024 deferred enforcement) 기여자가 **자발적으로** 다음 패턴을 따라야 추후 sandboxing 활성화 시 plugin 코드를 수정할 필요가 없습니다.

> ⚠️ **Adapter top-level code 권한 경고 (review eval H3)**: 현재 UMMAYA host 는 `register_plugin_adapter` 가 어댑터 모듈을 import 할 때 `spec.loader.exec_module(module)` 로 **UMMAYA process 권한** 으로 실행합니다. 이는 다음을 의미합니다:
> - 어댑터의 module-level (top-level) 코드는 V1-V6 invariant + permission gauntlet 적용 *전* 에 실행됩니다.
> - module-level 에서 `os.environ["UMMAYA_PERMISSION_KEY_PATH"]` 같은 secret 을 읽거나 `~/.ummaya/keys/ledger.key` 를 open 하는 것이 가능합니다.
>
> **기여자 가이드**: adapter.py 의 module-level 에는 *오직* schema import + 상수 정의 + GovAPITool 인스턴스 생성만 두십시오. 외부 I/O / subprocess / 환경변수 조회는 모두 `async def adapter(...)` 함수 본문 안에서 수행하세요. 본 issue 의 host-side mitigation (sandbox-exec / firejail / `--network=none` 컨테이너) 은 deferred enforcement 이며, 추후 강제 활성화 시 위 패턴을 따르지 않은 plugin 은 install 거부됩니다.

### macOS · `sandbox-exec`

```sh
# 어댑터 호출만을 위한 격리 sandbox profile.
sandbox-exec -p '
(version 1)
(deny default)
(allow file-read* (subpath "/usr/lib"))
(allow network-outbound (remote ip "<ALLOWED_HOST>:*"))
(deny network-outbound)  ; 그 외 모든 outbound 차단
' uv run pytest
```

원칙:
- **Outbound network 화이트리스트만 허용**. 어댑터의 `endpoint` URL 의 호스트만 통과.
- 파일시스템은 read-only + 어댑터 작업 디렉토리만 write.
- IPC / shared memory 차단.

### Linux · `firejail`

```sh
firejail \
  --net=none \
  --read-only=/usr \
  --private-tmp \
  --whitelist=/path/to/plugin \
  uv run pytest
```

> **참고**: `--net=none` 은 Live tier 어댑터의 happy-path 테스트가 fixture replay 만 사용함을 전제로 합니다 (Constitution §IV). 스캐폴드의 `tests/conftest.py` `block_network` fixture 가 IPv4/IPv6 socket 을 막아주기 때문에 추가 sandboxing 없이도 CI 가 안전.

### 컨테이너 · `--network=none`

CI workflow (`plugin-validation.yml`) 의 GitHub Actions runner 자체는 격리 컨테이너이며 추가로 `docker run --network=none` 으로 어댑터 코드를 실행하는 것이 가장 강한 격리입니다. T047 의 reusable workflow 가 향후 이 옵션을 지원할 예정 (현재 Phase 6 시점에서는 host runner 에서 직접 pytest 실행).

### 어댑터 코드 권장 패턴

L2+ 어댑터는 다음 추가 안전장치 적용:

```python
# adapter.py
import os
from urllib.parse import urlparse

_ALLOWED_HOST = urlparse(_ENDPOINT).netloc

def _check_url_safety(url: str) -> None:
    """Refuse to follow redirects to an unrelated host (SSRF defense)."""
    parsed = urlparse(url)
    if parsed.netloc != _ALLOWED_HOST:
        raise RuntimeError(
            f"refusing redirect to unrelated host: {parsed.netloc!r}"
        )

# httpx 호출 시 follow_redirects=False, 응답 검증
async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
    response = await client.get(url)
    response.raise_for_status()
```

핵심:
- **Redirect 추적 비활성화** + 명시적 host 검증 (SSRF 방어).
- **타임아웃 명시** — 무한 대기 차단.
- **응답 본문 사이즈 제한** — 거대 응답으로 메모리 고갈 방지 (`response.read()` 대신 `iter_bytes()` + length cap).

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 위탁자 | controller | UMMAYA 운영자. 시민에게 동의를 받고 처리 책임을 짐 (PIPA §15). |
| 수탁자 | trustee / processor | 플러그인 작성 조직. 위탁받은 범위 내에서만 PII 처리 (PIPA §26). |
| 동의문 | acknowledgment text | 본 문서의 마커 사이 canonical 텍스트. SHA-256 으로 무결성 검증. |
| 처리 위탁 | processing entrustment | PIPA §26 의 controller-trustee 체인. UMMAYA 의 기본 운영 모델. |
| 재위탁 | sub-entrustment | 수탁자가 다시 다른 조직에 처리를 맡기는 행위. 사전 서면 동의 필수. |
| 안전성 확보 조치 | safety measures | 기술적 (암호화, 접근통제) + 관리적 (인사보안, 교육) 조치 PIPA §29. |
| 권한 레이어 | permission layer | 1/2/3. Layer 3 은 irreversible + AAL2+ 필수. Spec 033. |
| Sandboxing | sandboxing | sandbox-exec / firejail / `--network=none` 컨테이너 등 OS 격리. |
| SLSA 증빙 | SLSA provenance | slsa-github-generator 산출 `.intoto.jsonl`. install 시 verify-artifact. |

---

## Reference

- 「개인정보 보호법」 제26조 (개인정보의 처리 위탁): https://www.law.go.kr/법령/개인정보보호법/제26조
- 「개인정보 보호법 시행령」 제28조 (위탁자의 관리·감독 의무): https://www.law.go.kr/법령/개인정보보호법시행령/제28조
- 「개인정보 보호법」 제29조 (안전조치의무): https://www.law.go.kr/법령/개인정보보호법/제29조
- Memory `project_pipa_role` — UMMAYA PIPA 기본 stance (수탁자 해석)
- [`specs/1636-plugin-dx-5tier/contracts/pipa-acknowledgment.md`](../../specs/1636-plugin-dx-5tier/contracts/pipa-acknowledgment.md) — canonical 텍스트 contract
- [`src/ummaya/plugins/canonical_acknowledgment.py`](../../src/ummaya/plugins/canonical_acknowledgment.py) — Python hash 산출 모듈
- [Spec 033 Permission v2 spectrum](../../specs/033-permission-v2-spectrum/spec.md) — Layer 1/2/3 enforcement
- [Spec 024 Tool Security V1-V4](../../specs/024-tool-security-v1/spec.md) — `pipa_class` / `dpa_reference` / V4 irreversible-AAL invariant
