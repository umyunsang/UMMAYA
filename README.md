<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/ummaya-banner-dark.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="assets/ummaya-banner-light.svg"/>
  <img alt="UMMAYA" src="assets/ummaya-banner-light.svg" width="600"/>
</picture>

# UMMAYA

**U**nified **M**ulti-**M**inistry **A**gent for **Y**our **A**dministration

**Handle Korean public-service tasks from one local conversational CLI.**

```bash
npm install -g ummaya
ummaya
```

or

```bash
brew install --cask ummaya
ummaya
```

> Academic R&D project. Not affiliated with Anthropic, LG AI Research, FriendliAI, or the Korean government.

![UMMAYA demo](assets/ummaya-demo.gif)

## Why UMMAYA

Public-service work rarely fits into one portal. A single life event can involve several agencies, forms, deadlines, certificates, payments, and follow-ups.

UMMAYA gives you one place to describe what you need in natural language. It helps turn a messy administrative task into a clear sequence of next steps, with confirmation before sensitive actions.

**One prompt. A clear plan. You stay in control.**

## Quickstart

### 1. Install UMMAYA

Install with npm:

```bash
npm install -g ummaya
ummaya
```

Install with Homebrew:

```bash
brew install --cask ummaya
ummaya
```

### 2. Sign in for AI requests

UMMAYA uses **K-EXAONE-236B-A23B** for LLM responses and requires a **FriendliAI API key** before it can answer requests.

Start UMMAYA and run:

```text
/login
```

Your FriendliAI key is session-scoped and is not saved to disk. Released CLI users are not asked to provide government-agency or public-service provider credentials.

### 3. Ask in plain language

Try a real task instead of searching for the right portal first:

```text
이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘.
```

UMMAYA will guide the flow, show what needs confirmation, and explain when a task must be completed through an official channel.

## What You Can Ask

| Life event | Try asking UMMAYA |
|---|---|
| Tax refund | "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘." |
| Moving home | "이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘." |
| Taxes and fines | "이번 달 재산세랑 자동차세, 과태료 밀린 거 확인하고 납부 가능한 건 처리해줘." |
| New baby | "아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘." |
| Housing contract | "전세 계약했어. 확정일자, 임대차 신고, 전세보증 관련 절차를 위험한 부분까지 체크해서 처리해줘." |
| Starting a business | "카페 창업하려고 해. 사업자등록, 영업신고, 위생교육, 카드가맹, 세금 준비까지 순서대로 처리해줘." |
| Night care | "아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 야간진료 병원 찾고 보험 적용되는지도 알려줘." |
| Safer travel | "내일 부산에서 서울 가는데 날씨, 도로 위험, 대중교통 지연까지 보고 가장 안전한 이동 방법 추천해줘." |
| Flood damage | "집이 침수됐어. 피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘." |
| Personal data | "정부기관들이 내 정보를 어디에 쓰고 있는지 확인하고 잘못된 주소나 연락처는 고쳐줘." |

## What UMMAYA Helps With

- Find the right public-service path when a task crosses multiple agencies or portals.
- Break a complex request into a step-by-step checklist.
- Identify likely documents, deadlines, eligibility checks, fees, and follow-ups.
- Separate general guidance from actions that need identity, consent, payment, or final confirmation.
- Provide handoff guidance when the released CLI cannot complete a step directly.

## Trust and Safety

UMMAYA is built for careful public-service assistance:

- It explains the intended next step before sensitive actions.
- It treats identity, consent, payment, official filings, and personal information as high-trust moments.
- It may guide you to an official service when direct completion is not available in the current release.
- It is not an official government service. For binding legal, tax, medical, disaster, or emergency decisions, verify final instructions through the relevant official channel.

## Public-Service API Reality

UMMAYA is transparent about what is live today and what is safely simulated. In the public release, public-service lookup is the live API path; protected agency workflows are mock APIs unless official access is granted.

- **Live lookup:** Public-service search and information lookup can use live, callable channels when public access or operator-managed credentials are available.
- **Mocked protected flows:** Government24, MyData, 간편인증, certificates, payments, official submissions, welfare applications, utility changes, and other institution-gated workflows are represented with mock APIs in the public release.
- **Why mocks exist:** Many real agency APIs are not publicly callable by an independent student or research project. They usually require institutional authorization, security review, production contracts, or delegated legal authority.
- **How the mocks were made:** The mock APIs are domain-informed simulations inferred from publicly visible service domains, public service pages, expected request and response patterns, and real administrative journeys. They are not unofficial access, credential bypass, private-system scraping, or a claim of agency endorsement.
- **For public institutions:** UMMAYA is intended to be a shared evaluation harness. Agencies, public-infrastructure operators, and civic-tech partners can run the project, experience the citizen journey, validate assumptions, identify policy gaps, and join co-development to turn the safest mock flows into official live integrations.

## Model and License

UMMAYA currently uses [K-EXAONE-236B-A23B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B) as its LLM model.

- **Model:** `LGAI-EXAONE/K-EXAONE-236B-A23B`
- **Model license:** [`K-EXAONE AI Model License Agreement`](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B/blob/main/LICENSE) (`k-exaone`)
- **Project license:** [Apache License 2.0](LICENSE)

The model license is separate from the UMMAYA source-code license. Review and comply with the K-EXAONE license before downloading, serving, modifying, redistributing, or commercially providing the model or derivative work. UMMAYA does not grant rights to LG AI Research, FriendliAI, Hugging Face, or any government-agency assets.

## Current Release

The public release is focused on the installable CLI:

- npm package: `ummaya`
- Homebrew cask: `ummaya`

UMMAYA is a student portfolio and academic R&D project. Some real-world public-service workflows may end with guidance, handoff, or a mock flow depending on official availability and access policy.

## Learn More

- [`CHANGELOG.md`](CHANGELOG.md) - release history
- [`SECURITY.md`](SECURITY.md) - vulnerability reporting
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - contribution guidelines
- Wiki - research notes and deep-dive project background, maintained separately from this README

## Contributing

Issues, discussions, scenario ideas, bug reports, and documentation improvements are welcome.

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and open a [Discussion](https://github.com/umyunsang/UMMAYA/discussions) before large project changes.

## License

Licensed under the [Apache License 2.0](LICENSE).
