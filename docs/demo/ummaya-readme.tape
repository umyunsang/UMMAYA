# SPDX-License-Identifier: Apache-2.0
# README demo generated with VHS. This drives the real UMMAYA Ink TUI and
# enters the README user-scenario prompts against an offline IPC backend.
#
# Regenerate:
#   vhs docs/demo/ummaya-readme.tape

Output assets/ummaya-demo.gif
Output assets/ummaya-demo.txt
Set Shell "bash"
Set FontSize 11
Set FontFamily "JetBrains Mono"
Set Width 940
Set Height 560
Set Framerate 5
Set PlaybackSpeed 2.4
Set Theme "TokyoNightStorm"
Set Padding 8
Set Margin 0
Set CursorBlink false
Set TypingSpeed 20ms

Hide
Type "cd /Users/um-yunsang/UMMAYA/tui && UMMAYA_FRIENDLI_TOKEN=sk-readme-demo UMMAYA_FRIENDLI_SESSION_ACTIVE=1 UMMAYA_ONBOARDING_AUTO_COMPLETE=1 UMMAYA_BACKEND_CMD='uv run python /Users/um-yunsang/UMMAYA/docs/demo/readme_scenario_backend.py' NODE_ENV=test IS_DEMO=1 /Users/um-yunsang/.bun/bin/bun run tui"
Enter
Wait+Screen@10s /UMMAYA/
Show
Sleep 500ms

Copy "작년 종합소득세 신고하고 환급받을 수 있으면 환급 계좌까지 등록해줘."
Paste
Enter
Wait+Screen@15s /Scenario TAX complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "이사했어. 전입신고하고 자동차, 건강보험, 학교 관련 주소도 한 번에 바꿔줘."
Paste
Enter
Wait+Screen@15s /Scenario MOVE complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "이번 달 재산세랑 자동차세, 과태료 밀린 거 확인하고 납부 가능한 건 처리해줘."
Paste
Enter
Wait+Screen@15s /Scenario PAY complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "아기가 태어났어. 출생신고, 아동수당, 첫만남이용권, 건강보험 피부양자 등록까지 도와줘."
Paste
Enter
Wait+Screen@15s /Scenario BIRTH complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "전세 계약했어. 확정일자, 임대차 신고, 전세보증 관련 절차를 위험한 부분까지 체크해서 처리해줘."
Paste
Enter
Wait+Screen@15s /Scenario HOME complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "카페 창업하려고 해. 사업자등록, 영업신고, 위생교육, 카드가맹, 세금 준비까지 순서대로 처리해줘."
Paste
Enter
Wait+Screen@15s /Scenario BIZ complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "아이가 밤에 열이 높아. 지금 갈 수 있는 응급실이나 야간진료 병원 찾고 보험 적용되는지도 알려줘."
Paste
Enter
Wait+Screen@15s /Scenario ER complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "내일 부산에서 서울 가는데 날씨, 도로 위험, 대중교통 지연까지 보고 가장 안전한 이동 방법 추천해줘."
Paste
Enter
Wait+Screen@15s /Scenario ROUTE complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "집이 침수됐어. 피해 신고, 재난지원금, 임시주거, 전기·가스 안전 점검까지 바로 도와줘."
Paste
Enter
Wait+Screen@15s /Scenario SAFE complete/
Sleep 1200ms
Type "/clear"
Enter
Sleep 500ms

Copy "정부기관들이 내 정보를 어디에 쓰고 있는지 확인하고 잘못된 주소나 연락처는 고쳐줘."
Paste
Enter
Wait+Screen@15s /Scenario DATA complete/
Sleep 1s

Ctrl+C
Sleep 300ms
Ctrl+C
Sleep 500ms
