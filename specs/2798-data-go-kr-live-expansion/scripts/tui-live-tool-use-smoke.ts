import type { Harness } from '../../../scripts/bun-pty-capture.ts'

export default async function scenario(h: Harness): Promise<void> {
  await h.waitForPane(/Allow external CLAUDE\.md file imports\?|UMMAYA|Not logged in|FriendliAI|사용자 입력|입력|>/, 45)
  h.snapshot('boot-or-import-gate')

  if (h.plain().includes('Allow external CLAUDE.md file imports?')) {
    h.sendEnter()
    await h.waitForPane(/UMMAYA|Not logged in|FriendliAI|사용자 입력|입력|>/, 45)
    h.snapshot('post-import-gate')
  }

  const turnStart = h.mark()
  h.sendText('타이레놀 효능과 복용 주의사항을 공식 자료로 알려줘.')
  h.sendEnter()
  h.snapshot('input-submitted')

  await h.waitForPaneSince(
    turnStart,
    /mfds_easy_drug_info_lookup|find\s*\(|find\s+mfds|Tool use|도구 사용/i,
    300,
  )
  h.snapshot('tool-use-visible')

  await h.waitForPaneSince(turnStart, /collection\s*—\s*7\s*results|collection.*7.*results/i, 300)
  h.snapshot('tool-result-visible')

  await h.waitForPaneSince(
    turnStart,
    /식품의약품안전처\s+e약은요에서\s+조회한\s+공식\s+자료|효능\s+\(사용\s+목적\)|타이레놀은\s+감기로\s+인한\s+발열/i,
    300,
  )
  h.snapshot('final-answer')

  const turnText = h.plainSince(turnStart)
  if (/신원 확인 권한 요청|check\s*\(|mock_verify_module_modid/.test(turnText)) {
    throw new Error('unexpected verify/check flow after public drug lookup')
  }

  h.sendCtrlC()
}
