# 빠른 시작 (Quickstart)

> KOSMOS 플러그인을 처음 만드는 기여자를 위한 가이드입니다. `git clone` 부터 로컬 `pytest` 통과까지 **30분 이내** 가 목표입니다 (SC-001).
>
> 영문 원본: [`specs/1636-plugin-dx-5tier/quickstart.md`](../../specs/1636-plugin-dx-5tier/quickstart.md). 코드 블록과 식별자는 영문 원본과 동일하게 유지하고 본 문서는 한국어 설명을 제공합니다.
>
> 참고: [Migration tree § B8](../requirements/kosmos-migration-tree.md), [Spec 022 BM25 retrieval](../../specs/022-mvp-main-tool/spec.md), [Constitution §IV — Live API 차단 규칙](../../.specify/memory/constitution.md).

---

## 단계 0 — 사전 준비 (시간 외)

- Python 3.12+ 와 `uv` 설치 (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- GitHub 계정.
- Live tier 플러그인 작성 시: [data.go.kr](https://data.go.kr) API 키 (무료 발급).
- 선택: KOSMOS TUI — `kosmos plugin init` 인터랙티브 플로우에만 필요. 비-TUI 환경에서는 `uvx kosmos-plugin-init <name>` 으로도 스캐폴딩 가능.

위 항목은 SC-001 의 30분 측정에 포함되지 않습니다 (시간 측정은 git clone 부터 시작).

---

## 단계 1 — 템플릿 복제 (1분)

두 가지 옵션 중 선택:

### 옵션 A — GitHub "Use this template" (권장)

1. <https://github.com/kosmos-plugin-store/kosmos-plugin-template> 방문
2. "Use this template" → "Create a new repository" 클릭
3. 새 repo 이름은 `kosmos-plugin-<your-plugin-name>` 형식 (예: `kosmos-plugin-busan-bike`)
4. 로컬 클론:
   ```sh
   git clone https://github.com/<your-org>/kosmos-plugin-busan-bike
   cd kosmos-plugin-busan-bike
   ```

### 옵션 B — `kosmos plugin init` CLI (TUI 가 있을 때)

```sh
kosmos plugin init busan_bike --non-interactive --tier live --layer 1 --no-pii
cd busan_bike
```

옵션 B 는 옵션 A 와 동일한 스캐폴드를 emit 하지만 tier / layer / PII 를 미리 설정합니다.

> **중요**: `<plugin_id>` 는 snake_case 만 허용 (`^[a-z][a-z0-9_]*$`). 디렉토리 이름과 `manifest.yaml` 의 `plugin_id` 가 일치해야 합니다 (FR-019, ADR-007).

---

## 단계 2 — 의존성 설치 + 스캐폴드 테스트 (3분)

```sh
uv sync           # ~30초 (pydantic, httpx, pytest 다운로드)
uv run pytest     # ~5초 (synthetic fixture 기반 happy-path 테스트 1건)
```

기대 결과:
```
============== 1 passed in 0.42s ==============
```

녹색이면 다음 단계로. 빨간색이면 `uv --version` ≥ `0.5`, Python ≥ 3.12 확인.

---

## 단계 3 — 아키텍처 읽기 (5분)

[`docs/plugins/architecture.md`](architecture.md) 의 핵심:

- **Active plugin primitive**: `lookup`, `submit`, `verify`. `subscribe` 는 앱/푸시 런타임이 생길 때까지 비활성.
- 플러그인의 `tool_id` 는 반드시 `plugin.<plugin_id>.<verb>` 형식이며 `<verb>` 는 active plugin primitive 중 하나여야 함 (ADR-007).
- `adapter.py` 는 `GovAPITool` 인스턴스를 모듈-레벨 `TOOL` 심볼로 export.
- **Live tier vs Mock tier** — 코드를 작성하기 전에 결정 (`docs/plugins/live-vs-mock.md`).

`busan-bike` 예시:
- `tool_id`: `plugin.busan_bike.lookup`
- `tier`: `live` (부산 공공데이터포털)
- `permission_layer`: 1 (공공 자전거 잔여대수 — PII 없음)

---

## 단계 4 — `manifest.yaml` 편집 (3분)

스캐폴드된 `manifest.yaml` 예시:

```yaml
plugin_id: busan_bike
version: 0.1.0
adapter:
  tool_id: plugin.busan_bike.lookup
  primitive: lookup
  module_path: plugin_busan_bike.adapter
  input_model_ref: plugin_busan_bike.schema:LookupInput
  source_mode: OPENAPI
  published_tier_minimum: digital_onepass_level1_aal1
  nist_aal_hint: AAL1
  auth_type: api_key
  auth_level: AAL1
  pipa_class: non_personal
tier: live
mock_source_spec: null
processes_pii: false
slsa_provenance_url: https://github.com/<your-org>/kosmos-plugin-busan-bike/releases/download/v0.1.0/busan_bike.intoto.jsonl
otel_attributes:
  kosmos.plugin.id: busan_bike
search_hint_ko: "부산 자전거 따릉이 대여소 자전거 잔여대수 부산광역시"
search_hint_en: "Busan bike rental station availability"
permission_layer: 1
```

`processes_pii: true` 일 때는 `pipa_trustee_acknowledgment` 블록이 필수 (`docs/plugins/security-review.md` 의 canonical 텍스트와 SHA-256 일치 필수).

---

## 단계 5 — `plugin_busan_bike/schema.py` 편집 (5분)

```python
from pydantic import BaseModel, ConfigDict, Field

class BusanBikeQueryInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    district: str = Field(min_length=1, description="부산 구 이름 (예: 해운대구, 수영구)")

class BusanBikeStation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    station_id: str = Field(description="대여소 ID")
    station_name_ko: str = Field(description="대여소 한국어 이름")
    bikes_available: int = Field(ge=0, description="현재 잔여 자전거 수")

class BusanBikeQueryOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stations: list[BusanBikeStation] = Field(description="구 내 대여소 목록")
```

규칙 (Q1-PYV2 / Q1-NOANY / Q1-FIELD-DESC 강제):
- Pydantic v2 `BaseModel` + `frozen=True, extra="forbid"`.
- `Any` 사용 금지. 모든 필드에 명시적 타입.
- 모든 `Field` 에 `description=` 필수 (Spec 019 input-discipline).

---

## 단계 6 — `plugin_busan_bike/adapter.py` 편집 (8분)

```python
import os
import httpx

from kosmos.tools.models import GovAPITool

from .schema import BusanBikeQueryInput, BusanBikeQueryOutput, BusanBikeStation

ENDPOINT = "https://api.bts.go.kr/openapi/bike/stations"


def _build_tool() -> GovAPITool:
    return GovAPITool(
        id="plugin.busan_bike.lookup",
        name_ko="부산 따릉이 대여소 잔여 자전거 조회",
        ministry="OTHER",
        category=["교통", "자전거"],
        endpoint=ENDPOINT,
        auth_type="api_key",
        input_schema=BusanBikeQueryInput,
        output_schema=BusanBikeQueryOutput,
        search_hint="부산 자전거 따릉이 대여소 잔여대수 / Busan bike rental availability",
        auth_level="AAL1",
        pipa_class="non_personal",
        is_irreversible=False,
        dpa_reference=None,
        is_personal_data=False,
        primitive="lookup",
        published_tier_minimum="digital_onepass_level1_aal1",
        nist_aal_hint="AAL1",
        is_concurrency_safe=True,
        cache_ttl_seconds=60,
        rate_limit_per_minute=30,
    )


TOOL = _build_tool()


async def adapter(payload: BusanBikeQueryInput) -> dict:
    api_key = os.environ["KOSMOS_DATA_GO_KR_API_KEY"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            ENDPOINT, params={"serviceKey": api_key, "district": payload.district}
        )
        r.raise_for_status()
        data = r.json()
    return {
        "stations": [
            {
                "station_id": s["id"],
                "station_name_ko": s["name"],
                "bikes_available": s["available"],
            }
            for s in data["stations"]
        ]
    }
```

규칙:
- API 키는 반드시 `KOSMOS_*` env var 에서 읽기 (Q-NO-HARDCODED-KEY).
- `GovAPITool` 의 모든 required 필드 작성. 생략 가능한 필드는 fail-closed default 사용.
- Live tier 는 실제 네트워크 호출, Mock tier 는 fixture replay (`docs/plugins/live-vs-mock.md`).

---

## 단계 7 — 테스트 업데이트 (3분)

`tests/test_adapter.py` 는 synthetic fixture (`tests/fixtures/plugin.busan_bike.lookup.json`) 와 함께 happy-path 테스트가 기본 포함됩니다. 자신의 `output_schema` 에 맞춰 fixture 편집:

```json
{
  "stations": [
    {"station_id": "BTS-001", "station_name_ko": "해운대해수욕장", "bikes_available": 7},
    {"station_id": "BTS-002", "station_name_ko": "광안리해수욕장", "bikes_available": 3}
  ]
}
```

error-path 테스트 추가 (Q10-ERROR-PATH):

```python
@pytest.mark.asyncio
async def test_invalid_district_raises(monkeypatch):
    async def _fail(*args, **kwargs):
        import httpx
        raise httpx.HTTPStatusError("404", request=None, response=None)
    monkeypatch.setattr("httpx.AsyncClient.get", _fail)
    with pytest.raises(httpx.HTTPStatusError):
        await adapter(BusanBikeQueryInput(district="존재하지않는구"))
```

실행:
```sh
uv run pytest
```

기대: `2 passed`.

---

## 단계 8 — 로컬 검증 (2분)

```sh
uvx --from git+https://github.com/umyunsang/KOSMOS@main \
    kosmos-plugin-validate .
```

50개 review-checklist 항목을 모두 로컬에서 실행. GitHub workflow 가 PR 에 실행하는 동일한 검증입니다. 기대:
```
✓ 50 / 50 통과
```

실패 항목이 있으면 항목 ID 와 수정 힌트가 출력됩니다. 녹색이 될 때까지 수정 후 재실행.

---

## 단계 9 — Push 와 PR 작성 (1분)

```sh
git add -A
git commit -m "feat: initial busan-bike plugin"
git push origin main
```

PR 작성 후 `plugin-validation.yml` workflow 가 PR 에 자동 실행. 기대 결과: 녹색 체크 + 한국어 요약 코멘트 "✓ 50 / 50 통과 — 검증 완료. 머지를 위해 maintainer 의 리뷰가 필요합니다."

---

## 시간 예산 요약

| 단계 | 소요 시간 | 누적 |
|---|---|---|
| 0. 사전 준비 | (시간 외) | — |
| 1. 템플릿 복제 | 1분 | 1분 |
| 2. 의존성 + 테스트 | 3분 | 4분 |
| 3. 아키텍처 읽기 | 5분 | 9분 |
| 4. manifest 편집 | 3분 | 12분 |
| 5. schema 편집 | 5분 | 17분 |
| 6. adapter 편집 | 8분 | 25분 |
| 7. 테스트 업데이트 | 3분 | 28분 |
| 8. 로컬 검증 | 2분 | 30분 |
| 9. Push + PR | 1분 | 31분 |

**SC-001 예산**: ≤ 30분. push 단계는 별도 CI 사이클이라 측정에서 제외.

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함되며 (FR-006), 한국어 ↔ English 핵심 용어 매핑을 제공합니다.

| 한국어 | English | 설명 |
|---|---|---|
| 어댑터 | adapter | `kosmos.tools.models.GovAPITool` 을 export 하는 플러그인의 코어 모듈 (`adapter.py`). |
| 매니페스트 | manifest | `manifest.yaml` 파일. `PluginManifest` Pydantic 스키마로 검증되는 플러그인 메타데이터. |
| 권한 레이어 | permission layer | 1 (green) / 2 (orange) / 3 (red) — 시민 동의 강도. Spec 033 이 enforce. Migration tree § UI-C. |
| 검색 힌트 | search hint | BM25 인덱스에 등록되는 한국어/영어 토큰 (`search_hint_ko` / `search_hint_en`). Spec 022. |
| 카탈로그 | catalog | `kosmos-plugin-store/index/index.json` — 설치 가능한 플러그인 메타 인덱스. |
| 수탁자 | trustee | PIPA §26 기반 위탁자/수탁자 체인의 수탁 측. Live tier + PII 처리 시 필수. |
| 동의 영수증 | consent receipt | 플러그인 install/uninstall 시 `~/.kosmos/memdir/user/consent/<id>.json` 에 append. Spec 035 ledger 확장. |
| 프리미티브 | primitive | active plugin 동사 (`lookup`, `submit`, `verify`). 플러그인은 이 중 하나에 binding. |
| 1차 매핑 | byte mirror | OpenAPI 사양과 byte-equivalent 한 어댑터 (Spec 031 `source_mode=OPENAPI`). |
| 2차 매핑 | shape mirror | OSS SDK 와 shape-compatible 한 어댑터 (`source_mode=OOS`). |

---

## 이 문서가 다루지 않는 것

- **PIPA acknowledgment 플로우** — `processes_pii: true` 일 때만 발동. `docs/plugins/security-review.md` 참고.
- **Mock tier 경로** — `docs/plugins/live-vs-mock.md`.
- **`kosmos-plugin-store` 게시** — quickstart 범위 외; PR merge 후 자동 진행.
- **마켓플레이스 브라우저 UI** — 별도 epic (#1820).
