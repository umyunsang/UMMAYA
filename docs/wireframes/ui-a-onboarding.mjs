// SPDX-License-Identifier: Apache-2.0
// UI-A · Historical onboarding L2 proposal · 5 decision points
// Current docs/vision.md keeps UMMAYA setup aligned with the Claude Code runtime
// path; this file is retained as a comparison sketch, not an active product gate.
//   A.1 각 단계 UI 레이아웃 (preflight / theme / pipa-consent / ministry / terminal)
//   A.2 스킵 가능성 · 재실행
//   A.3 다국어 지원
//   A.4 접근성 (스크린리더 · 큰 글씨)
//   A.5 동의 철회 UX
//
// Run: cd tui && bun ../docs/wireframes/ui-a-onboarding.mjs

import { render } from 'ink'
import { h, Box, Text, C, Divider, BorderedNotice } from './_shared.mjs'

// ══ A.1 · 각 단계 UI 레이아웃 ═══════════════════════════════════════════

function StepHeader({ n, total, label }) {
  const dots = Array.from({ length: total }, (_, i) =>
    i < n ? '●' : i === n ? '◉' : '○').join(' ')
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.brand, bold: true }, `${label}`),
    h(Text, { color: C.dim }, `${dots}     ${n + 1} / ${total}`),
  )
}

function Step1_Preflight() {
  return h(Box, { flexDirection: 'column' },
    h(StepHeader, { n: 0, total: 5, label: '1. 사전 확인 · Preflight' }),
    h(Box, { marginTop: 1, flexDirection: 'column' },
      h(Text, null, '  ✓ Node / Bun 런타임 확인'),
      h(Text, null, '  ✓ 터미널 UTF-8 지원'),
      h(Text, null, '  ✓ UMMAYA_FRIENDLI_TOKEN · ~/.ummaya session login'),
      h(Text, null, '  ⚠ UMMAYA_DATA_GO_KR_API_KEY (선택) — live public API canary only'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.brand, bold: true }, '[Enter] '),
      h(Text, null, '다음')),
  )
}

function Step2_Theme() {
  return h(Box, { flexDirection: 'column' },
    h(StepHeader, { n: 1, total: 5, label: '2. 테마 선택 · Theme' }),
    h(Box, { marginTop: 1, flexDirection: 'column', marginLeft: 2 },
      h(Text, null,
        h(Text, { color: C.brand, bold: true }, '▸ '),
        h(Text, { bold: true }, 'dark  '),
        h(Text, { color: C.dim }, '  어두운 배경 (기본)'),
      ),
      h(Text, null, '  light   밝은 배경'),
      h(Text, null, '  default 시스템 따름'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true }, '  ↑↓ 선택 · Enter 다음 · /theme 으로 나중 변경')),
  )
}

function Step3_PIPA() {
  return h(Box, { flexDirection: 'column' },
    h(StepHeader, { n: 2, total: 5, label: '3. 개인정보 처리 동의 · PIPA §17' }),
    h(Box, { marginTop: 1 },
      h(BorderedNotice, {
        label: '⚠ 수탁자 책임 안내', color: '#fb923c', width: 70,
      },
        h(Text, null, 'UMMAYA는 PIPA §26 수탁자로 귀하의 질의를 공공 API'),
        h(Text, null, '수탁 처리합니다. 처리 정보:'),
        h(Box, { marginTop: 1 },
          h(Text, null, '  · 질의 원문 (세션 종료 시 자동 삭제 옵션)'),
          h(Text, null, '  · 위치/주소 (`locate` 필요 시만)'),
          h(Text, null, '  · 제출/납부 payload (`send` 호출 시)'),
        ),
      )
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.brand, bold: true }, '[Y] '),
      h(Text, null, '동의 후 진행   '),
      h(Text, { color: C.brand, bold: true }, '[N] '),
      h(Text, null, '동의 안 함 (종료)')),
  )
}

function Step4_Ministry() {
  const ministries = [
    { code: 'KOROAD', label: '도로교통공단',    on: true },
    { code: 'KMA',    label: '기상청',          on: true },
    { code: 'HIRA',   label: '건강보험심사평가원', on: true },
    { code: 'NMC',    label: '국립중앙의료원',    on: true },
    { code: 'NFA',    label: '소방청',          on: false },
    { code: 'MOHW',   label: '보건복지부',      on: false },
  ]
  return h(Box, { flexDirection: 'column' },
    h(StepHeader, { n: 3, total: 5, label: '4. 기관 범위 · Agency Scope' }),
    h(Box, { marginTop: 1, flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.subtle }, '호출 가능한 기관/공공채널 범위:'),
      ...ministries.map(m => h(Box, { key: m.code },
        h(Text, null, `  ${m.on ? '[✓]' : '[ ]'} `),
        h(Text, { bold: m.on }, m.code.padEnd(8)),
        h(Text, { color: C.dim }, m.label),
      )),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.dim, dimColor: true },
        '  Space 토글 · A 전체선택 · Enter 다음')),
  )
}

function Step5_Terminal() {
  return h(Box, { flexDirection: 'column' },
    h(StepHeader, { n: 4, total: 5, label: '5. 터미널 최종 설정 · Terminal' }),
    h(Box, { marginTop: 1, flexDirection: 'column', marginLeft: 2 },
      h(Text, null, '  [✓] Shift+Tab · 권한 모드 전환'),
      h(Text, null, '  [✓] Ctrl+C · 작업 취소'),
      h(Text, null, '  [✓] 한글 IME 조합 안정 모드'),
      h(Text, null, '  [ ] 터미널 알림음 (벨)'),
    ),
    h(Box, { marginTop: 1 },
      h(Text, { color: C.brand, bold: true }, '[Enter] '),
      h(Text, null, '완료 · REPL 시작')),
  )
}

// ══ A.2 · 스킵 · 재실행 ═══════════════════════════════════════════════
function ReRun() {
  return h(Box, { flexDirection: 'column' },
    h(Text, null, '  /onboarding        처음부터 재실행'),
    h(Text, null, '  /onboarding theme  특정 단계만'),
    h(Text, { color: C.dim, dimColor: true },
      '  · 재실행 시 기존 동의 영수증 유지 (overwrite 확인 모달)'),
  )
}

// ══ A.3 · 다국어 ══════════════════════════════════════════════════════
function Language() {
  return h(Box, { flexDirection: 'column' },
    h(Text, null,
      h(Text, { color: C.brand, bold: true }, '▸ '),
      h(Text, { bold: true }, '한국어 '),
      h(Text, { color: C.dim }, '   (기본)'),
    ),
    h(Text, null, '  English    fallback'),
    h(Text, null, '  日本語      (예정)'),
    h(Text, { color: C.dim, dimColor: true, marginTop: 1 },
      '  공공 서비스 특성상 한국어 primary · 체류 외국인 지원 English 병행'),
  )
}

// ══ A.4 · 접근성 ══════════════════════════════════════════════════════
function Accessibility() {
  return h(Box, { flexDirection: 'column' },
    h(Text, null, '  [ ] 스크린리더 모드 (aria 힌트 · 음성 설명)'),
    h(Text, null, '  [ ] 큰 글씨 모드 (주요 라벨 +2pt)'),
    h(Text, null, '  [ ] 고대비 테마 (ANSI 16색 제한)'),
    h(Text, null, '  [ ] reduced motion (hover bob · spinner 정지)'),
    h(Text, { color: C.dim, dimColor: true, marginTop: 1 },
      '  · /config a11y 로 언제든 변경'),
  )
}

// ══ A.5 · 동의 철회 ═══════════════════════════════════════════════════
function ConsentRevoke() {
  return h(Box, { flexDirection: 'column' },
    h(BorderedNotice, {
      label: '⚠ PIPA 동의 철회', color: C.red, width: 70,
    },
      h(Text, null, '현재 세션의 모든 권한 영수증이 무효화됩니다.'),
      h(Text, null, '진행 중인 send/check 작업은 즉시 중단.'),
      h(Text, null, '저장된 대화 기록은 별도 설정에 따라 보존 또는 삭제.'),
      h(Box, { marginTop: 1 },
        h(Text, null, '  [ ] 모든 대화 기록도 즉시 삭제'),
        h(Text, null, '  [✓] OTEL span · audit ledger 보존 (법적 증적)'),
      ),
      h(Box, { marginTop: 1 },
        h(Text, { color: C.brand, bold: true }, '[Y] '),
        h(Text, null, '철회 확정 · 세션 종료')),
    )
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
    h(Text, { bold: true, color: C.brand }, 'UI-A · Historical Onboarding L2'),
    h(Text, { color: C.subtle }, '현재 제품 게이트 아님 · 5-step 비교 스케치'),

    h(Section, { title: 'A.1.1 · Preflight' }, h(Step1_Preflight)),
    h(Section, { title: 'A.1.2 · Theme' }, h(Step2_Theme)),
    h(Section, { title: 'A.1.3 · PIPA Consent' }, h(Step3_PIPA)),
    h(Section, { title: 'A.1.4 · Agency Scope' }, h(Step4_Ministry)),
    h(Section, { title: 'A.1.5 · Terminal Setup' }, h(Step5_Terminal)),

    h(Section, { title: 'A.2 · 스킵 · 재실행' }, h(ReRun)),
    h(Section, { title: 'A.3 · 다국어' }, h(Language)),
    h(Section, { title: 'A.4 · 접근성' }, h(Accessibility)),
    h(Section, { title: 'A.5 · 동의 철회' }, h(ConsentRevoke)),

    h(Divider, { label: '요청' }),
    h(Box, { flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.dim }, 'A.1 각 단계 레이아웃 OK?'),
      h(Text, { color: C.dim }, 'A.2 /onboarding · /onboarding <step> 명령 체계 OK?'),
      h(Text, { color: C.dim }, 'A.3 한국어 primary / English fallback OK?'),
      h(Text, { color: C.dim }, 'A.4 a11y 4종 토글 항목 OK?'),
      h(Text, { color: C.dim }, 'A.5 철회 시 audit 보존 정책 OK?'),
    ),
  )
}

render(h(App))
