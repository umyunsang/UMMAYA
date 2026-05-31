# UMMAYA Research Plan

Academic research artifacts for UMMAYA. This directory supports the KSC 2026
paper/presentation track and later journal expansion while staying aligned with
the implementation source of truth in `docs/vision.md`.

Refreshed: 2026-05-29 KST.

## Current Research Claim

UMMAYA is a conversational execution platform that migrates the Claude Code
harness from developer workflows to Korean national administrative
infrastructure.

The research unit is not "many public APIs." It is:

```text
Claude Code-style harness
  + K-EXAONE/FriendliAI
  + Korean public-service tool surface
  + permission-aware Live/Mock/Handoff execution boundary
```

## Directory Structure

```text
research/
├── papers/              # Paper drafts and outlines
│   ├── ksc2026/         # KSC 2026 target submission
│   └── journal/         # Later KCI/JOK/KTCP-oriented expansion
├── experiments/         # Evaluation scripts and results
│   ├── scenarios/       # Research-only scenario notes
│   ├── baselines/       # Baseline implementations or comparison notes
│   └── results/         # Raw experiment output (CSV/JSON)
├── figures/             # Charts, diagrams, architecture figures
├── data/                # Public source material, no PII or secrets
└── README.md
```

The implementation evidence source has moved to `evidence/`:

- scenario dataset: `evidence/scenarios/national_ax_citizen_requests_v1.yaml`
- registry entrypoint: `evidence/registry.yaml`
- local evidence command: `uv run python -m ummaya.evidence ...`

## Paper Targets

| Venue | Type | Status |
|---|---|---|
| KSC 2026 | Research paper / student presentation target | CFP not public in checked KIISE HTML as of 2026-05-29 KST |
| KIISE journal route | JOK or KTCP article candidate | Later, after KSC paper and stronger evaluation results |
| KCI journal route | Expanded public-service AX architecture article | Later, after live/handoff evidence grows |

KSC source check:

- KSC 2025 official KIISE page:
  `https://www.kiise.or.kr/conference/main/index.do?CC=KSC&CS=2025`
- KSC 2026 direct page:
  `https://www.kiise.or.kr/conference/KSC/2026/` returned KIISE 404 on
  2026-05-29 KST.
- KSC 2026 main shell:
  `https://www.kiise.or.kr/conference/main/index.do?CC=KSC&CS=2026` loaded a
  shell but exposed no public 2026 CFP details in the fetched HTML.

Do not invent KSC 2026 deadline, venue, track, or page length until the official
CFP is visible.

## Evaluation Plan

### E1. Scenario Contract Coverage

- Source: `evidence/scenarios/national_ax_citizen_requests_v1.yaml`
- Goal: cover the target-state citizen demand surface across tax, civil affairs,
  payment, utilities, identity, welfare, healthcare, housing, mobility,
  business, labor, education, safety, immigration, legal, and personal-data
  domains.
- Metric: scenario count by lifecycle domain, priority, protected-vs-public
  route, and expected primitive chain.

### E2. Tool-Surface Contract Quality

- Source: registered tool schemas, `docs/api/`, and generated JSON Schemas.
- Goal: prove that model-visible tools have concrete IDs, descriptions,
  Pydantic-derived schemas, required fields, and no leaked hidden answer keys.
- Metrics: schema validity, required-field coverage, description coverage,
  adapter primitive coverage, and negative checks for fixture/expected-ID leaks.

### E3. Permission And Authority Boundary

- Source: `check`/`send` tests, adapter metadata, permission receipts, and
  Evidence Fabric output.
- Goal: distinguish public lookup, delegated identity, side-effecting
  submission/payment, mock result, and official handoff.
- Metrics: irreversible-action confirmation rate, mock-disclosure coverage,
  handoff clarity, and fail-closed behavior on missing delegation.

### E4. Tool-Loop And TUI Evidence

- Source: query loop tests, IPC frame tests, and reviewer-readable TUI artifacts.
- Goal: show that ordinary citizen input produces progress, tool dispatch,
  tool result, and final answer in the correct order.
- Metrics: frame-order invariants, `correlation_id` propagation, progress-before-
  final-answer checks, and UX artifact attachment when the render path changes.

### E5. Cost And Retrieval Efficiency

- Source: prompt manifest, tool catalog hash, candidate counts, and session
  telemetry.
- Goal: compare always-loaded primitive surface plus deferred adapter discovery
  against naive all-tool exposure.
- Metrics: tool catalog size, candidate recall, latency, prompt-cache stability,
  and token budget.

### E6. Manual Live Canary

- Source: sanitized direct `curl` evidence for official public-service channels.
- Goal: verify live credentials and upstream behavior only when a credential and
  official contract exist.
- Rule: never call live data.go.kr, government, identity, payment, certificate,
  utility, or other citizen-infrastructure channels from CI.

## KSC 2026 Milestones

| Window | Output |
|---|---|
| 2026-05 to 2026-06 | Lock paper claim, update presentation/wireframes, stabilize Evidence Fabric narrative |
| 2026-06 to 2026-07 | Build tables for scenario coverage, tool-surface coverage, and permission-boundary results |
| 2026-07 to 2026-08 | Replace historical v0.1-alpha screenshots with current protected/public scenario artifacts |
| CFP release + 2 weeks | Conform page length, template, topic track, submission metadata, and author affiliation |
| Submission month | Final paper, presentation deck, rendered figures, reproducibility appendix |

## Research Rules

- No PII or real citizen data in this directory.
- No API keys or secrets.
- Do not overclaim Live execution: mark Live, Mock, and Handoff explicitly.
- Do not use legacy primitive names as active roots. The active surface is
  `find`, `locate`, `send`, and `check`.
- Treat `subscribe` as deferred until an app/push runtime exists.
- Use Evidence Fabric v2 instead of retired standalone eval, shadow-eval, or
  TUI-only smoke artifacts.
- Raw results should be committed when small and reproducible; derived figures
  should be regenerated from scripts.
