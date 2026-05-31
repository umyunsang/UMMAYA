// SPDX-License-Identifier: Apache-2.0
// UI-E · 보조 surface L2 드릴다운 · 5 decision points
//   E.1 HelpV2 레이아웃 (그룹화 · 검색)
//   E.2 Config overlay 구조
//   E.3 Plugin browser UX
//   E.4 Export PDF 레이아웃
//   E.5 History search 기본 옵션
//
// Run: cd tui && bun ../docs/wireframes/ui-e-auxiliary.mjs

import { render } from 'ink'
import { h, Box, Text, C, Divider, BorderedNotice } from './_shared.mjs'

// ── E.1 · HelpV2 레이아웃 ══════════════════════════════════════════════
function HelpView() {
  return h(BorderedNotice, {
    label: '◆ /help · 자주 쓰는 커맨드', color: C.brand, width: 72,
  },
    h(Text, { bold: true, color: C.subtle }, '세션'),
    h(Text, null, '  /new          새 대화'),
    h(Text, null, '  /resume       최근 세션 재개'),
    h(Text, null, '  /fork-session 현재 세션 분기'),
    h(Box, { marginTop: 1 }, h(Text, { bold: true, color: C.subtle }, '권한')),
    h(Text, null, '  /consent      동의 이력 / 철회'),
    h(Text, null, '  ⇧⇥           권한 모드 전환'),
    h(Box, { marginTop: 1 }, h(Text, { bold: true, color: C.subtle }, '도구')),
    h(Text, null, '  /agents       활성 부처 에이전트'),
    h(Text, null, '  /plugins      설치된 플러그인'),
    h(Box, { marginTop: 1 }, h(Text, { bold: true, color: C.subtle }, '세션 저장')),
    h(Text, null, '  /export pdf   세션 PDF 내보내기'),
    h(Text, null, '  /history      이전 세션 검색'),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '? 로 도움말 토글 · / 입력시 자동완성')
    ),
  )
}

// ── E.2 · Config overlay ═══════════════════════════════════════════════
function ConfigOverlay() {
  const items = [
    { k: 'UMMAYA_TUI_THEME',          v: 'dark',         edit: true },
    { k: 'UMMAYA_REDUCED_MOTION',     v: '0',            edit: true },
    { k: 'UMMAYA_OTEL_DISABLED',      v: '0',            edit: true },
    { k: 'UMMAYA_AGENT_MAILBOX_ROOT', v: '~/.ummaya/...', edit: false },
    { k: 'UMMAYA_FRIENDLI_TOKEN',     v: '(secret)',     edit: false },
  ]
  return h(BorderedNotice, {
    label: '◆ /config · UMMAYA 환경 설정', color: C.brand, width: 72,
  },
    ...items.map((it, i) => h(Box, { key: i },
      h(Text, { color: it.edit ? C.text : C.dim, dimColor: !it.edit },
        it.k.padEnd(28)),
      h(Text, { color: C.subtle }, `  ${it.v.padEnd(20)}`),
      h(Text, { color: C.dim, dimColor: true },
        it.edit ? ' [편집]' : ' [읽기전용]'),
    )),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '↑↓ 이동 · Enter 편집 · 비밀값은 .env 편집 필요'))
  )
}

// ── E.3 · Plugin browser ═══════════════════════════════════════════════
function PluginBrowser() {
  const plugins = [
    { id: 'seoul-subway',  on: true,  ver: '0.2.1', desc: '지하철 실시간 도착' },
    { id: 'post-office',   on: true,  ver: '0.1.3', desc: '우체국 택배 추적' },
    { id: 'nts-homtax',    on: false, ver: '0.1.0', desc: '홈택스 shape-mirror' },
    { id: 'nhis-check',    on: false, ver: '0.1.0', desc: '건강검진 handoff' },
  ]
  return h(BorderedNotice, {
    label: '◆ /plugins · 설치된 플러그인', color: '#a78bfa', width: 72,
  },
    ...plugins.map((p, i) => h(Box, { key: i },
      h(Text, { color: p.on ? C.ring : C.dim, dimColor: !p.on },
        p.on ? '⏺ ' : '○ '),
      h(Text, { bold: p.on }, p.id.padEnd(18)),
      h(Text, { color: C.dim, dimColor: true }, `${p.ver}  `),
      h(Text, { color: p.on ? C.subtle : C.dim, dimColor: !p.on }, p.desc),
    )),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '↑↓ 이동 · Space 토글 · i 상세 · r 제거 · a ummaya-plugin-store 추가')),
  )
}

// ── E.4 · Export PDF 레이아웃 ══════════════════════════════════════════
function ExportPDF() {
  return h(BorderedNotice, {
    label: '◆ /export pdf · 세션 PDF 내보내기', color: C.brand, width: 72,
  },
    h(Text, null, '파일명:  ummaya-session-2026-04-24-1402.pdf'),
    h(Text, null, '포함:    ✓ 대화 · ✓ 도구 호출 · ✓ 권한 영수증'),
    h(Text, null, '제외:    ✗ OTEL 로그 · ✗ 플러그인 내부 상태'),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true }, 'PDF 1페이지:')),
    h(Box, { marginLeft: 2, marginTop: 1, borderStyle: 'single',
             borderColor: C.dim, paddingX: 1 },
      h(Text, { bold: true }, 'UMMAYA 세션 기록'),
      h(Text, { color: C.dim }, '2026-04-24 14:02:31 · session ab12cd34'),
      h(Text, null, ''),
      h(Text, null, '[사용자] 오늘 서울 날씨 어때?'),
      h(Text, null, '[도구] KMA.find [LIVE]'),
      h(Text, null, '  → 12°C 맑음, 미세먼지 보통'),
      h(Text, null, '[답변] 서울 현재 12°C, 맑고 미세먼지는 보통입니다.'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.brand, bold: true }, '[Y] '),
      h(Text, null, '저장   '),
      h(Text, { color: C.brand, bold: true }, '[E] '),
      h(Text, null, '설정 편집   '),
      h(Text, { color: C.brand, bold: true }, '[N] '),
      h(Text, null, '취소'),
    ),
  )
}

// ── E.5 · History search ═══════════════════════════════════════════════
function HistorySearch() {
  return h(BorderedNotice, {
    label: '◆ /history · 이전 세션 검색', color: C.brand, width: 72,
  },
    h(Box, null,
      h(Text, { color: C.brand, bold: true }, '검색: '),
      h(Text, null, '전입신고'),
      h(Text, { color: C.ring }, '▍'),
    ),
    h(Text, { color: C.dim, dimColor: true },
      '필터: 날짜 전체 · 세션 전체 · Layer 전체'),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.subtle, bold: true }, '결과 3건:')),
    h(Text, null, '  2026-04-22  · MOIS 전입신고 절차 조회'),
    h(Text, null, '  2026-04-20  · 이사 준비 복합 질의'),
    h(Text, null, '  2026-04-18  · 주소 변경 관련 질의'),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '↑↓ 이동 · Enter 세션 열기 · f 필터 변경 · Esc 닫기'),
    ),
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
    h(Text, { bold: true, color: C.brand }, 'UI-E · 보조 surface L2'),
    h(Text, { color: C.subtle }, 'Help · Config · Plugin browser · Export PDF · History'),

    h(Section, { title: 'E.1 · HelpV2 그룹화 레이아웃' }, h(HelpView)),
    h(Section, { title: 'E.2 · Config overlay · env 편집' }, h(ConfigOverlay)),
    h(Section, { title: 'E.3 · Plugin browser' }, h(PluginBrowser)),
    h(Section, { title: 'E.4 · Export PDF · 세션 저장' }, h(ExportPDF)),
    h(Section, { title: 'E.5 · History search' }, h(HistorySearch)),

    h(Divider, { label: '요청' }),
    h(Box, { flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.dim }, 'E.1 Help 그룹: 세션/권한/도구/저장 OK?'),
      h(Text, { color: C.dim }, 'E.2 Config: 비밀값은 .env 편집으로 격리 OK?'),
      h(Text, { color: C.dim }, 'E.3 Plugin: ⏺/○ 토글 + id 인라인 레이아웃 OK?'),
      h(Text, { color: C.dim }, 'E.4 PDF 포함/제외 항목 OK?'),
      h(Text, { color: C.dim }, 'E.5 History 필터(날짜·세션·Layer) 3종 OK?'),
    ),
  )
}

render(h(App))
