# Contract — SmokeChecklist template

**Purpose**: defines the format the release validator uses to drive `bun run tui` end-to-end and capture ANSI evidence. The populated artifact lives at `specs/1637-p6-docs-smoke/smoke-checklist.md` after implement; this template gates spec FR-013 / FR-014 and SC-005.

---

```markdown
# Smoke checklist — KOSMOS v0.1-alpha pre-merge gate

**Branch**: `feat/1637-p6-docs-smoke`
**Run date**: <YYYY-MM-DD>
**Validator**: <name>
**Bun version**: `bun --version`
**Terminal**: <Kitty / iTerm2 / Terminal.app / other>

## Capture procedure

```bash
mkdir -p specs/1637-p6-docs-smoke/visual-evidence
script -q "specs/1637-p6-docs-smoke/visual-evidence/<step-id>.ansi.txt" \
  bun run tui
# Drive the requested step interactively, then Ctrl-D to end capture.

# Strip escape codes for the plain-text companion:
sed 's/\x1b\[[0-9;]*m//g' \
  "specs/1637-p6-docs-smoke/visual-evidence/<step-id>.ansi.txt" \
  > "specs/1637-p6-docs-smoke/visual-evidence/<step-id>.txt"
```

## Onboarding flow (5 steps)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `onboarding-1-preflight` | Auto on TUI start; preflight panel renders | All checks green; "Continue" hint visible | `onboarding-1-preflight.ansi.txt` + `.txt` | ☐ |
| `onboarding-2-theme` | Theme selector | Selected theme applied to next frame | `onboarding-2-theme.ansi.txt` + `.txt` | ☐ |
| `onboarding-3-pipa` | PIPA consent prompt | Receipt ID rendered after Y | `onboarding-3-pipa.ansi.txt` + `.txt` | ☐ |
| `onboarding-4-ministry` | Ministry scope selection | Selected scope persisted to `~/.kosmos/memdir/user/onboarding/state.json` | `onboarding-4-ministry.ansi.txt` + `.txt` | ☐ |
| `onboarding-5-terminal` | Terminal setup; transition to REPL | Main REPL prompt visible | `onboarding-5-terminal.ansi.txt` + `.txt` | ☐ |

## Primitive flows (active flows)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `primitive-lookup-search` | `lookup` BM25 search | Top-3 candidates listed with tool_id + tier | `primitive-lookup-search.ansi.txt` + `.txt` | ☐ |
| `primitive-lookup-fetch` | `lookup` adapter fetch | Adapter response rendered with envelope | `primitive-lookup-fetch.ansi.txt` + `.txt` | ☐ |
| `primitive-submit` | `submit` mock adapter | Mock submission receipt | `primitive-submit.ansi.txt` + `.txt` | ☐ |
| `primitive-verify` | `verify` mock adapter | Verification mock result | `primitive-verify.ansi.txt` + `.txt` | ☐ |

## Slash commands (4 commands)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `slash-agents` | `/agents` panel | Spec 027 swarm agents listed | `slash-agents.ansi.txt` + `.txt` | ☐ |
| `slash-plugins` | `/plugins` browser | Plugin browser overlay renders | `slash-plugins.ansi.txt` + `.txt` | ☐ |
| `slash-consent-list` | `/consent list` | Consent receipts listed | `slash-consent-list.ansi.txt` + `.txt` | ☐ |
| `slash-help` | `/help` panel | HelpV2 grouped command list | `slash-help.ansi.txt` + `.txt` | ☐ |

## Error envelopes (3 envelopes)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `error-llm-4xx` | LLM 4xx (force via mock provider) | Spec 035 envelope; remediation hint | `error-llm-4xx.ansi.txt` + `.txt` | ☐ |
| `error-tool-fail-closed` | L3 fail-closed (force unauthenticated `nmc_emergency_search`) | Fail-closed envelope; no PII leak | `error-tool-fail-closed.ansi.txt` + `.txt` | ☐ |
| `error-network-timeout` | Network timeout (offline) | Network envelope; retry hint | `error-network-timeout.ansi.txt` + `.txt` | ☐ |

## PDF inline render (1 path)

| Step ID | Description | Pass criterion | Evidence | Result |
|---|---|---|---|---|
| `pdf-inline-render` | `/export pdf` after a sample conversation | Inline render in Kitty/iTerm2 OR documented `open` fallback elsewhere | `pdf-inline-render.ansi.txt` + `.txt` | ☐ |

## Summary

- Total steps cover onboarding, active primitive flows, slash commands, error envelopes, and PDF fallback.
- Pass count: <fill at end>
- Fail count: <fill at end>
- Blocked count: <fill at end>
- Sign-off: <validator name> on <date>

If any row fails, the PR is blocked until the failing step is either fixed or explicitly downgraded with rationale.
```

---

## Notes

- `script(1)` is part of the macOS base system; no new dependencies required (research.md § R6).
- The visual-evidence convention exactly mirrors `specs/1636-plugin-dx-5tier/visual-evidence/` (Spec 1636 precedent).
- The PDF step accepts the `open` fallback for non-Kitty/iTerm2 terminals — visual-fidelity inline is asserted only on the supported set.
- `primitive-lookup` stays split into search + fetch rows; `subscribe` is deferred until an app/push-notification runtime exists.
