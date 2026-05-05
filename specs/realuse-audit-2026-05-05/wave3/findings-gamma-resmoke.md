# Wave-3 γ-domain Re-smoke Report

> Agent: Wave-3 re-smoke γ · HEAD: `995b88bb` · Date: 2026-05-05

## Verdicts

| Finding | Fix | Verdict |
|---|---|---|
| F-gamma-01 | G3 — slot unblock | CLOSED |
| F-gamma-02 | G3 — wontfix | WONTFIX |
| F-gamma-04 | G3 — indirect | PARTIAL |
| F-gamma-05 | G3 — downstream F-01 | CLOSED |
| F-gamma-06 | G3 — Tier-1 handler | PARTIAL |
| F-gamma-07 | G1 — PIPA directive | CLOSED |

## Evidence per Finding

### F-gamma-01 CLOSED
- γ1-Y snap-003: permission modal shown (한 번만 허용)
- γ1-Y snap-006: Beaming... (dispatch started immediately post-Y)
- γ-combined snap-002: Razzmatazzing... after Y
- Wave-1: slot blocked 300s. Now: resolves same tick (G3 fix ipcPermissionBridge.ts:185 resolvePermissionDecision)

### F-gamma-02 WONTFIX-BY-DESIGN
- γ1 (verify): ⓵ 낮은 위험 correct
- γ5 (subscribe): ⓶ 중간 위험 correct per aalToLayer.ts (Spec 2294 SSOT)

### F-gamma-04 PARTIAL
- γ6 standalone: 0 receipts (fresh session, no prior grants)
- γ-combined: 0 receipts when checked while K-EXAONE still reasoning
- Root: receipt watcher fires on backend echo (arrives only after K-EXAONE ~60s); disk receipts confirmed (2026-05-05.jsonl 582 lines)
- Needs: aimock-based test or longer wait window to confirm TUI in-memory receipt

### F-gamma-05 CLOSED
- Downstream of F-gamma-01: renderer now reachable because slot unblocked
- VerifyPrimitive.renderToolResultMessage banner path confirmed by G3 unit tests

### F-gamma-06 PARTIAL
- γ8 snap-001: ● high · /effort (default)
- γ8 snap-002: Use meta+t to toggle thinking (mode changed after S-Tab)
- γ8 snap-003: ● high · /effort (alternates)
- Shift+Tab delivered to Ink (escape-time=0 effective). Mode cycles. bypassPermissions banner not observable in this window — deferred to Bun PTY harness follow-up.

### F-gamma-07 CLOSED
- γ9 snap-005: verify(mock_verify_mobile_id) dispatched, NOT RRN solicited
- K-EXAONE reasoning explicitly processed RRN request and routed to secure modal
- pytest tests/llm/test_g1_pipa_safety_directive.py: 12/12 passed

## No New Regressions
