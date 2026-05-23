---
title: クイックスタート
description: packaged UMMAYA CLI をインストールし、セッションを開始し、安全な public-service prompt を一つ実行します。
source_of_truth:
- docs/research/ummaya-docs-goal-brief-2026-05-15.md
- README.md
- package.json
audience:
- new_user
- considering_user
---

この quickstart は packaged UMMAYA CLI のためのものです。目的は documentation files を確認することでも、repository を clone することでも、source tests を実行することでもありません。目的は user-facing command をインストールし、セッションを開始し、FriendliAI に sign in し、安全な public-service question を一つ試すことです。

最初の実行では public lookup を使います。payment、certificate issuance、identity verification、tax filing、official record changes、personal account data から始めないでください。これらの flow は明示的な authority を必要とし、多くの場合 Mock または Handoff で止まります。

## インストール経路を選ぶ

macOS では可能なら Homebrew を使います。published package path を使いたい場合や Homebrew を使わない場合は npm を使います。どちらの経路も同じ user command、`ummaya` を提供するべきです。

| Platform path | Best for | Command |
|---|---|---|
| Homebrew cask | native install/update path を望む macOS users | `brew install --cask umyunsang/ummaya/ummaya` |
| npm global package | CLI tools を npm で管理している users | `npm install -g ummaya` |

ユーザーとして UMMAYA を評価するなら、source checkout より packaged paths を優先してください。source workflows は contributor documentation の領域です。

## macOS でインストール

Homebrew cask で install または upgrade します。

```bash
brew install --cask umyunsang/ummaya/ummaya
ummaya --version
```

version command は shell が packaged CLI を見つけられる最初の証拠です。失敗したら新しい terminal を開き、Homebrew の binary path が shell で使えるか確認します。

packaging issue を直すために source checkout へ切り替えないでください。project に貢献する場合を除き、user quickstart は ordinary users が実行する published command を検証するべきです。

## npm でインストール

package を global にインストールします。

```bash
npm install -g ummaya
ummaya --version
```

npm package は `bin/ummaya` から `ummaya` command を公開します。wrapper は terminal UI と backend を一緒に起動するため、Bun や `uv` などの runtime dependencies が machine に必要です。

npm install が成功して command が失敗する場合は、error message を残してください。package resolution、runtime dependency、provider setup、startup logic のどこに問題があるか示します。

## 起動して sign in

UMMAYA を起動します。

```bash
ummaya
```

最初のセッションでは、必要に応じて provider setup または sign-in に進みます。UMMAYA は model reasoning に FriendliAI/K-EXAONE を使います。sign-in が失敗する場合、adapter を試す前に修正してください。provider failure は public-service failure ではありません。

sign-in 成功が証明するのは model access だけです。government portals、identity systems、payments、certificates への authority を与えるものではありません。

## 安全な最初の prompt を実行

公共情報を求め、場所を明確にする prompt を使います。

```text
동아대 승학캠퍼스 근처 응급실이나 야간 진료 정보를 공식 정보 기준으로 찾아줘.
```

よい最初の回答は、location resolution から public healthcare または emergency information lookup に進むような public-service path を示すべきです。ある step が live でない、または protected になる場合、UMMAYA は完了したふりをせず Mock または Handoff と表示するべきです。

## 成功とは何か

最初の成功セッションが証明するのは次の狭い経路です。

- packaged command が起動する；
- FriendliAI/K-EXAONE に到達できる；
- query engine が user request を処理できる；
- public lookup または honest stop reason が現れる；
- final answer が source、state、boundary、next action を示す。

すべての national-infrastructure domain が live である証明ではありません。user query から tool-backed または boundary-aware answer へ進める harness であることを証明します。

## よくある復旧

`ummaya` が見つからない場合は package path から再インストールし、新しい shell を開きます。command が起動して sign-in が失敗する場合は provider credentials を直します。回答が Mock と言うなら simulation として扱います。Handoff と言うなら回答に示された official service で続けます。

public lookup が失敗する場合は、location と一つの public information need を持つより単純な prompt を試してください。これにより install/provider problems と adapter coverage problems を分離できます。

## 更新または再インストール

インストールに使った package manager を使います。

```bash
brew upgrade --cask umyunsang/ummaya/ummaya
```

```bash
npm install -g ummaya@latest
```

更新後、`ummaya --version` と安全な public prompt をもう一度実行します。repository internals に触れずに user-level smoke test ができます。

挙動が変わった場合、version number だけで判断しないでください。重要な regression signal は public lookup、Mock、Handoff labels が正しく見えるかです。

## 次のステップ

最初の成功 prompt の後は、より良い prompt を書くために [What You Can Ask](/jg/start/what-you-can-ask/) を読み、protected workflows を試す前に [Live, Mock, And Handoff](/jg/trust/live-mock-handoff/) を読んでください。
