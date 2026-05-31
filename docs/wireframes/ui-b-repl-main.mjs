// SPDX-License-Identifier: Apache-2.0
// UI-B · REPL Main surface L2 드릴다운
//
// 6개 결정 포인트:
//   B.1 메시지 스트리밍 렌더 (token vs chunk vs sentence)
//   B.2 긴 응답 scroll 동작 (PageUp/Down · scrollback 제한)
//   B.3 마크다운·링크·표 렌더
//   B.4 에러 envelope 표시 (LLM · tool · network)
//   B.5 multi-turn 맥락 인용 표시
//   B.6 slash command 자동완성
//
// Run: cd tui && bun ../docs/wireframes/ui-b-repl-main.mjs

import { render } from 'ink'
import {
  h, Box, Text, C, Divider, CondensedLogo, PromptBand, PromptFooter,
  UserMsg, ToolUseBlock, AsstLine, Spinner,
} from './_shared.mjs'

// ══ B.1 Streaming render ═══════════════════════════════════════════════

function B1_TokenStream() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  현재 스트리밍 중 (token 단위):'),
    h(Box, { marginLeft: 2 },
      h(Text, null, '서울 현재 12°C, 맑음, 미세먼지는 '),
      h(Text, { color: C.ring, bold: true }, '보'),
      h(Text, { color: C.subtle, dimColor: true }, '통'),
    ),
    h(Text, { color: C.dim, dimColor: true },
      '  · 장점: 반응성 ↑ · 단점: cursor 떨림, Korean 조합 중 깜빡임'),
  )
}

function B1_ChunkStream() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  현재 스트리밍 중 (chunk ≈20 token):'),
    h(Box, { marginLeft: 2 },
      h(Text, null, '서울 현재 12°C, 맑음, 미세먼지는 보통입니다. '),
      h(Text, { color: C.ring }, '▍'),
    ),
    h(Text, { color: C.dim, dimColor: true },
      '  · 장점: 한글 조합 안정 · 단점: ~400ms 단위 업데이트 (체감 리듬)'),
  )
}

function B1_SentenceStream() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  현재 스트리밍 중 (문장 단위):'),
    h(Box, { marginLeft: 2 },
      h(Text, null, '서울 현재 12°C, 맑음, 미세먼지는 보통입니다.'),
    ),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.ring }, '⠋ '),
      h(Text, null, '다음 문장 작성 중...'),
    ),
    h(Text, { color: C.dim, dimColor: true },
      '  · 장점: 가장 안정 · 단점: 응답 지연 큼 (문장 끝까지 대기)'),
  )
}

// ══ B.2 Scroll / scrollback ════════════════════════════════════════════

function B2_ScrollOverlay() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { color: C.subtle }, '  긴 응답 중 PageUp 누름:'),
    h(Box, { marginLeft: 2, flexDirection: 'column' },
      h(Text, { color: C.dim, dimColor: true }, '... (스크롤 중)'),
      h(Text, null, '[23 / 120 행] ← → : Home/End  ↑ ↓ : 한 줄  PgUp/Dn : 한 페이지  Esc : 복귀'),
    ),
  )
}

// ══ B.3 Markdown / 링크 / 표 ═══════════════════════════════════════════

function B3_MarkdownRich() {
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Text, null,
      h(Text, { color: C.subtle }, '  ### '),
      h(Text, { bold: true }, '서울 날씨 요약'),
    ),
    h(Text, null, '  · 기온: '),
    h(Box, { marginLeft: 2 },
      h(Text, null, '최저 '),
      h(Text, { bold: true }, '8°C'),
      h(Text, null, ' / 최고 '),
      h(Text, { bold: true }, '14°C'),
    ),
    h(Text, { color: C.dim, dimColor: true }, '  · 출처: '),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.ring, underline: true }, 'KMA API Hub · current observation'),
    ),
    h(Text, { color: C.dim, dimColor: true }, '  · 원문 문서: '),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.ring, underline: true }, 'kma-20260424-seoul.pdf'),
      h(Text, { color: C.dim, dimColor: true }, ' (미리보기: /open kma-...)'),
    ),
  )
}

function B3_TablePreview() {
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Text, null, '  ┌──────┬─────┬──────┐'),
    h(Text, null, '  │ 지역 │ 기온 │ 미세 │'),
    h(Text, null, '  ├──────┼─────┼──────┤'),
    h(Text, null, '  │ 서울 │ 12°C │ 보통 │'),
    h(Text, null, '  │ 부산 │ 16°C │ 좋음 │'),
    h(Text, null, '  └──────┴─────┴──────┘'),
  )
}

// ══ B.4 에러 envelope ══════════════════════════════════════════════════

function B4_LLMError() {
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Box, null,
      h(Text, { color: C.red, bold: true }, '⚠ LLM 응답 실패 '),
      h(Text, { color: C.dim, dimColor: true }, '· FriendliAI: timeout after 30s'),
    ),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.dim, dimColor: true }, '자동 재시도 중... (2/3)'),
    ),
  )
}

function B4_ToolError() {
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Box, null,
      h(Text, { color: C.red, bold: true }, '⏺ '),
      h(Text, { bold: true }, 'KMA'),
      h(Text, { color: C.dim, dimColor: true }, '   도구 호출 실패'),
    ),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.subtle }, '   → '),
      h(Text, { color: C.red }, 'HTTP 503'),
      h(Text, null, ' · official handoff 또는 cached public result만 허용'),
    ),
  )
}

function B4_NetworkError() {
  return h(Box, { flexDirection: 'column', marginLeft: 2 },
    h(Box, null,
      h(Text, { color: C.red, bold: true }, '✗ 네트워크 단절 '),
      h(Text, { color: C.dim, dimColor: true }, '· 재연결 대기 중'),
    ),
    h(Box, { marginLeft: 2 },
      h(Text, { color: C.dim, dimColor: true },
        '⚙ 오프라인 모드 · 캐시된 응답만 가능')
    ),
  )
}

// ══ B.5 multi-turn 맥락 인용 ═══════════════════════════════════════════

function B5_ContextRef() {
  return h(Box, { flexDirection: 'column' },
    h(UserMsg, { text: '그럼 미세먼지는 어디 기준이야?' }),
    h(Box, { marginLeft: 2, marginTop: 1,
             borderStyle: 'single', borderColor: C.dim, paddingX: 1 },
      h(Text, { color: C.dim, dimColor: true }, '⎿ 이전 응답 인용 ·'),
      h(Text, { color: C.subtle }, '  "서울 현재 12°C, 맑음, 미세먼지는 보통"'),
    ),
    h(Box, { marginLeft: 2, marginTop: 1 },
      h(ToolUseBlock, {
        primitive: 'find', ministry: 'KMA',
        detail: '미세먼지 측정소 · 서울',
        result: '종로구 측정소 기준 PM10 45µg/m³',
      })
    ),
  )
}

// ══ B.6 Slash command 자동완성 ═════════════════════════════════════════

function B6_SlashCompletion() {
  return h(Box, { flexDirection: 'column' },
    h(Box, null,
      h(Text, { color: C.brand, bold: true }, '> '),
      h(Text, null, '/age'),
      h(Text, { color: C.ring }, '▍'),
    ),
    h(Box, { marginLeft: 2, marginTop: 1, borderStyle: 'single',
             borderColor: C.dim, paddingX: 1, flexDirection: 'column' },
      h(Text, null,
        h(Text, { bold: true, color: C.brand }, '/agents'),
        h(Text, { color: C.dim, dimColor: true }, '   활성 부처 에이전트 목록'),
      ),
      h(Text, null,
        h(Text, { color: C.subtle }, '/age'),
        h(Text, { bold: true }, 'nda'),
        h(Text, { color: C.dim, dimColor: true }, '    세션 agenda 보기'),
      ),
    ),
  )
}

// ══ Section renderer ══════════════════════════════════════════════════

function Section({ title, children }) {
  return h(Box, { flexDirection: 'column', marginBottom: 2 },
    h(Divider, { label: title }),
    h(Box, { marginLeft: 2, marginTop: 1 }, children),
  )
}

function App() {
  return h(Box, { flexDirection: 'column' },
    h(Text, { bold: true, color: C.brand },
      'UI-B · REPL Main surface · L2 드릴다운'),
    h(Text, { color: C.subtle },
      '6개 결정 포인트 wireframe · 각 옵션 선택 필요'),

    // B.1
    h(Section, { title: 'B.1 · 메시지 스트리밍 렌더 (3 options)' },
      h(Box, { flexDirection: 'column' },
        h(B1_TokenStream),
        h(Box, { marginTop: 1 }, h(B1_ChunkStream)),
        h(Box, { marginTop: 1 }, h(B1_SentenceStream)),
        h(Box, { marginTop: 1 },
          h(Text, { color: C.brand }, '  👉 권장: chunk (한글 IME 조합 안정 · 리듬 감각 적정)'),
        )
      )
    ),

    // B.2
    h(Section, { title: 'B.2 · 긴 응답 scroll 동작' },
      h(B2_ScrollOverlay)
    ),

    // B.3
    h(Section, { title: 'B.3 · 마크다운 · 링크 · 표 렌더' },
      h(Box, { flexDirection: 'column' },
        h(Text, { color: C.subtle }, '  (a) 제목·리스트·링크·인라인 미리보기'),
        h(B3_MarkdownRich),
        h(Box, { marginTop: 1 }, h(Text, { color: C.subtle }, '  (b) 표 렌더')),
        h(B3_TablePreview),
      )
    ),

    // B.4
    h(Section, { title: 'B.4 · 에러 envelope 3종' },
      h(Box, { flexDirection: 'column' },
        h(B4_LLMError),
        h(Box, { marginTop: 1 }, h(B4_ToolError)),
        h(Box, { marginTop: 1 }, h(B4_NetworkError)),
      )
    ),

    // B.5
    h(Section, { title: 'B.5 · multi-turn 맥락 인용 표시' },
      h(B5_ContextRef)
    ),

    // B.6
    h(Section, { title: 'B.6 · Slash command 자동완성' },
      h(B6_SlashCompletion)
    ),

    h(Divider, { label: '요청' }),
    h(Box, { flexDirection: 'column', marginLeft: 2 },
      h(Text, { color: C.dim }, 'B.1 streaming: token / chunk(권장) / sentence'),
      h(Text, { color: C.dim }, 'B.2 scroll: 현안 OK? 레이아웃 변경 필요?'),
      h(Text, { color: C.dim }, 'B.3 markdown 범위: (a)+(b) / (a)만 / 단순 텍스트'),
      h(Text, { color: C.dim }, 'B.4 에러: 3종 패턴 OK?'),
      h(Text, { color: C.dim }, 'B.5 context ref: 인용 박스 표시? 생략?'),
      h(Text, { color: C.dim }, 'B.6 autocomplete: 드롭다운 / 인라인 / 없음'),
    ),
  )
}

render(h(App))
