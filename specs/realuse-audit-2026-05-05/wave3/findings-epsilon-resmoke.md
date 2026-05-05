# Wave 3 — Domain ε re-smoke verdict (post G2/G4)

> ε Sonnet completed 4 scenario captures but exceeded context budget before authoring this file. Captures verified directly by coordinator. **CRITICAL caveat**: ε Opus did NOT set `KOSMOS_PIPA_CONSENT=opt-in-explicit` — boot path stayed gated at PIPA step in 2 of 4 scenarios → those captures invalid for plugin/agent surface verification.

| Finding | Verdict | Evidence frame |
|---|---|---|
| F-ε-02 `/plugin list` IPC silence | **INVALID — onboarding-blocked** | `f-epsilon-02/snap-003-e2-result.txt` shows preflight step 1 not REPL. Captures cannot validate plugin overlay. Re-test required with `KOSMOS_PIPA_CONSENT=opt-in-explicit` set |
| F-ε-03 `/plugin install` SLO | **INVALID — input-not-delivered** | `f-epsilon-03/snap-004-t11s.txt` shows REPL with empty `❯ ` prompt. Slash command never reached input. Re-test required |
| F-ε-05 `/agents` Esc dismiss | **NOT_CLOSED** | `f-epsilon-05/snap-004-agents-open.txt` ≡ `snap-005-after-esc.txt` (diff returns empty). Esc unchanged the panel. G2 chord block was added for `Help` and `Autocomplete` contexts but NOT for `Agents` — incomplete coverage |
| F-ε-04 phase counter 2/7 vs 8 | **DEFERRED** | not retested due to F-ε-03 invalid |

**ε summary**: 0 CLOSED (F-ε-05 NOT_CLOSED, F-ε-02/03 invalid pending re-test). G2 fix needs an `Agents` chord block addition (analogous to Help). ε P1 findings (queue-trap, swarm trigger, AgentVisibilityPanel) untouched and remain open per triage Wave-3 deferral.
