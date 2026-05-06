#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Generic real-use scenario for one target-state AX citizen request.
# Sourced by scripts/tui-tmux-capture.sh.
#
# Required env:
#   KOSMOS_REALUSE_PROMPT
# Optional env:
#   KOSMOS_REALUSE_LABEL
#   KOSMOS_REALUSE_EXPECT
#   KOSMOS_REALUSE_LOCATION_CONTEXT
#   KOSMOS_REALUSE_AUTO_ALLOW_PERMISSIONS=1

: "${KOSMOS_REALUSE_PROMPT:?KOSMOS_REALUSE_PROMPT is required}"

__label="${KOSMOS_REALUSE_LABEL:-target-state}"
__expect="${KOSMOS_REALUSE_EXPECT:-locate|find|auth|send|watch|resolve_location|lookup|verify|submit|subscribe|Permission|권한|확인|조회|신청|제출|안내|handoff|공식|오류|error}"
__prompt="$KOSMOS_REALUSE_PROMPT"
__active_spinner_re="^[[:space:]]*[^[:alnum:][:space:]][[:space:]]+[[:alpha:]][[:alpha:]'’/-]*…[[:space:]]*\\([0-9]+(ms|s|m|h)"
if [[ -n "${KOSMOS_REALUSE_LOCATION_CONTEXT:-}" ]]; then
  __prompt="현재 위치는 ${KOSMOS_REALUSE_LOCATION_CONTEXT}입니다. ${__prompt}"
fi

wait_for_pane "tool_registry: [0-9]+ entries verified" 60
wait_for_pane "KOSMOS" 30
snapshot_pane "${__label}-boot"

send_text_pane "$__prompt"
sleep 0.5
send_enter_pane
snapshot_pane "${__label}-input-submitted"

wait_for_pane "$__expect" 180 || true
snapshot_pane "${__label}-first-observable"

__permission_round=0
allow_visible_permission() {
  if [[ "${KOSMOS_REALUSE_AUTO_ALLOW_PERMISSIONS:-0}" != "1" ]]; then
    return 1
  fi
  if (( __permission_round >= 12 )); then
    return 1
  fi
  local pane
  pane="$(tmux capture-pane -t "$TMUX_SESSION" -p)"
  if ! grep -qE "권한 요청|Permission request|실행을 허용|허용하시겠습니까|Do you want to proceed\\?|Esc to cancel · Tab to amend" <<<"$pane"; then
    return 1
  fi
  snapshot_pane "${__label}-permission-${__permission_round}-before-allow"
  send_enter_pane
  sleep 0.5
  snapshot_pane "${__label}-permission-${__permission_round}-after-allow"
  __permission_round=$((__permission_round + 1))
  return 0
}

if [[ "${KOSMOS_REALUSE_AUTO_ALLOW_PERMISSIONS:-0}" == "1" ]]; then
  while allow_visible_permission; do
    wait_for_pane "$__expect" 180 || true
  done
fi

__prev=""
__stable_start=$(date +%s)
__settle_deadline=$(( $(date +%s) + 300 ))
while (( $(date +%s) < __settle_deadline )); do
  if allow_visible_permission; then
    __prev=""
    __stable_start=$(date +%s)
    continue
  fi
  __cur=$(tmux capture-pane -t "$TMUX_SESSION" -p)
  if [[ "$__cur" != "$__prev" ]]; then
    __prev="$__cur"
    __stable_start=$(date +%s)
  fi
  if grep -qE "$__active_spinner_re" <<<"$__cur"; then
    __stable_start=$(date +%s)
  fi
  if (( $(date +%s) - __stable_start >= 5 )); then break; fi
  sleep 0.5
done

snapshot_pane "${__label}-stable"
tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 > "$OUTDIR/final-scrollback.txt" 2>/dev/null || true

if tmux capture-pane -t "$TMUX_SESSION" -p -S -10000 | grep -qE "네트워크 오류|활성 부처 에이전트|0 agents|Cannot find module|TungstenTool|permission_timeout|$__active_spinner_re"; then
  echo "::error::Forbidden real-use UI/backend pattern rendered" >&2
  snapshot_pane "${__label}-forbidden-pattern"
  exit 1
fi
