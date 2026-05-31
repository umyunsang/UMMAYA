// SPDX-License-Identifier: Apache-2.0
// UI-D · Agency/worker visibility L2 extension · 2 decision points
//   D.1 /agents 상세 정보 (SLA · 마지막 호출 시각 · 건강)
//   D.2 swarm 활성 임계치 정의
//
// proposal-iv.mjs 의 5 states는 이미 확정. 여기선 세부 동작 제안만.
//
// Run: cd tui && bun ../docs/wireframes/ui-d-extensions.mjs

import { render } from 'ink'
import { h, Box, Text, C, Divider, BorderedNotice,
         CondensedLogo, PhaseIndicator, UserMsg, AsstLine } from './_shared.mjs'

// ══ D.1 · /agents 상세 정보 ════════════════════════════════════════════

function AgentsDetailed() {
  const rows = [
    { code: 'KOROAD', dot: C.findDot, status: 'live',    last: '2m',   health: 'OK',       avg: '320ms' },
    { code: 'KMA',    dot: C.findDot, status: 'live',    last: '10s',  health: 'OK',       avg: '140ms' },
    { code: 'HIRA',   dot: C.findDot, status: 'live',    last: '1m',   health: 'OK',       avg: '210ms' },
    { code: 'NMC',    dot: '#fbbf24',   status: 'shape',   last: '—',    health: '계약 미검증',  avg: '—' },
    { code: 'NFA',    dot: '#fbbf24',   status: 'handoff', last: '—',    health: '공식 경로 안내', avg: '—' },
    { code: 'MOHW',   dot: C.dim,       status: 'offline', last: '5m',   health: '인증 실패',    avg: 'ERR' },
  ]
  return h(BorderedNotice, {
    label: '◆ /agents --detail · 부처 에이전트 상세', color: C.brand, width: 72,
  },
    h(Box, null,
      h(Text, { color: C.dim, dimColor: true, bold: true },
        '  부처      상태      마지막     평균응답   건강'),
    ),
    ...rows.map((r, i) => h(Box, { key: i },
      h(Text, { color: r.dot, bold: true }, '  ⏺ '),
      h(Text, { bold: true }, r.code.padEnd(9)),
      h(Text, { color: C.subtle }, r.status.padEnd(10)),
      h(Text, null, r.last.padEnd(10)),
      h(Text, null, r.avg.padEnd(10)),
      h(Text, { color: r.status === 'live' ? '#34d399'
              : r.status === 'shape' || r.status === 'handoff' ? '#fbbf24' : C.red }, r.health),
    )),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '  /agents retry MOHW · /agents details KMA · 30s 간격 상태 폴링'))
  )
}

function AgentsSimple() {
  return h(BorderedNotice, {
    label: '◆ /agents · 간단 리스트 (기본)', color: C.brand, width: 60,
  },
    h(Text, null,
      h(Text, { color: C.findDot, bold: true }, '  ⏺ KOROAD  '),
      h(Text, null, '도로교통공단'),
    ),
    h(Text, null,
      h(Text, { color: C.findDot, bold: true }, '  ⏺ KMA     '),
      h(Text, null, '기상청'),
    ),
    h(Text, null,
      h(Text, { color: C.findDot, bold: true }, '  ⏺ HIRA    '),
      h(Text, null, '건강보험심사평가원'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '  /agents --detail 로 SLA · 건강 · 응답속도 확인'))
  )
}

// ══ D.2 · Swarm 활성 임계치 ═════════════════════════════════════════════

function SwarmThresholds() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  옵션 A · 부처 개수 기반 (단순)'),
    h(Box, { marginLeft: 4 },
      h(Text, null, '· 1-2 부처 필요 → 단일 LLM function calling'),
      h(Text, null, '· 3+ 부처 필요 → swarm 활성, 각 부처별 worker'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.subtle }, '  옵션 B · 토큰 예산 기반')),
    h(Box, { marginLeft: 4 },
      h(Text, null, '· system prompt + adapter schemas < 4k → 단일'),
      h(Text, null, '· 그 이상 → swarm (context 분산)'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.subtle }, '  옵션 C · LLM 판단 기반 (동적)')),
    h(Box, { marginLeft: 4 },
      h(Text, null, '· 첫 응답에서 LLM이 "복잡" 태그 방출 → swarm 활성'),
      h(Text, null, '· 복잡도 신호: 기관≥3, send 필요, check 필요, 등'),
    ),
    h(Box, { marginTop: 2 },
      h(Text, { color: C.brand },
        '  👉 권장: A + C 혼합 — 명시적 3+ 트리거 + LLM "복잡" 태그 보정')),
  )
}

function SwarmActiveExample() {
  return h(Box, { flexDirection: 'column' },
    h(CondensedLogo),
    h(Box, { marginTop: 1 }, h(PhaseIndicator, { phase: 'swarm' })),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '  [swarm 활성 근거] 임계치 A 매칭 (3 부처 감지) + LLM "복잡" 태그 확인'),
    ),
    h(Box, { marginTop: 1 }, h(UserMsg, {
      text: '이사 준비 중이야. 전입신고·자동차·건보 주소변경 다 해야해',
    })),
    h(Box, { marginTop: 1 }, h(AsstLine, {
      text: 'assistant: check 이후 3개 기관 worker 분기 · Coordinator가 순서 조율',
    })),
  )
}

function Section({ title, children }) {
  return h(Box, { flexDirection: 'column', marginBottom: 2 },
    h(Divider, { label: title }),
    h(Box, { marginLeft: 2, marginTop: 1 }, children),
  )
}

function App() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { bold: true, color: C.brand }, 'UI-D · Agency/Worker Visibility L2'),
    h(Text, { color: C.subtle },
      '5 states는 proposal-iv.mjs로 확정 · 여기선 D.1/D.2 세부 결정만'),

    h(Section, { title: 'D.1 · /agents 명령 출력 두 레벨' },
      h(Box, { flexDirection: 'column' },
        h(Text, { color: C.subtle }, '(a) 기본 모드:'),
        h(AgentsSimple),
        h(Box, { marginTop: 1 }, h(Text, { color: C.subtle }, '(b) --detail 플래그:')),
        h(AgentsDetailed),
      )
    ),

    h(Section, { title: 'D.2 · Swarm 활성 임계치' },
      h(Box, { flexDirection: 'column' },
        h(SwarmThresholds),
        h(Box, { marginTop: 2 },
          h(Text, { color: C.subtle }, '실제 swarm 활성 시 화면 (예시):')),
        h(Box, { marginTop: 1, marginLeft: 2 }, h(SwarmActiveExample)),
      )
    ),

    h(Divider, { label: '요청' }),
    h(Box, { flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.dim }, 'D.1 /agents 두 레벨(기본/--detail) OK?'),
      h(Text, { color: C.dim }, 'D.2 swarm 임계치: A(부처개수) / B(토큰) / C(LLM태그) / A+C(권장)'),
    ),
  )
}

render(h(App))
