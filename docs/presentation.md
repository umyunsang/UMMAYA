<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/ummaya-banner-dark.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="../assets/ummaya-banner-light.svg"/>
  <img alt="UMMAYA" src="../assets/ummaya-banner-light.svg" width="600"/>
</picture>

# UMMAYA

> **Target**: KSC 2026 research presentation
> **Status**: Working deck notes, refreshed 2026-05-29 KST
> **Stack**: Python 3.12 + FriendliAI Serverless K-EXAONE + Ink TUI

UMMAYA is a student portfolio project. It is not affiliated with Anthropic, LG AI
Research, FriendliAI, or the Korean government.

---

## 1. One-Slide Thesis

**UMMAYA migrates the Claude Code harness from software development to Korean
national administrative infrastructure.**

Claude Code proved that a model can work as a planner/executor when it has a
stable tool loop, permission gauntlet, context assembly, and TUI. UMMAYA keeps
that harness shape and swaps two things:

1. **LLM**: K-EXAONE on FriendliAI Serverless.
2. **Tool surface**: Korean public-service, identity, payment, certificate,
   welfare, health, housing, labor, education, safety, and utility channels.

Everything else is treated as a parity problem first: if the restored Claude
Code source already defines the loop, input model, render order, permission
request, or TUI boundary, UMMAYA ports that structure before adding domain text.

---

## 2. Why This Is Not Just RAG

RAG answers questions. UMMAYA is designed to **execute administrative outcomes**
inside a permissioned tool loop.

```text
Citizen: "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘."

UMMAYA:
  check  -> establish scoped identity / delegation context
  find   -> collect tax basis through the available channel or fixture
  send   -> submit only after explicit citizen confirmation
  receipt/handoff -> return audit evidence or official handoff boundary
```

The model's job is not to memorize which portal owns each step. It decomposes
the request, chooses registered tools, checks authority, inspects results, and
continues or stops with a reviewable receipt.

---

## 3. Policy Fit

The project is framed against Korea's 2026-2028 public AX direction:

- Open API and OpenMCP-style public-service composition.
- AI-native government and single-window citizen service.
- One-ID, no-paper, approval-based information reuse.
- Explicit controls against AI-agent malfunction, abuse, and policy bypass.

UMMAYA is the **client-side reference implementation** for consuming those
channels. It does not ask agencies to change systems and it does not claim
government authority.

Reference source in this repo:
[`docs/references/korea-ai-action-plan-2026-2028.pdf`](references/korea-ai-action-plan-2026-2028.pdf)

---

## 4. Current Product Boundary

The old "5,000 data.go.kr APIs" framing is too narrow. `data.go.kr` remains one
adapter family, but the target is broader national infrastructure AX:

- Hometax tax handling
- Government24 civil-affairs submission
- KFTC/OpenGiro and payment rails
- mobile ID, simple authentication, certificates, MyData
- utilities, welfare, healthcare, housing, labor, education, immigration,
  disaster response, and local civil-affairs channels

Every domain is classified before it becomes a tool:

| Class | Meaning | Presentation claim |
|---|---|---|
| Live | Official callable channel + valid credential exists | Demonstrate real adapter behavior with sanitized evidence |
| Mock | Channel exists or is policy-mandated, but credential/access is unavailable | Shape-mirror the public contract and disclose "no real administrative effect" |
| Handoff | Opaque portal or no callable channel | Explain official path; do not fake execution |

---

## 5. Active Primitive Surface

The active root surface is four verbs:

| Primitive | Role | Permission posture |
|---|---|---|
| `find` | read/search/fetch public or delegated information | auto-allowed unless adapter metadata says otherwise |
| `locate` | resolve places, addresses, coordinates, and administrative codes | auto-allowed, then followed by concrete data tools |
| `check` | identity, consent, credential, or delegation ceremony | light permission gate |
| `send` | submit, pay, file, register, or mutate official-state-like records | heavy permission gate |

`subscribe` is deferred until UMMAYA owns an app/push delivery runtime. Domain
verbs such as `pay`, `issue_certificate`, and `submit_application` live inside
adapter metadata, not as always-loaded root verbs.

---

## 6. Six-Layer Architecture

<img src="diagrams/ummaya_6_layer_architecture.svg" alt="UMMAYA 6-Layer Architecture" width="100%">

| Layer | Current claim |
|---|---|
| Query Engine | Claude Code-style tool loop; TUI sends tools-aware `chat_request` frames and backend returns tool-aware responses |
| Tool System | Pydantic v2 schemas, Draft 2020-12 JSON Schemas, BM25/dense discovery, concrete registered adapters |
| Permission Pipeline | CC `<PermissionRequest>` UX plus Korean PIPA/identity/delegation constraints |
| Agent Swarms | Coordinator-owned synthesis and worker findings; permissions do not flow laterally |
| Context Assembly | System prompt, session guidance, compaction, prompt cache discipline |
| Error Recovery | Fail-closed adapters, explicit upstream error classes, no silent fake recovery |

The restored Claude Code source under
`.references/claude-code-sourcemap/restored-src/` is the first reference for
tool-loop and TUI behavior.

---

## 7. KSC 2026 Presentation Spine

1. **Problem**: public services are portal-centered, institution-specific, and
   authority-sensitive.
2. **Insight**: the coding-agent harness is reusable wherever work reduces to
   "call the right tools in the right order under permission boundaries."
3. **Design**: CC harness + K-EXAONE + Korean public-service tool surface.
4. **Mechanism**: `find/locate/check/send`, adapter registry, permission
   gauntlet, Live/Mock/Handoff boundary.
5. **Evidence**: Evidence Fabric v2 connects scenario contracts, tool schemas,
   prompt integrity, observability join keys, UX artifacts, and manual live
   canaries.
6. **Limitations**: Live access is credential-bound; opaque portals remain
   handoff; mock results must never be phrased as official completion.
7. **Contribution**: an open-source caller pattern for national AX channels,
   not a claim of agency integration.

---

## 8. Demonstration Scenarios

Target-state scenarios come from
[`evidence/scenarios/national_ax_citizen_requests_v1.yaml`](../evidence/scenarios/national_ax_citizen_requests_v1.yaml).
Use these in the KSC story:

1. **Tax execution**: identity/delegation → tax basis lookup → filing or handoff
   with receipt.
2. **Life-event bundle**: move-in report → vehicle, insurance, and education
   address updates in legal order.
3. **Payment consolidation**: bill discovery → explicit payment selection →
   payment or official handoff.
4. **Birth and welfare bundle**: birth registration, child allowance, voucher,
   and health-insurance dependent registration.
5. **Emergency and safety**: disaster report, relief, temporary housing, and
   utility safety inspection routing.

The older route-safety and hospital-search frames under
`docs/presentation/v0.1-alpha/` remain historical v0.1-alpha evidence. They are
not the final KSC 2026 product boundary.

---

## 9. Evaluation Story

KSC 2026 evaluation should lead with full-system evidence rather than isolated
answer grading:

| Gate | Measures |
|---|---|
| Scenario contract | natural citizen requests cover tax, civil affairs, payment, utilities, identity, welfare, healthcare, housing, mobility, business, labor, education, safety, immigration, legal, and personal-data domains |
| Tool surface | model-visible tool definitions expose concrete schemas without leaking hidden expected adapter IDs |
| Prompt integrity | prompt manifests and session guidance remain stable and testable |
| Observability | `scenario_id`, `trace_id`, `correlation_id`, `prompt_manifest_hash`, `tool_catalog_hash`, and `frame_hash` join the run |
| UX artifact | TUI proof shows input, progress, tool dispatch/result boundaries, and final answer order |
| Live canary | manual-only live checks with sanitized request/response evidence; never CI |

Primary command:

```bash
uv run pytest tests/evidence tests/ci -q
uv run python -m ummaya.evidence --source-ref local --dataset-ref ummaya/national-ax-core@local --out .evidence/run.json
```

---

## 10. UI Story

The TUI is not a decorative shell. It is the citizen-visible proof that the
harness is doing ordered work:

- Korean-primary output with English fallback only where domain labels require it.
- CC-style progress before final answer.
- Tool result boundaries between model turns.
- Permission requests through the CC modal path.
- Mock/handoff disclosures in result copy, not hidden in a diagram footnote.
- Expand/collapse, transcript, and keyboard behavior ported from Claude Code
  unless a public-service constraint forces a documented divergence.

Current wireframe notes:
[`docs/wireframes/README.md`](wireframes/README.md)

---

## 11. KSC Source Status

Checked on 2026-05-29 KST:

- KIISE's KSC 2025 page was live at
  `https://www.kiise.or.kr/conference/main/index.do?CC=KSC&CS=2025`, listing
  "2025 한국소프트웨어종합학술대회 (KSC2025)", the theme "AX 시대의 소프트웨어
  혁신과 미래", and the event dates 2025-12-16 to 2025-12-19.
- `https://www.kiise.or.kr/conference/KSC/2026/` returned the KIISE 404 page.
- `https://www.kiise.or.kr/conference/main/index.do?CC=KSC&CS=2026` returned a
  page shell but did not expose public 2026 event details in the fetched HTML.

Therefore the deck should not invent a KSC 2026 deadline, venue, paper length,
or track. Use "KSC 2026 target" until the official CFP is public.

---

## 12. Slide Asset Backlog

- Replace the old `data.go.kr`-only architecture figure with a national
  infrastructure AX figure.
- Add a one-slide Live/Mock/Handoff matrix.
- Add a `find/locate/check/send` primitive diagram.
- Add an Evidence Fabric v2 run-evidence diagram.
- Replace route-safety/hospital-only screenshots with at least one protected
  `check -> send` scenario and one public `locate -> find` scenario.

---

## 13. Source Map

- Architecture thesis: [`docs/vision.md`](vision.md)
- Migration tree: [`docs/requirements/ummaya-migration-tree.md`](requirements/ummaya-migration-tree.md)
- Primitive correction: [`docs/onboarding/five-primitive-harness.md`](onboarding/five-primitive-harness.md)
- Evidence gate: [`docs/design/verification-fabric-v2.md`](design/verification-fabric-v2.md)
- Active primitive registry: [`src/ummaya/primitives/__init__.py`](../src/ummaya/primitives/__init__.py)
- KSC official page checked: <https://www.kiise.or.kr/conference/main/index.do?CC=KSC&CS=2025>
