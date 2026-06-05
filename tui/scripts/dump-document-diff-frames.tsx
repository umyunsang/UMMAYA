#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
// Evidence Fabric — capture the inline document-change diff frames the TUI now
// renders (deep-research-migration approach D2). Replaces the retired
// dump-document-render-png raster/viewer evidence. Frames are reviewer-readable
// and joinable by correlation_id + frame_hash.
//
//   bun run scripts/dump-document-diff-frames.tsx
//   UMMAYA_EVIDENCE_OUT_DIR=/abs/dir bun run scripts/dump-document-diff-frames.tsx

import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import React from 'react'
import { render } from 'ink-testing-library'

import { TerminalSizeContext } from '../src/ink/components/TerminalSizeContext'
import { PrimitiveDispatcher } from '../src/components/primitive'
import { ThemeProvider } from '../src/theme/provider'

interface Scenario {
  readonly slug: string
  readonly title: string
  readonly columns: number
  readonly expanded?: boolean
  readonly payload: Record<string, unknown>
}

const SCENARIOS: readonly Scenario[] = [
  {
    slug: 'single-primitive-document-fill',
    title: 'document — single model-facing primitive inline diff',
    columns: 100,
    payload: {
      tool_id: 'document',
      correlation_id: 'corr-document-primitive-evidence',
      status: 'ok',
      text_summary: 'Document edit completed with automatic compact diff review evidence.',
      artifact_refs: [
        'source-weekly-hwp',
        'working-weekly-hwpx',
        'derivative-weekly-hwpx',
        'render-weekly-hwpx-001',
      ],
      diff: {
        diff_id: 'diff-document-primitive-evidence',
        source_artifact_id: 'working-weekly-hwpx',
        derivative_artifact_id: 'derivative-weekly-hwpx',
        changes: [
          {
            change_id: 'c1',
            operation_id: 'fill-week',
            change_type: 'field',
            target_path: '/hwpx/text[1]',
            before_value: '12주차',
            after_value: '13주차',
          },
        ],
      },
      render_artifacts: [
        {
          render_artifact_id: 'render-weekly-hwpx-001',
          render_path: '/tmp/ummaya/renders/render-weekly-hwpx-001.svg',
          render_mime_type: 'image/svg+xml',
          page_number: 1,
          engine_id: 'rhwp-node-wasm',
        },
      ],
    },
  },
  {
    slug: 'apply-fill-mutation',
    title: 'document_apply_fill — per-mutation inline diff',
    columns: 100,
    payload: {
      tool_id: 'document_apply_fill',
      correlation_id: 'corr-fill-evidence',
      status: 'ok',
      text_summary: '주민등록등본.hwpx 의 성명·주민등록번호 칸을 채웠습니다.',
      diff: {
        diff_id: 'diff-fill-evidence',
        source_artifact_id: 'working-evidence',
        derivative_artifact_id: 'derivative-evidence',
        changes: [
          { change_id: 'c1', operation_id: 'o1', change_type: 'field', target_path: '/hwpx/text[2]', before_value: '', after_value: '홍길동' },
          { change_id: 'c2', operation_id: 'o2', change_type: 'field', target_path: '/hwpx/text[5]', before_value: '', after_value: '900101-1******' },
        ],
      },
    },
  },
  {
    slug: 'single-primitive-style-save',
    title: 'document — style + save payload inline diff',
    columns: 100,
    payload: {
      tool_id: 'document',
      correlation_id: 'corr-document-style-save-evidence',
      status: 'ok',
      text_summary: 'Styled and saved seoul-culture-application-plan.docx.',
      saved_exports: [
        {
          local_path: '/tmp/ummaya/tui-exports/seoul-culture-application-plan.docx',
          sha256: '9f59d2f1e8c4b0a8d1cafe000000000000000000000000000000000000000000',
        },
      ],
      diff: {
        diff_id: 'diff-document-style-save-evidence',
        source_artifact_id: 'working-style-save-docx',
        derivative_artifact_id: 'derivative-style-save-docx',
        changes: [
          {
            change_id: 'c1',
            operation_id: 'style-receipt',
            change_type: 'style',
            target_path: '/docx/table[1]/cell[2]/style',
            display_label: '접수번호 서식',
            before_value: '맑은 고딕 10pt',
            after_value: 'Malgun Gothic 12pt bold #1F4E79 on #FFF2CC',
          },
          {
            change_id: 'c2',
            operation_id: 'fill-receipt',
            change_type: 'field',
            target_path: '/docx/table[1]/cell[2]/text',
            display_label: '접수번호',
            before_value: '',
            after_value: 'UMMAYA-2026-0007',
          },
        ],
      },
    },
  },
  {
    slug: 'render-review',
    title: 'document_render — revdiff-style inline structural review',
    columns: 100,
    payload: {
      tool_id: 'document_render',
      correlation_id: 'corr-render-evidence',
      status: 'ok',
      text_summary: '근로계약서.docx 의 변경을 렌더링했습니다.',
      render_artifacts: [
        { render_artifact_id: 'render-evidence-001', render_path: '/tmp/ummaya/renders/evidence.svg', render_mime_type: 'image/svg+xml', page_number: 1, engine_id: 'rhwp-node-wasm' },
      ],
      diff: {
        diff_id: 'diff-render-evidence',
        source_artifact_id: 'working-render-evidence',
        derivative_artifact_id: 'derivative-render-evidence',
        changes: [
          { change_id: 'c1', operation_id: 'o1', change_type: 'field', target_path: '근무주차', before_value: '12 주차', after_value: '13 주차' },
        ],
      },
    },
  },
  {
    slug: 'blocked-no-engine',
    title: 'document_render blocked — no false success, no viewer',
    columns: 100,
    payload: {
      tool_id: 'document_render',
      correlation_id: 'corr-blocked-evidence',
      status: 'blocked',
      text_summary: 'No render-capable engine is registered for hwpx.',
      blocked_reason: 'unsupported_operation',
      promotion_gate_result: {
        capability: 'render',
        promotion_state: 'blocked',
        hard_gate_failures: ['hwpx_render_engine_unpromoted'],
      },
    },
  },
  {
    slug: 'narrow-terminal',
    title: 'document_apply_fill at 40 columns — width safe',
    columns: 40,
    payload: {
      tool_id: 'document_apply_fill',
      correlation_id: 'corr-narrow-evidence',
      status: 'ok',
      text_summary: '좁은 터미널에서도 폭을 넘지 않습니다.',
      diff: {
        diff_id: 'diff-narrow-evidence',
        source_artifact_id: 'working-narrow',
        derivative_artifact_id: 'derivative-narrow',
        changes: [
          { change_id: 'c1', operation_id: 'o1', change_type: 'field', target_path: '성명', before_value: '', after_value: '홍길동' },
        ],
      },
    },
  },
]

function frameFor(scenario: Scenario): string {
  const { lastFrame } = render(
    React.createElement(
      ThemeProvider,
      null,
      React.createElement(
        TerminalSizeContext.Provider,
        { value: { columns: scenario.columns, rows: 24 } },
        React.createElement(PrimitiveDispatcher, {
          payload: scenario.payload as never,
          expanded: scenario.expanded ?? false,
        }),
      ),
    ),
  )
  return lastFrame() ?? ''
}

function main(): void {
  const outDir = process.env['UMMAYA_EVIDENCE_OUT_DIR'] ?? join(import.meta.dir, '..', '..', '.evidence', 'document-diff')
  mkdirSync(outDir, { recursive: true })

  const manifest: Array<Record<string, unknown>> = []
  const lines: string[] = ['# Document revdiff-style inline TUI evidence (approach D2)', '']

  for (const scenario of SCENARIOS) {
    const frame = frameFor(scenario)
    const frameHash = createHash('sha256').update(frame).digest('hex')
    const framePath = join(outDir, `${scenario.slug}.txt`)
    mkdirSync(dirname(framePath), { recursive: true })
    writeFileSync(framePath, frame, 'utf-8')
    manifest.push({
      slug: scenario.slug,
      title: scenario.title,
      columns: scenario.columns,
      correlation_id: scenario.payload['correlation_id'],
      tool_id: scenario.payload['tool_id'],
      frame_hash: frameHash,
      frame_path: `${scenario.slug}.txt`,
      has_saved_exports: Array.isArray(scenario.payload['saved_exports']),
    })
    lines.push(`## ${scenario.title}`, '', '```', frame, '```', '', `frame_hash: \`${frameHash}\``, '')
  }

  writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf-8')
  writeFileSync(join(outDir, 'frames.md'), lines.join('\n'), 'utf-8')
  // eslint-disable-next-line no-console
  console.log(`Wrote ${SCENARIOS.length} document-diff evidence frames to ${outDir}`)
}

main()
