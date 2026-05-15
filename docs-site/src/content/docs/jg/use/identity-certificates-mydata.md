---
title: "ID、証明書、MyData"
description: "今日、多くが Mock または official Handoff を必要とする identity-bound workflows を理解します。"
llm_index: true
audience:
  - citizen_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs-site/src/data/generated/adapters.json
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

identity、certificates、MyData は Korean national-infrastructure AX の中心ですが、UMMAYA が最も保守的であるべき domains でもあります。有用な assistant は path を explain し、user を prepare し、permission shape を demonstrate できます。live official channel、credential、consent、evidence なしに identity verification、certificate issuance、document signing、personal data reading を pretend できません。

この page は identity-bound work around で UMMAYA が today 何を安全にできるか知りたい users のためのものです。短く言えば、public explanations は有用で、mock flows は shape を示せ、official Handoff がしばしば正しい stop point です。

## よい prompt

protected action を silently complete させるのではなく、preparation、official path explanation、permission boundary を求めます。

```text
주민등록등본 발급을 준비하려고 해. 필요한 인증 단계와 공식 서비스에서 이어서 해야 할 일을 정리해줘.
```

```text
MyData로 필요한 서류를 확인하는 흐름을 보여줘. 실제 개인 데이터 접근 없이 Mock 기준으로 어디서 consent가 필요한지 알려줘.
```

これらの prompt は hidden authority を主張せずに UMMAYA が explain と prepare をできるため有効です。user が `issue it now` または `log in for me` と求める場合、system は access を発明せず permission または Handoff に進むべきです。

## 期待される flow

identity-bound work は通常 `find` から始まり、`check` に進むことがあり、多くの場合 `send` の前で止まります。public guidance は official service が求めるものを説明できます。Mock は consent と schema shape を demonstrate します。live authority がない場合、Handoff が user を official service に送ります。

| Step | UMMAYA behavior | Boundary |
|---|---|---|
| Public explanation | `find` retrieves official guidance or known public material | Explanation only |
| Identity boundary | `check` exposes consent and credential requirements | Mock unless live authority exists |
| Certificate or MyData action | `send` only with official channel, credential, consent, and evidence | Otherwise Handoff |

重要なのは sequence です。UMMAYA は public explanation から `completed certificate issuance` へ飛んではいけません。どの step が protected になり、なぜ official path が引き継ぐか示すべきです。

## 見えるべきもの

identity answer は、関わる data、必要な consent、どの system が official か、UMMAYA が何を did not do したかを伝えるべきです。Live、Mock、Handoff label は protected step の近くに出るべきで、footnote に隠してはいけません。

evaluator にとって、この page は contract でもあります。正しい flow は adapter mode、permission decision、stop reason が final wording と一致した evidence を残すべきです。final answer が `issued` と言い、flow が Mock までなら、documentation と product language は wrong です。

## Mock がなお重要な理由

Mocks は明確に label される場合に価値があります。live credentials または official channels がない段階で、consent prompts、schema validation、tool calling、receipts、handoff copy の UX を test できます。

mock が official に見えると価値は消えます。mock identity verification は identity verification ではありません。mock certificate result は certificate ではありません。answer はその差を見逃せないようにする必要があります。

## Recovery

UMMAYA が hand off するとき、user は何を持って進むべきか知るべきです。official service name、required authentication type、必要になりそうな documents/data、UMMAYA ができなかった exact step です。これにより Handoff は evasive ではなく useful になります。

product promise は `UMMAYA bypasses identity rails` ではありません。`official identity rail が引き継ぐまで confusion を減らす` ことです。
