---
title: トラブルシューティング
description: maintainer debugging に進む前に、user-facing problems を解決します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs/testing.md
- docs/onboarding/codex-continuation.md
audience:
- citizen_user
- maintainer
---

Troubleshooting は repository internals ではなく user が見る symptom から始めるべきです。UMMAYA を試している人は、command が installed か、sign-in が working か、public lookup が run するか、protected step が正しく stopped したかを知る必要があります。

maintainer debugging は重要ですが、user path が clear になった後です。最初の answer が `run tests` または `inspect git status` なら、docs は reader problem を飛ばしています。

## Symptom Map

visible symptom で first check を選びます。simple user path を除外する前に deep debugging へ飛ばないでください。

| Symptom | First check | Likely next step |
|---|---|---|
| `ummaya` command not found | install path | rerun installer, Homebrew cask, or npm global install |
| command starts but cannot sign in | FriendliAI login or token state | sign in again and confirm provider configuration |
| first prompt returns no useful result | prompt shape and public adapter availability | try a public lookup prompt with a clear place |
| answer says Mock | domain has shape but no live authority | read Live/Mock/Handoff and treat it as simulation |
| answer says Handoff | next step needs official authority | continue through the official service |
| session resume fails | session ID and local session availability | check the printed resume command and local storage |

この table は triage map であり proof ではありません。first fix の後も symptom が繰り返されるなら、exact command、visible message、failure が起きた page または workflow を capture します。

## Install Checks

command が missing の場合、まずどの installation method を使ったか確認します。packaged CLI が user path です。source checkout commands は contributors のためです。

```bash
ummaya --version
```

shell が `ummaya` を見つけられない場合、chosen package path で再インストールし、新しい shell を開きます。command が存在するが startup で失敗する場合、別 installer を試す前に visible error を記録します。

## Login Checks

UMMAYA は model provider として FriendliAI/K-EXAONE を使います。sign-in が失敗する場合、最初の question は provider credential が存在し CLI が reach できるかです。login failure は adapter failure ではなく、public-service problem と書くべきではありません。

login を直したら、protected workflow の前に safe public prompt を使います。よい smoke prompt は clear location と public weather、road、hospital、safety information を求めます。

## Mock または Handoff の混乱

Mock と Handoff はそれ自体 error ではありません。Mock は UMMAYA が official completion なしに workflow shape を demonstrate したことです。Handoff は UMMAYA に safe callable path がないため next step が official service に属することです。

recovery は state label を読み、次に必要なものを判断することです。demo が目的なら Mock で十分かもしれません。real filing、payment、certificate、identity verification、record change が目的なら、live authority が configured でない限り Handoff が honest result です。

## Maintainer Debugging

maintainers は user symptom を preserving した後で generated docs、tests、IPC frames、adapter schemas、TUI captures を inspect できます。debugging note は original symptom を残すべきです。command、prompt、expected state、actual state、failure が install、provider、retrieval、permission、adapter execution、rendering のどこで起きたかです。

user-facing failure を internal shorthand に置き換えないでください。`Adapter error` だけでは不十分です。どの adapter、どの mode、どの primitive、どの stop reason が関与したかを書きます。

## Recovery

user checks がどれも効かない場合、最小限の useful report を集めます。operating system、install method、`ummaya --version`、prompt used、visible state label、exact stop message です。この report は user に repository 全体を理解させずに maintainer へ必要な context を渡します。
