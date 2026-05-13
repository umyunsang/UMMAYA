# Permission Layer 1/2/3 결정 트리

> 새 어댑터를 작성할 때 `permission_layer` 를 1/2/3 중 어느 값으로 설정할지 결정하는 가이드. Spec 033 Permission v2 spectrum 이 enforce 하는 시민 동의 강도를 어댑터 작성 시점에 정확히 매핑합니다.
>
> 참고: [Spec 033 Permission v2 Spectrum](../../specs/033-permission-v2-spectrum/spec.md), [Migration tree § UI-C](../requirements/ummaya-migration-tree.md), [docs/plugins/security-review.md](security-review.md) (Layer 3 + PIPA), [Spec 024 V4 irreversible-AAL invariant](../../specs/024-tool-security-v1/spec.md).

---

## TL;DR — 결정 트리

```
질문 1: 어댑터가 외부 시스템 상태를 변경하는가? (제출/신청/결제/발급)
├─ 예 → Layer 3 (red), is_irreversible=True, auth_level ≥ AAL2
└─ 아니오 → 질문 2

질문 2: 응답에 PII (개인정보) 가 포함되는가?
├─ 예 → Layer 2 (orange), processes_pii=True, PIPA §26 trustee acknowledgment
└─ 아니오 → Layer 1 (green), processes_pii=False
```

---

## 3-Layer 정의

### Layer 1 (green) — Public read-only

**언제 사용**: 시민 동의 없이 호출 가능한 공공 데이터.

**예시**:
- KOROAD 사고 다발 지역 (위치 + 통계)
- KMA 일기예보 (격자 좌표 + 예보값)
- HIRA 병원 검색 (좌표 + 반경)
- 서울 지하철 도착 정보 (역 이름)
- 우체국 등기 추적 (등기번호 + 마스킹된 발/수신자)

**매니페스트**:
```yaml
permission_layer: 1
processes_pii: false
adapter:
  ...
  is_personal_data: false
  pipa_class: non_personal
  is_irreversible: false
  auth_level: AAL1   # 또는 public
  dpa_reference: null
```

**Spec 033 동작**: 동의 프롬프트 없이 즉시 호출. 시민이 결과만 확인.

> **두 개의 `pipa_class` enum 표기**: `manifest.yaml` 의 `adapter.pipa_class` 는 `AdapterRegistration` enum (`non_personal` / `personal_standard` / `personal_sensitive` / `personal_unique_id`) 을 사용합니다. 한편 `adapter.py` 안에서 `GovAPITool(...)` 를 직접 생성할 때는 `GovAPITool.pipa_class` enum (`non_personal` / `personal` / `sensitive` / `identifier`) 을 사용합니다. 두 enum 의 매핑:
>
> | manifest.yaml (AdapterRegistration) | adapter.py (GovAPITool) |
> |---|---|
> | `non_personal` | `non_personal` |
> | `personal_standard` | `personal` |
> | `personal_sensitive` | `sensitive` |
> | `personal_unique_id` | `identifier` |
>
> Default scaffold (`ummaya plugin init`) 는 양쪽 모두 `non_personal` 을 emit 하므로 처음 시작할 때는 신경 쓸 필요 없습니다. PII 처리로 전환할 때만 두 곳을 함께 갱신하세요.

---

### Layer 2 (orange) — Citizen-scoped, consent required

**언제 사용**: 응답에 시민의 개인정보가 포함되는 read-only 어댑터. 처리는 read-only 라도 PIPA §15 (개인정보 수집·이용) 에 따른 동의가 필요.

**예시**:
- 본인 세무 자료 (홈택스 연말정산 간소화)
- 본인 건강검진 결과 (NHIS)
- 본인 자동차 등록 정보 (국토부 자동차 365)
- 본인 민원 처리 상태 조회 (정부24)

**매니페스트**:
```yaml
permission_layer: 2
processes_pii: true
pipa_trustee_acknowledgment:
  trustee_org_name: "<수탁자 조직명>"
  trustee_contact: "<연락처>"
  pii_fields_handled: [...]
  legal_basis: "「개인정보 보호법」 제15조 제1항 제2호"
  acknowledgment_sha256: "<canonical hash>"
adapter:
  ...
  is_personal_data: true
  pipa_class: personal_standard   # 또는 personal_sensitive (의료/유전 등 §23)
  is_irreversible: false
  auth_level: AAL2                # 본인인증 필수
  dpa_reference: "DPA-..."
```

**Spec 033 동작**: 호출 직전 시민에게 동의 모달 표시 — `[Y 한번만 / A 세션 자동 / N 거부]`. `A` 선택 시 같은 어댑터의 후속 호출은 자동 통과 (세션 종료 시 만료).

---

### Layer 3 (red) — Irreversible action

**언제 사용**: 어댑터 호출이 외부 시스템의 상태를 변경하는 모든 경우. 재호출로 되돌릴 수 없는 행위.

**예시**:
- 정부24 민원 제출 (`send` primitive)
- KEC 차량 검사 결과 발급 + 결제
- NPKI 본인인증 후 read-back
- 신고 / 신청 / 발급 / 결제 / 송금 등 모든 시민 행위

**매니페스트**:
```yaml
permission_layer: 3
processes_pii: true
pipa_trustee_acknowledgment:
  ...
adapter:
  ...
  is_personal_data: true
  pipa_class: personal_standard   # 또는 더 강한 분류
  is_irreversible: true            # ← Q3-V4-IRREVERSIBLE-AAL 가 검증
  auth_level: AAL2                 # 또는 AAL3
  dpa_reference: "DPA-..."
```

**Spec 033 동작**: 시민 동의 모달이 더 강한 경고 (red 색 + 명시적 행위 설명) 와 함께 표시. `A 세션 자동` 옵션이 비활성 — 매 호출마다 명시적 동의 필요.

**Spec 024 V4 invariant**: `is_irreversible=True` 어댑터는 반드시 `auth_level ≥ AAL2`. AAL1 (digital_onepass_level1 등) 으로는 등록 자체 거부.

**release gate**: Layer 3 어댑터는 `plugin-validation.yml` 외에 maintainer 의 보안 리뷰 필수 (`docs/plugins/security-review.md` § L3 Gate Procedure).

---

## 매핑 표 — 데이터 종류 ↔ Layer

| 데이터 종류 | Layer | 이유 |
|---|---|---|
| 일기예보 / 미세먼지 / 재난경보 | 1 | 공공 read-only |
| 병원 / 약국 / 응급실 위치 | 1 | 공공 read-only |
| 도로 / 교통 / 사고 통계 | 1 | 공공 read-only |
| 우편 등기 추적 (마스킹) | 1 | 마스킹된 발/수신자만 |
| 주소 → 행정구역 코드 | 1 | host built-in (resolve_location) |
| 본인 세무 자료 | 2 | 본인 PII read |
| 본인 건강검진 / 의료기록 | 2 | 민감정보 (PIPA §23) |
| 본인 자동차 / 부동산 등록 | 2 | 본인 식별정보 |
| 본인 민원 처리 상태 | 2 | 본인 행정정보 |
| 정부24 민원 제출 | 3 | 외부 상태 변경 |
| 결제 / 송금 / 환급 | 3 | 금융 거래 |
| 본인인증 후 발급 (KEC) | 3 | irreversible 발급 |
| 신고 / 신청 / 등록 | 3 | 외부 상태 변경 |

---

## 흔한 오해

### ❌ "본인 데이터 read-only 라 Layer 1"

```yaml
permission_layer: 1
processes_pii: true   # 본인 PII 처리
```

→ Q5-LAYER-MATCHES-PII fail. PII 를 처리하면 최소 Layer 2.

### ❌ "send 인데 Layer 2"

```yaml
permission_layer: 2
adapter:
  is_irreversible: true
```

→ 작동하지만 시민 안전 약화. send + irreversible = Layer 3 가 정답.

### ❌ "AAL1 이지만 is_irreversible 합리화"

```yaml
adapter:
  auth_level: AAL1
  is_irreversible: true
```

→ Spec 024 V4 가 거부. `is_irreversible=True ⇒ auth_level ≥ AAL2`. AdapterRegistration 검증 시점에 차단.

---

## Layer 변경 시 SemVer

```
0.x.y → 1.0.0   # Layer 1 → Layer 2 (PII read 추가, 동의 필수로 강화)
1.x.y → 2.0.0   # Layer 2 → Layer 3 (irreversible 추가, AAL2+ 강제)
1.x.y → 1.x.y+1 # 같은 Layer 내 minor / patch — backward-compatible
```

Layer 다운그레이드 (3 → 2 → 1) 는 contract change — major bump. 기존 시민의 신뢰 모델 (어댑터의 위험도) 이 변하기 때문.

---

## 권한 ↔ 색상 ↔ icon (UI 표준)

Migration tree § UI-C:

| Layer | 색 | Icon | TUI 모달 톤 |
|---|---|---|---|
| 1 | green ⓵ | ✓ | 정보성 (자동 통과) |
| 2 | orange ⓶ | ⚠ | 동의 요청 (한번만 / 세션) |
| 3 | red ⓷ | 🔴 | 강한 경고 (매번 명시적 동의) |

Plugin 작성자는 매니페스트의 `permission_layer` 값만 설정하면 TUI 가 위 표시를 자동으로 적용합니다.

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 권한 레이어 | permission layer | 1/2/3 — 시민 동의 강도. Spec 033 enforce. |
| Read-only | read-only | 외부 시스템 상태 미변경. Layer 1 또는 2. |
| Irreversible | irreversible | 외부 상태 변경 후 되돌릴 수 없음. Layer 3 + AAL2+ 필수. |
| AAL | AAL | NIST SP 800-63 Authenticator Assurance Level. AAL1 → AAL2 → AAL3. |
| 동의 모달 | consent modal | TUI 의 [Y/A/N] 프롬프트. Spec 033 + Migration tree § UI-C. |
| 동의 영수증 | consent receipt | 동의 후 ledger 에 기록되는 JSON. Spec 035. |
| 민감정보 | sensitive PII | 의료 / 유전 / 사상 등 PIPA §23. `pipa_class: personal_sensitive`. |
| 고유식별정보 | unique-id PII | 주민등록번호 등 PIPA §24. `pipa_class: personal_unique_id`. |
| Fail-closed | fail-closed | 의심스러우면 거부. Layer 가 모호하면 더 높은 값 선택. |

---

## Reference

- [Spec 033 Permission v2 Spectrum](../../specs/033-permission-v2-spectrum/spec.md) — Layer 1/2/3 enforcement gauntlet
- [Spec 024 V4 invariant](../../specs/024-tool-security-v1/spec.md) — `is_irreversible ⇒ auth_level ≥ AAL2`
- [Migration tree § UI-C](../requirements/ummaya-migration-tree.md) — UI 색상 + icon 표준
- [docs/plugins/security-review.md § L3 Gate Procedure](security-review.md) — Layer 3 release 절차
- [50-item Q5 그룹](review-checklist.md#q5--permission-tier-3) — Q5-LAYER-DECLARED / Q5-LAYER-MATCHES-PII / Q5-LAYER-DOC
