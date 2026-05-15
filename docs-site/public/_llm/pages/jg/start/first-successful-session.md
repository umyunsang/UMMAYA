---
title: 最初の成功セッション
description: 最初の実行で何が見えるべきか、そして何を主張してはいけないか。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- docs-site/src/data/generated/adapters.json
audience:
- new_user
- considering_user
- public_sector_evaluator
---

UMMAYA の最初の成功セッションが証明するのは、狭いが重要な経路です。packaged command が起動し、model provider に到達でき、query engine が市民の依頼を処理し、回答が Live、Mock、Handoff の状態を正直に示すことです。

それは UMMAYA がすべての protected public-service action を完了できる証明ではありません。最初の実行では identity、payment、certificate issuance、tax filing、official record change ではなく、安全な public lookup を試すべきです。

## 最初のセッションの流れ

成功した最初のセッションは、ユーザーが何が起きたか理解できる程度に見える必要があります。UI は変わっても、順序は理解可能であるべきです。

```text
1. The `ummaya` command starts.
2. Provider setup or sign-in is available if needed.
3. The user asks a public-service question.
4. UMMAYA routes the request through the query engine.
5. A public adapter runs, or the system explains why no safe live action exists.
6. The final answer summarizes result, state, boundary, and next action.
```

大事なのはアニメーションや branding ではありません。見える回答が tool-backed path または clear stop reason に追跡できることです。

## よい最初の prompt

有用だが低リスクな prompt を使います。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

この prompt は場所を与え、公共情報を求め、official/public grounding を要求します。identity verification、payment、certificate issuance、filing、account-specific data は求めていません。

## 回答が示すべきこと

回答は、ユーザーが次の手順を信頼できるだけの構造を持つべきです。public-service path、そのステップが Live/Mock/Handoff のどれか、回答を支える source または adapter result、そして next action を含めます。

UMMAYA が live public path を見つけられない場合でも、Handoff は正しい結果になり得ます。official access を作り話にしないとき、製品は誠実に動作しています。

## 起きてはいけないこと

最初のセッションで UMMAYA が certificate を発行した、identity を verified した、bill を paid した、tax return を submitted した、official record を changed した、personal account data にアクセスした、と主張してはいけません。これらには official callable channel、credentials、explicit consent、evidence が必要です。

回答は曖昧な権威表現も避けるべきです。`officially completed`、`verified`、`submitted`、`paid` には live proof が必要です。証拠がない場合は `prepared`、`found`、`explained`、`handed off` が安全な語です。

## 最初のセッションが失敗したら

症状で次の行動を決めます。command がないなら Quickstart に戻ります。sign-in が失敗するなら provider setup を直します。prompt が Mock または Handoff を返すなら、失敗扱いする前に state label を読みます。public lookup が失敗するなら、より明確な場所と一つの public information need に絞ります。

最初のセッションは、UMMAYA が誠実で検査可能なら成功です。最も難しい protected action を完了したふりをすることが成功ではありません。

## 次に読むもの

最初の public lookup の後は、より良い prompt を選ぶために [What You Can Ask](/jg/start/what-you-can-ask/) を読み、protected workflows を試す前に [Live, Mock, And Handoff](/jg/trust/live-mock-handoff/) を読んでください。
