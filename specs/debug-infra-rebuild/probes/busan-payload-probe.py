#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Busan-weather payload probe.

Mirrors the EXACT system prompt KOSMOS sends when the citizen says
"부산 사하구 날씨 알려줘".  Built from:
  - prompts/system_v1.md  (static prefix via PromptLoader)
  - build_system_prompt_with_tools(base, llm_tools)   (adds ## Available tools)
  - _DYNAMIC_BOUNDARY_MARKER  (cache boundary)
  - today date injection  (## Current session context)
  - _build_available_adapters_suffix(user_query)  (schema-dump suffix)

Run: uv run python specs/debug-infra-rebuild/probes/busan-payload-probe.py
Output: specs/debug-infra-rebuild/probes/busan-payload-probe.output.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Repo root on sys.path so KOSMOS modules are importable
# ---------------------------------------------------------------------------
REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

from kosmos.tools.kma.kma_short_term_forecast import (  # noqa: E402
    KMA_SHORT_TERM_FORECAST_TOOL,
    KmaShortTermForecastInput,
)

# ---------------------------------------------------------------------------
# Build the exact available_adapters suffix that _build_available_adapters_suffix
# would produce for "부산 사하구 날씨 알려줘" → top hit = kma_short_term_forecast
# ---------------------------------------------------------------------------

USER_QUERY = "부산 사하구 날씨 알려줘"

_TRUNCATED_SUFFIX_LIMIT = 80  # matches stdio.py line 837


def _render_adapter_block() -> str:
    """Reproduce _build_available_adapters_suffix for kma_short_term_forecast."""
    schema = KmaShortTermForecastInput.model_json_schema()
    properties = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    hint = (KMA_SHORT_TERM_FORECAST_TOOL.search_hint or "").strip()
    if len(hint) > 90:
        hint = hint[:87] + "..."

    lines: list[str] = [
        f'<available_adapters query="{USER_QUERY[:120]}">',
        "백엔드 BM25 후보 (top 1, 점수 내림차순):",
        "",
        f"- kma_short_term_forecast [3.50] — {hint}",
    ]

    for fname, fmeta in properties.items():
        if not isinstance(fmeta, dict):
            continue
        ftype = fmeta.get("type") or fmeta.get("anyOf") or "any"
        if isinstance(ftype, list):
            ftype = "|".join(str(t) for t in ftype)
        fdesc = str(fmeta.get("description", "")).strip().replace("\n", " ")
        if len(fdesc) > _TRUNCATED_SUFFIX_LIMIT:
            fdesc = fdesc[: _TRUNCATED_SUFFIX_LIMIT - 3] + "..."
        pat = fmeta.get("pattern")
        pat_part = f" pattern={pat!r}" if isinstance(pat, str) else ""
        enum = fmeta.get("enum")
        enum_part = (
            f" enum={enum}"
            if isinstance(enum, list) and len(enum) <= 8
            else ""
        )
        flag = "필수" if fname in required else "선택"
        lines.append(
            f"    · {fname} ({ftype}, {flag}{pat_part}{enum_part})"
            + (f" — {fdesc}" if fdesc else "")
        )

    lines.append("")
    lines.append(
        '규칙: 위 목록의 tool_id 만 lookup({"tool_id":"...", "params":{...}})'
        " 으로 호출하세요. 동일 tool_id 를 한 turn 안에서 반복 호출하지 마세요."
    )
    lines.append(
        'params 는 위에 표시된 정확한 필드명만 사용하세요 — 일반적인 "location"/'
        '"date" 같은 추측 키는 모든 어댑터에서 invalid_params 로 거부됩니다.'
    )
    lines.append(
        "BM25 도구 발견은 백엔드 internal 기능 — lookup(mode='search') 같은 호출은"
        " 무효화됩니다 (Spec 2521)."
    )
    lines.append("</available_adapters>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build system prompt — mirrors stdio.py _handle_chat_request assembly
# ---------------------------------------------------------------------------

# Load static prefix from prompts/system_v1.md
SYSTEM_V1_PATH = REPO / "prompts" / "system_v1.md"
base_system = SYSTEM_V1_PATH.read_text(encoding="utf-8").strip()

# Append ## Available tools block (mirrors build_system_prompt_with_tools).
# The real function adds OpenAI function definitions, but for this probe
# we want to test the suffix injection — so we use the minimal lookup tool
# (same as what the dispatcher registers).
_DYNAMIC_BOUNDARY_MARKER = "\nSYSTEM_PROMPT_DYNAMIC_BOUNDARY\n"

today_iso = datetime.now(UTC).strftime("%Y-%m-%d")

available_adapters_suffix = _render_adapter_block()

full_system = (
    base_system
    + _DYNAMIC_BOUNDARY_MARKER
    + f"\n\n## Current session context\n\n오늘 날짜: {today_iso} (UTC).\n"
    "이 날짜를 기준으로 시간 표현을 해석합니다. "
    "날짜 / 시간 정보를 추측 또는 fabricate 하지 말고, "
    "필요하면 도구 (예: kma_short_term_forecast) 를 호출해서 "
    "실제 데이터를 받아 응답에 인용합니다.\n"
    + "\n\n"
    + available_adapters_suffix
    + "\n"
)

print(f"System prompt length: {len(full_system)} chars", file=sys.stderr)
print("--- SUFFIX RENDERED ---", file=sys.stderr)
print(available_adapters_suffix, file=sys.stderr)
print("--- END SUFFIX ---", file=sys.stderr)

# ---------------------------------------------------------------------------
# The lookup primitive tool definition (exact shape KOSMOS registers)
# ---------------------------------------------------------------------------

lookup_tool = {
    "type": "function",
    "function": {
        "name": "lookup",
        "description": (
            "외부 도메인 API 조회 도구 (기상청, HIRA, KOROAD 등). "
            "백엔드가 BM25로 후보 어댑터를 선별해 <available_adapters>에 inject — "
            "그 목록에서 tool_id 를 골라 fetch 호출만 합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_id": {
                    "type": "string",
                    "description": "Registered adapter id from <available_adapters>.",
                },
                "params": {
                    "type": "object",
                    "description": (
                        "Adapter-specific params. "
                        "Field names must exactly match the adapter's input schema."
                    ),
                },
            },
            "required": ["tool_id", "params"],
        },
    },
}

resolve_location_tool = {
    "type": "function",
    "function": {
        "name": "resolve_location",
        "description": (
            "위치 / 주소 / 역 / 관공서 좌표 + 행정동 + POI 한 번에 반환. "
            "반환에는 KMA 격자 좌표 nx/ny 도 포함됩니다. "
            "KMA 날씨 도구 호출 전에 반드시 먼저 호출하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "지역명 또는 주소 (예: '부산 사하구', '서울 종로구청')",
                },
            },
            "required": ["query"],
        },
    },
}

# ---------------------------------------------------------------------------
# FriendliAI API call
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("KOSMOS_FRIENDLI_TOKEN", "")
if not TOKEN:
    print("ERROR: KOSMOS_FRIENDLI_TOKEN not set", file=sys.stderr)
    sys.exit(1)

BASE_URL = os.environ.get(
    "KOSMOS_FRIENDLI_BASE_URL", "https://api.friendli.ai/serverless/v1"
)
MODEL = "LGAI-EXAONE/K-EXAONE-236B-A23B"

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": full_system},
        {"role": "user", "content": USER_QUERY},
    ],
    "tools": [resolve_location_tool, lookup_tool],
    "tool_choice": "auto",
    "parallel_tool_calls": False,
    "stream": True,
    "max_tokens": 512,
    "temperature": 0.3,
    "chat_template_kwargs": {"enable_thinking": True},
}

print(f"Calling {MODEL} with user: {USER_QUERY!r}", file=sys.stderr)
print(f"System prompt total length: {len(full_system)}", file=sys.stderr)

t0 = time.perf_counter()
ttft: float | None = None
content_buf: list[str] = []
reasoning_buf: list[str] = []
tool_calls_raw: dict[int, dict] = {}  # index → accumulated delta

with httpx.Client(timeout=180.0) as cli:
    with cli.stream(
        "POST",
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "text/event-stream",
        },
        json=payload,
    ) as resp:
        if resp.status_code != 200:
            body = resp.read().decode("utf-8", "replace")
            print(f"HTTP {resp.status_code}: {body}", file=sys.stderr)
            sys.exit(1)

        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw == "[DONE]":
                break
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if ttft is None:
                ttft = time.perf_counter() - t0
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            # Content / reasoning
            if delta.get("content"):
                content_buf.append(delta["content"])
            if delta.get("reasoning_content"):
                reasoning_buf.append(delta["reasoning_content"])
            # Tool calls
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                if idx not in tool_calls_raw:
                    tool_calls_raw[idx] = {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {"name": "", "arguments": ""},
                    }
                fn = tc.get("function") or {}
                if fn.get("name"):
                    tool_calls_raw[idx]["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    tool_calls_raw[idx]["function"]["arguments"] += fn["arguments"]

total_time = time.perf_counter() - t0

# Parse accumulated tool_call arguments
parsed_tool_calls = []
for idx in sorted(tool_calls_raw):
    tc = tool_calls_raw[idx]
    args_str = tc["function"]["arguments"]
    try:
        args_parsed = json.loads(args_str)
    except json.JSONDecodeError:
        args_parsed = {"_raw_unparsed": args_str}
    parsed_tool_calls.append(
        {
            "index": idx,
            "name": tc["function"]["name"],
            "arguments": args_parsed,
        }
    )

result = {
    "probe": "busan-payload-probe",
    "user_query": USER_QUERY,
    "system_prompt_length": len(full_system),
    "suffix_included": True,
    "ttft_s": round(ttft, 3) if ttft else None,
    "total_time_s": round(total_time, 3),
    "reasoning_chars": sum(len(r) for r in reasoning_buf),
    "content": "".join(content_buf),
    "tool_calls": parsed_tool_calls,
    "tool_calls_count": len(parsed_tool_calls),
    "diagnosis": {
        "kma_called_directly_without_resolve": any(
            tc["name"] == "lookup"
            and isinstance(tc["arguments"].get("params"), dict)
            and tc["arguments"].get("tool_id") == "kma_short_term_forecast"
            and "nx" not in tc["arguments"].get("params", {})
            for tc in parsed_tool_calls
        ),
        "resolve_location_called_first": bool(
            parsed_tool_calls and parsed_tool_calls[0]["name"] == "resolve_location"
        ),
        "kma_called_with_nx_ny": any(
            tc["name"] == "lookup"
            and isinstance(tc["arguments"].get("params"), dict)
            and "nx" in tc["arguments"].get("params", {})
            and "ny" in tc["arguments"].get("params", {})
            for tc in parsed_tool_calls
        ),
    },
}

# Print summary to stderr
print(f"\nTTFT: {result['ttft_s']}s  Total: {result['total_time_s']}s", file=sys.stderr)
print(f"Tool calls: {result['tool_calls_count']}", file=sys.stderr)
for tc in parsed_tool_calls:
    print(f"  [{tc['index']}] {tc['name']}({json.dumps(tc['arguments'], ensure_ascii=False)})", file=sys.stderr)

print(f"\nDiagnosis:", file=sys.stderr)
for k, v in result["diagnosis"].items():
    print(f"  {k}: {v}", file=sys.stderr)

# Write output JSON
OUT = Path(__file__).parent / "busan-payload-probe.output.json"
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nOutput written to: {OUT}", file=sys.stderr)

# Also print JSON to stdout for piping
print(json.dumps(result, ensure_ascii=False, indent=2))
