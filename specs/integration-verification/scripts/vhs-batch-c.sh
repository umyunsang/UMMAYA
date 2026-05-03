#!/usr/bin/env bash
# Generate 12 additional vhs tape files in one batch.
set -euo pipefail
cd "$(dirname "$0")"
BASE="../frames"

generate_tape() {
  local id="$1" label="$2" prompt="$3"
  cat > "vhs-${id}-${label}.tape" <<EOF
Output ${BASE}/vhs-${id}-${label}.gif
Output ${BASE}/vhs-${id}-${label}.txt
Set Shell "bash"
Set FontSize 14
Set Width 1600
Set Height 900
Set Theme "TokyoNightStorm"
Hide
Type "cd /Users/um-yunsang/KOSMOS/tui && KOSMOS_ONBOARDING_AUTO_COMPLETE=1 bun run tui"
Enter
Sleep 5s
Show
Screenshot ${BASE}/vhs-${id}-keyframe-1-boot.png
Type "${prompt}"
Enter
Sleep 35s
Screenshot ${BASE}/vhs-${id}-keyframe-2-mid.png
Sleep 25s
Screenshot ${BASE}/vhs-${id}-keyframe-3-final.png
Ctrl+C
Sleep 500ms
Ctrl+C
Sleep 1s
EOF
}

generate_tape "22" "kma-ultra"     "서울 1시간 후 강수 알려줘"
generate_tape "23" "kma-pre-warn"  "서울 호우주의보 발효 가능성 알려줘"
generate_tape "24" "koroad-hazard" "서울 강남구 사고 다발 위험지역 알려줘"
generate_tape "25" "resolve-busan" "부산 해운대 좌표 알려줘"
generate_tape "26" "resolve-jeju"  "제주도 한라산 위경도 알려줘"
generate_tape "27" "mock-mydata"   "마이데이터 본인인증 시뮬레이션 해줘"
generate_tape "28" "mock-kec"      "전자서명 KEC 인증 시뮬레이션 해줘"
generate_tape "29" "mock-modid"    "모바일 ID 발급 시뮬레이션 해줘"
generate_tape "30" "mock-simple"   "간편인증 카카오 시뮬레이션 해줘"
generate_tape "31" "mock-gongdong" "공동인증서 시뮬레이션 해줘"
generate_tape "32" "mock-geumyung" "금융인증서 시뮬레이션 해줘"
generate_tape "33" "error-envelope" "INVALID_QUERY_!!!@@@"

echo "Generated 12 tape files."
ls vhs-2[2-9]-*.tape vhs-3[0-3]-*.tape 2>/dev/null
