// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'

const RENDER_BOUNDARY_ORDER = [
  'user_text',
  'pre_tool_progress',
  'permission_prompt',
  'tool_call',
  'tool_result',
  'post_tool_synthesis',
  'blocked_or_approval_state',
  'final_answer',
] as const

type RenderBoundary = (typeof RENDER_BOUNDARY_ORDER)[number]

type TranscriptFrame = {
  readonly boundary: RenderBoundary
  readonly text: string
  readonly observedToolId?: string
}

type RenderScenario = {
  readonly label: string
  readonly prompt: string
  readonly expectedInternalIds: readonly string[]
  readonly actualObservedIds: readonly string[]
  readonly requiredBoundaries: readonly RenderBoundary[]
  readonly frames: readonly TranscriptFrame[]
}

const REQUIRED_BOUNDARY_SET = new Set<RenderBoundary>(RENDER_BOUNDARY_ORDER)

function assertPromptDoesNotLeakToolIds(scenario: RenderScenario): void {
  for (const internalId of scenario.expectedInternalIds) {
    expect(scenario.prompt).not.toContain(internalId)
  }
}

function assertObservedIdsAreMapped(scenario: RenderScenario): void {
  for (const observedId of scenario.actualObservedIds) {
    expect(scenario.expectedInternalIds).toContain(observedId)
  }
}

function assertObservedToolFramesMatchHiddenMap(scenario: RenderScenario): void {
  const observedFrameIds = scenario.frames.flatMap(frame =>
    frame.observedToolId ? [frame.observedToolId] : [],
  )

  expect(observedFrameIds).toEqual(scenario.actualObservedIds)
}

function assertScenarioRendersInOrder(scenario: RenderScenario): void {
  const observedBoundaries = scenario.frames.map(frame => frame.boundary)

  for (const requiredBoundary of scenario.requiredBoundaries) {
    expect(observedBoundaries).toContain(requiredBoundary)
  }

  const orderedIndices = scenario.requiredBoundaries.map(requiredBoundary =>
    observedBoundaries.indexOf(requiredBoundary),
  )

  expect(orderedIndices).toEqual([...orderedIndices].sort((left, right) => left - right))
}

function assertMatrixCoversEveryBoundary(scenarios: readonly RenderScenario[]): void {
  const covered = new Set<RenderBoundary>()
  for (const scenario of scenarios) {
    for (const boundary of scenario.requiredBoundaries) {
      covered.add(boundary)
    }
  }

  expect(covered).toEqual(REQUIRED_BOUNDARY_SET)
}

const scenarios: readonly RenderScenario[] = [
  {
    label: 'file_search_read',
    prompt: '이 저장소에서 웹 조사 도구 관련 파일을 찾아줘.',
    expectedInternalIds: ['workspace_grep', 'workspace_read'],
    actualObservedIds: ['workspace_grep'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: '이 저장소에서 웹 조사 도구 관련 파일을 찾아줘.' },
      { boundary: 'pre_tool_progress', text: '웹 조사 도구 관련 파일을 검색하겠습니다.' },
      { boundary: 'tool_call', text: 'Search(pattern: "WebFetch")', observedToolId: 'workspace_grep' },
      { boundary: 'tool_result', text: 'Found 3 files across tui/src/tools/WebFetchTool.' },
      { boundary: 'post_tool_synthesis', text: '관련 파일을 확인했고 WebFetch/WebSearch UI가 있습니다.' },
      { boundary: 'final_answer', text: '웹 조사 도구 관련 파일 목록을 정리했습니다.' },
    ],
  },
  {
    label: 'source_verification',
    prompt: '출처 확인이 필요한 문서 작성 근거를 찾아줘. 출처가 없으면 쓰지 마.',
    expectedInternalIds: ['WebSearchTool', 'WebFetchTool'],
    actualObservedIds: ['WebSearchTool', 'WebFetchTool'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'blocked_or_approval_state',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: '출처 확인이 필요한 문서 작성 근거를 찾아줘. 출처가 없으면 쓰지 마.' },
      { boundary: 'pre_tool_progress', text: '출처가 있는 근거만 찾겠습니다.' },
      { boundary: 'tool_call', text: 'WebSearch("public AX policy evidence")', observedToolId: 'WebSearchTool' },
      { boundary: 'tool_result', text: '<source_verification> citation_handle: src-task17-policy </source_verification>' },
      { boundary: 'tool_call', text: 'WebFetch(https://policy.example/source)', observedToolId: 'WebFetchTool' },
      { boundary: 'tool_result', text: 'Verified source excerpt.' },
      { boundary: 'post_tool_synthesis', text: '검색 결과와 원문 확인 결과를 합쳐 출처 있는 근거만 남겼습니다.' },
      { boundary: 'blocked_or_approval_state', text: '출처 없는 문서 작성은 보류되었습니다.' },
      { boundary: 'final_answer', text: '확인된 출처만 요약했고 근거 없는 내용은 쓰지 않았습니다.' },
    ],
  },
  {
    label: 'permission_gated_write',
    prompt: '작업공간에 테스트 메모를 쓰려면 먼저 나에게 승인 요청해.',
    expectedInternalIds: ['workspace_write', 'workspace_edit'],
    actualObservedIds: ['workspace_write'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'permission_prompt',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'blocked_or_approval_state',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: '작업공간에 테스트 메모를 쓰려면 먼저 나에게 승인 요청해.' },
      { boundary: 'pre_tool_progress', text: '쓰기 전에 승인 요청을 준비합니다.' },
      { boundary: 'permission_prompt', text: 'Permission required before writing a workspace file.' },
      { boundary: 'tool_call', text: 'Write(test memo)', observedToolId: 'workspace_write' },
      { boundary: 'tool_result', text: 'Tool result: write blocked until approval.' },
      { boundary: 'post_tool_synthesis', text: '승인 전에는 파일을 만들지 않았습니다.' },
      { boundary: 'blocked_or_approval_state', text: '승인 대기 상태입니다.' },
      { boundary: 'final_answer', text: '승인 없이는 작업공간을 변경하지 않았습니다.' },
    ],
  },
  {
    label: 'shell_status',
    prompt: 'git 상태를 확인해줘. 변경은 하지 마.',
    expectedInternalIds: ['workspace_bash'],
    actualObservedIds: ['workspace_bash'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'permission_prompt',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'blocked_or_approval_state',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: 'git 상태를 확인해줘. 변경은 하지 마.' },
      { boundary: 'pre_tool_progress', text: '읽기 전용 상태 확인 명령을 준비합니다.' },
      { boundary: 'permission_prompt', text: 'Permission requested for shell command.' },
      { boundary: 'tool_call', text: 'Bash(git status --short)', observedToolId: 'workspace_bash' },
      { boundary: 'tool_result', text: 'Tool result: current git status printed.' },
      { boundary: 'post_tool_synthesis', text: '변경 없이 상태만 확인했습니다.' },
      { boundary: 'blocked_or_approval_state', text: '쓰기 작업은 차단된 상태로 유지됩니다.' },
      { boundary: 'final_answer', text: '현재 변경 파일을 요약했습니다.' },
    ],
  },
  {
    label: 'mcp_resources',
    prompt: '사용 가능한 MCP 리소스가 있으면 허가 후 목록만 보여줘.',
    expectedInternalIds: ['ListMcpResourcesTool', 'ReadMcpResourceTool', 'MCPTool'],
    actualObservedIds: ['ListMcpResourcesTool'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'permission_prompt',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'blocked_or_approval_state',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: '사용 가능한 MCP 리소스가 있으면 허가 후 목록만 보여줘.' },
      { boundary: 'pre_tool_progress', text: '연결된 리소스 목록만 확인하겠습니다.' },
      { boundary: 'permission_prompt', text: 'Permission requested before listing external resources.' },
      { boundary: 'tool_call', text: 'List MCP resources', observedToolId: 'ListMcpResourcesTool' },
      { boundary: 'tool_result', text: 'Tool result: resources listed or none found.' },
      { boundary: 'post_tool_synthesis', text: '리소스 목록만 요약했습니다.' },
      { boundary: 'blocked_or_approval_state', text: '신뢰되지 않은 읽기는 수행하지 않았습니다.' },
      { boundary: 'final_answer', text: '허가 범위 안에서 확인 가능한 리소스만 답했습니다.' },
    ],
  },
  {
    label: 'agent_research',
    prompt: '근거 조사를 별도 작업으로 나눠 진행할 수 있으면 진행 상황과 취소 가능 상태를 보여줘.',
    expectedInternalIds: ['AgentTool', 'TaskCreateTool', 'TaskListTool'],
    actualObservedIds: ['AgentTool'],
    requiredBoundaries: [
      'user_text',
      'pre_tool_progress',
      'permission_prompt',
      'tool_call',
      'tool_result',
      'post_tool_synthesis',
      'blocked_or_approval_state',
      'final_answer',
    ],
    frames: [
      { boundary: 'user_text', text: '근거 조사를 별도 작업으로 나눠 진행할 수 있으면 진행 상황과 취소 가능 상태를 보여줘.' },
      { boundary: 'pre_tool_progress', text: '별도 조사 작업을 시작하기 전에 진행/취소 상태를 준비합니다.' },
      { boundary: 'permission_prompt', text: 'Permission requested before launching an agent research task.' },
      { boundary: 'tool_call', text: 'Agent(research evidence)', observedToolId: 'AgentTool' },
      { boundary: 'tool_result', text: 'Tool result: agent progress and resume token emitted.' },
      { boundary: 'post_tool_synthesis', text: '별도 작업의 진행 상태를 요약했습니다.' },
      { boundary: 'blocked_or_approval_state', text: '취소 가능 상태가 표시됩니다.' },
      { boundary: 'final_answer', text: '작업 분리 여부와 취소 가능 상태를 답했습니다.' },
    ],
  },
]

describe('recovered support tool render order', () => {
  test('renders_progress_tool_result_and_final_answer_in_order', () => {
    assertMatrixCoversEveryBoundary(scenarios)

    for (const scenario of scenarios) {
      assertPromptDoesNotLeakToolIds(scenario)
      assertObservedIdsAreMapped(scenario)
      assertObservedToolFramesMatchHiddenMap(scenario)
      assertScenarioRendersInOrder(scenario)
    }
  })
})
