# 테스트 작성 컨벤션

> 플러그인의 `tests/` 디렉토리를 작성할 때 따라야 하는 pytest 컨벤션. 50-item 검증 워크플로의 Q10 (4 항목) 이 이 컨벤션을 enforce 합니다.
>
> 참고: [Constitution §IV — Live API CI 차단](../../.specify/memory/constitution.md), [`docs/design/verification-fabric-v2.md`](../design/verification-fabric-v2.md), [50-item Q10 그룹](review-checklist.md#q10--tests--fixtures-4).

---

## 디렉토리 구조

```
plugin_<name>/
└── tests/
    ├── __init__.py
    ├── conftest.py                          # block_network autouse fixture
    ├── test_adapter.py                      # happy + error path tests
    └── fixtures/
        └── plugin.<tool_id>.json            # recorded fixture
```

`pyproject.toml` 의 `[tool.pytest.ini_options]` 에 `asyncio_mode = "auto"` 가 설정되어 async 함수에 별도 데코레이터 불필요 (스캐폴드 default).

---

## conftest.py — Network block fixture

scaffold가 emit 하는 `tests/conftest.py` 는 IPv4/IPv6 socket 만 차단 (AF_UNIX 는 asyncio event loop 가 사용하므로 통과):

```python
@pytest.fixture(autouse=True)
def block_network(monkeypatch, request):
    if request.node.get_closest_marker("allow_network") is not None:
        yield
        return

    def _maybe_block(*args, **kwargs):
        family = kwargs.get("family") if "family" in kwargs else (
            args[0] if args else socket.AF_INET
        )
        if family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("Outbound network access is blocked ...")
        return _REAL_SOCKET(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", _maybe_block)
    yield
```

**규칙**:
- 절대 conftest 를 수정해서 block 을 풀지 마세요. live 호출이 필요한 통합 테스트는 `@pytest.mark.live` 로 격리.
- `@pytest.mark.allow_network` 는 monkeypatched httpx 로 fixture replay 하는 happy-path 에만 사용 — 실제 socket 은 여전히 막혀 있음 (httpx.AsyncClient.get 가 monkey-patch 되어 socket 호출 도달 안함).

---

## Q10 4 항목 매핑

| ID | 의미 | 패턴 |
|---|---|---|
| Q10-HAPPY-PATH | 1개 이상 test_* 함수 | `async def test_adapter_happy_path()` |
| Q10-ERROR-PATH | 1개 이상 `pytest.raises(...)` | input validation 또는 HTTP 에러 |
| Q10-FIXTURE-EXISTS | tests/fixtures/*.json 1개 이상 + valid JSON | `json.loads()` 통과 |
| Q10-NO-LIVE-IN-CI | live-only 테스트는 `@pytest.mark.live` 필수 | live 호출 격리 |

---

## Live tier 테스트 패턴

```python
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from plugin_<name>.adapter import adapter
from plugin_<name>.schema import LookupInput, LookupOutput

_FIXTURE = Path(__file__).parent / "fixtures" / "plugin.<tool_id>.lookup.json"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None: ...

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.fixture
def fixture_payload() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UMMAYA_<MINISTRY>_API_KEY", "test-key")


@pytest.mark.allow_network              # ← httpx monkey-patch 통과용
async def test_adapter_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    env_key: None,
    fixture_payload: dict[str, Any],
) -> None:
    async def _fake_get(self, url, **_):
        return _FakeResponse(fixture_payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await adapter(LookupInput(...))
    parsed = LookupOutput.model_validate(result)
    assert parsed.<expected_field> == ...


async def test_adapter_missing_api_key(monkeypatch):
    monkeypatch.delenv("UMMAYA_<MINISTRY>_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="API_KEY"):
        await adapter(LookupInput(...))


def test_input_validation_rejects_empty():
    with pytest.raises(Exception):
        LookupInput(query="")
```

규칙:
- happy-path 는 fixture replay (CI 안전).
- error-path 1개 이상 — input validation 또는 HTTP 에러.
- 통합 테스트 (실제 호출) 는 `@pytest.mark.live` 로 격리:

```python
@pytest.mark.live
@pytest.mark.allow_network
async def test_adapter_against_real_api():
    """수동 실행 전용. CI 에서 -m 'not live' 로 deselect."""
    ...
```

`pyproject.toml` 에 marker 등록 필요 (스캐폴드 default 에 포함):

```toml
[tool.pytest.ini_options]
markers = [
    "live: hits real public API — skipped in CI",
    "allow_network: opt-out of autouse network block",
]
```

---

## Mock tier 테스트 패턴

Mock 어댑터는 fixture replay 만 사용 — `httpx` import 자체가 없으므로 monkey-patch 불필요:

```python
import pytest

from plugin_<name>.adapter import adapter
from plugin_<name>.schema import LookupInput, LookupOutput


async def test_adapter_replays_fixture():
    payload = LookupInput(...)
    result = await adapter(payload)
    parsed = LookupOutput.model_validate(result)
    # Mock 보장: 모든 식별자가 "MOCK-" 접두사로 시작
    assert all(d["document_id"].startswith("MOCK-") for d in parsed.documents)


async def test_adapter_synthetic_only():
    """fixture 의 모든 식별자가 합성값임을 검증 — 실제 PII 누출 방지."""
    payload = LookupInput(...)
    result = await adapter(payload)
    assert "MOCK-" in result["institution_ko"]


def test_input_validation_rejects_invalid():
    with pytest.raises(Exception):
        LookupInput(...)
```

`@pytest.mark.allow_network` 불필요 — mock 어댑터는 socket 자체를 열지 않음.

---

## Fixture 기록 절차

[`docs/plugins/data-go-kr.md` § 5](data-go-kr.md) 의 절차를 따르세요. 요약:

```python
# scripts/record_fixture.py
import asyncio, json, os
from pathlib import Path
from plugin_<name>.adapter import adapter
from plugin_<name>.schema import LookupInput

async def main():
    # 로컬에서 .env 로 UMMAYA_<MINISTRY>_API_KEY 설정 후 실행
    payload = LookupInput(...)
    result = await adapter(payload)
    Path("tests/fixtures/plugin.<tool_id>.lookup.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )

asyncio.run(main())
```

기록 후 PII 마스킹 (주민번호 → `010-****-1234` 등) 후 commit. mock 어댑터는 합성값만 — `MOCK-` 접두사로 일관 표시 권장.

---

## 검증 명령

```bash
uv sync
uv run pytest                     # CI 와 동일 — live 마커 자동 deselect
uv run pytest -m live             # 수동 통합 테스트
uv run pytest -v tests/test_adapter.py::test_adapter_happy_path
```

50-item 매트릭스의 Q10 그룹은 `plugin-validation.yml` 가 자동 실행 — 위 컨벤션을 따르면 4/4 통과.

---

## 흔한 안티 패턴

### ❌ conftest 의 block_network 우회

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def block_network():
    yield   # block 자체를 비활성화 — Constitution §IV 위반
```

→ Q10-NO-LIVE-IN-CI 가 fail. CI 에서 실제 호출 가능 → quota 폭발 + PII 노출 위험.

### ❌ Live 호출을 CI 에 노출

```python
async def test_real_api():   # @pytest.mark.live 마커 누락
    result = await adapter(...)   # 실제 UMMAYA_*_API_KEY 사용
```

→ CI 가 secret 으로 키 주입 시 quota 소진. `@pytest.mark.live` 마커 + CI 가 `-m 'not live'` 로 deselect 권장.

### ❌ Fixture 가 invalid JSON

```json
{ "key": "value", }   // ← trailing comma
```

→ Q10-FIXTURE-EXISTS fail. `json.loads()` 가 파싱 못 함.

### ❌ Mock 인데 fixture 미정렬

```python
# adapter.py (mock)
async def adapter(payload):
    return {"hardcoded": "value"}   # fixture 무시
```

→ 시민 호출 결과가 항상 동일. `_FIXTURE_PATH` 를 read 하는 패턴 사용.

---

## Bilingual glossary

> 이 섹션은 9개 가이드 (`docs/plugins/*.md`) 모두에 동일한 형식으로 포함됩니다 (FR-006).

| 한국어 | English | 설명 |
|---|---|---|
| 자동사용 fixture | autouse fixture | `@pytest.fixture(autouse=True)` — 명시적 의존 없이 모든 테스트에 적용. |
| Network block | network block | conftest 의 IPv4/IPv6 socket 차단. AF_UNIX 는 통과. |
| Recorded fixture | recorded fixture | `tests/fixtures/<id>.json` — 로컬 호출 → JSON 저장. |
| Monkey-patch | monkey-patch | `pytest.MonkeyPatch` 로 객체/속성 임시 교체. |
| Live 마커 | live marker | `@pytest.mark.live` — CI deselect 용 격리 마커. |
| Allow-network 마커 | allow_network marker | autouse block 우회 — fixture replay 패턴 전용. |
| Asyncio mode auto | asyncio_mode auto | pytest-asyncio 설정. async 함수 자동 인식 (마커 불필요). |
| Happy path | happy path | 정상 입력 + 예상 응답 검증. |
| Error path | error path | 잘못된 입력 / HTTP 에러 → `pytest.raises(...)` 검증. |

---

## Reference

- [Constitution §IV](../../.specify/memory/constitution.md) — Government API Compliance + Live API CI 차단
- [`docs/design/verification-fabric-v2.md`](../design/verification-fabric-v2.md) — UMMAYA 메인 테스트 가이드
- [50-item Q10 그룹](review-checklist.md#q10--tests--fixtures-4) — 4 항목 매트릭스
- [`src/ummaya/plugins/checks/q10_tests.py`](../../src/ummaya/plugins/checks/q10_tests.py) — 검사 구현
- [docs/plugins/data-go-kr.md § 5](data-go-kr.md) — Fixture 기록 절차
- [docs/plugins/live-vs-mock.md](live-vs-mock.md) — Tier 별 테스트 패턴 차이
