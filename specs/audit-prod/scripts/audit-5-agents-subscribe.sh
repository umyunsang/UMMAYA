# SPDX-License-Identifier: Apache-2.0
# audit-prod § Audit 5 — /agents + Ministry agent + Subscribe primitive integration
#
# Scope (cross-references):
#   - tui/src/commands/agents.tsx                        (resolveInitialEntries)
#   - tui/src/components/agents/AgentVisibilityPanel.tsx (worker_status subscription)
#   - tui/src/state/subscriptionRegistry.ts              (Lead-FU-5 process singleton)
#   - tui/src/tools/SubscribePrimitive/SubscribePrimitive.ts (call() → registry.record())
#   - tui/src/schemas/ui-l2/agent.ts                     (shouldActivateSwarm A+C union)
#   - src/kosmos/primitives/subscribe.py                  (4 modality drivers)
#   - src/kosmos/tools/mock/cbs/disaster_feed.py         (mock_cbs_disaster_v1)
#   - src/kosmos/tools/mock/data_go_kr/rss_notices.py    (mock_rss_public_notices_v1)
#   - src/kosmos/tools/mock/data_go_kr/rest_pull_tick.py (mock_rest_pull_tick_v1)
#   - src/kosmos/ipc/frame_schema.py:516                 (WorkerStatusFrame)
#
# Probe matrix (5 mandatory probe points per AGENTS.md):
#   1. Input ingress  — /agents + /agents --detail keystrokes (snap-* labels)
#   2. IPC frame      — chat_request, tool_call(subscribe), tool_result, [worker_status?]
#   3. Tool dispatch  — backend stdio.py:1806 subscribe primitive branch
#   4. Render commit  — tmux capture-pane snapshots at every transition
#   5. Snapshot       — /tmp/audit-5-agents/snap-NNN-*.txt + scrollback
#
# Helpers (from tui-tmux-capture.sh):
#   wait_for_pane <regex> [deadline_seconds=30]
#   snapshot_pane <label>
#   send_text_pane <text>
#   send_enter_pane
#   send_keys_pane <key1> [...]

set -uo pipefail

# ---------------------------------------------------------------------------
# Stage 0 — Boot + branding
# ---------------------------------------------------------------------------
wait_for_pane "KOSMOS|kosmos|external CLAUDE" 60 || true
snapshot_pane stage0-boot

# Auto-allow CLAUDE.md external imports prompt (1 = Yes), then onboarding Esc
send_text_pane '1'
send_enter_pane
sleep 1
send_keys_pane Escape
sleep 1
snapshot_pane stage0-post-esc

# ---------------------------------------------------------------------------
# Stage 1 — /agents BEFORE any subscribe call (empty-state baseline)
# Expected: "활성 부처 에이전트 없음"
# ---------------------------------------------------------------------------
send_text_pane '/agents'
send_enter_pane
wait_for_pane "0 agents|활성 부처 에이전트 없음" 30 || true
snapshot_pane stage1-agents-empty

# Esc dismiss — issue: AgentVisibilityPanel has NO useInput Esc handler
# (AgentVisibilityPanel.tsx:139-281 — handleSelect/onSelect missing).
# AgentsCommandView in commands/agents.tsx:117 owns the Esc, but the
# panel itself isn't unmounted. Documented as P0 BUG #1.
send_keys_pane Escape
sleep 1
snapshot_pane stage1-after-esc

# ---------------------------------------------------------------------------
# Stage 2 — /agents --detail BEFORE subscribe (empty-state with placeholder)
# Expected:
#   - column header "부처  상태  SLA  건강  평균응답"
#   - empty placeholder row "subscribe 도구 호출 시 여기에 활성 채널이 표시됩니다."
# This is the FU-5 fix per AgentVisibilityPanel.tsx:251-255
# ---------------------------------------------------------------------------
send_text_pane '/agents --detail'
send_enter_pane
wait_for_pane "부처|SLA|건강|평균응답" 30 || true
snapshot_pane stage2-detail-empty

# Esc dismiss
send_keys_pane Escape
sleep 1
snapshot_pane stage2-after-esc

# ---------------------------------------------------------------------------
# Stage 3 — Subscribe #1: CBS 재난방송 (mock_cbs_disaster_v1)
# Expected:
#   - LLM picks subscribe primitive with tool_id=mock_cbs_disaster_v1
#   - permission gauntlet asks (Layer ⓶) — citizen approves Y
#   - "구독 완료: <handle_id>" rendered with MessageResponse ⎿ prefix
#   - subscriptionRegistry.record() fires in SubscribePrimitive.call:367
# ---------------------------------------------------------------------------
send_text_pane '재난방송 CBS 긴급재난문자 알림 구독해줘'
send_enter_pane
# Wait for the permission modal title — must be unique to this turn.
wait_for_pane "구독 권한 요청|cbs_disaster|3GPP" 120 || true
snapshot_pane stage3-cbs-permission

# Approve permission — PermissionPrompt accepts numeric '1' (Y position)
# NOT the letter 'Y' (label is cosmetic; CustomSelect input.ts:257 only
# matches /^[0-9]+$/). This is documented in the audit findings.
send_text_pane '1'
sleep 3
wait_for_pane "구독 완료|subscription_id|opened|handle_id|구독 실패" 60 || true
snapshot_pane stage3-cbs-result

# ---------------------------------------------------------------------------
# Stage 4 — Subscribe #2: RSS 공공 공지 (mock_rss_public_notices_v1)
# ---------------------------------------------------------------------------
send_text_pane '공공 공지 RSS 정부 announcement 구독해줘'
send_enter_pane
wait_for_pane "구독 권한 요청|RSS|공지" 120 || true
snapshot_pane stage4-rss-permission

send_text_pane '1'
sleep 3
wait_for_pane "구독 완료|subscription_id|opened|handle_id|구독 실패" 60 || true
snapshot_pane stage4-rss-result

# ---------------------------------------------------------------------------
# Stage 5 — Subscribe #3: REST-pull 폴링 (mock_rest_pull_tick_v1)
# ---------------------------------------------------------------------------
send_text_pane 'REST 폴링 데이터고닷케이알 periodic 구독해줘'
send_enter_pane
wait_for_pane "구독 권한 요청|REST|폴링|polling" 120 || true
snapshot_pane stage5-rest-permission

send_text_pane '1'
sleep 3
wait_for_pane "구독 완료|subscription_id|opened|handle_id|구독 실패" 60 || true
snapshot_pane stage5-rest-result

# ---------------------------------------------------------------------------
# Stage 6 — /agents AFTER 3 subscribe calls
# Expected:
#   - 3 entries with "subscribe:<handle_id>" agent_id pattern
#   - ministry derived from tool_id prefix (CBS / DATA_GO_KR for the latter 2)
#     deriveMinistryFromToolId in subscriptionRegistry.ts:101
#   - state="running" / health="green" (subscriptionRegistry default)
# ---------------------------------------------------------------------------
send_text_pane '/agents'
send_enter_pane
wait_for_pane "agents|CBS|DATA|MOCK|3 agents|subscribe" 30 || true
snapshot_pane stage6-agents-after-3-subs

send_keys_pane Escape
sleep 1
snapshot_pane stage6-after-esc

# ---------------------------------------------------------------------------
# Stage 7 — /agents --detail AFTER 3 subs (SLA / 건강 / 평균응답 columns)
# Expected:
#   - SLA shows "—" (sla_remaining_ms=null in resolveInitialEntries)
#   - 건강 shows "green"
#   - 평균응답 shows "—" (rolling_avg_response_ms=null)
# ---------------------------------------------------------------------------
send_text_pane '/agents --detail'
send_enter_pane
wait_for_pane "SLA|건강|평균응답|green|—|3 agents" 30 || true
snapshot_pane stage7-detail-after-3-subs

send_keys_pane Escape
sleep 1
snapshot_pane stage7-after-esc

# ---------------------------------------------------------------------------
# Stage 8 — Swarm threshold trigger (UI-D.2 A+C: 3+ ministries OR complex tag)
# This sentence mentions 4 explicit ministries (KMA · KOROAD · NMC · NFA119).
# Expected:
#   - shouldActivateSwarm() should return true (distinct.size >= 3)
#   - But: REPL.tsx imports shouldActivateSwarm and never calls it
#     (verified by grep -c "shouldActivateSwarm" tui/src/screens/REPL.tsx == 1)
#   - So the swarm "activated" banner from i18n/uiL2.ts:138 should NOT appear
# This snapshot documents the dead-code wiring.
# ---------------------------------------------------------------------------
send_text_pane '서울에 폭우 경보·119 출동·교통사고·응급실 현황 한꺼번에 알려줘'
send_enter_pane
wait_for_pane "Swarm|swarm|활성화|complex|복잡|kma|koroad|nmc|nfa" 60 || true
snapshot_pane stage8-swarm-threshold-attempt
sleep 3
snapshot_pane stage8-swarm-threshold-after-3s

# ---------------------------------------------------------------------------
# Stage 9 — Final exit
# ---------------------------------------------------------------------------
send_text_pane '/exit'
send_enter_pane
sleep 2
snapshot_pane stage9-final
