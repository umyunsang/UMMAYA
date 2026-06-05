#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
// Spec 1635 P4 UI L2 — UX snapshot dumper.
//
// Renders current, live TUI surfaces through the same UMMAYA Ink runtime used
// by focused component tests. Output is written to:
// specs/1635-ui-l2-citizen-port/ux-snapshots/<surface>.txt

import React from 'react'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { PassThrough, Writable } from 'node:stream'

import { AppStateProvider } from '../src/state/AppState.js'
import { KeybindingSetup } from '../src/keybindings/KeybindingProviderSetup.js'
import { render as renderInk, Box, Text } from '../src/ink.js'
import { ThemeProvider } from '../src/theme/provider.js'

import { WelcomeV2 } from '../src/components/LogoV2/WelcomeV2.js'
import { UmmayaPrimitivePermissionRequest } from '../src/components/permissions/UmmayaPrimitivePermissionRequest/UmmayaPrimitivePermissionRequest.js'
import { BypassPermissionsModeDialog } from '../src/components/BypassPermissionsModeDialog.js'
import { ConsentListView } from '../src/components/consent/ConsentListView.js'
import { ConsentRevokeConfirmDialog } from '../src/components/consent/ConsentRevokeConfirmDialog.js'
import { ErrorEnvelope } from '../src/components/messages/ErrorEnvelope.js'
import { ContextQuoteBlock } from '../src/components/messages/ContextQuoteBlock.js'
import { StreamingChunk } from '../src/components/messages/StreamingChunk.js'
import { SlashCommandSuggestions } from '../src/components/PromptInput/SlashCommandSuggestions.js'
import { HelpV2Grouped } from '../src/components/help/HelpV2Grouped.js'
import {
  PluginBrowser,
  type PluginEntry,
} from '../src/components/plugins/PluginBrowser.js'
import { PointCard } from '../src/components/primitive/PointCard.js'
import { CollectionList } from '../src/components/primitive/CollectionList.js'
import { DetailView } from '../src/components/primitive/DetailView.js'
import { TimeseriesTable } from '../src/components/primitive/TimeseriesTable.js'
import { ErrorBanner } from '../src/components/primitive/ErrorBanner.js'
import { SubmitReceipt } from '../src/components/primitive/SubmitReceipt.js'
import { SubmitErrorBanner } from '../src/components/primitive/SubmitErrorBanner.js'
import { AuthContextCard } from '../src/components/primitive/AuthContextCard.js'

import type { PermissionReceiptT } from '../src/schemas/ui-l2/permission.js'
import type { ErrorEnvelopeT } from '../src/schemas/ui-l2/error.js'

const OUT_DIR = join(
  import.meta.dir,
  '..',
  '..',
  'specs',
  '1635-ui-l2-citizen-port',
  'ux-snapshots',
)
mkdirSync(OUT_DIR, { recursive: true })

process.env['UMMAYA_TUI_LOCALE'] ??= 'ko'

type Snapshot = {
  readonly name: string
  readonly note: string
  readonly component: React.ReactElement
}

type TestStdin = PassThrough & {
  isTTY: true
  isRaw: boolean
  setRawMode: (mode: boolean) => void
  ref: () => TestStdin
  unref: () => TestStdin
}

type TestStdout = Writable & {
  isTTY: true
  columns: number
  rows: number
  output: string
}

function tick(ms = 80): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function makeLocalInkStreams(): { stdin: TestStdin; stdout: TestStdout } {
  const stdin = new PassThrough() as TestStdin
  stdin.isTTY = true
  stdin.isRaw = false
  stdin.setRawMode = (mode: boolean) => {
    stdin.isRaw = mode
  }
  stdin.ref = () => stdin
  stdin.unref = () => stdin

  const stdout = new Writable({
    write(chunk, _encoding, callback) {
      stdout.output += chunk.toString()
      callback()
    },
  }) as TestStdout
  stdout.isTTY = true
  stdout.columns = 110
  stdout.rows = 34
  stdout.output = ''

  return { stdin, stdout }
}

function normalizeFrameText(output: string): string {
  return output
    .replace(/\u001B\]([^\u0007]|\u001B\\)*(\u0007|\u001B\\)/g, '')
    .replace(/\u001B\[1C/g, ' ')
    .replace(/\u001B\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(/\r/g, '')
}

function Runtime({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <AppStateProvider>
      <KeybindingSetup>
        <ThemeProvider>{children}</ThemeProvider>
      </KeybindingSetup>
    </AppStateProvider>
  )
}

async function renderSnapshot(component: React.ReactElement): Promise<string> {
  const streams = makeLocalInkStreams()
  const instance = await renderInk(<Runtime>{component}</Runtime>, {
    stdin: streams.stdin,
    stdout: streams.stdout,
    stderr: streams.stdout,
    exitOnCtrlC: false,
    patchConsole: false,
  })

  try {
    await tick()
    return normalizeFrameText(streams.stdout.output) || '<empty frame>'
  } finally {
    instance.unmount()
    instance.cleanup()
  }
}

function receipt(overrides: Partial<PermissionReceiptT> = {}): PermissionReceiptT {
  return {
    receipt_id: 'rcpt-7d3a8f2e9c4b',
    layer: 2,
    tool_name: 'gov24_application_submit',
    decision: 'allow_once',
    decided_at: '2026-04-25T12:00:00.000Z',
    session_id: 'sess-ui-l2-snapshot',
    revoked_at: null,
    ...overrides,
  }
}

const plugins: PluginEntry[] = [
  {
    id: 'ummaya-koroad',
    name: 'KOROAD Traffic',
    version: '0.1.0',
    description_ko: '도로교통공단 사고 정보 조회',
    description_en: 'KOROAD traffic accident lookup',
    isActive: true,
    tier: 'live',
    layer: 1,
  },
  {
    id: 'ummaya-gov24',
    name: 'Government24 Submit',
    version: '0.0.5',
    description_ko: '정부24 민원 제출 모의 어댑터',
    description_en: 'Government24 submission mock adapter',
    isActive: false,
    tier: 'mock',
    layer: 3,
  },
]

const llmError: ErrorEnvelopeT = {
  type: 'llm',
  title_ko: 'LLM 응답 오류',
  title_en: 'LLM response error',
  detail_ko: 'EXAONE 모델이 4xx 응답을 반환했습니다.',
  detail_en: 'EXAONE returned a 4xx response.',
  retry_suggested: true,
  occurred_at: '2026-04-25T12:00:00.000Z',
}

const toolError: ErrorEnvelopeT = {
  type: 'tool',
  title_ko: '도구 호출 오류',
  title_en: 'Tool invocation error',
  detail_ko: 'KOROAD 어댑터가 timeout 에러를 반환했습니다.',
  detail_en: 'KOROAD adapter returned timeout.',
  retry_suggested: true,
  occurred_at: '2026-04-25T12:00:00.000Z',
}

const networkError: ErrorEnvelopeT = {
  type: 'network',
  title_ko: '네트워크 연결이 끊어졌습니다',
  title_en: 'Network connection lost',
  detail_ko: '5초간 응답이 없습니다. 다시 시도해주세요.',
  detail_en: 'No response for 5 seconds. Please retry.',
  retry_suggested: true,
  occurred_at: '2026-04-25T12:00:00.000Z',
}

const snapshots: Snapshot[] = [
  {
    name: '01-welcome-v2',
    note: 'Current welcome surface with UMMAYA brand glyph',
    component: <WelcomeV2 />,
  },
  {
    name: '02-permission-check-layer1',
    note: 'check primitive permission modal, layer 1 glyph',
    component: (
      <UmmayaPrimitivePermissionRequest
        primitive="check"
        toolName="hira_hospital_search"
        onDecision={() => {}}
      />
    ),
  },
  {
    name: '03-permission-send-layer2',
    note: 'send primitive reversible permission modal, layer 2 glyph',
    component: (
      <UmmayaPrimitivePermissionRequest
        primitive="send"
        toolName="gov24_draft_submit"
        onDecision={() => {}}
      />
    ),
  },
  {
    name: '04-permission-send-layer3',
    note: 'send primitive irreversible permission modal, layer 3 glyph plus receipt',
    component: (
      <UmmayaPrimitivePermissionRequest
        primitive="send"
        toolName="payment_rail_commit"
        isIrreversible
        receiptId="rcpt-layer3-final"
        onDecision={() => {}}
      />
    ),
  },
  {
    name: '05-consent-list-empty',
    note: '/consent empty receipt list',
    component: <ConsentListView receipts={[]} onExit={() => {}} />,
  },
  {
    name: '06-consent-list-populated',
    note: '/consent receipt table with revoked marker',
    component: (
      <ConsentListView
        receipts={[
          receipt({ receipt_id: 'rcpt-active001', layer: 1, tool_name: 'kma_forecast' }),
          receipt({
            receipt_id: 'rcpt-revoked02',
            layer: 3,
            decision: 'allow_session',
            revoked_at: '2026-04-25T13:00:00.000Z',
          }),
        ]}
        onExit={() => {}}
      />
    ),
  },
  {
    name: '07-consent-revoke-confirm',
    note: '/consent revoke confirmation modal',
    component: (
      <ConsentRevokeConfirmDialog
        receipt={receipt()}
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    ),
  },
  {
    name: '08-consent-revoke-already',
    note: '/consent revoke already-revoked modal copy',
    component: (
      <ConsentRevokeConfirmDialog
        receipt={receipt({ revoked_at: '2026-04-25T13:00:00.000Z' })}
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    ),
  },
  {
    name: '09-bypass-permissions-dialog',
    note: 'Bypass permissions warning dialog',
    component: <BypassPermissionsModeDialog onAccept={() => {}} />,
  },
  {
    name: '10-error-envelope-llm',
    note: 'LLM error envelope',
    component: <ErrorEnvelope error={llmError} onRetry={() => {}} />,
  },
  {
    name: '11-error-envelope-tool',
    note: 'Tool error envelope',
    component: <ErrorEnvelope error={toolError} onRetry={() => {}} />,
  },
  {
    name: '12-error-envelope-network',
    note: 'Network error envelope',
    component: <ErrorEnvelope error={networkError} onRetry={() => {}} />,
  },
  {
    name: '13-context-quote-block',
    note: 'Context quote with thread glyph',
    component: (
      <ContextQuoteBlock label="Turn 3">
        <Text>시민님이 의료급여 신청을 시작했습니다.</Text>
      </ContextQuoteBlock>
    ),
  },
  {
    name: '14-streaming-chunk-active',
    note: 'Streaming response chunk with active hint',
    component: (
      <StreamingChunk
        streamedText="오늘 서울 강남구 일대 도로 상황을 조회하고 있습니다. 현재 잠실대교 부근에서 "
        isStreaming
      />
    ),
  },
  {
    name: '15-slash-autocomplete',
    note: 'Slash command suggestions after /c',
    component: <SlashCommandSuggestions inputText="/c" selectedIndex={0} />,
  },
  {
    name: '16-help-v2-grouped',
    note: '/help grouped command catalog',
    component: <HelpV2Grouped onDismiss={() => {}} />,
  },
  {
    name: '17-plugin-browser',
    note: '/plugins browser with live/mock rows',
    component: (
      <PluginBrowser
        plugins={plugins}
        onToggle={() => {}}
        onDetail={() => {}}
        onRemove={() => {}}
        onMarketplace={() => {}}
        onDismiss={() => {}}
      />
    ),
  },
  {
    name: '18-plugin-browser-empty',
    note: '/plugins empty-state',
    component: (
      <PluginBrowser
        plugins={[]}
        onToggle={() => {}}
        onDetail={() => {}}
        onRemove={() => {}}
        onMarketplace={() => {}}
        onDismiss={() => {}}
      />
    ),
  },
  {
    name: '19-primitive-point-card',
    note: 'find point renderer',
    component: (
      <PointCard
        payload={{
          kind: 'find',
          subtype: 'point',
          tool_id: 'koroad_accident_search',
          title: '서울특별시 강남구 테헤란로',
          subtitle: '교통사고 잦은 곳',
          fields: [
            { label: '사고 건수', value: '17건' },
            { label: '제한 속도', value: '50 km/h' },
          ],
        }}
      />
    ),
  },
  {
    name: '20-primitive-collection-list',
    note: 'find collection renderer',
    component: (
      <CollectionList
        payload={{
          kind: 'find',
          subtype: 'collection',
          tool_id: 'find',
          items: [
            { index: 1, title: 'koroad_accident_search', meta: '교통사고 잦은 곳' },
            { index: 2, title: 'kma_short_term_forecast', meta: '단기 예보' },
            { index: 3, title: 'hira_hospital_search', meta: '병의원 검색' },
          ],
        }}
      />
    ),
  },
  {
    name: '21-primitive-detail-view',
    note: 'find detail renderer',
    component: (
      <DetailView
        payload={{
          kind: 'find',
          subtype: 'detail',
          tool_id: 'hira_hospital_search',
          fields: [
            { label: '기관명', value: '서울시민병원' },
            { label: '진료과', value: '내과, 응급의학과' },
          ],
        }}
      />
    ),
  },
  {
    name: '22-primitive-timeseries',
    note: 'find timeseries renderer',
    component: (
      <TimeseriesTable
        payload={{
          kind: 'find',
          subtype: 'timeseries',
          tool_id: 'kma_short_term_forecast',
          unit: '°C',
          rows: [
            { ts: '2026-04-25T09:00', value: '11.2' },
            { ts: '2026-04-25T12:00', value: '15.8' },
            { ts: '2026-04-25T15:00', value: '17.4' },
          ],
        }}
      />
    ),
  },
  {
    name: '23-primitive-find-error',
    note: 'find error renderer',
    component: (
      <ErrorBanner
        payload={{
          kind: 'find',
          subtype: 'error',
          tool_id: 'data_go_kr_lookup',
          title: '조회 실패',
          description: '공공데이터 응답 시간이 초과되었습니다.',
          retry_hint: '잠시 후 다시 조회하세요.',
        }}
      />
    ),
  },
  {
    name: '24-primitive-submit-success',
    note: 'send success receipt renderer',
    component: (
      <SubmitReceipt
        payload={{
          kind: 'send',
          tool_id: 'gov24_mock_submit',
          family: 'submit_application',
          ok: true,
          confirmation_id: 'GOV24-20260425-001',
          timestamp: '2026-04-25T12:00:00+09:00',
          summary: '정부24 민원 제출 모의 접수가 완료되었습니다.',
          mock_reason: 'delegation_absent',
        }}
      />
    ),
  },
  {
    name: '25-primitive-submit-error',
    note: 'send failure renderer',
    component: (
      <SubmitErrorBanner
        payload={{
          kind: 'send',
          tool_id: 'payment_rail_commit',
          family: 'pay',
          ok: false,
          error_code: 'permission_required',
          message: '레이어 3 권한 확인이 필요합니다.',
          retry_hint: '/consent에서 권한을 확인하세요.',
          mock_reason: 'payment_rail',
        }}
      />
    ),
  },
  {
    name: '26-primitive-auth-context',
    note: 'check success renderer',
    component: (
      <AuthContextCard
        payload={{
          kind: 'check',
          tool_id: 'mobile_id_verify',
          family: 'mobile_id',
          ok: true,
          korea_tier: '모바일 신분증',
          nist_aal_hint: 'AAL2',
          identity_label: '홍길동 (1985년생)',
        }}
      />
    ),
  },
]

let pass = 0
let fail = 0
const failures: Array<{ name: string; error: string }> = []

for (const snapshot of snapshots) {
  try {
    const frame = await renderSnapshot(snapshot.component)
    const out = [
      `# UX Snapshot: ${snapshot.name}`,
      `# Note: ${snapshot.note}`,
      `# Generated: ${new Date().toISOString()}`,
      '',
      frame,
      '',
    ].join('\n')
    writeFileSync(join(OUT_DIR, `${snapshot.name}.txt`), out, 'utf8')
    pass += 1
    console.log(`OK ${snapshot.name}`)
  } catch (err) {
    fail += 1
    const error = err instanceof Error ? err.message : String(err)
    failures.push({ name: snapshot.name, error })
    console.error(`FAIL ${snapshot.name}: ${error}`)
  }
}

const indexLines = [
  '# UX Snapshots — Spec 1635 P4 UI L2 Citizen Port',
  `# Generated: ${new Date().toISOString()}`,
  `# Pass: ${pass} · Fail: ${fail} · Total: ${snapshots.length}`,
  '',
]
for (const snapshot of snapshots) {
  indexLines.push(`- ${snapshot.name}.txt — ${snapshot.note}`)
}
writeFileSync(join(OUT_DIR, 'INDEX.txt'), `${indexLines.join('\n')}\n`, 'utf8')

console.log('')
console.log('=== Summary ===')
console.log(`Pass: ${pass} / Fail: ${fail} / Total: ${snapshots.length}`)
console.log(`Output: ${OUT_DIR}`)

if (fail > 0) {
  console.log('')
  console.log('Failures:')
  for (const failure of failures) {
    console.log(`  ${failure.name}: ${failure.error}`)
  }
  process.exit(1)
}
