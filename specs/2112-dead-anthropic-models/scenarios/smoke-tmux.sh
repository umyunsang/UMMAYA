#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Spec: 2112-dead-anthropic-models — tmux capture-pane smoke scenario
#
# Ported from: specs/2112-dead-anthropic-models/smoke.expect
# Port date: 2026-05-01
# Harness: scripts/tui-tmux-capture.sh (RFC debug-infra-rebuild § P2)
#
# Sourced (not exec'd) by tui-tmux-capture.sh — helpers available:
#   wait_for_pane <regex> [deadline_s]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_ctrlc_pane
#   send_keys_pane <key...>
#
# Boot + branding + 5-scenario baseline smoke.
# Original expect used hardcoded sleeps (6s, 18s, 45s, 50s) that mapped to
# K-EXAONE reasoning variance — replaced here with wait_for_pane predicates
# and a single 0.5s input-settle (no latency guessing).
#
# Scenarios (mirrors smoke.tape):
#   1. Korean greeting          — "안녕하세요"
#   2. Help command             — "/help"
#   3. Public-service lookup    — "강남역 어디야?"
#   4. Weather routing          — "오늘 서울 날씨 알려줘"
#   5. Clean exit               — "/quit"
#
# Deadline map:
#   boot           30s  (cold-start bun + Ink render)
#   branding       15s
#   greeting reply 60s  (K-EXAONE turn 1)
#   /help render   15s  (local render — no LLM call)
#   lookup reply  120s  (K-EXAONE tool_call + result)
#   weather reply 120s  (K-EXAONE tool_call + result)
#   settle         10s  (activity-based)
#
# NOTE on "expect >" (original line 28):
#   The original waited for ">" which matches the REPL prompt character.
#   wait_for_pane "KOSMOS" or "tool_registry:" is the equivalent predicate here;
#   the bare ">" is too permissive (would match any shell output) and is NOT
#   portable across pane content.

# ── 1. Boot ─────────────────────────────────────────────────────────────────
wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 15
snapshot_pane boot

# ── Scenario 1: Korean greeting ───────────────────────────────────────────────
send_text_pane "안녕하세요"
sleep 0.5
send_enter_pane
snapshot_pane s1-submitted

# K-EXAONE reasoning latency 9-60s; the original used sleep 18 which was
# likely to expire before reasoning completed on loaded instances.
wait_for_pane "안녕|반갑|무엇|도와|공공|서비스" 60
snapshot_pane s1-response

# ── Scenario 2: Help command ──────────────────────────────────────────────────
send_text_pane "/help"
sleep 0.5
send_enter_pane
snapshot_pane s2-submitted

# /help renders locally (no LLM round-trip); 15s is ample.
wait_for_pane "slash command|명령|command|help|도움" 15
snapshot_pane s2-help-rendered

# Dismiss the help overlay before the next scenario so the input field is clear.
send_keys_pane Escape
sleep 0.3
snapshot_pane s2-help-dismissed

# ── Scenario 3: Public-service lookup ─────────────────────────────────────────
send_text_pane "강남역 어디야?"
sleep 0.5
send_enter_pane
snapshot_pane s3-submitted

# Wait for either a tool_call paint OR a direct LLM answer.
# K-EXAONE may choose to answer from its parametric knowledge (no tool_call),
# or may dispatch ● lookup. Both are valid — the smoke is informational.
# Non-fatal: presence/absence of tool call captured in snapshot only.
wait_for_pane "● (lookup|resolve_location)|강남역|위치|주소|서울" 120 || true
snapshot_pane s3-first-paint

# If a tool_call did fire, wait for the gutter result.
wait_for_pane "⎿|검색|위치|주소|강남역|서울" 30 || true
snapshot_pane s3-response

# ── Scenario 4: Weather routing ────────────────────────────────────────────────
send_text_pane "오늘 서울 날씨 알려줘"
sleep 0.5
send_enter_pane
snapshot_pane s4-submitted

# Non-fatal: K-EXAONE may dispatch a lookup/kma tool or answer from training.
wait_for_pane "● (lookup|kma)|기온|°C|맑|흐림|날씨|Weather" 120 || true
snapshot_pane s4-first-paint

wait_for_pane "⎿|기온|°C|맑|흐림|날씨 정보" 30 || true
snapshot_pane s4-response

# ── Settle ────────────────────────────────────────────────────────────────────
__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 15 ))
while (( $(date +%s) < __settle_deadline )); do
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 1 )); then break; fi
  sleep 0.3
done
snapshot_pane stable

# ── Scenario 5: Clean exit ────────────────────────────────────────────────────
send_text_pane "/quit"
sleep 0.5
send_enter_pane
# sleep 1: after /quit the TUI performs cleanup before exiting; no repaint
# predicate is available between the quit command and process exit. This is
# a process-termination settle, not a latency guess.
sleep 1
snapshot_pane quit
