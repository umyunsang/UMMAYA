# README Demo Pipeline

UMMAYA's README demo is generated with `t-rec` only, without VHS, asciinema,
agg, or a mock IPC backend.

The pipeline records a real `ummaya` terminal session. By default, the person
recording types the natural Korean scenario prompt into the live Ink TUI, then
the running product calls FriendliAI and the public API adapters through the normal
`chat_request` path. Tool calls are not scripted; the model chooses them from
the scenario.

Use separate task-shaped prompts rather than one tool-catalog prompt:

```text
오늘 저녁 동아대학교 승학캠퍼스 근처에 비 올까?
부산 사하구 다대1동 근처에서 지금 전화해볼 만한 병원 3곳 찾아줘.
오늘 밤 동아대학교에서 다대포해수욕장까지 차로 가려는데, 조심해야 할 구간 있어?
```

These prompts show natural user requests, not a tool catalog pitch. In the
release path, public API credentials are operator-managed by the live adapter
gateway; the user only logs in to FriendliAI.

## Generate

Before recording, run `ummaya` once and complete `/login` if the FriendliAI
session is not already active. Do not export Kakao/data.go.kr keys for the
README demo.

```bash
npm run demo:readme
```

When the `ummaya` prompt appears, type one scenario, wait for the answer, then
type `/clear` before the next scenario. After the final answer is visible, type
`/exit` and press Enter so `t-rec` can finish and write the GIF/MP4.

Outputs:

- `assets/ummaya-demo.gif` - README-embedded animation
- `assets/ummaya-demo.txt` - plain terminal evidence from the same run
- `assets/ummaya-demo.mp4` - t-rec video when video capture succeeds

## Toolchain

Install the recorder stack on macOS:

```bash
brew install t-rec gifsicle ffmpeg
```

`t-rec` must run from a macOS GUI terminal that it can identify and that has
Screen Recording permission. If automatic window detection fails, set
`UMMAYA_TREC_WIN_ID` to one of the IDs from `t-rec --ls-win`. The script
intentionally fails instead of switching to another recorder when `t-rec` cannot
capture the target window.
