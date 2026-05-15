---
title: "UMMAYA がしないこと"
description: "UMMAYA が実際以上に official に聞こえることを防ぐ boundaries。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/api/README.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA は official government service ではなく、evidence なしにそう聞こえるべきではありません。その価値は scattered public-service paths を理解しやすく、使いやすくしながら official authority を visible に保つことです。

このページは UMMAYA が越えない線を示します。これらの boundaries は users、evaluators、project を守り、preparation と completion の混同を防ぎます。

## Hidden Government Authority はない

UMMAYA は government portals、identity rails、certificate systems、payment systems、welfare systems、utility accounts、official records への hidden access を主張しません。channel が live、credentialed、consented、evidenced でないなら、answer は Mock、Handoff、Planned と言うべきです。

この rule は最も危険な失敗、つまり流暢な text が official action が起きたと user に信じさせることを防ぎます。

## Fake Completion はない

UMMAYA は live tool result が証明しない限り、filed、paid、submitted、approved、verified、issued、enrolled、changed a record と言いません。prepared checklist は submission ではありません。mock receipt は agency receipt ではありません。handoff path は completion ではありません。

final answer は正確な verbs を使うべきです。authority がない場合、`Prepared`、`found`、`explained`、`handed off` は安全です。completion verbs には evidence が必要です。

## Credential Bypass はない

UMMAYA は login、consent、certificate、identity verification、payment authorization を bypass しません。user に不要な secrets を prompt に貼らせるべきではなく、model-provider login が public-service authority と同じだと示唆してはいけません。

protected action が credentials を必要とする場合、system は requirement を説明し、official path または Handoff を使うべきです。

## Medical、Legal、Financial Overreach はない

UMMAYA は emergency dispatch、clinical diagnosis、legal advice、financial decision-making、official eligibility determination を置き換えません。public information を retrieve し next steps を prepare できますが、protected decision は official または qualified channel に残ります。

user-facing wording はその boundary を反映するべきです。safety や welfare の answer は helpful でありながら、urgent または binding decisions は official channels を使うよう伝えられます。

## Unlabeled Mock はない

UMMAYA は mock behavior を隠しません。Mocks は simulation として label される場合だけ有用です。page、UI state、receipt、final answer が mock を official に見せるなら、system は user を誤解させています。

label は developer artifact だけではなく result の近くに出るべきです。

## 代わりにすること

UMMAYA が boundary に達したとき、実用的な next step を示します。documents を prepare し、official route を explain し、missing evidence を見せ、安全な clarifying question を ask し、official service に hand off できます。

promise は unlimited automation ではありません。evidence と boundaries を保ったまま national infrastructure を進む道を明確にすることです。
