---
title: "Troubleshooting"
description: "maintainer debugging으로 들어가기 전에 common user-facing problem을 해결합니다."
llm_index: true
audience:
  - citizen_user
  - maintainer
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/testing.md
  - docs/onboarding/codex-continuation.md
---

Troubleshooting은 사용자가 보는 symptom에서 시작해야 합니다. repository 내부에서 시작하면 안 됩니다. UMMAYA를 시도하는 사람은 command가 설치되었는지, sign-in이 되었는지, public lookup이 가능한지, protected step이 올바르게 멈췄는지 알고 싶어 합니다.

maintainer debugging도 중요하지만 user path가 명확해진 뒤에 나와야 합니다. 첫 답변이 `run tests`나 `inspect git status`라면 문서는 reader's problem을 건너뛴 것입니다.

## Symptom Map

보이는 symptom으로 첫 check를 고르세요. simple user path가 배제되기 전에는 deep debugging으로 뛰지 마세요.

| Symptom | First check | Likely next step |
|---|---|---|
| `ummaya` command not found | install path | installer, Homebrew cask, npm global install 재실행 |
| command starts but cannot sign in | FriendliAI login 또는 token state | 다시 sign in하고 provider configuration 확인 |
| first prompt returns no useful result | prompt shape와 public adapter availability | clear place가 있는 public lookup prompt 시도 |
| answer says Mock | domain shape는 있으나 live authority 없음 | Live/Mock/Handoff를 읽고 simulation으로 취급 |
| answer says Handoff | official authority 필요 | official service에서 계속 진행 |
| session resume fails | session ID와 local session availability | printed resume command와 local storage 확인 |

이 표는 triage map이지 proof가 아닙니다. symptom이 반복되면 정확한 command, visible message, failure가 발생한 page 또는 workflow를 capture하세요.

## Install Checks

command가 없으면 어떤 설치 방법을 썼는지 먼저 확인하세요. packaged CLI가 user path입니다. source checkout command는 contributor documentation에 속합니다.

```bash
ummaya --version
```

shell이 `ummaya`를 찾지 못하면 선택한 package path로 다시 설치하고 새 shell을 여세요. command는 있는데 startup에서 실패하면 다른 installer를 시도하기 전에 visible error를 기록하세요.

## Login Checks

UMMAYA는 model provider로 FriendliAI/K-EXAONE을 사용합니다. sign-in이 실패하면 provider credential이 존재하고 CLI가 접근할 수 있는지 먼저 확인해야 합니다. login failure는 adapter failure가 아니며 public-service problem으로 설명하면 안 됩니다.

login을 고친 뒤에는 protected workflow 전에 safe public prompt를 사용하세요. 좋은 smoke prompt는 명확한 location과 함께 public weather, road, hospital, safety information을 요청합니다.

## Mock Or Handoff Confusion

Mock과 Handoff는 그 자체로 error가 아닙니다. Mock은 workflow shape가 demonstration되었지만 official completion이 아니라는 뜻입니다. Handoff는 다음 step이 official service에서 이루어져야 한다는 뜻입니다.

복구 방법은 state label을 읽고 다음 필요를 결정하는 것입니다. demo가 목적이면 Mock으로 충분할 수 있습니다. 실제 filing, payment, certificate, identity verification, record change가 목적이면 live authority가 설정되지 않는 한 Handoff가 정직한 결과입니다.

## Maintainer Debugging

Maintainer는 user symptom이 보존된 뒤 generated docs, tests, IPC frames, adapter schemas, TUI captures를 inspect할 수 있습니다. debugging note는 original symptom을 유지해야 합니다. command, prompt, expected state, actual state, failure layer를 남겨야 합니다.

user-facing failure를 internal shorthand로 바꾸면 안 됩니다. `Adapter error`만으로는 부족합니다. 어떤 adapter, mode, primitive, stop reason이 관련되었는지 말해야 합니다.

## 복구

user checks가 모두 실패하면 최소한의 report를 모읍니다. operating system, install method, `ummaya --version`, 사용한 prompt, visible state label, exact stop message가 있으면 maintainer가 전체 repository를 사용자에게 설명시키지 않고도 문제를 좁힐 수 있습니다.
