#!/usr/bin/env -S uv run python
# SPDX-License-Identifier: Apache-2.0
"""Probe FriendliAI K-EXAONE-236B-A23B raw SSE stream channels.

Question being answered:
    When the citizen asks "오늘 부산 날씨 어땠어?", does K-EXAONE's verbose
    narration (the ReAct-style "검색 결과에서 ... 찾았습니다 ... 이 어댑터를
    사용하겠습니다 ..." plan-out) come back on:

      (a) ``delta.content``           — visible text channel (LEAK)
      (b) ``delta.reasoning_content`` — separated CoT channel (PROPER)
      (c) ``delta.tool_calls``        — function calling channel (EXPECTED)

    Two passes:  KOSMOS_K_EXAONE_THINKING=false (KOSMOS default)
                 KOSMOS_K_EXAONE_THINKING=true  (model card default)

Output: per-pass tally of bytes routed to each channel + first 800 chars of
each channel's accumulated text + tool_call summary.

Runtime: ~30-90s per pass (real LLM call). Requires KOSMOS_FRIENDLI_TOKEN.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from kosmos._dotenv import load_repo_dotenv
from kosmos.llm.config import LLMClientConfig

load_repo_dotenv()

CITIZEN_PROMPT = "오늘 부산 날씨 어땠어?"

SYSTEM_PROMPT = (REPO_ROOT / "prompts" / "system_v1.md").read_text(encoding="utf-8")

# Minimal 5-tool LLM-visible surface (citizen-facing).
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_location",
            "description": (
                "Convert a free-text Korean place name, address, or landmark into "
                "structured location identifiers (coordinates + 10-digit 행정동 code)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "want": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": (
                "Two-mode adapter discovery + invocation. mode='search' returns BM25 "
                "candidates; mode='fetch' executes a tool_id with params."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["search", "fetch"]},
                    "query": {"type": "string"},
                    "tool_id": {"type": "string"},
                    "params": {"type": "object"},
                    "top_k": {"type": "integer"},
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify",
            "description": "Authentication ceremony. Returns DelegationContext.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["tool_id", "params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": "OPAQUE-domain administrative submission. Returns receipt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["tool_id", "params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subscribe",
            "description": "Real-time stream subscription (disaster broadcast / RSS).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_id": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["tool_id", "params"],
            },
        },
    },
]


async def probe_one(*, enable_thinking: bool) -> dict:
    cfg = LLMClientConfig()  # type: ignore[call-arg]
    base_url = str(cfg.base_url).rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.token.get_secret_value()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.model,
        "stream": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": CITIZEN_PROMPT},
        ],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 1.0,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "max_tokens": 4096,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }

    content_buf: list[str] = []
    reasoning_buf: list[str] = []
    tool_calls_seen: list[dict] = []
    raw_chunks: list[dict] = []
    finish_reason: str | None = None

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                body = line[len("data: "):].strip()
                if body == "[DONE]":
                    break
                try:
                    chunk = json.loads(body)
                except json.JSONDecodeError:
                    continue
                raw_chunks.append(chunk)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                # Channel routing — record what arrives where.
                if "content" in delta and delta["content"] is not None:
                    content_buf.append(delta["content"])
                if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                    reasoning_buf.append(delta["reasoning_content"])
                tcs = delta.get("tool_calls")
                if tcs:
                    for tc in tcs:
                        idx = tc.get("index", 0)
                        while len(tool_calls_seen) <= idx:
                            tool_calls_seen.append({"name": "", "args": ""})
                        slot = tool_calls_seen[idx]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["args"] += fn["arguments"]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

    return {
        "enable_thinking": enable_thinking,
        "content_bytes": sum(len(s) for s in content_buf),
        "reasoning_bytes": sum(len(s) for s in reasoning_buf),
        "tool_call_count": len(tool_calls_seen),
        "tool_calls": tool_calls_seen,
        "finish_reason": finish_reason,
        "content_head": ("".join(content_buf))[:800],
        "reasoning_head": ("".join(reasoning_buf))[:800],
        "chunk_count": len(raw_chunks),
    }


async def main() -> None:
    print("=" * 78)
    print(f"Citizen prompt: {CITIZEN_PROMPT}")
    print(f"Model: {LLMClientConfig().model}")  # type: ignore[call-arg]
    print(f"Tools exposed: {len(TOOLS)}")
    print("=" * 78)

    for thinking in (False, True):
        print(f"\n--- PASS: enable_thinking={thinking} ---")
        try:
            result = await probe_one(enable_thinking=thinking)
        except httpx.HTTPStatusError as exc:
            print(f"  HTTP error: {exc.response.status_code} {exc.response.text[:300]}")
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"  Error: {type(exc).__name__}: {exc}")
            continue
        print(f"  chunks: {result['chunk_count']}")
        print(f"  finish_reason: {result['finish_reason']}")
        print(f"  content channel bytes: {result['content_bytes']}")
        print(f"  reasoning_content bytes: {result['reasoning_bytes']}")
        print(f"  tool_calls emitted: {result['tool_call_count']}")
        for i, tc in enumerate(result["tool_calls"]):
            print(f"    [{i}] {tc['name']}({tc['args'][:120]}...)")
        if result["content_head"]:
            print(f"  content[0:800]: {result['content_head']!r}")
        if result["reasoning_head"]:
            print(f"  reasoning_content[0:800]: {result['reasoning_head']!r}")


if __name__ == "__main__":
    asyncio.run(main())
