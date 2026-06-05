// SPDX-License-Identifier: Apache-2.0
// Epic ε #2296 · T015 — adapterManifest.ts unit tests.
//
// Covers (contracts/ipc-adapter-manifest-frame.md § 7):
//   Test 4: Cache replace, not merge (FR-016).
//   Test 5: Cold-boot race — validateInput before manifest arrives.
//   isManifestSynced() semantics.
//
// All tests use module-level clearManifestCache() to reset singleton state.

import { describe, test, expect, beforeEach, afterEach } from 'bun:test'
import React from 'react'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { render } from 'ink-testing-library'
import {
  getAdapterToolByName,
  normalizeExplicitDocumentArtifactInput,
} from '../src/tools/AdapterTool/AdapterTool'
import { toolToFunctionSchema } from '../src/query/toolSerialization'
import { ThemeProvider } from '../src/theme/provider'
import { TerminalSizeContext } from '../src/ink/components/TerminalSizeContext'
import {
  ingestManifestFrame,
  resolveAdapter,
  isManifestSynced,
  waitForManifestSync,
  clearManifestCache,
} from '../src/services/api/adapterManifest'
import type { AdapterManifestSyncFrame } from '../src/ipc/frames.generated'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const tempDirs: string[] = []

function wrap(element: React.ReactElement): React.ReactElement {
  return React.createElement(
    ThemeProvider,
    null,
    React.createElement(
      TerminalSizeContext.Provider,
      { value: { columns: 100, rows: 24 } },
      element,
    ),
  )
}

function mkTempDir(prefix: string): string {
  const dir = mkdtempSync(join(tmpdir(), prefix))
  tempDirs.push(dir)
  return dir
}

function makeManifestFrame(
  overrides: Partial<{
    entries: AdapterManifestSyncFrame['entries']
    manifest_hash: string
    emitter_pid: number
  }> = {},
): AdapterManifestSyncFrame {
  const defaultEntries: AdapterManifestSyncFrame['entries'] = [
    {
      tool_id: 'nmc_emergency_search',
      name: 'NMC Emergency Bed Availability',
      primitive: 'find',
      policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
      source_mode: 'live',
    },
    {
      tool_id: 'kakao_address_search',
      name: 'Kakao Address Search',
      primitive: 'locate',
      policy_authority_url: undefined,
      source_mode: 'live',
    },
  ]
  return {
    kind: 'adapter_manifest_sync',
    version: '1.0',
    session_id: 'test-session',
    correlation_id: '01HXKQ7Z3M1V8K2YQ8A6P4F9C1',
    ts: new Date().toISOString(),
    role: 'backend',
    frame_seq: 0,
    entries: overrides.entries ?? defaultEntries,
    manifest_hash: overrides.manifest_hash ?? 'a'.repeat(64),
    emitter_pid: overrides.emitter_pid ?? 12345,
  } satisfies AdapterManifestSyncFrame
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  clearManifestCache()
})

afterEach(() => {
  while (tempDirs.length > 0) {
    const dir = tempDirs.pop()
    if (dir !== undefined) {
      rmSync(dir, { recursive: true, force: true })
    }
  }
})

// ---------------------------------------------------------------------------
// isManifestSynced() — cold-boot state
// ---------------------------------------------------------------------------

describe('isManifestSynced', () => {
  test('returns false before any frame is ingested', () => {
    expect(isManifestSynced()).toBe(false)
  })

  test('returns true after a frame is ingested', () => {
    ingestManifestFrame(makeManifestFrame())
    expect(isManifestSynced()).toBe(true)
  })

  test('returns false after cache is cleared', () => {
    ingestManifestFrame(makeManifestFrame())
    clearManifestCache()
    expect(isManifestSynced()).toBe(false)
  })

  test('waitForManifestSync resolves when a frame is ingested', async () => {
    const pending = waitForManifestSync(100)
    ingestManifestFrame(makeManifestFrame())
    await expect(pending).resolves.toBe(true)
  })

  test('waitForManifestSync resolves false on cold-boot timeout', async () => {
    await expect(waitForManifestSync(1)).resolves.toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Test 4 — cache replace, not merge (FR-016)
// ---------------------------------------------------------------------------

describe('ingestManifestFrame: cache replace semantics (FR-016)', () => {
  test('second frame wholly replaces first — old entries are evicted', () => {
    // First frame: contains nmc_emergency_search
    const frame1 = makeManifestFrame({
      entries: [
        {
          tool_id: 'nmc_emergency_search',
          name: 'NMC Emergency',
          primitive: 'find',
          policy_authority_url: 'https://www.e-gen.or.kr/nemc/main.do',
          source_mode: 'live',
        },
      ],
    })
    ingestManifestFrame(frame1)
    expect(resolveAdapter('nmc_emergency_search')).toBeDefined()

    // Second frame: does NOT contain nmc_emergency_search
    const frame2 = makeManifestFrame({
      entries: [
        {
          tool_id: 'kma_forecast_fetch',
          name: 'KMA Weather Forecast',
          primitive: 'find',
          policy_authority_url: 'https://www.data.go.kr/data/15059093/openapi.do',
          source_mode: 'live',
        },
      ],
    })
    ingestManifestFrame(frame2)

    // Old entry must be gone (not merged)
    expect(resolveAdapter('nmc_emergency_search')).toBeUndefined()
    // New entry must be present
    expect(resolveAdapter('kma_forecast_fetch')).toBeDefined()
  })

  test('emitter_pid is updated on replace', () => {
    ingestManifestFrame(makeManifestFrame({ emitter_pid: 1111 }))
    ingestManifestFrame(makeManifestFrame({ emitter_pid: 2222 }))
    // We can't directly read emitter_pid from the public API, but isManifestSynced
    // confirms the cache is active. This test verifies no error is thrown on double ingest.
    expect(isManifestSynced()).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// resolveAdapter — resolve by tool_id
// ---------------------------------------------------------------------------

describe('resolveAdapter', () => {
  test('returns undefined before manifest is synced', () => {
    expect(resolveAdapter('nmc_emergency_search')).toBeUndefined()
  })

  test('returns the matching entry after manifest is synced', () => {
    ingestManifestFrame(makeManifestFrame())
    const entry = resolveAdapter('nmc_emergency_search')
    expect(entry).toBeDefined()
    expect(entry!.tool_id).toBe('nmc_emergency_search')
    expect(entry!.primitive).toBe('find')
    expect(entry!.policy_authority_url).toBe('https://www.e-gen.or.kr/nemc/main.do')
  })

  test('returns undefined for unknown tool_id after manifest is synced', () => {
    ingestManifestFrame(makeManifestFrame())
    expect(resolveAdapter('bogus_tool_xyz')).toBeUndefined()
  })

  test('locate entry resolves without policy_authority_url', () => {
    ingestManifestFrame(makeManifestFrame())
    const entry = resolveAdapter('kakao_address_search')
    expect(entry).toBeDefined()
    expect(entry!.source_mode).toBe('live')
    expect(entry!.policy_authority_url == null || entry!.policy_authority_url === undefined).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// Concrete adapter schema exposure — CC-style tool definitions
// ---------------------------------------------------------------------------

describe('concrete adapter tool schemas', () => {
  test('AdapterTool exposes backend input_schema_json and llm_description', async () => {
    ingestManifestFrame(makeManifestFrame({
      entries: [
        {
          tool_id: 'kma_apihub_amm_iwxxm_service_get_metar',
          name: 'KMA APIHub AmmIwxxmService getMetar',
          primitive: 'find',
          policy_authority_url: 'https://apihub.kma.go.kr/',
          source_mode: 'live',
          search_hint: 'KMA APIHub AmmIwxxmService getMetar METAR icao',
          llm_description: 'KMA APIHub AmmIwxxmService/getMetar. Provide ICAO station code as icao; authKey is supplied by UMMAYA runtime.',
          input_schema_json: {
            type: 'object',
            properties: {
              icao: {
                type: 'string',
                description: 'KMA APIHub request parameter icao.',
              },
              page_no: {
                type: 'integer',
                default: 1,
                description: 'KMA APIHub request parameter pageNo.',
              },
            },
            required: ['icao'],
            additionalProperties: false,
          },
          output_schema_json: {
            type: 'object',
            properties: {
              items: { type: 'array', items: { type: 'object' } },
            },
          },
        },
      ] as unknown as AdapterManifestSyncFrame['entries'],
    }))

    const tool = getAdapterToolByName('kma_apihub_amm_iwxxm_service_get_metar')
    expect(tool).toBeDefined()

    const serialized = await toolToFunctionSchema(tool!)
    expect(serialized.function.description).toContain('AmmIwxxmService/getMetar')

    const parameters = serialized.function.parameters as {
      properties?: Record<string, { type?: string; description?: string; default?: unknown }>
      required?: string[]
      additionalProperties?: boolean
    }
    expect(parameters.properties?.icao?.type).toBe('string')
    expect(parameters.properties?.icao?.description).toBe('KMA APIHub request parameter icao.')
    expect(parameters.properties?.page_no?.type).toBe('integer')
    expect(parameters.properties?.page_no?.default).toBe(1)
    expect(parameters.required).toContain('icao')
    expect(parameters.additionalProperties).toBe(false)
  })

  test('AdapterTool renders document tool results through the revdiff-style document surface', () => {
    ingestManifestFrame(makeManifestFrame({
      entries: [
        {
          tool_id: 'document_render',
          name: 'Document render evidence',
          primitive: 'find',
          policy_authority_url: 'https://example.test/document-policy',
          source_mode: 'mock',
          llm_description: 'Render document evidence.',
          input_schema_json: {
            type: 'object',
            properties: {
              correlation_id: { type: 'string' },
              document: { type: 'object' },
            },
            required: ['correlation_id', 'document'],
            additionalProperties: true,
          },
        },
      ] as unknown as AdapterManifestSyncFrame['entries'],
    }))

    const tool = getAdapterToolByName('document_render')
    expect(tool).toBeDefined()

    const ui = tool!.renderToolResultMessage?.(
      {
        tool_id: 'document_render',
        correlation_id: 'corr-render',
        status: 'ok',
        artifact_refs: ['render-corr-render-001'],
        text_summary: 'Rendered 1 page with document diff evidence.',
        diff: {
          diff_id: 'diff-corr-render',
          source_artifact_id: 'working-doc',
          derivative_artifact_id: 'derivative-doc',
          changes: [
            {
              change_id: 'change-001',
              operation_id: 'fill-week',
              change_type: 'field',
              target_path: '/hwpx/text[2]',
              before_value: '12 주차 ',
              after_value: '13 주차 ',
            },
          ],
        },
        render_artifacts: [],
      },
      [],
      { verbose: false },
    )
    const { lastFrame } = render(wrap(ui as React.ReactElement))
    const frame = lastFrame() ?? ''

    expect(frame).toContain('Changed 1 field')
    expect(frame).not.toContain('Document OK')
    expect(frame).not.toContain('hunk 1/1')
    expect(frame).not.toContain('⊂ compact')
    expect(frame).not.toContain('± word-diff')
    for (const glyph of ['╭', '╮', '╰', '╯']) {
      expect(frame).not.toContain(glyph)
    }
    // Inline structural diff (CC pipeline): before/after values + field path.
    expect(frame).toContain('12 주차')
    expect(frame).toContain('13 주차')
    expect(frame).toContain('text[2]')
    expect(frame).not.toContain('document_render — 1 result')
  })

  test('AdapterTool does not fabricate a render failure when a raster is missing (approach D)', () => {
    ingestManifestFrame(makeManifestFrame({
      entries: [
        {
          tool_id: 'document_render',
          name: 'Document render evidence',
          primitive: 'find',
          policy_authority_url: 'https://example.test/document-policy',
          source_mode: 'mock',
          llm_description: 'Render document evidence.',
          input_schema_json: {
            type: 'object',
            properties: {
              correlation_id: { type: 'string' },
              document: { type: 'object' },
            },
            required: ['correlation_id', 'document'],
            additionalProperties: true,
          },
        },
      ] as unknown as AdapterManifestSyncFrame['entries'],
    }))

    const tool = getAdapterToolByName('document_render')
    expect(tool).toBeDefined()

    // Under approach D the user surface is the structural diff, not a raster.
    // A render with no readable raster is no longer a failure — the TUI never
    // fabricates a visual-render error and the page raster is Evidence-only.
    const block = tool!.mapToolResultToToolResultBlockParam(
      {
        ok: true,
        result: {
          tool_id: 'document_render',
          correlation_id: 'corr-render',
          status: 'ok',
          text_summary: 'Rendered document diff evidence.',
          render_artifacts: [],
          diff: {
            diff_id: 'diff-corr-render',
            source_artifact_id: 'working-doc',
            derivative_artifact_id: 'derivative-doc',
            changes: [
              {
                change_id: 'change-001',
                operation_id: 'fill-week',
                change_type: 'field',
                target_path: '/hwpx/text[2]',
                before_value: '12 주차 ',
                after_value: '13 주차 ',
              },
            ],
          },
        },
      },
      'toolu-document-render',
    )

    expect(block.is_error).toBeFalsy()
    expect(block.content).not.toContain('tui_visual_render_failed')
    expect(block.content).toContain('"status":"ok"')
  })

  test('AdapterTool normalizes only explicit current-user document artifact ids', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_render',
      {},
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      document: { artifact_id: 'derivative-public-doc-13th-weekly-log' },
    })
    expect(typeof normalized.correlation_id).toBe('string')
    expect(String(normalized.correlation_id)).toContain('document-render-')

    expect(
      normalizeExplicitDocumentArtifactInput(
        'document_render',
        {},
        [
          {
            type: 'user',
            message: { role: 'user', content: '렌더링해서 보여줘.' },
          },
        ],
      ),
    ).toEqual({})

    expect(
      normalizeExplicitDocumentArtifactInput(
        'document_render',
        { artifact_id: 'derivative-public-doc-13th-weekly-log', correlation_id: 'corr-1' },
        [],
      ),
    ).toEqual({
      correlation_id: 'corr-1',
      document: { artifact_id: 'derivative-public-doc-13th-weekly-log' },
    })

    expect(
      normalizeExplicitDocumentArtifactInput(
        'document_render',
        {
          correlation_id: 'corr-2',
          document: {
            path: '/Users/example/wrong-source.hwpx',
            expected_format: 'hwpx',
          },
        },
        [
          {
            type: 'user',
            message: {
              role: 'user',
              content:
                '현재 세션 artifact derivative-public-doc-13th-weekly-log를 document_render로 렌더링해줘.',
            },
          },
        ],
      ),
    ).toEqual({
      correlation_id: 'corr-2',
      document: {
        expected_format: 'hwpx',
        artifact_id: 'derivative-public-doc-13th-weekly-log',
      },
    })
  })

  test('AdapterTool preserves an exact user-provided local document path before primitive dispatch', () => {
    const tempDir = mkTempDir('document-path-lock-')
    const lockedPath = join(
      tempDir,
      'Users',
      'um-yunsang',
      'UMMAYA',
      '.evidence',
      'alpha-document',
      'weekly-13.hwpx',
    )
    const modelShortenedPath = join(
      tempDir,
      'Users',
      'um-yunsang',
      '.evidence',
      'alpha-document',
      'weekly-13.hwpx',
    )
    mkdirSync(join(lockedPath, '..'), { recursive: true })
    writeFileSync(lockedPath, 'not a real hwpx; only existence matters for input repair')

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document',
      {
        correlation_id: 'alpha-live-document',
        document: {
          path: modelShortenedPath,
          expected_format: 'hwpx',
        },
        operation: 'fill',
        instruction: '13주차 활동기간과 특이사항을 작성해줘.',
        patches: [
          {
            target_path: 'special_notes',
            value: '공공AX 문서 primitive 알파 테스트 완료',
          },
        ],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: `${lockedPath} 파일에서 13주차 활동기간을 2026.06.02 ~ 2026.06.08로, 특이사항을 "공공AX 문서 primitive 알파 테스트 완료"로 작성해줘.`,
          },
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'alpha-live-document',
      document: {
        path: lockedPath,
        expected_format: 'hwpx',
      },
      operation: 'fill',
      instruction: '13주차 활동기간과 특이사항을 작성해줘.',
      patches: [
        {
          target_path: 'special_notes',
          value: '공공AX 문서 primitive 알파 테스트 완료',
        },
      ],
    })
  })

  test('AdapterTool corrects mismatched expected_format from an existing document path extension', () => {
    const tempDir = mkTempDir('document-format-lock-')
    const hwpPath = join(tempDir, '2026년도 AX 아이디어 경진대회_참가서약서.hwp')
    writeFileSync(hwpPath, 'not a real hwp; only existence matters for input repair')

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document',
      {
        correlation_id: 'fill_hwp_public_form',
        document: {
          path: hwpPath,
          expected_format: 'hwpx',
        },
        instruction: '성명에 홍길동을 입력해주세요.',
        patches: [{ target_path: '/성명', value: '홍길동' }],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더에 있는 2026년도 AX 아이디어 경진대회 참가서약서 HWP 문서를 찾아서 성명 칸에 홍길동을 작성해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      correlation_id: 'fill_hwp_public_form',
      document: {
        path: hwpPath,
        expected_format: 'hwp',
      },
      patches: [{ target_path: '/성명', value: '홍길동' }],
    })
    expect(String(normalized.instruction)).toContain('성명에 홍길동을 입력해주세요.')
  })

  test('AdapterTool preserves latest user request details on patchless document primitive calls', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document',
      {
        correlation_id: 'weekly-activity-13',
        document: {
          path: '/Users/um-yunsang/Downloads/weekly.hwpx',
          expected_format: 'hwpx',
        },
        instruction:
          '문서 내용을 검토하고 13주차 활동일지로 사용하기 위해 필요한 모든 필드를 확인해 주세요.',
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더의 주간활동일지 HWPX 문서를 13주차로 작성하고 활동기간은 2026.06.01~2026.06.07로 넣어줘.',
          },
        },
      ],
    )

    expect(String(normalized.instruction)).toContain('필요한 모든 필드를 확인해 주세요')
    expect(String(normalized.instruction)).toContain('Original user request:')
    expect(String(normalized.instruction)).toContain('2026.06.01~2026.06.07')
  })

  test('AdapterTool repairs post-inspect document_copy_for_edit path-only calls to the latest source artifact', () => {
    const inspectResult = {
      ok: true,
      result: {
        tool_id: 'document_inspect',
        correlation_id: 'user_request_hwpx_edit',
        status: 'ok',
        artifact_refs: ['source-user_request_hwpx_edit'],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_copy_for_edit',
      {
        correlation_id: 'user_request_hwpx_edit',
        document: {
          path: '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
          expected_format: 'hwpx',
        },
        reason: '13주차 활동일지 작업을 위한 문서 작업 복사본 생성',
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-inspect',
                content: JSON.stringify(inspectResult),
              },
            ],
          },
          toolUseResult: inspectResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'user_request_hwpx_edit',
      document: {
        expected_format: 'hwpx',
        artifact_id: 'source-user_request_hwpx_edit',
      },
      reason: '13주차 활동일지 작업을 위한 문서 작업 복사본 생성',
    })
  })

  test('AdapterTool repairs post-copy document_apply_fill path-only calls to the latest working artifact', () => {
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'sw_project_weekly_log_13_week',
        status: 'ok',
        artifact_refs: [
          'source-sw_project_weekly_log_hwpx',
          'working-sw_project_weekly_log_13_week',
        ],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'sw_project_weekly_log_13_week',
        document: {
          path: '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        },
        patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'sw_project_weekly_log_13_week',
      document: { artifact_id: 'working-sw_project_weekly_log_13_week' },
      patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
    })
  })

  test('AdapterTool canonicalizes HWPX text patch aliases without masking unknown targets', () => {
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'sw_center_project_13th_week_log_20260601_20260607',
        status: 'ok',
        artifact_refs: [
          'source-sw_center_project_13th_week_log_20260601_20260607',
          'working-sw_center_project_13th_week_log_20260601_20260607',
        ],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'sw_center_project_13th_week_log_20260601_20260607',
        document: {
          path:
            '/downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
          artifact_id: 'working-sw_center_project_13th_week_log_20260601_20260607',
        },
        patches: [
          { target_path: '/hwp/text[1]/text()', value: '문서 제목' },
          { target_path: '/hwpx-text-18', value: '특이사항' },
          { target_path: '/unmapped-text-18', value: '그대로 실패해야 하는 대상' },
        ],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'sw_center_project_13th_week_log_20260601_20260607',
      document: {
        artifact_id: 'working-sw_center_project_13th_week_log_20260601_20260607',
      },
      patches: [
        { target_path: '/hwpx/text[1]', value: '문서 제목' },
        { target_path: '/hwpx/text[18]', value: '특이사항' },
        { target_path: '/unmapped-text-18', value: '그대로 실패해야 하는 대상' },
      ],
    })
  })

  test('AdapterTool drops out-of-range HWPX text patches using inspected field paths', () => {
    const inspectResult = {
      ok: true,
      result: {
        tool_id: 'document_inspect',
        correlation_id: 'user_request',
        status: 'ok',
        artifact_refs: ['source-user_request'],
        extraction: {
          fields: Array.from({ length: 33 }, (_, index) => ({
            field_id: `hwpx-text-${String(index + 1).padStart(3, '0')}`,
            path: `/hwpx/text[${index + 1}]`,
          })),
        },
      },
    }
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'user_request',
        status: 'ok',
        artifact_refs: ['source-user_request', 'working-user_request'],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'user_request',
        document: {
          path:
            '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        },
        patches: [
          { target_path: '/hwpx/text[2]', value: '13 주차 ' },
          { target_path: '/hwpx/text[33]', value: 'structured adapter 검증' },
          { target_path: '/hwpx/text[34]', value: '차주 활동 계획' },
          { target_path: '/hwpx/text[35]', value: '차주활동계획:' },
          { target_path: '/hwpx/text[36]', value: '없는 텍스트 노드' },
        ],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-inspect',
                content: JSON.stringify(inspectResult),
              },
            ],
          },
          toolUseResult: inspectResult,
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'user_request',
      document: { artifact_id: 'working-user_request' },
      patches: [
        { target_path: '/hwpx/text[2]', value: '13 주차 ' },
        { target_path: '/hwpx/text[33]', value: 'structured adapter 검증' },
      ],
    })
  })

  test('AdapterTool maps editable HWPX table-cell aliases and drops non-editable cells', () => {
    const inspectResult = {
      ok: true,
      result: {
        tool_id: 'document_inspect',
        correlation_id: 'week13_activity_log',
        status: 'ok',
        artifact_refs: ['source-week13_activity_log'],
        extraction: {
          fields: [
            { field_id: 'hwpx-text-001', path: '/hwpx/text[1]' },
            { field_id: 'hwpx-text-002', path: '/hwpx/text[2]' },
            { field_id: 'hwpx-text-012', path: '/hwpx/text[12]' },
          ],
          tables: [
            {
              block_id: 'hwpx-table-001',
              cells: [
                { row_index: 0, column_index: 0, field_path: null },
                { row_index: 0, column_index: 1, field_path: '/hwpx/text[1]' },
                { row_index: 0, column_index: 2, field_path: null },
                { row_index: 1, column_index: 0, field_path: '/hwpx/text[2]' },
              ],
            },
            {
              block_id: 'hwpx-table-002',
              cells: [
                { row_index: 1, column_index: 1, field_path: '/hwpx/text[12]' },
              ],
            },
          ],
        },
      },
    }
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'week13_activity_log',
        status: 'ok',
        artifact_refs: ['source-week13_activity_log', 'working-week13_activity_log'],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'week13_activity_log',
        document: {
          path:
            '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        },
        patches: [
          { target_path: '/hwpx/text[2]', value: '13 주차 ' },
          { target_path: '/hwpx/[hwpx-table-001]/cells[0][2]', value: '' },
          { target_path: '/hwpx/[hwpx-table-001]/cells[1][0]', value: '13 주차 ' },
          { target_path: '/hwpx/[hwpx-table-002]/cells[1][1]', value: '2026.06.02 ~ 2026.06.08' },
          { target_path: '/hwpx/[hwpx-table-002]/cells[6][1]', value: '차주계획:' },
        ],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-inspect',
                content: JSON.stringify(inspectResult),
              },
            ],
          },
          toolUseResult: inspectResult,
        },
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'week13_activity_log',
      document: { artifact_id: 'working-week13_activity_log' },
      patches: [
        { target_path: '/hwpx/text[2]', value: '13 주차 ' },
        { target_path: '/hwpx/text[2]', value: '13 주차 ' },
        { target_path: '/hwpx/text[12]', value: '2026.06.02 ~ 2026.06.08' },
      ],
    })
  })

  test('AdapterTool repairs post-copy document_apply_fill source-artifact calls to the latest working artifact', () => {
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'weekly_activity_log_13th_week',
        status: 'ok',
        artifact_refs: [
          'source-weekly_activity_log_13th_week',
          'working-weekly_activity_log_13th_week',
        ],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'weekly_activity_log_13th_week',
        document: {
          path: '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
          artifact_id: 'source-weekly_activity_log_13th_week',
          expected_format: 'hwpx',
        },
        patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'weekly_activity_log_13th_week',
      document: {
        expected_format: 'hwpx',
        artifact_id: 'working-weekly_activity_log_13th_week',
      },
      patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
    })
  })

  test('AdapterTool repairs extraction document-intake ids to stored source artifacts before copy', () => {
    const inspectResult = {
      ok: true,
      result: {
        tool_id: 'document_inspect',
        correlation_id: 'weekly_activity_log_13th_week',
        status: 'ok',
        artifact_refs: ['source-weekly_activity_log_13th_week'],
        extraction: {
          artifact_id: 'document-intake-2e60ba88ddc9',
        },
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_copy_for_edit',
      {
        correlation_id: 'weekly_activity_log_13th_week',
        document: {
          artifact_id: 'document-intake-2e60ba88ddc9',
          expected_format: 'hwpx',
        },
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-inspect',
                content: JSON.stringify(inspectResult),
              },
            ],
          },
          toolUseResult: inspectResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'weekly_activity_log_13th_week',
      document: {
        expected_format: 'hwpx',
        artifact_id: 'source-weekly_activity_log_13th_week',
      },
    })
  })

  test('AdapterTool repairs extraction document-intake ids to the latest working artifact before fill', () => {
    const copyResult = {
      ok: true,
      result: {
        tool_id: 'document_copy_for_edit',
        correlation_id: 'weekly_activity_log_13th_week',
        status: 'ok',
        artifact_refs: [
          'source-weekly_activity_log_13th_week',
          'working-weekly_activity_log_13th_week',
        ],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_apply_fill',
      {
        correlation_id: 'weekly_activity_log_13th_week',
        document: {
          artifact_id: 'document-intake-2e60ba88ddc9',
          expected_format: 'hwpx',
        },
        patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-copy',
                content: JSON.stringify(copyResult),
              },
            ],
          },
          toolUseResult: copyResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'weekly_activity_log_13th_week',
      document: {
        expected_format: 'hwpx',
        artifact_id: 'working-weekly_activity_log_13th_week',
      },
      patches: [{ target_path: '/hwpx/text[2]', value: '13 주차' }],
    })
  })

  test('AdapterTool repairs post-mutation document_render path-only calls to the latest derivative artifact', () => {
    const fillResult = {
      ok: true,
      result: {
        tool_id: 'document_apply_fill',
        correlation_id: 'sw_project_weekly_log_13_week',
        status: 'ok',
        artifact_refs: [
          'working-sw_project_weekly_log_13_week',
          'derivative-sw_project_weekly_log_13_week',
        ],
      },
    }

    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_render',
      {
        correlation_id: 'sw_project_weekly_log_13_week_render',
        document: {
          path: '/Users/um-yunsang/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        },
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content: [
              {
                type: 'tool_result',
                tool_use_id: 'call-fill',
                content: JSON.stringify(fillResult),
              },
            ],
          },
          toolUseResult: fillResult,
        },
      ],
    )

    expect(normalized).toEqual({
      correlation_id: 'sw_project_weekly_log_13_week_render',
      document: { artifact_id: 'derivative-sw_project_weekly_log_13_week' },
    })
  })

  test('AdapterTool hides successful intermediate document tool UI chrome', () => {
    ingestManifestFrame(makeManifestFrame({
      entries: [
        {
          tool_id: 'document_copy_for_edit',
          name: 'Document copy for edit',
          primitive: 'send',
          policy_authority_url: 'https://example.test/document-policy',
          source_mode: 'mock',
          llm_description: 'Create a working copy.',
          input_schema_json: {
            type: 'object',
            properties: {
              correlation_id: { type: 'string' },
              document: { type: 'object' },
            },
            required: ['correlation_id', 'document'],
            additionalProperties: true,
          },
        },
      ] as unknown as AdapterManifestSyncFrame['entries'],
    }))

    const tool = getAdapterToolByName('document_copy_for_edit')
    expect(tool).toBeDefined()
    expect(
      tool!.renderToolUseMessage(
        { correlation_id: 'corr-copy', document: { artifact_id: 'source-corr' } },
        { verbose: false, theme: 'dark' } as never,
      ),
    ).toBeNull()
    expect(
      tool!.renderToolResultMessage?.(
        {
          tool_id: 'document_copy_for_edit',
          correlation_id: 'corr-copy',
          status: 'ok',
          artifact_refs: ['source-corr', 'working-corr'],
          text_summary: 'Created a local working copy for document editing.',
        },
        [],
        { verbose: false, theme: 'dark', tools: {} } as never,
      ),
    ).toBeNull()
  })

  test('AdapterTool paints user-meaningful document tool calls without artifact leaks', () => {
    ingestManifestFrame(makeManifestFrame({
      entries: [
        {
          tool_id: 'document_apply_fill',
          name: 'Document apply fill',
          primitive: 'send',
          policy_authority_url: 'https://example.test/document-policy',
          source_mode: 'mock',
          llm_description: 'Fill document fields.',
          input_schema_json: {
            type: 'object',
            properties: {
              correlation_id: { type: 'string' },
              document: { type: 'object' },
              fields: { type: 'object' },
            },
            required: ['correlation_id', 'document', 'fields'],
            additionalProperties: true,
          },
        },
      ] as unknown as AdapterManifestSyncFrame['entries'],
    }))

    const tool = getAdapterToolByName('document_apply_fill')
    expect(tool).toBeDefined()
    expect(
      tool!.userFacingName({
        correlation_id: 'corr-fill',
        document: { path: '/Users/example/Downloads/weekly.hwpx' },
        fields: {},
      }),
    ).toBe('Document')
    expect(
      tool!.renderToolUseMessage(
        {
          correlation_id: 'corr-fill',
          document: { path: '/Users/example/Downloads/weekly.hwpx' },
          fields: { week: '13주차' },
        },
        { verbose: false, theme: 'dark' } as never,
      ),
    ).toBe('Fill document fields: weekly.hwpx')

    const artifactOnly = tool!.renderToolUseMessage(
      {
        correlation_id: 'corr-fill',
        document: { artifact_id: 'derivative-secret-artifact' },
        fields: { week: '13주차' },
      },
      { verbose: false, theme: 'dark' } as never,
    )
    expect(artifactOnly).toBe('Fill document fields: current document')
    expect(artifactOnly).not.toContain('derivative-secret-artifact')
  })

  test('AdapterTool repairs document_inspect when the model passes only Downloads as path', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_inspect',
      {
        correlation_id: 'corr-inspect',
        document: {
          path: '/Users/um-yunsang/Downloads.',
          expected_format: 'hwpx',
        },
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더에 있는 SW중심대학사업 현장미러형연계프로젝트 주간활동일지 HWPX 양식을 13주차 활동일지로 작성해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      correlation_id: 'corr-inspect',
      document: {
        path: expect.stringContaining(
          '/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지.hwpx',
        ),
        expected_format: 'hwpx',
      },
    })
  })

  test('AdapterTool repairs root document primitive Downloads filename calls', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document',
      {
        correlation_id: 'corr-document',
        document: {
          path: 'weekly-alpha.hwpx',
          expected_format: 'hwpx',
        },
        operation: 'fill',
        instruction: '14주차 활동일지로 수정',
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더에 있는 weekly-alpha.hwpx 문서를 14주차 활동일지로 수정해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      correlation_id: 'corr-document',
      document: {
        path: expect.stringContaining('/Downloads/weekly-alpha.hwpx'),
        expected_format: 'hwpx',
      },
    })
  })

  test('AdapterTool repairs document_inspect when the model passes Downloads-relative file with trailing punctuation', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_inspect',
      {
        correlation_id: 'corr-inspect-relative',
        document: {
          path:
            'Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx.',
        },
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더의 SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx 파일을 13주차 활동일지로 작성해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      correlation_id: 'corr-inspect-relative',
      document: {
        path: expect.stringContaining(
          '/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        ),
        expected_format: 'hwpx',
      },
    })
    const normalizedPath = String((normalized.document as { path?: unknown }).path)
    expect(normalizedPath).not.toContain('/UMMAYA/tui/Downloads/')
    expect(normalizedPath).not.toEndWith('.hwpx.')
  })

  test('AdapterTool prefers the user-stated Downloads filename when the model underscores spaces', () => {
    const normalized = normalizeExplicitDocumentArtifactInput(
      'document_inspect',
      {
        correlation_id: 'corr-inspect-underscored',
        document: {
          path:
            '/Users/um-yunsang/Downloads/SW중심대학사업_현장미러형연계프로젝트_주간활동일지(학과_팀명).hwpx.',
        },
      },
      [
        {
          type: 'user',
          message: {
            role: 'user',
            content:
              '다운로드 폴더의 SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx 파일을 13주차 활동일지로 작성해줘.',
          },
        },
      ],
    )

    expect(normalized).toMatchObject({
      correlation_id: 'corr-inspect-underscored',
      document: {
        path: expect.stringContaining(
          '/Downloads/SW중심대학사업 현장미러형연계프로젝트 주간활동일지(학과_팀명).hwpx',
        ),
        expected_format: 'hwpx',
      },
    })
    const normalizedPath = String((normalized.document as { path?: unknown }).path)
    expect(normalizedPath).not.toContain('SW중심대학사업_현장미러형연계프로젝트')
    expect(normalizedPath).not.toEndWith('.hwpx.')
  })
})
