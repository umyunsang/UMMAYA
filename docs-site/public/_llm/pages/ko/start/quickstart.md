---
title: Quickstart
description: packaged UMMAYA CLI를 설치하고 session을 시작한 뒤 안전한 public-service prompt를 실행합니다.
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- README.md
- package.json
audience:
- new_user
- considering_user
---

이 quickstart는 packaged UMMAYA CLI를 위한 문서입니다. 목표는 documentation file을 검사하거나 repository를 clone하거나 source test를 실행하는 것이 아닙니다. user-facing command를 설치하고, session을 시작하고, FriendliAI에 sign in한 뒤 safe public-service question 하나를 묻는 것입니다.

첫 실행은 public lookup으로 시작하세요. payment, certificate issuance, identity verification, tax filing, official record change, personal account data로 시작하지 마세요. 그런 flow는 explicit authority가 필요하고 자주 Mock 또는 Handoff에서 멈춥니다.

## 설치 경로 선택

macOS에서는 가능하면 Homebrew를 사용하세요. Homebrew를 쓰지 않거나 published package path를 직접 쓰고 싶다면 npm을 사용할 수 있습니다. 두 경로 모두 같은 user command인 `ummaya`를 노출해야 합니다.

| Platform path | 적합한 경우 | Command |
|---|---|---|
| Homebrew cask | macOS에서 native install/update path를 원하는 경우 | `brew install --cask umyunsang/ummaya/ummaya` |
| npm global package | CLI tool을 npm으로 관리하는 경우 | `npm install -g ummaya` |

UMMAYA를 user로 평가한다면 source checkout보다 packaged path를 우선하세요. source workflow는 contributor documentation에 속합니다.

## macOS 설치

Homebrew cask로 설치하거나 upgrade합니다.

```bash
brew install --cask umyunsang/ummaya/ummaya
ummaya --version
```

version command는 shell이 packaged CLI를 찾을 수 있다는 첫 proof입니다. 실패하면 새 terminal을 열고 Homebrew binary path가 shell에서 보이는지 확인하세요.

source checkout으로 packaging 문제를 우회하지 마세요. user quickstart는 ordinary user가 실행할 published command를 검증해야 합니다.

## npm 설치

global package로 설치합니다.

```bash
npm install -g ummaya
ummaya --version
```

npm package는 `bin/ummaya`를 통해 `ummaya` command를 노출합니다. wrapper는 terminal UI와 backend를 함께 시작하므로 Bun과 `uv` 같은 runtime dependency가 machine에 있어야 합니다.

npm install은 성공했지만 command가 실패하면 error message를 보존하세요. package resolution, runtime dependency, provider setup, startup logic 중 어디 문제인지 알려줍니다.

## 시작과 sign in

UMMAYA를 시작합니다.

```bash
ummaya
```

첫 session은 필요하면 provider setup 또는 sign-in으로 안내해야 합니다. UMMAYA는 model reasoning에 FriendliAI/K-EXAONE을 사용합니다. sign-in이 실패하면 adapter를 테스트하기 전에 이를 먼저 고치세요. provider failure는 public-service failure가 아닙니다.

sign-in 성공은 model access만 증명합니다. government portals, identity systems, payments, certificates에 대한 authority를 주지는 않습니다.

## 안전한 첫 프롬프트 실행

공개 정보를 요청하고 장소가 명확한 prompt를 사용하세요.

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

좋은 첫 답변은 location resolution 다음 public healthcare 또는 emergency information lookup 같은 public-service path를 보여야 합니다. 어떤 단계가 live가 아니거나 protected가 되면 UMMAYA는 완료를 가장하지 말고 Mock 또는 Handoff로 표시해야 합니다.

## 성공 모습 알기

첫 성공 session은 좁은 path를 증명합니다.

- packaged command가 시작됨;
- FriendliAI/K-EXAONE에 접근 가능함;
- query engine이 user request를 처리함;
- public lookup 또는 honest stop reason이 나타남;
- final answer가 source, state, boundary, next action을 말함.

모든 national-infrastructure domain이 live임을 증명하지 않습니다. harness가 user query에서 tool-backed 또는 boundary-aware answer로 이동할 수 있음을 증명합니다.

## 일반 복구

`ummaya`를 찾을 수 없으면 package path로 돌아가 다시 설치하고 새 shell을 여세요. command는 시작되지만 sign-in이 실패하면 다른 prompt 전에 provider credential을 고치세요. 답변이 Mock이면 simulation으로 다루세요. Handoff이면 답변이 말하는 official service에서 이어가세요.

public lookup이 실패하면 location과 하나의 public information need만 있는 더 단순한 prompt를 시도하세요. 이렇게 하면 install/provider 문제와 adapter coverage 문제를 분리할 수 있습니다.

## 업데이트 또는 재설치

설치에 사용한 package manager를 그대로 사용하세요.

```bash
brew upgrade --cask umyunsang/ummaya/ummaya
```

```bash
npm install -g ummaya@latest
```

업데이트 후 `ummaya --version`과 safe public prompt 하나를 다시 실행하세요. repository internals를 건드리지 않는 user-level smoke test입니다.

behavior가 바뀌었다면 version number만 비교하지 말고 visible answer state를 비교하세요. 중요한 regression signal은 public lookup, Mock, Handoff label이 여전히 정확히 나타나는지입니다.

## 다음 단계

첫 prompt가 성공하면 [What You Can Ask](/ko/start/what-you-can-ask/)에서 더 좋은 prompt를 작성하는 법을 읽고, protected workflow 전에 [Live, Mock, And Handoff](/ko/trust/live-mock-handoff/)를 읽으세요.

이 순서가 중요합니다. 좋은 prompt는 첫 경험을 유용하게 만들고, trust page는 protected workflow가 automatic official completion으로 오해되는 것을 막습니다.
