---
title: "なぜ UMMAYA なのか"
description: "UMMAYA が national-infrastructure AX harness として存在する理由。"
llm_index: true
audience:
  - non_user
  - considering_user
  - public_sector_evaluator
source_of_truth:
  - docs/research/ummaya-docs-goal-brief-2026-05-15.md
  - docs/vision.md
  - docs/requirements/ummaya-migration-tree.md
  - eval/scenarios/national_ax_citizen_requests_v1.yaml
---

UMMAYA が存在する理由は、ユーザーから見ると韓国の public-service work が分断されているからです。一つの life event が portals、agencies、identity rails、certificates、payments、local records、welfare rules、healthcare data、safety sources、public-data APIs にまたがります。ユーザーは outcome を頼む前にその map を理解する必要はありません。

UMMAYA の目標は Korean national-infrastructure AX です。分散した public-service domains の上に one approachable query surface を置きます。system は request を decompose し、tools を選び、必要なら permission を求め、evidence を返し、official path が引き継ぐべき場所で誠実に停止します。

## ユーザー問題

問題は public-service websites が多いことだけではありません。より深い問題は、ユーザーが現実の need を agencies、forms、credentials、portals の言葉に翻訳しなければ work が始まらないことです。

たとえば「引っ越した」は address resolution、local government records、utilities、vehicle/parking rules、housing documents、official handoff を含み得ます。「支援が必要」は welfare guidance、household documents、eligibility boundaries、application channels を含み得ます。user intent は一文でも、infrastructure path は multi-domain です。

UMMAYA はこの翻訳負担を吸収するために設計されています。ただし official authority が消えるふりはしません。

## product claim

UMMAYA は、人が public-service outcome を頼み、その後何が起きたか見えるようにするべきです。有用な回答は、どの step が public lookup で、どの step が consent を要し、どの step が Mock で、どの step が Handoff になったか示します。

だから UMMAYA は general chatbot ではなく agent harness です。chatbot は service を説明し、evidence がなくても authority あるように聞こえます。UMMAYA は回答を controlled loop、つまり context、retrieval、primitive choice、validation、permission、adapter execution、stop reason に接続しなければなりません。

## mechanism

UMMAYA は public-service channels と policy-shaped workflows を tools として wrap します。model が見るのは小さな primitive surface、現在は `locate`、`find`、`check`、`send` です。adapter layer は domain detail、schema、status、citation、permission metadata を持ちます。

query engine は次の step が location resolution、public lookup、protected checking、submission preparation、Handoff のどれかを決めます。この decision が national AX の中心です。user は outcome で話し、system が routing と evidence を処理します。

## Claude Code を参照する理由

Claude Code は tool use、permission prompts、context assembly、session continuity、terminal UX を一つの working harness に結合しているため reference です。UMMAYA はその harness pattern を developer work から public-service work に移します。

許される swap は狭いです。model provider は FriendliAI の K-EXAONE に置き換わり、tool surface は files、shell、git、code tools から Korean public-service tools に置き換わります。bounded tool use、permission、context、visible progress の discipline は保つべきです。

## この site が証明すべきこと

この site は overclaim せずに説得する必要があります。UMMAYA が today 何をできるか、何が Mock または Handoff か、packaged CLI の install 方法、first successful session の姿、architecture が public-service claims をどう grounded にするかを示します。

docs が UMMAYA を official government service のように見せたら失敗です。normal chatbot のように見せても失敗です。正しい promise はより狭く、より強いものです。one query surface、tool-backed evidence、visible boundaries、honest official handoff です。
