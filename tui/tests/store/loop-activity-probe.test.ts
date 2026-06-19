import { beforeEach, describe, expect, it } from 'bun:test'
import {
  computeCurrentToolCallId,
  computeIsAgentLoopActive,
  dispatchSessionAction,
  getSessionSnapshot,
} from '../../src/store/session-store'
import type { Message } from '../../src/store/session-store'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetStore(): void {
  dispatchSessionAction({ type: 'SESSION_EVENT', event: 'new', payload: {} })
}

function snapshotMessages(): ReadonlyMap<string, Message> {
  return getSessionSnapshot().messages
}

describe('computeIsAgentLoopActive — derived probe (Spec 288 Codex P1)', () => {
  beforeEach(() => {
    resetStore()
  })

  it('returns true when a TOOL_CALL has no matching TOOL_RESULT yet', () => {
    dispatchSessionAction({
      type: 'ASSISTANT_CHUNK',
      message_id: 'assist-1',
      delta: 'calling a tool',
      done: true,
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'assist-1',
      tool_call: {
        call_id: 'call-a',
        name: 'koroad_accident_hazard_search',
        arguments: { region: 'seoul' },
      },
    })

    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(true)
    expect(computeCurrentToolCallId(messages)).toBe('call-a')
  })

  // -------------------------------------------------------------------------
  // Case 2 — an in-flight assistant chunk (done:false) is loop-active.
  // -------------------------------------------------------------------------
  it('returns true when an ASSISTANT_CHUNK is streaming (done:false)', () => {
    dispatchSessionAction({
      type: 'ASSISTANT_CHUNK',
      message_id: 'assist-2',
      delta: 'streaming...',
      done: false,
    })

    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(true)
    // No tool call was registered; the in-flight-tool-call probe stays null.
    expect(computeCurrentToolCallId(messages)).toBeNull()
  })

  // -------------------------------------------------------------------------
  // Case 3 — assistant done AND tool result returned means the loop is idle.
  // -------------------------------------------------------------------------
  it('returns false once ASSISTANT_CHUNK done:true and TOOL_RESULT has arrived', () => {
    dispatchSessionAction({
      type: 'USER_INPUT',
      message_id: 'user-1',
      text: 'hello',
    })
    dispatchSessionAction({
      type: 'ASSISTANT_CHUNK',
      message_id: 'assist-3',
      delta: 'response',
      done: true,
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'assist-3',
      tool_call: {
        call_id: 'call-b',
        name: 'kma_forecast_fetch',
        arguments: {},
      },
    })
    dispatchSessionAction({
      type: 'TOOL_RESULT',
      call_id: 'call-b',
      envelope: { ok: true },
    })

    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(false)
    expect(computeCurrentToolCallId(messages)).toBeNull()
  })

  it('returns true when a TOOL_CALL arrives before any ASSISTANT_CHUNK (Codex bug case)', () => {
    dispatchSessionAction({
      type: 'USER_INPUT',
      message_id: 'user-2',
      text: 'run a tool please',
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'msg-call-c',
      tool_call: {
        call_id: 'call-c',
        name: 'hira_hospital_search',
        arguments: { specialty: '내과' },
      },
    })

    const snap = getSessionSnapshot()
    expect(snap.messages.has('msg-call-c')).toBe(true)
    expect(snap.message_order).toContain('msg-call-c')

    // Derived probe sees the in-flight tool call via the map scan.
    expect(computeIsAgentLoopActive(snap.messages)).toBe(true)
    expect(computeCurrentToolCallId(snap.messages)).toBe('call-c')
  })

  it('render-orders a CIV-003 tool-call-only assistant after the prior Stage A turns', () => {
    const priorPrompts = [
      '작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘.',
      '개인사업자 부가세 신고해야 하는데 매출 자료 모아서 납부까지 진행해줘.',
      '아파트 팔았는데 양도소득세 얼마나 나오는지 계산하고 신고 절차까지 안내해줘.',
      '이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘.',
      '아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘.',
    ] as const

    priorPrompts.forEach((prompt, index) => {
      dispatchSessionAction({
        type: 'USER_INPUT',
        message_id: `user-prior-${index}`,
        text: prompt,
      })
      dispatchSessionAction({
        type: 'ASSISTANT_CHUNK',
        message_id: `assistant-prior-${index}`,
        delta: `prior visible answer ${index}`,
        done: true,
      })
    })
    dispatchSessionAction({
      type: 'USER_INPUT',
      message_id: 'user-civ003',
      text: '아버지가 돌아가셨어. 사망신고, 장례 지원, 국민연금 유족급여, 재산 관련 절차를 순서대로 알려줘.',
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'msg-call-civ003-bfc',
      tool_call: {
        call_id: 'call-civ003-bfc',
        name: 'bfc_funeral_area_fee',
        arguments: { page_no: 1, num_of_rows: 10 },
      },
    })

    const snap = getSessionSnapshot()
    expect(snap.messages.has('msg-call-civ003-bfc')).toBe(true)
    expect(snap.message_order).toContain('msg-call-civ003-bfc')
    expect(computeIsAgentLoopActive(snap.messages)).toBe(true)
    expect(computeCurrentToolCallId(snap.messages)).toBe('call-civ003-bfc')
  })

  // -------------------------------------------------------------------------
  // Empty-store sanity — brand-new session reports idle.
  // -------------------------------------------------------------------------
  it('returns false on a freshly reset store', () => {
    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(false)
    expect(computeCurrentToolCallId(messages)).toBeNull()
  })

  // -------------------------------------------------------------------------
  // User-only history (no assistant work yet) reports idle.
  // -------------------------------------------------------------------------
  it('returns false when only user messages exist', () => {
    dispatchSessionAction({
      type: 'USER_INPUT',
      message_id: 'user-3',
      text: 'hi',
    })

    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(false)
    expect(computeCurrentToolCallId(messages)).toBeNull()
  })

  // -------------------------------------------------------------------------
  // Multiple tool calls — the most recent pending one wins.
  // -------------------------------------------------------------------------
  it('returns the newest pending call_id when multiple tool calls are in flight', () => {
    dispatchSessionAction({
      type: 'ASSISTANT_CHUNK',
      message_id: 'assist-4',
      delta: 'chaining tools',
      done: true,
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'assist-4',
      tool_call: {
        call_id: 'call-x',
        name: 'koroad_accident_hazard_search',
        arguments: {},
      },
    })
    dispatchSessionAction({
      type: 'TOOL_CALL',
      message_id: 'assist-4',
      tool_call: {
        call_id: 'call-y',
        name: 'kma_forecast_fetch',
        arguments: {},
      },
    })

    const messages = snapshotMessages()
    expect(computeIsAgentLoopActive(messages)).toBe(true)
    // call-y was registered last → it is the in-flight id surfaced to
    // `agent-interrupt` for the cancellation envelope.
    expect(computeCurrentToolCallId(messages)).toBe('call-y')

    // Resolving call-y should expose call-x (still pending) as the next
    // in-flight id.
    dispatchSessionAction({
      type: 'TOOL_RESULT',
      call_id: 'call-y',
      envelope: { ok: true },
    })
    const afterY = snapshotMessages()
    expect(computeIsAgentLoopActive(afterY)).toBe(true)
    expect(computeCurrentToolCallId(afterY)).toBe('call-x')

    // Resolving call-x too drops the loop to idle.
    dispatchSessionAction({
      type: 'TOOL_RESULT',
      call_id: 'call-x',
      envelope: { ok: true },
    })
    const afterX = snapshotMessages()
    expect(computeIsAgentLoopActive(afterX)).toBe(false)
    expect(computeCurrentToolCallId(afterX)).toBeNull()
  })
})
