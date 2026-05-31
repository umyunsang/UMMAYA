// SPDX-License-Identifier: Apache-2.0
// UI-C · Permission Gauntlet L2 드릴다운 · 5 decision points
//   C.1 Layer 1/2/3 색·글리프 규약
//   C.2 consent receipt 표시 위치
//   C.3 권한 이력 조회 (/consent 커맨드)
//   C.4 철회 플로우
//   C.5 권한 모드 전환 UX (Shift+Tab)
//
// Run: cd tui && bun ../docs/wireframes/ui-c-permission.mjs

import { render } from 'ink'
import { h, Box, Text, C, Divider, BorderedNotice,
         CondensedLogo, PromptBand, PromptFooter } from './_shared.mjs'

// Layer palette
const L1 = { color: '#34d399', glyph: '⓵', label: 'find/locate · Layer 1', desc: '공개/저위험 조회 · 자동 승인' }
const L2 = { color: '#f87171', glyph: '⓶', label: 'check · Layer 2', desc: '본인확인/위임 · 명시 동의' }
const L3 = { color: '#fb923c', glyph: '⓷', label: 'send · Layer 3', desc: '제출/납부/접수 · 최종 확인' }

// ── C.1 · Layer 색·글리프 규약 ─────────────────────────────────────────
function LayerBadge({ L }) {
  return h(Box, null,
    h(Text, { color: L.color, bold: true }, `${L.glyph} `),
    h(Text, { bold: true }, L.label),
    h(Text, { color: C.dim, dimColor: true }, `   ${L.desc}`),
  )
}

// ── C.2 · Permission Modal (Layer 2 예시) ══════════════════════════════
function PermissionModal({ L }) {
  return h(Box, { flexDirection: 'column',
                  borderStyle: 'round', borderColor: L.color,
                  paddingX: 2, paddingY: 1, width: 70 },
    h(Box, null,
      h(Text, { color: L.color, bold: true }, `${L.glyph} `),
      h(Text, { bold: true }, '권한 확인 필요 · '),
      h(Text, { color: L.color }, L.label),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim }, '요청: '),
      h(Text, null, 'AUTH 주소변경 위임 확인 · mock_verify_module_simple_auth'),
    ),
    h(Box, null,
      h(Text, { color: C.dim }, '정보: '),
      h(Text, null, '목적·범위·세션 ID (PIPA §17 처리위탁)'),
    ),
    h(Box, { marginTop: 1, flexDirection: 'row', justifyContent: 'space-between' },
      h(Text, null,
        h(Text, { color: C.brand, bold: true }, '[Y] '),
        h(Text, null, '한 번 허용   '),
        h(Text, { color: C.brand, bold: true }, '[A] '),
        h(Text, null, '세션 내 자동   '),
        h(Text, { color: C.brand, bold: true }, '[N] '),
        h(Text, null, '거부'),
      ),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true }, '영수증: rcpt-01943af2-5e27-72b5-...'),
    ),
  )
}

// ── C.3 · /consent 명령 결과 (권한 이력) ═══════════════════════════════
function ConsentHistory() {
  const rows = [
    { t: '14:02:31', layer: L1, adapter: 'KMA.find', action: '자동' },
    { t: '14:05:12', layer: L2, adapter: 'AUTH.check', action: '허용' },
    { t: '14:07:55', layer: L3, adapter: 'GOV24.send', action: '거부' },
    { t: '14:12:08', layer: L3, adapter: 'GOV24.send', action: '허용' },
  ]
  return h(BorderedNotice, {
    label: '◆ 동의 이력 · 현재 세션', color: C.brand, width: 70,
  },
    ...rows.map((r, i) => h(Box, { key: i },
      h(Text, { color: C.dim, dimColor: true }, `${r.t}  `),
      h(Text, { color: r.layer.color, bold: true }, `${r.layer.glyph} `),
      h(Text, null, `${r.adapter.padEnd(18)} `),
      h(Text, { color: r.action === '거부' ? C.red : C.subtle }, r.action),
    )),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        `/consent revoke <id> · /consent list --all`)
    ),
  )
}

// ── C.4 · 철회 플로우 ═════════════════════════════════════════════════
function RevokeFlow() {
  return h(Box, { flexDirection: 'column' },
    h(Box, { flexDirection: 'row' },
      h(Text, { color: C.brand, bold: true }, '> '),
      h(Text, null, '/consent revoke rcpt-01943af2'),
    ),
    h(Box, { marginTop: 1 },
      h(BorderedNotice, {
        label: '⚠ 동의 철회 · 이 영수증에 묶인 작업 중단', color: C.red, width: 70,
      },
        h(Text, null, '어댑터: GOVERNMENT24.send · 전입신고 접수'),
        h(Text, null, '시각: 2026-04-24 14:05:12'),
        h(Box, { marginTop: 1 },
          h(Text, { color: C.brand, bold: true }, '[Y] '),
          h(Text, null, '철회 확정   '),
          h(Text, { color: C.brand, bold: true }, '[N] '),
          h(Text, null, '취소'),
        ),
      )
    ),
  )
}

// ── C.5 · 권한 모드 전환 (Shift+Tab) ═══════════════════════════════════
function ModeSwitch() {
  const modes = [
    { id: 'default', color: C.subtle, label: '기본' },
    { id: 'plan', color: '#c084fc', label: 'plan' },
    { id: 'acceptEdits', color: '#34d399', label: 'accept edits' },
    { id: 'bypassPermissions', color: C.red, label: 'bypass' },
    { id: 'dontAsk', color: '#fb923c', label: 'don\'t ask' },
  ]
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  Shift+⇥ 눌러 모드 전환:'),
    h(Box, { flexDirection: 'row', marginTop: 1 },
      ...modes.map((m, i) => h(Box, {
        key: m.id, marginRight: i < modes.length - 1 ? 2 : 0,
        borderStyle: i === 2 ? 'round' : undefined,
        borderColor: m.color, paddingX: 1,
      },
        h(Text, { color: m.color, bold: i === 2 }, m.label),
      ))
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '  현재: accept edits · find/locate 자동, check/send는 여전히 확인 필요'),
    ),
    h(Box, { marginTop: 1 },
      h(BorderedNotice, {
        label: '⚠ bypassPermissions 전환 확인', color: C.red, width: 60,
      },
        h(Text, null, '개발자 편의 모드여도 PIPA/신원/send 게이트는 우회 불가'),
        h(Box, { marginTop: 1 },
          h(Text, { color: C.brand, bold: true }, '[Y] '),
          h(Text, null, '확정   '),
          h(Text, { color: C.brand, bold: true }, '[N] '),
          h(Text, null, '취소'),
        ),
      )
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
    h(Text, { bold: true, color: C.brand }, 'UI-C · Permission Gauntlet L2'),
    h(Text, { color: C.subtle }, 'find/locate · check · send 시민-안전 게이트 + PIPA 수탁자 영수증'),

    h(Section, { title: 'C.1 · Layer 1/2/3 색·글리프 규약' },
      h(Box, { flexDirection: 'column' },
        h(LayerBadge, { L: L1 }),
        h(LayerBadge, { L: L2 }),
        h(LayerBadge, { L: L3 }),
      )
    ),

    h(Section, { title: 'C.2 · Permission Modal (check 예시)' },
      h(PermissionModal, { L: L2 })
    ),

    h(Section, { title: 'C.3 · /consent 명령 · 권한 이력' },
      h(ConsentHistory)
    ),

    h(Section, { title: 'C.4 · 동의 철회 플로우' },
      h(RevokeFlow)
    ),

    h(Section, { title: 'C.5 · 권한 모드 전환 · Shift+Tab' },
      h(ModeSwitch)
    ),

    h(Divider, { label: '요청' }),
    h(Box, { flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.dim }, 'C.1 Layer 색: green/orange/red OK?'),
      h(Text, { color: C.dim }, 'C.2 modal: [Y/A/N] 3-choice 적정?'),
      h(Text, { color: C.dim }, 'C.3 이력: /consent list 형식 OK?'),
      h(Text, { color: C.dim }, 'C.4 철회: 단발(rcpt-id)/전체 옵션 추가 필요?'),
      h(Text, { color: C.dim }, 'C.5 모드 전환: bypass 확인 다이얼로그 OK?'),
    ),
  )
}

render(h(App))
