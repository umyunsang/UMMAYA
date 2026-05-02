# Debug-infra-rebuild — proof runs

Captured outputs from the new tmux capture-pane harness verifying that
the rebuilt infrastructure detects regressions the legacy
asciinema-in-asciinema setup hid behind 90 s timeouts.

## busan-weather (2026-05-02)

Scenario: `specs/debug-infra-rebuild/scenarios/busan-weather.sh`
Harness: `scripts/tui-tmux-capture.sh`

**Timeline (from `wait_for_pane MATCH` log):**

| Stage | wall-clock | predicate |
|---|---|---|
| boot | 1 s | `tool_registry: [0-9]+ entries verified` |
| branding | 0 s | `KOSMOS` |
| first tool_call | **8 s** | `● lookup` |
| result/error/answer | 0 s | `⎿\|검색 오류\|invalid\|기온\|°C\|구름\|맑\|흐림` |

**Comparison vs legacy harness** (asciinema + expect + pyte):

| Harness | Behavior on this scenario | Outcome |
|---|---|---|
| Legacy `tui-text-debug.sh` | 90 s timeout, never matched `● lookup`, only `Cooking…` spinner | False negative — claimed TUI was hung |
| New `tui-tmux-capture.sh` | 8 s match on real tool_call paint | True positive — captured exact regression |

**Findings unblocked by the new infrastructure:**

1. ✅ Multi-tool layout fix (`parallel_tool_calls=False` + frontend
   suppressTopMargin) confirmed working — single `● lookup` per turn,
   ReAct order (Thinking → tool_call → result).
2. ❌ **Schema visibility fix did NOT solve invalid_params** —
   `snap-003-after-result.txt` line 12 shows
   `⎿  검색 오류: Invalid parameters for tool.`. K-EXAONE still calls
   `kma_short_term_forecast` with mis-formatted params despite the
   `<available_adapters>` schema dump being in the system prompt.
   This was previously hidden by 90 s timeouts. **Next investigation
   target.**

**Why this matters:** the legacy harness gave false confidence that
fixes worked because it timed out before regressions could surface. The
new harness gives ground truth in 8 s instead of 90 s and reproduces the
user's interactive environment exactly (no PTY-in-PTY race).
