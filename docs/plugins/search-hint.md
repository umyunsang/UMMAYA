# Ko/En Bilingual Search Hint 작성 가이드

> 플러그인의 `search_hint_ko` + `search_hint_en` 은 BM25 검색 (Spec 022) 인덱스에 직접 들어갑니다. 잘 작성된 hint 는 시민이 한국어로 자연스럽게 묻는 질문에 LLM 이 정확히 어댑터를 호출하게 만드는 첫 번째 신호입니다.
>
> 참고: [Spec 022 BM25 retrieval](../../specs/022-mvp-main-tool/spec.md), [Spec 1636 plugin DX](../../specs/1636-plugin-dx-5tier/spec.md), [docs/plugins/review-checklist.md](review-checklist.md) Q4 (8 항목).

---

## 왜 두 언어인가?

UMMAYA 의 시민은 **한국어로 질문** 하지만 LLM 의 토큰 분포는 양방향 — 영문 키워드도 함께 들어가야 BM25 의 IDF 분포가 안정적이고 검색 recall 이 높아집니다.

| 언어 | 용도 | 예시 |
|---|---|---|
| `search_hint_ko` | 시민의 자연어 질의 매칭 | `서울 지하철 도착 정보 실시간 호선 환승 강남` |
| `search_hint_en` | 영문 키워드 fallback + 알파벳 검색 보조 | `Seoul subway realtime arrival station line transfer` |

---

## Q4 5개 검사 항목

50-item 검증 워크플로의 Q4 그룹은 hint 품질을 5가지 차원으로 enforce:

| ID | 의미 | 검증 |
|---|---|---|
| Q4-HINT-KO | `search_hint_ko` 비어 있지 않음 | string length |
| Q4-HINT-EN | `search_hint_en` 비어 있지 않음 | string length |
| Q4-HINT-NOUNS | `search_hint_ko` 한국어 명사 ≥ 3 | Kiwipiepy tokenizer (Spec 022) |
| Q4-HINT-MINISTRY | `search_hint_ko` 에 부처/기관/지자체 이름 | substring match |
| Q4-NAME-KO | 한국어 문자 포함 | regex `[가-힣]` |

---

## 작성 패턴

### 1. 부처/기관 + 데이터 종류 + 시민 행위

```yaml
search_hint_ko: "도로교통공단 사고 다발 지역 검색 통계 행정구역 adm_cd"
search_hint_en: "KOROAD accident hotspot search statistics administrative area"
```

3-요소 구조:
- **누가** (부처/기관) — `도로교통공단` (Q4-HINT-MINISTRY 통과)
- **무엇** (데이터 종류) — `사고 다발 지역`, `통계`
- **어떻게** (시민 행위) — `검색`, `조회`

### 2. 명사 ≥ 3개 (Q4-HINT-NOUNS)

Kiwipiepy 가 한국어 형태소 분석으로 명사를 추출합니다. 다음 형태가 명사로 인식:

| ✓ 명사 인식 | ✗ 명사 미인식 |
|---|---|
| `사고`, `다발`, `지역`, `통계` | `~의`, `~를`, `~이다`, 조사 |
| `도로교통공단`, `행정구역` (복합어) | `~ㅂ니다`, 동사형 |
| `KOROAD` (외래어/약어) | `매우`, `정말` 등 부사 |

3개 이상 — 4-7개 권장. 너무 많으면 BM25 IDF 가 평준화되어 ranking 손실.

### 3. 부처/기관 이름 강제 (Q4-HINT-MINISTRY)

UMMAYA 의 ministry 화이트리스트 (`q4_discovery.py:_MINISTRY_NAMES_KO`):
- 도로교통공단, 기상청, 국립중앙의료원, 건강보험심사평가원, 소방청
- 보건복지부, 국토교통부, 행정안전부, 한국교통안전공단
- 식품의약품안전처, 정부24, 우정사업본부, 우체국
- 통계청, 국세청, 한국전력, 교육부, 여성가족부
- 법무부, 환경부, 국방부, 외교부
- `서울`, `부산`, `공공` (지자체 + 일반 fallback)

이 중 1개 이상이 `search_hint_ko` 에 포함되어야 합니다. 본인의 어댑터가 위 목록에 없는 부처라면:
1. 가장 가까운 상위 부처를 추가 (예: `여성가족부 산하 청소년상담복지센터` → `여성가족부` 포함).
2. 또는 일반 fallback `공공` 추가.
3. 또는 화이트리스트 확장 PR 제출 (`docs/plugins/data-go-kr.md` § 6 부처별 특수 사항 참고).

---

## 영어 hint 작성

영어는 BM25 의 보조 신호 — 한국어만큼 까다롭게 작성할 필요 없지만 명확한 글로스 권장:

```yaml
# ✓ 좋음
search_hint_en: "Seoul subway realtime arrival station line transfer metro"

# ⚠ 너무 짧음 — 검색 recall 저하
search_hint_en: "Seoul subway"

# ✗ 한국어 그대로
search_hint_en: "서울 지하철"  # search_hint_en 의 목적 무시
```

---

## 실제 예시 비교

### 좋은 예 — `seoul_subway`

```yaml
search_hint_ko: "서울 지하철 도착 정보 실시간 호선 환승 station 운행 metro"
search_hint_en: "Seoul subway realtime arrival station line metro transfer"
```

- ✓ `서울` (지자체) — Q4-HINT-MINISTRY
- ✓ 명사 7개 — Q4-HINT-NOUNS
- ✓ 영어 글로스 충분 — Q4-HINT-EN
- ✓ 한국어 + 영어 키워드 mix → 시민의 자연어 + 코드 키워드 모두 매칭

### 나쁜 예 — 너무 짧음

```yaml
search_hint_ko: "지하철"
search_hint_en: "subway"
```

- ✗ Q4-HINT-NOUNS 실패 (1개)
- ✗ Q4-HINT-MINISTRY 실패 (어떤 지하철?)
- 검색에서 `서울 지하철 도착` 질의에 다른 어댑터가 더 높은 score 받을 수 있음

### 나쁜 예 — 부처 누락

```yaml
search_hint_ko: "사고 다발 지역 검색 통계"
```

- ✗ Q4-HINT-MINISTRY 실패 (도로교통공단? 안전보건공단? 서울시?)
- 시민이 "교통사고" 라고 묻거나 "범죄율" 이라고 묻거나 식별 불가능

---

## Korean morphology 디버깅

명사 카운트가 의외의 결과면 다음으로 직접 확인:

```bash
uv run python -c "
from kiwipiepy import Kiwi
text = '도로교통공단 사고 다발 지역 검색 통계 adm_cd'
nouns = [tok.form for tok in Kiwi().tokenize(text) if tok.tag.startswith('N')]
print(nouns)
"
```

기대 출력: `['도로교통공단', '사고', '다발', '지역', '검색', '통계', 'adm', 'cd']` (8개).

> **참고**: `adm_cd` 같은 식별자는 underscore 가 토크나이저에 의해 분리되어 두 개 명사로 카운트됩니다. 식별자 형태의 토큰을 hint 에 넣을 때는 **추가 명사 수** 를 의식하지 마세요 — Q4-HINT-NOUNS 는 ≥ 3 인지만 봅니다.

---

## hint 와 BM25 검색 ranking

Spec 022 의 BM25 는 다음 weights:
- term frequency (TF) — 한 hint 에 같은 단어 여러 번 = 중복은 score 약간 증가
- inverse document frequency (IDF) — 모든 어댑터에 흔한 단어는 weight 낮음
- 길이 정규화 — 너무 긴 hint 는 score 낮아짐

**실용 규칙**:
- 5-15개 명사 권장.
- 같은 단어 반복 자제 (`서울 서울 지하철 지하철` ✗).
- 부처 이름은 **1번** 이면 충분.
- 시민 행위 (`검색`, `조회`, `추천`) 은 모든 어댑터에 흔하므로 IDF 낮음 — 위 카운트에 포함하지 말 것.

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 검색 힌트 | search hint | BM25 인덱스에 등록되는 한국어/영어 토큰. |
| 형태소 분석 | morphology / tokenization | Kiwipiepy 가 한국어 명사 / 동사 / 조사 분리. |
| 부처 화이트리스트 | ministry whitelist | Q4-HINT-MINISTRY 가 매칭하는 부처/기관 이름 목록. |
| 인덱스 | index | BM25 가 검색 대상으로 보유하는 모든 hint 의 토큰 분포. |
| 색인 재구성 | reindex | 새 plugin 등록 시 ToolRegistry.register 가 자동 수행. |
| 명사 카운트 | noun count | Kiwipiepy 의 N\* 태그 토큰 수. Q4-HINT-NOUNS 임계 3. |
| TF / IDF | TF / IDF | term-frequency × inverse-document-frequency BM25 weight. |
| 영어 글로스 | English gloss | 한국어 hint 의 보조 영어 키워드. |
| 시민 행위 | citizen verb | `조회`, `검색`, `추천` 같은 시민의 동작 단어 — 보통 모든 hint 에 공통. |

---

## Reference

- [Spec 022 BM25 retrieval](../../specs/022-mvp-main-tool/spec.md) — `find` 후보 선별에 쓰는 BM25 ranking 모델
- [Q4 row 그룹](review-checklist.md#q4--discovery--docs-8) — 50-item 검증 매트릭스의 8 항목
- [`src/ummaya/plugins/checks/q4_discovery.py`](../../src/ummaya/plugins/checks/q4_discovery.py) — 검사 구현
- [Kiwipiepy 문서](https://github.com/bab2min/kiwipiepy) — Korean morphology library
