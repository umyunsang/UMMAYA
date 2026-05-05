#!/usr/bin/env -S uv run python
# SPDX-License-Identifier: Apache-2.0
"""Full-backend channel probe — spawns the actual KOSMOS stdio backend, sends
a real ChatRequestFrame, and dumps every IPC frame back, including the channel
each AssistantChunkFrame uses (delta = visible content vs thinking = reasoning).

Goal: settle whether the user's verbose `●` narration comes from
    (a) FriendliAI delta.content being non-empty (model behavior + augmented prompt)
    (b) FriendliAI delta.reasoning_content leaking into TUI as visible content
    (c) Textual <tool_call> markers + StreamGate leaking the surrounding prose
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


async def main() -> None:
    enable_thinking = os.environ.get("PROBE_THINKING", "false")
    env = dict(os.environ)
    env["KOSMOS_K_EXAONE_THINKING"] = enable_thinking

    sid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    now = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Five-tool surface as the TUI emits.
    tools = [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": f"KOSMOS {n} primitive (probe stub)",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
            },
        }
        for n in ("resolve_location", "lookup", "verify", "submit", "subscribe")
    ]
    chat_request = {
        "version": "1.0",
        "kind": "chat_request",
        "role": "tui",
        "session_id": sid,
        "correlation_id": cid,
        "frame_seq": 1,
        "ts": now,
        "messages": [{"role": "user", "content": "오늘 부산 날씨 어땠어?"}],
        "tools": tools,
        "system": None,  # let backend pull from manifest
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 4096,
    }
    exit_event = {
        "version": "1.0",
        "kind": "session_event",
        "role": "tui",
        "session_id": sid,
        "correlation_id": str(uuid.uuid4()),
        "frame_seq": 2,
        "ts": now,
        "event": "exit",
        "payload": {},
    }

    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "kosmos", "--ipc", "stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(REPO_ROOT),
    )

    assert proc.stdin and proc.stdout and proc.stderr

    # Send chat_request, then exit, then close stdin.
    proc.stdin.write((json.dumps(chat_request, ensure_ascii=False) + "\n").encode())
    proc.stdin.write((json.dumps(exit_event, ensure_ascii=False) + "\n").encode())
    await proc.stdin.drain()
    proc.stdin.close()

    # Aggregate channel byte tallies.
    delta_bytes = 0
    thinking_bytes = 0
    delta_sample: list[str] = []
    thinking_sample: list[str] = []
    tool_calls: list[dict] = []
    tool_results: list[dict] = []
    other_kinds: dict[str, int] = {}

    try:
        async with asyncio.timeout(180):
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    frame = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                kind = frame.get("kind", "?")
                if kind == "assistant_chunk":
                    delta = frame.get("delta") or ""
                    thinking = frame.get("thinking") or ""
                    if delta:
                        delta_bytes += len(delta.encode("utf-8"))
                        if len(delta_sample) < 20:
                            delta_sample.append(delta)
                    if thinking:
                        thinking_bytes += len(thinking.encode("utf-8"))
                        if len(thinking_sample) < 6:
                            thinking_sample.append(thinking)
                elif kind == "tool_call":
                    tool_calls.append({"name": frame.get("name"), "args": frame.get("arguments")})
                elif kind == "tool_result":
                    env_payload = frame.get("envelope") or {}
                    tool_results.append({
                        "kind": env_payload.get("kind"),
                        "result_kind": (env_payload.get("result") or {}).get("kind") if isinstance(env_payload.get("result"), dict) else None,
                        "error": env_payload.get("error"),
                    })
                else:
                    other_kinds[kind] = other_kinds.get(kind, 0) + 1
    except TimeoutError:
        print("(probe timed out — killing backend)")
    finally:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()

    print("=" * 78)
    print(f"PROBE_THINKING={enable_thinking}")
    print(f"KOSMOS_K_EXAONE_THINKING={env.get('KOSMOS_K_EXAONE_THINKING')}")
    print("=" * 78)
    print(f"\ndelta (visible content) bytes: {delta_bytes}")
    print(f"thinking (reasoning) bytes:    {thinking_bytes}")
    print(f"tool_calls emitted:            {len(tool_calls)}")
    print(f"tool_results received:         {len(tool_results)}")
    print(f"other frame kinds:             {other_kinds}")

    if delta_sample:
        print("\n=== visible DELTA samples (first 20 chunks) ===")
        joined = "".join(delta_sample)
        print(repr(joined[:1500]))

    if thinking_sample:
        print("\n=== thinking samples (first 6 chunks) ===")
        for s in thinking_sample:
            print(repr(s[:300]))

    print("\n=== tool_calls ===")
    for tc in tool_calls:
        args_short = json.dumps(tc.get("args"), ensure_ascii=False)[:200]
        print(f"  {tc['name']}({args_short})")

    print("\n=== tool_results ===")
    for tr in tool_results[:10]:
        print(f"  {tr}")


if __name__ == "__main__":
    asyncio.run(main())
