#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
// KOSMOS KSC 2026 presentation — Live-only scenario frame dump.
//
// Captures 2 additional Live-adapter scenarios (도로 안전 / 병원 검색) to
// complement the existing 응급 capture. All three scenarios use only Live
// adapters (KOROAD / KMA / HIRA / NMC / NFA119 / resolve_location) — no Mock.
// Each scenario fans out across 4 ministries to demonstrate KOSMOS's
// 부처 횡단 차별점 directly.

import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import React from 'react'
import { render } from 'ink-testing-library'
import { Box, Text } from 'ink'

import { ThemeProvider } from '../src/theme/provider'
import { CollectionList } from '../src/components/primitive/CollectionList'
import { DetailView } from '../src/components/primitive/DetailView'

const OUT_DIR = join(
  import.meta.dir,
  '..',
  '..',
  'docs',
  'presentation',
  'v0.1-alpha',
  'scenarios',
)
mkdirSync(OUT_DIR, { recursive: true })

interface ScenarioStep {
  readonly slug: string
  readonly description: string
  readonly element: React.ReactElement
}

function withTheme(child: React.ReactElement): React.ReactElement {
  return <ThemeProvider>{child}</ThemeProvider>
}

function CitizenMessage({ text }: { text: string }): React.ReactElement {
  return (
    <Box flexDirection="column" borderStyle="round" borderColor="#a78bfa" paddingX={2} paddingY={1}>
      <Text color="#7c3aed" bold>
        ✻ 시민
      </Text>
      <Text color="#e9d5ff">{text}</Text>
    </Box>
  )
}

function KosmosResponse({
  title,
  lines,
}: {
  title: string
  lines: readonly string[]
}): React.ReactElement {
  return (
    <Box flexDirection="column" borderStyle="round" borderColor="#7c3aed" paddingX={2} paddingY={1}>
      <Text color="#a78bfa" bold>
        ✻ KOSMOS · {title}
      </Text>
      {lines.map((line, idx) => (
        <Text key={idx} color="#e9d5ff">
          {line}
        </Text>
      ))}
    </Box>
  )
}

function ProcessingBanner({
  step,
  total,
  message,
}: {
  step: number
  total: number
  message: string
}): React.ReactElement {
  return (
    <Box borderStyle="single" borderColor="#5b21b6" paddingX={2} paddingY={0}>
      <Text color="#c4b5fd">
        ⏺ 단계 {step}/{total} · {message}
      </Text>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 시나리오 — 도로 안전 (KOROAD ×2 + KMA + resolve_location, 4 부처 fan-out)
// ---------------------------------------------------------------------------
const SCENARIO_ROAD: readonly ScenarioStep[] = [
  {
    slug: '도로안전/01-citizen-input',
    description: '도로 안전 — 시민 자연어 입력',
    element: withTheme(
      <CitizenMessage text="내일 부산에서 서울 가는데, 사고 잦은 구간 피해서 안전한 경로 추천해줘." />,
    ),
  },
  {
    slug: '도로안전/02-query-engine-search',
    description: '도로 안전 — 쿼리엔진 RAG 검색 (4 부처 후보)',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={2} total={5} message="K-EXAONE → RAG 검색 (BM25 + dense hybrid)" />
        <CollectionList
          payload={{
            kind: 'lookup',
            subtype: 'collection',
            tool_id: 'lookup',
            items: [
              { index: 1, title: 'koroad_accident_search', meta: '교통사고 잦은 곳 (KOROAD)' },
              { index: 2, title: 'koroad_accident_hazard_search', meta: '교통사고 위험구간 (KOROAD)' },
              { index: 3, title: 'kma_weather_alert_status', meta: '도로 기상 특보 (KMA)' },
              { index: 4, title: 'kma_short_term_forecast', meta: '단기 예보 시간별 (KMA)' },
              { index: 5, title: 'resolve_location', meta: '경로 좌표화 (juso/sgis/kakao)' },
            ],
          }}
        />
      </Box>,
    ),
  },
  {
    slug: '도로안전/03-permission-gauntlet',
    description: '도로 안전 — Layer 1 통과 (공개 데이터)',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={3} total={5} message="권한 게이트 — Layer 1 (api_key · 공개 데이터)" />
        <Box flexDirection="column" borderStyle="round" borderColor="#10b981" paddingX={2} paddingY={1}>
          <Text color="#34d399" bold>⓵ Layer 1 — 공개 데이터 통과</Text>
          <Text color="#e9d5ff">도구: koroad_accident_search · kma_weather_alert_status</Text>
          <Text color="#c4b5fd">사유: 공개 통계 / api_key 인증만</Text>
          <Text color="#7c3aed">→ 영수증: rcpt-road-2026-04-26-3A91 · 자동 통과</Text>
        </Box>
      </Box>,
    ),
  },
  {
    slug: '도로안전/04-adapter-detail',
    description: '도로 안전 — 4 부처 응답 합성 (사고 잦은 곳 + 위험구간 + 기상)',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={4} total={5} message="4 부처 동시 fan-out → 합성" />
        <DetailView
          payload={{
            kind: 'lookup',
            subtype: 'detail',
            tool_id: '4-adapter fan-out (KOROAD ×2 + KMA + resolve_location)',
            fields: [
              { label: '경로', value: '경부고속도로 부산 → 서울 (약 392 km)' },
              { label: '사고 잦은 곳 (연간 ≥ 5건)', value: '대전-천안 구간 3개소 · 안성IC 1개소' },
              { label: '위험구간 (KOROAD)', value: '추풍령 휴게소 인근 (포장 노후 + 굴곡)' },
              { label: 'KMA 도로 기상', value: '⚠ 안개 주의보 발효 (대전 03~07시) · 강풍 X' },
              { label: '경로 좌표 (kakao)', value: '37.5665, 126.9780 → 35.1796, 129.0756' },
              { label: '데이터 출처', value: 'KOROAD getRestFrequentzoneLg + getRestFrequentzoneHazard + KMA getPwnStatus' },
            ],
          }}
        />
      </Box>,
    ),
  },
  {
    slug: '도로안전/05-kosmos-response',
    description: '도로 안전 — KOSMOS 통합 응답 (부처 횡단)',
    element: withTheme(
      <KosmosResponse
        title="응답 (4 부처 통합)"
        lines={[
          '',
          '경부 고속도로 392 km 경로에 위험 구간 4개 식별:',
          '  · 대전-천안 (사고 잦은 곳 3개소)',
          '  · 안성IC (사고 잦은 곳 1개소)',
          '  · 추풍령 (포장 노후 + 굴곡 위험)',
          '',
          '⚠ KMA 안개 주의보 발효 — 대전 구간 03~07시 통과 시 감속 필수.',
          '',
          '권고: 새벽 시간대 대전 우회 (중부내륙) 경로 추천.',
          '데이터 출처: KOROAD ×2 + KMA + Kakao 로컬',
        ]}
      />,
    ),
  },
] as const

// ---------------------------------------------------------------------------
// 시나리오 — 병원 검색 (HIRA + KMA + resolve_location, 3 부처 fan-out)
// ---------------------------------------------------------------------------
const SCENARIO_HOSPITAL: readonly ScenarioStep[] = [
  {
    slug: '병원검색/01-citizen-input',
    description: '병원 검색 — 시민 자연어 입력',
    element: withTheme(
      <CitizenMessage text="아이가 열이 나는데 근처 야간 진료 소아과 어디 있어?" />,
    ),
  },
  {
    slug: '병원검색/02-query-engine-search',
    description: '병원 검색 — 쿼리엔진 RAG 검색',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={2} total={5} message="K-EXAONE → RAG 검색 (BM25 + dense hybrid)" />
        <CollectionList
          payload={{
            kind: 'lookup',
            subtype: 'collection',
            tool_id: 'lookup',
            items: [
              { index: 1, title: 'hira_hospital_search', meta: '병의원 + 진료과 검색 (HIRA)' },
              { index: 2, title: 'resolve_location', meta: '시민 위치 → 좌표 (kakao)' },
              { index: 3, title: 'kma_current_observation', meta: '현재 기온 / 강수 (KMA)' },
              { index: 4, title: 'kma_pre_warning', meta: '한파/폭염 예비특보 (KMA)' },
            ],
          }}
        />
      </Box>,
    ),
  },
  {
    slug: '병원검색/03-permission-gauntlet',
    description: '병원 검색 — Layer 1 통과',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={3} total={5} message="권한 게이트 — Layer 1 (공개 데이터)" />
        <Box flexDirection="column" borderStyle="round" borderColor="#10b981" paddingX={2} paddingY={1}>
          <Text color="#34d399" bold>⓵ Layer 1 — 공개 데이터 통과</Text>
          <Text color="#e9d5ff">도구: hira_hospital_search + kma_current_observation</Text>
          <Text color="#c4b5fd">사유: 공개 의료기관 정보 + 공개 기상 관측</Text>
          <Text color="#7c3aed">→ 영수증: rcpt-hosp-2026-04-26-5D7E · 자동 통과</Text>
        </Box>
      </Box>,
    ),
  },
  {
    slug: '병원검색/04-adapter-detail',
    description: '병원 검색 — 3 부처 응답 합성',
    element: withTheme(
      <Box flexDirection="column" gap={1}>
        <ProcessingBanner step={4} total={5} message="3 부처 동시 fan-out → 합성" />
        <DetailView
          payload={{
            kind: 'lookup',
            subtype: 'detail',
            tool_id: '3-adapter fan-out (HIRA + KMA + resolve_location)',
            fields: [
              { label: '추천 병원', value: '○○어린이병원 야간진료센터 (소아청소년과)' },
              { label: '거리 / 예상 도착', value: '5분 (1.2 km, 도보 15분)' },
              { label: '진료 시간', value: '평일 18:00~24:00 · 주말 09:00~24:00' },
              { label: '현재 시각 진료', value: '✓ 진료 중 (다음 마감 24:00)' },
              { label: '주차', value: '병원 부설 / 공영 (50m)' },
              { label: 'KMA 현재 기상', value: '기온 -3°C · ⚠ 한파 예비특보 (보온 필수)' },
              { label: '데이터 출처', value: 'HIRA getHospBasisList + KMA getUltraSrtNcst + Kakao 로컬' },
            ],
          }}
        />
      </Box>,
    ),
  },
  {
    slug: '병원검색/05-kosmos-response',
    description: '병원 검색 — KOSMOS 통합 응답',
    element: withTheme(
      <KosmosResponse
        title="응답 (3 부처 통합)"
        lines={[
          '',
          '가장 가까운 야간 진료 소아과:',
          '  ○○어린이병원 야간진료센터 (5분, 1.2 km)',
          '  · 진료 중 (마감 24:00)',
          '  · 소아청소년과 24시간 응급 대응',
          '  · 부설 주차장 + 공영 (50m)',
          '',
          '⚠ 현재 기온 -3°C — 한파 예비특보 발효 중. 아이 보온 충분히 챙기세요.',
          '',
          '데이터 출처: HIRA · KMA 실황 · Kakao 로컬',
        ]}
      />,
    ),
  },
] as const

const ALL_STEPS: readonly ScenarioStep[] = [...SCENARIO_ROAD, ...SCENARIO_HOSPITAL]

interface DumpOutcome {
  readonly slug: string
  readonly status: 'ok' | 'fail'
  readonly bytes: number
  readonly error?: string
}

function dump(step: ScenarioStep): DumpOutcome {
  try {
    const { lastFrame, unmount } = render(step.element)
    const frame = lastFrame() ?? '(empty frame)'
    const header = `# Citizen scenario frame — ${step.slug}\n# ${step.description}\n# Captured ${new Date().toISOString()} via ink-testing-library render()\n# KOSMOS v0.1-alpha · K-EXAONE-236B-A23B + FriendliAI Serverless\n\n`
    const txtPath = join(OUT_DIR, `${step.slug}.txt`)
    mkdirSync(join(OUT_DIR, step.slug.split('/')[0] ?? ''), { recursive: true })
    writeFileSync(txtPath, header + frame + '\n', 'utf-8')
    unmount()
    return { slug: step.slug, status: 'ok', bytes: frame.length }
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err)
    return { slug: step.slug, status: 'fail', bytes: 0, error }
  }
}

const outcomes = ALL_STEPS.map(dump)
const ok = outcomes.filter((o) => o.status === 'ok').length
const fail = outcomes.filter((o) => o.status === 'fail').length
console.log(`[dump-live-scenario-frames] ${ok} ok, ${fail} fail (out: ${OUT_DIR})`)
for (const o of outcomes) {
  console.log(
    `  ${o.status === 'ok' ? '✓' : '✗'} ${o.slug.padEnd(36)} ${o.status === 'ok' ? `${o.bytes}B` : o.error}`,
  )
}
process.exit(fail === 0 ? 0 : 1)
