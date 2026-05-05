# Wave 3 — Domain δ re-smoke verdict (post G2/G7)

> δ Sonnet completed 4 scenarios but exceeded context budget before authoring this file. Captures verified directly by coordinator from `wave3/delta/{delta1,delta4,delta8}-captures/`. Memdir restore confirmed (`~/.kosmos/` present, no `~/.kosmos.bak.*` leftover).

| Finding | Verdict | Evidence frame |
|---|---|---|
| F-delta-01 onboarding preflight Enter | **NOT_CLOSED** | `delta1-captures/snap-002-step2-theme.txt` ≡ `snap-000-boot-preflight.txt`. Banner `◉ ○ ○ ○ ○ 1/5` unchanged after Enter. G2 fix present but runtime symptom persists — same root cause as F-alpha-02 (ChordInterceptor routing `enter` to `chat:submit` before PreflightStep `useInput(key.return)` fires) |
| F-delta-02 KOSMOS_ONBOARDING_AUTO_COMPLETE escape hatch | **PARTIAL_BLOCKED** | now correctly gates at PIPA step (G1 fail-closed enforcement intentional); requires `KOSMOS_PIPA_CONSENT=opt-in-explicit` to proceed |
| F-delta-04 /help Esc dismiss | **CLOSED** | `delta4-captures/snap-002-help-open.txt` shows `✻ KOSMOS · 도움말 / Help` with sections; `snap-003-after-esc.txt` shows REPL `❯` prompt restored. G2 chord block registration effective |
| F-delta-08 slash autocomplete prefix | **NOT_CLOSED (or capture-timing)** | `delta8-captures/snap-004-slash-pl.txt` shows `❯ /pl` but no dropdown rendered. G7 prefix matcher applied to source but no match candidates surfaced in capture window. May be capture-timing (dropdown flashed sub-frame) — needs Layer 5c frame-hash sequence assertion |

**δ summary**: 1 CLOSED, 1 NOT_CLOSED, 1 PARTIAL_BLOCKED, 1 ambiguous. F-delta-01 root cause shared with F-alpha-02 (Wave-4 G8 priority).
