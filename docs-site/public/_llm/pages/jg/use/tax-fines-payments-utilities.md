---
title: 税、罰金、支払い、公共料金
description: mock path を official completion と混同せず、重要な payment と filing workflows
  を準備します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- eval/scenarios/national_ax_citizen_requests_v1.yaml
audience:
- citizen_user
- considering_user
- public_sector_evaluator
---

tax、fines、payments、utility bills は UMMAYA の target state を説得的に示します。common で fragmented で consequential だからです。同時に、checklist、estimate、mock、handoff が official filing や payment のように聞こえると危険です。

有用な UMMAYA はこの違いを隠しません。likely path を explain し、public guidance を gather し、required information を prepare し、consent または official login が必要な場所を示します。live official channel が evidence を返さない限り、money was paid、tax return was filed、official record was changed と主張してはいけません。

## よい prompt

よい prompt は path を prepare し boundary を mark するよう求めます。

```text
자동차 과태료를 납부해야 하는지 확인하려고 해. 어떤 공식 경로와 준비물이 필요한지 정리하고, 실제 납부가 필요한 단계는 Handoff로 표시해줘.
```

```text
종합소득세 신고를 준비하려고 해. UMMAYA가 확인할 수 있는 공개 정보와 공식 홈택스에서 해야 하는 단계를 나눠서 알려줘.
```

これらは preparation と execution を分けるため有効です。user が immediate payment または filing を求める場合、UMMAYA は `send` の前に live authority、credential、consent、receipt evidence を要求するべきです。

## 期待される flow

payment と filing workflows は public explanation から始まり、すぐ protected state に入ることが多いです。UMMAYA は layer を分けて扱うべきです。

```text
User asks about tax, fine, payment, or utility work
  -> `find` retrieves public guidance or general path
  -> `check` may reveal that user-specific state requires authority
  -> `send` is allowed only with live official channel and consent
  -> Handoff if the next step must happen on the official service
```

正しい stop は failure ではありません。live official channel がなければ、UMMAYA は path を prepared したが file、pay、change a record はしていないと言うべきです。

## 安全な result shape

final answer は四つに分けます。UMMAYA が found したこと、user-specific として残るもの、workflow を続ける official service、UMMAYA が did not do したことです。

| Need | Safe UMMAYA output | Unsafe output |
|---|---|---|
| Public filing guidance | steps, required documents, official service name | "your filing is done" |
| User-specific amount | consent-gated `check` or Handoff | guessed amount |
| Payment execution | live `send` with receipt evidence | mock payment described as paid |
| Receipt | Live receipt or clearly labeled mock receipt | unlabeled confirmation |

この language は user が false completion に基づいて行動することを防ぎます。evaluator にも明確な test を与えます。すべての completion word は tool evidence に支えられている必要があります。

## 強い言葉が必要な理由

この domain の false answer は実害を生みます。deadline を逃す、fine が paid と思い込む、filing が accepted と思う、credentials を間違った場所に渡す可能性があります。UMMAYA は impressive phrasing より explicit boundary wording を優先すべきです。

`prepared`、`identified`、`requires official login`、`not submitted`、`continue through the official service` を使います。live result が prove しない限り `paid`、`filed`、`accepted`、`approved`、`changed` は避けます。

## Recovery

protected payment または filing flow が止まった場合でも、answer は有用であるべきです。どの official service を開くか、何を prepare するか、どの consent または credential が missing か、将来 UMMAYA が live に実行するにはどんな evidence が必要かを伝えます。

target state は payment boundaries を消すことではありません。official authority を visible に保ちながら path を理解しやすくすることです。
