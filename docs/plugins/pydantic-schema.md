# Pydantic Schema 작성 규칙

> 플러그인의 `schema.py` 가 따라야 하는 Pydantic v2 규약. 50-item 검증 워크플로의 Q1 (10 항목) 과 Q3 (V1) 가 이 규약을 enforce 합니다.
>
> 참고: [Constitution §III](../../.specify/memory/constitution.md), [Spec 019 input discipline](../../specs/019-phase1-hardening/spec.md), [Spec 024 V1 (extra=forbid)](../../specs/024-tool-security-v1/spec.md), [docs/plugins/review-checklist.md](review-checklist.md).

---

## 1. 모듈 레벨 import

```python
# plugin_<name>/schema.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
```

규칙:
- `from pydantic import` 형태 — `pydantic.v1` 같은 legacy compat 경로 금지 (Q1-PYV2).
- `from typing import Any` 금지 (Q1-NOANY). `Any` 가 필요해 보이면 *진짜로 필요한지* 다시 검토 — 보통 좁은 union, `dict[str, str]`, 또는 `BaseModel` subclass 로 대체 가능.
- `__future__` annotations 권장 (forward ref 필요 시 명시적 quoting 회피).

---

## 2. `model_config` 필수 kwargs

모든 input / output 클래스는 `model_config = ConfigDict(...)` 를 선언:

| kwarg | 값 | 이유 |
|---|---|---|
| `frozen` | `True` | Spec 027/032 패턴. 한 번 검증 후 mutable 하면 invariant chain 신뢰성 깨짐 (Q1-FROZEN). |
| `extra` | `"forbid"` (input) / `"forbid"` 또는 `"allow"` (output) | Spec 024 V1. Input 은 항상 forbid; output 은 upstream 응답이 시간이 갈수록 필드를 추가할 수 있어 `"allow"` 도 허용 (Q1-EXTRA-FORBID). |

```python
class LookupInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    ...

class LookupOutput(BaseModel):
    # output 은 upstream API 가 향후 필드 추가 가능 → allow 권장
    model_config = ConfigDict(frozen=True, extra="allow")
    ...
```

---

## 3. 모든 `Field(...)` 에 `description=`

LLM 이 tool input 을 채울 때 보는 필드 설명입니다 — Spec 019 의 input-discipline 패턴을 그대로 따릅니다 (Q1-FIELD-DESC).

```python
# ✓ 올바름
station_name: str = Field(
    min_length=1,
    description="역 이름 한국어 (예: '강남'). UTF-8 그대로 전달.",
)

# ✗ 금지
station_name: str = Field(min_length=1)  # description 누락
station_name: str  # 또는 plain annotation 만
```

description 작성 가이드:
- **무엇** 을 받는지 — 단위, 형식, 예시.
- **언제** 필요/불필요한지 — optional 의 의미.
- 한국어 표시 텍스트로 작성. 영문 식별자나 단위는 인용부호 안에 그대로.

---

## 4. Required vs Optional

```python
# Required (default 없음)
query: str = Field(min_length=1, description="...")

# Optional with explicit default
limit: int = Field(default=10, ge=1, le=100, description="...")

# Optional, none 허용
note: str | None = Field(default=None, description="...")
```

규칙:
- **fail-closed default** — Q2 가 enforce. 예: `requires_auth=True`, `is_personal_data=True`, `cache_ttl_seconds=0`, `rate_limit_per_minute ≤ 30`.
- Optional 필드는 명시적 default 또는 `| None`. 둘 다 빠지면 Pydantic 이 required 로 처리.

---

## 5. 클래스 명명 규약

LLM-visible primitive 와 1:1:

| Primitive | input class | output class |
|---|---|---|
| `lookup` | `LookupInput` | `LookupOutput` |
| `submit` | `SubmitInput` | `SubmitOutput` |
| `verify` | `VerifyInput` | `VerifyOutput` |

(Q1-INPUT-MODEL / Q1-OUTPUT-MODEL 이 위 3쌍 중 하나가 존재하는지 확인.)

내부 모델 (`SubwayArrival`, `TrackingEvent` 등) 은 자유 명명. 단 `LookupInput` 의 필드 type 으로 사용되는 nested model 은 동일한 `model_config` 규약 적용.

---

## 6. 흔한 안티 패턴

### ❌ 자유 dict 사용

```python
# 안티 패턴
result: dict[str, Any] = Field(description="...")  # Any 금지

# 권장
class Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    field_a: str = Field(...)
    field_b: int = Field(...)
result: Result = Field(description="...")
```

### ❌ description 생략

```python
# 안티 패턴
query: str = Field(min_length=1)  # LLM 이 의미를 모름
```

### ❌ frozen 누락

```python
# 안티 패턴 — model_config 자체를 빠뜨림
class LookupInput(BaseModel):
    query: str
```

### ❌ output 모델 `extra="forbid"` 강제

```python
# 안티 패턴 — upstream 이 필드 추가하면 즉시 깨짐
class LookupOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")  # output 은 allow 권장
```

---

## 7. 검증 도구

로컬에서 schema 만 빠르게 검증:

```bash
uv run python -c "
from plugin_my_plugin.schema import LookupInput, LookupOutput
print(LookupInput.model_json_schema())
print(LookupOutput.model_json_schema())
"
```

50-item 전체 검증:

```bash
# 외부 plugin repo 의 .github/workflows/plugin-validation.yml 가
# umyunsang/KOSMOS/.github/workflows/plugin-validation.yml@main 을 호출.
# 로컬에서도 직접 실행 가능:
uv run python -c "
from pathlib import Path
from kosmos.plugins.checks.framework import run_all_checks
results = run_all_checks(
    plugin_root=Path('.'),
    yaml_path=Path('tests/fixtures/plugin_validation/checklist_manifest.yaml'),
)
for row, outcome in results:
    mark = '✓' if outcome.passed else '✗'
    print(f'{mark} {row.id}: {outcome.failure_message_ko or row.description_ko}')
"
```

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 모델 설정 | model_config | `ConfigDict(frozen=True, extra="forbid")` 같은 클래스 메타. |
| 동결 | frozen | `frozen=True` — 인스턴스 불변. Spec 027/032 패턴. |
| 추가 필드 금지 | extra="forbid" | 정의되지 않은 필드를 reject. Spec 024 V1. |
| 필드 설명 | Field description | LLM 이 input 채울 때 보는 한국어 텍스트. Spec 019 input-discipline. |
| 입력 모델 | input model | LookupInput 등 4 primitive-paired class. |
| 출력 모델 | output model | LookupOutput 등. upstream 변동 흡수 위해 `extra="allow"` 권장. |
| 보수적 default | conservative default | fail-closed 원칙으로 작은 rate-limit / 짧은 cache-TTL 부터 시작. |
| 50-item 매트릭스 | 50-item matrix | tests/fixtures/plugin_validation/checklist_manifest.yaml. Q1-Q10 의 50개 항목. |
| 검증 워크플로 | validation workflow | .github/workflows/plugin-validation.yml. 외부 plugin repo 가 reusable 호출. |
