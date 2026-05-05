# Wave-4 G12 Re-smoke Findings

> Agent: Wave-4 Sonnet G12 (verification-only)
> Date: 2026-05-05
> HEAD: main (post-G1/G2/G3/G4/G5/G6/G7 fixups)
> Method: tmux capture-pane + aimock (KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1)
> Env used: KOSMOS_ONBOARDING_AUTO_COMPLETE=1 + KOSMOS_PIPA_CONSENT=opt-in-explicit

| Finding | Target | Verdict |
|---|---|---|
| F-ε-02 /plugin list overlay | G12a | PARTIAL |
| F-ε-03 /plugin install SLO | G12a | PARTIAL |
| F-delta-08 slash autocomplete /pl | G12b | NOT_CLOSED |
| F-gamma-04 consent receipt TUI display | G12c | NOT_CLOSED |
| F-beta-04 NMC modal | G12d | DEFERRED |

## G12a — F-ε-02 + F-ε-03

Env fix confirmed: both KOSMOS_ONBOARDING_AUTO_COMPLETE=1 AND KOSMOS_PIPA_CONSENT=opt-in-explicit bypass onboarding (Wave-3 invalidity resolved).

F-ε-02: /plugins typed manually renders PluginBrowser ("플러그인 브라우저 · 플러그인이 없습니다"). PARTIAL — command works when typed in full; autocomplete /p/pl still silent (see G12b root cause).

F-ε-03: Phase 0s shows "⏳ 요청 전송 — 백엔드 응답 대기 중…"; Phase 2s shows "⏳ Phase 1/7 — 📡 카탈로그 조회 중…" — input IS delivered now. PARTIAL — Phase 1 fires within 2s (SLO met for start); backend emits no error/terminal frame for unknown plugin within 30s.

## G12b — F-delta-08

ROOT CAUSE IDENTIFIED: filterToKosmosCommands() filters runtime commands against KOSMOS_CITIZEN_COMMAND_NAMES built from catalog. Catalog entry = /plugins (name='plugins'). Runtime command in plugin.tsx:251 has name='plugin' (singular). Mismatch → plugin command excluded from citizen set → G7 prefix filter never sees it → no dropdown for /p or /pl.

G7 fix IS effective for matching commands: /he → ▶ /help (PASS); /fork → ▶ /fork no /branch (PASS). G7 is incomplete only because catalog name ≠ command name for the plugin command.

## G12c — F-gamma-04

CONFIRMED NOT_CLOSED via aimock (independent of K-EXAONE timing):
- aimock triggered kma_short_term_forecast (auto-allowed, no grant)
- /consent list → 총 0건 · 0 receipts
- Disk: ~/.kosmos/memdir/user/consent/2026-05-05.jsonl = 524 lines

TUI loads empty receipt store at startup and does NOT sync prior-session disk records. Fix scope: ConsentReceiptsPanel must read from disk on open, OR receipt store seeded from disk at boot.

## G12d — deferred

F-beta-04 not executed. Pending G9 commit.
