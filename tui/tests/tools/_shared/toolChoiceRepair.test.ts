// SPDX-License-Identifier: Apache-2.0

import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Tools } from '../../../src/Tool.js'
import type { Message } from '../../../src/types/message.js'
import {
  backfillUmmayaObservableToolInputFromUserQuery,
  buildDocumentCompletionPromptIfNeeded,
  repairUmmayaExplicitDocumentToolUseFromUserQuery,
  selectUmmayaToolChoiceOverride,
  selectUmmayaClientForcedToolUse,
  shouldCompleteAfterSuccessfulDocumentRender,
  shouldCompleteAfterTerminalDocumentToolResult,
  shouldSuppressUmmayaToolCallsForAnswerSynthesis,
} from '../../../src/tools/_shared/toolChoiceRepair.js'

const TUI_ROOT = join(import.meta.dir, '../../..')

const docQuery =
  '이 HWPX 문서를 13주차로 작성하고 compact diff로 변경사항을 보여줘: /Users/example/주간활동일지.hwpx'

const documentTools = [
  'document',
].map(name => ({ name })) as Tools

const documentAndGlobTools = [
  'document',
  'workspace_glob',
].map(name => ({ name })) as Tools

const documentAndLegacyGlobTools = [
  'document',
  'Glob',
].map(name => ({ name })) as Tools

const toolSearchOnlyTools = [{ name: 'ToolSearch' }] as Tools

function user(text: string): Message {
  return {
    type: 'user',
    message: { role: 'user', content: text },
  } as Message
}

function toolUse(id: string, name: string, input: Record<string, unknown> = {}): Message {
  return {
    type: 'assistant',
    message: {
      role: 'assistant',
      content: [{ type: 'tool_use', id, name, input }],
    },
  } as Message
}

function toolResult(id: string, payload: Record<string, unknown>): Message {
  return {
    type: 'user',
    message: {
      role: 'user',
      content: [
        {
          type: 'tool_result',
          tool_use_id: id,
          content: JSON.stringify({ ok: true, result: payload }),
        },
      ],
    },
  } as Message
}

describe('document harness tool-choice repair', () => {
  test('starts local HWPX write/diff requests with the document primitive', () => {
    expect(
      selectUmmayaToolChoiceOverride({
        messages: [user(docQuery)],
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
  })

  test('routes explicit current-session artifact render requests to the document primitive', () => {
    expect(
      selectUmmayaToolChoiceOverride({
        messages: [
          user(
            '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘.',
          ),
        ],
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
  })

  test('keeps visual diff wording on the document primitive', () => {
    expect(
      selectUmmayaToolChoiceOverride({
        messages: [
          user(
            '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 실제 document_render 결과 카드가 Minimap / Before viewport / After viewport / Changes 구조와 빨간/초록 변경 박스로 화면에 붙어야 해.',
          ),
        ],
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
  })

  test('does not synthesize incomplete document arguments when the primitive is available', () => {
    const messages = [
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘.',
      ),
      toolUse('render-1', 'document_render'),
      toolResult('render-1', { tool_id: 'document_render', status: 'ok' }),
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 실제 document_render 결과 카드가 Minimap / Before viewport / After viewport / Changes 구조와 빨간/초록 변경 박스로 화면에 붙어야 해.',
      ),
      toolUse('copy-1', 'document_copy_for_edit'),
      toolResult('copy-1', { tool_id: 'document_copy_for_edit', status: 'timeout', ok: false }),
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 실제 document_render 결과 카드가 Minimap / Before viewport / After viewport / Changes 구조와 빨간/초록 변경 박스로 화면에 붙어야 해.',
      ),
    ]

    expect(selectUmmayaClientForcedToolUse({ messages, tools: documentTools })).toBeUndefined()
  })

  test('routes deferred document requests through ToolSearch before prose fallback', () => {
    const messages = [
      user(
        '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 작성이 끝나면 원본과 달라진 부분을 문서 화면으로 비교해서 보여줘.',
      ),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages,
        tools: toolSearchOnlyTools,
      }),
    ).toEqual({ type: 'tool', name: 'ToolSearch' })
    expect(selectUmmayaClientForcedToolUse({ messages, tools: toolSearchOnlyTools })).toEqual({
      name: 'ToolSearch',
      input: {
        query: 'select:document',
        max_results: 1,
      },
    })
  })

  test('does not bypass model intent analysis for Downloads HWPX edit requests', () => {
    const messages = [
      user(
        '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 활동기간은 2026.06.01부터 2026.06.07까지고, 작성이 끝나면 원본과 달라진 부분을 문서 화면으로 비교해서 보여줘.',
      ),
    ]

    expect(selectUmmayaClientForcedToolUse({ messages, tools: documentTools })).toBeUndefined()
  })

  test('client-forces the document primitive when provider ignores tool_choice for an explicit local path', () => {
    const prompt =
      '웹에서 받은 서울문화포털 DDP 참가신청서 DOCX 사본 /tmp/ummaya-g011-live-tui/inputs/seoul-culture-application-plan.docx 내용을 파악해서 접수번호 옆 빈칸에 UMMAYA-G011-2026을 넣고, 그 칸을 Malgun Gothic 12pt 굵게, 글자색 1F4E79, 배경색 FFF2CC, 가운데 정렬로 보정한 뒤 /tmp/ummaya-g011-live-tui/tui-exports/g011-seoul-culture-application-plan.docx 로 저장해줘. 수정 후 변경된 부분을 바로 확인할 수 있게 보여줘.'
    const messages = [
      user(prompt),
      {
        type: 'assistant',
        message: {
          role: 'assistant',
          content: [
            {
              type: 'text',
              text: '문서 구조를 파악한 뒤 document 도구를 호출하겠습니다.',
            },
          ],
        },
      } as Message,
    ]

    expect(selectUmmayaClientForcedToolUse({ messages, tools: documentTools })).toEqual({
      name: 'document',
      input: {
        correlation_id: expect.stringMatching(/^client-forced-document-[a-f0-9]{8}$/),
        document: {
          path: '/tmp/ummaya-g011-live-tui/inputs/seoul-culture-application-plan.docx',
          expected_format: 'docx',
        },
        operation: 'fill',
        instruction: prompt,
        destination_path:
          '/tmp/ummaya-g011-live-tui/tui-exports/g011-seoul-culture-application-plan.docx',
      },
    })
  })

  test('repairs non-document tool calls when the latest user turn has an explicit document path', () => {
    const prompt =
      '공식 국세청 사업자등록신청서 파일을 내용에 맞게 알아서 채워줘. 원본은 건드리지 말고 검토 가능한 복사본으로 만들어줘: /Users/example/nts_business_registration_individual.hwpx'

    expect(
      repairUmmayaExplicitDocumentToolUseFromUserQuery({
        toolName: 'tago_bus_station_search',
        input: {
          city_code: '21',
          node_nm: '/Users/example/nts_business_registration_individual.hwpx',
        },
        messages: [user(prompt)],
        tools: documentTools,
      }),
    ).toEqual({
      name: 'document',
      input: {
        correlation_id: expect.stringMatching(/^client-forced-document-[a-f0-9]{8}$/),
        document: {
          path: '/Users/example/nts_business_registration_individual.hwpx',
          expected_format: 'hwpx',
        },
        operation: 'fill',
        instruction: prompt,
      },
    })
  })

  test('keeps explicit read-only document requests on inspect without display fill backfill', () => {
    const prompt =
      '수정 없이 열람만 해줘. 양식의 문서 제목과 작성해야 할 항목명만 알려줘: /Users/example/nts_business_registration_individual.hwpx'
    const input: Record<string, unknown> = {
      correlation_id: 'read-only-document',
      document: {
        path: '/Users/example/nts_business_registration_individual.hwpx',
        expected_format: 'hwpx',
      },
      operation: 'inspect',
      instruction: '문서 제목과 작성해야 할 항목명만 추출해주세요.',
    }

    expect(selectUmmayaToolChoiceOverride({
      messages: [user(prompt)],
      tools: documentTools,
    })).toEqual({ type: 'tool', name: 'document' })
    expect(selectUmmayaClientForcedToolUse({
      messages: [user(prompt)],
      tools: documentTools,
    })?.input.operation).toBe('inspect')

    backfillUmmayaObservableToolInputFromUserQuery({
      toolName: 'document',
      input,
      messages: [user(prompt)],
    })

    expect(input.__ummaya_display_operation).toBeUndefined()
  })

  test('keeps write requests as fill when the user asks to be told the saved path', () => {
    const prompt =
      '이 양식을 채워줘. 저장 경로만 알려줘: /Users/example/nts_business_registration_individual.hwpx'

    expect(selectUmmayaClientForcedToolUse({
      messages: [user(prompt)],
      tools: documentTools,
    })?.input.operation).toBe('fill')
  })

  test('repairs provider document fill calls back to inspect for explicit read-only requests', () => {
    const prompt =
      '수정 없이 열람만 해줘. 이 공식 국세청 사업자등록신청서 파일의 문서 제목과 작성해야 할 항목명만 알려줘: /Users/example/nts_business_registration_individual.hwp'

    expect(
      repairUmmayaExplicitDocumentToolUseFromUserQuery({
        toolName: 'document',
        input: {
          correlation_id: 'provider-readonly-misfire',
          document: {
            path: '/Users/example/nts_business_registration_individual.hwp',
            expected_format: 'hwp',
          },
          operation: 'fill',
          instruction: prompt,
        },
        messages: [user(prompt)],
        tools: documentTools,
      }),
    ).toEqual({
      name: 'document',
      input: {
        correlation_id: expect.stringMatching(/^client-forced-document-[a-f0-9]{8}$/),
        document: {
          path: '/Users/example/nts_business_registration_individual.hwp',
          expected_format: 'hwp',
        },
        operation: 'inspect',
        instruction: prompt,
      },
    })
  })

  test('backfills observable document operation for provider inspect calls on explicit write requests', () => {
    const prompt =
      '웹에서 받은 서울문화포털 DDP 참가신청서 DOCX 사본 /tmp/ummaya-g011-live-tui/inputs/seoul-culture-application-plan.docx 내용을 파악해서 접수번호 옆 빈칸에 UMMAYA-G011-2026을 넣고 저장해줘.'
    const input: Record<string, unknown> = {
      correlation_id: 'g011-seoul-culture-application-plan',
      document: {
        path: '/tmp/ummaya-g011-live-tui/inputs/seoul-culture-application-plan.docx',
        expected_format: 'docx',
      },
      operation: 'inspect',
      instruction: '문서의 구조와 접수번호 관련 필드 위치를 확인합니다.',
    }

    backfillUmmayaObservableToolInputFromUserQuery({
      toolName: 'document',
      input,
      messages: [user(prompt)],
    })

    expect(input.operation).toBe('inspect')
    expect(input.__ummaya_display_operation).toBe('fill')
  })

  test('uses the workspace glob adapter before document when the user gives a folder and filename hint', () => {
    const messages = [
      user(
        '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 작성이 끝나면 변경사항을 바로 보여줘.',
      ),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages,
        tools: documentAndGlobTools,
      }),
    ).toEqual({ type: 'tool', name: 'workspace_glob' })
  })

  test('keeps a legacy CC glob fallback only when the workspace adapter is absent', () => {
    const messages = [
      user(
        '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 작성이 끝나면 변경사항을 바로 보여줘.',
      ),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages,
        tools: documentAndLegacyGlobTools,
      }),
    ).toEqual({ type: 'tool', name: 'Glob' })
  })

  test('uses document directly when the user already supplied an exact local document path', () => {
    const messages = [
      user(
        '/Users/um-yunsang/UMMAYA/.evidence/alpha-document/weekly-13.hwpx 파일에서 13주차 활동기간과 특이사항을 작성해줘.',
      ),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages,
        tools: documentAndGlobTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
  })

  test('reroutes a new explicit artifact render request even when the session has an older render', () => {
    const priorRendered = [
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘.',
      ),
      toolUse('render-1', 'document_render'),
      toolResult('render-1', { tool_id: 'document_render', status: 'ok' }),
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 document_render 결과 UI 카드가 화면에 보이게 해줘.',
      ),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages: priorRendered,
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: priorRendered,
        tools: documentTools,
      }),
    ).toBe(false)
  })

  test('stops forcing document_render after the latest explicit render request has a result', () => {
    const latestRendered = [
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 document_render 결과 UI 카드가 화면에 보이게 해줘.',
      ),
      toolUse('render-1', 'document_render'),
      toolResult('render-1', { tool_id: 'document_render', status: 'ok' }),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages: latestRendered,
        tools: documentTools,
      }),
    ).toBeUndefined()
    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: latestRendered,
        tools: documentTools,
      }),
    ).toBe(true)
    expect(
      shouldCompleteAfterSuccessfulDocumentRender({
        messages: latestRendered,
      }),
    ).toBe(true)
  })

  test('does not complete explicit document render turns when the latest render result failed', () => {
    const failedRender = [
      user(
        '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해서 compact diff를 보여줘. 텍스트 요약 말고 실제 document_render 결과 카드가 보여야 해.',
      ),
      toolUse('render-1', 'document_render'),
      toolResult('render-1', {
        tool_id: 'document_render',
        status: 'failed',
        error: { kind: 'invalid_params' },
      }),
    ]

    expect(
      shouldCompleteAfterSuccessfulDocumentRender({
        messages: failedRender,
      }),
    ).toBe(false)
  })

  test('requires final assistant synthesis after a blocked document primitive result', () => {
    const blockedInspect = [
      user(
        '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘. 작성이 끝나면 원본과 달라진 부분을 문서 화면으로 비교해서 보여줘.',
      ),
      toolUse('document-1', 'document'),
      toolResult('document-1', {
        tool_id: 'document',
        status: 'needs_input',
        text_summary: 'Document path does not exist. Matching local candidates require selection.',
      }),
    ]

    expect(
      shouldCompleteAfterTerminalDocumentToolResult({
        messages: blockedInspect,
      }),
    ).toBe(true)
    expect(
      selectUmmayaToolChoiceOverride({
        messages: blockedInspect,
        tools: documentTools,
      }),
    ).toBeUndefined()
    expect(selectUmmayaClientForcedToolUse({ messages: blockedInspect, tools: documentTools })).toBeUndefined()
    expect(
      buildDocumentCompletionPromptIfNeeded({
        messages: blockedInspect,
      }),
    ).toContain('Document primitive result complete')
  })

  test('does not repeat document calls after missing-file needs_input results', () => {
    const missingFile = [
      user(
        '문서 /tmp/ummaya-g011-live-tui/inputs/does-not-exist.hwpx 내용을 파악해서 알아서 작성하고 /tmp/ummaya-g011-live-tui/tui-exports/missing-file-output.hwpx 로 저장해줘.',
      ),
      toolUse('document-1', 'document'),
      toolResult('document-1', {
        tool_id: 'document',
        status: 'needs_input',
        text_summary:
          'Document path does not exist: /tmp/ummaya-g011-live-tui/inputs/does-not-exist.hwpx.',
      }),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages: missingFile,
        tools: documentTools,
      }),
    ).toBeUndefined()
    expect(selectUmmayaClientForcedToolUse({ messages: missingFile, tools: documentTools })).toBeUndefined()
    const completionPrompt = buildDocumentCompletionPromptIfNeeded({ messages: missingFile })
    expect(completionPrompt).toContain('Document primitive result complete')
    expect(completionPrompt).toContain('provide an exact existing file path')
  })

  test('does not complete natural document turns after successful legacy inspect because the legacy chain is incomplete', () => {
    const inspected = [
      user(docQuery),
      toolUse('inspect-1', 'document_inspect'),
      toolResult('inspect-1', {
        tool_id: 'document_inspect',
        status: 'ok',
        artifact_refs: ['source-doc'],
      }),
    ]

    expect(
      shouldCompleteAfterTerminalDocumentToolResult({
        messages: inspected,
      }),
    ).toBe(false)
  })

  test('recovers from premature legacy stage attempts by returning to the document primitive', () => {
    const messages = [
      user(docQuery),
      toolUse('fill-1', 'document_apply_fill'),
      toolResult('fill-1', { tool_id: 'document_apply_fill', status: 'needs_input' }),
      toolUse('render-1', 'document_render'),
      toolResult('render-1', { tool_id: 'document_render', status: 'needs_input' }),
    ]

    expect(
      selectUmmayaToolChoiceOverride({
        messages,
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })
  })

  test('requires one successful document primitive result instead of an exposed stage chain', () => {
    const beforeResult = [
      user(docQuery),
    ]
    expect(
      selectUmmayaToolChoiceOverride({
        messages: beforeResult,
        tools: documentTools,
      }),
    ).toEqual({ type: 'tool', name: 'document' })

    const rendered = [
      ...beforeResult,
      toolUse('document-1', 'document'),
      toolResult('document-1', {
        tool_id: 'document',
        status: 'ok',
        text_summary: 'Document updated. Compact diff rendered automatically.',
        diff: { changes: [] },
      }),
    ]
    expect(
      selectUmmayaToolChoiceOverride({
        messages: rendered,
        tools: documentTools,
      }),
    ).toBeUndefined()
    expect(
      shouldSuppressUmmayaToolCallsForAnswerSynthesis({
        messages: rendered,
        tools: documentTools,
      }),
    ).toBe(true)
    const completionPrompt = buildDocumentCompletionPromptIfNeeded({ messages: rendered })
    expect(completionPrompt).toContain('Document primitive result complete')
    expect(completionPrompt).toContain('Answer in Korean only.')
    expect(completionPrompt).toContain('mention only changed field labels/values')
    expect(completionPrompt).toContain(
      'Do not invent units, parenthetical labels, workflow steps, style claims, or extra facts.',
    )
    expect(completionPrompt).toContain(
      'Do not say an image, screenshot, viewport, render artifact, browser view, viewer, or visual artifact was generated.',
    )
  })

  test('document completion does not cite save path without saved_exports', () => {
    const prompt =
      '다운로드 폴더에 있는 weekly.hwpx 문서내용을 파악하고 알아서 다음 주차 활동일지로 작성한 뒤 /Users/me/Downloads/weekly-14.hwpx 로 저장해줘. 최종적으로 실제로 바뀐 내용과 저장 위치만 답변해줘.'
    const messages = [
      user(prompt),
      toolUse('document-1', 'document'),
      toolResult('document-1', {
        tool_id: 'document',
        status: 'ok',
        text_summary: 'Document updated without save export.',
        diff: {
          changes: [
            {
              target_path: '/hwpx/text[2]',
              before_value: '13 주차 ',
              after_value: '14주차',
            },
          ],
        },
      }),
    ]

    const completionPrompt = buildDocumentCompletionPromptIfNeeded({ messages })

    expect(completionPrompt).toContain('실제 변경된 내용:')
    expect(completionPrompt).toContain('- /hwpx/text[2]: 13 주차  -> 14주차')
    expect(completionPrompt).not.toContain('저장 위치:')
    expect(completionPrompt).not.toContain('/Users/me/Downloads/weekly-14.hwpx')
    expect(completionPrompt).toContain('saved_exports is absent')
  })

  test('does not keep hidden document input repair fallback hooks', () => {
    const repairSource = readFileSync(
      join(TUI_ROOT, 'src/tools/_shared/toolChoiceRepair.ts'),
      'utf8',
    )
    const adapterSource = readFileSync(
      join(TUI_ROOT, 'src/tools/AdapterTool/AdapterTool.ts'),
      'utf8',
    )

    expect(repairSource).not.toContain('repairDocumentToolInputFromHistory')
    expect(repairSource).not.toContain('documentArtifactRefForNextTool')
    expect(adapterSource).not.toContain('repairDocumentToolInputFromHistory')
  })
})
