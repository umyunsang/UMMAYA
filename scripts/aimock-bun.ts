#!/usr/bin/env bun
// SPDX-License-Identifier: Apache-2.0
// aimock-bun.ts — hand-rolled Bun HTTP server that serves OpenAI-compatible
// SSE responses from the KOSMOS fixture JSON files.
//
// Fallback for environments where ghcr.io/copilotkit/aimock:latest is
// unavailable (Docker not installed, image pull failure, CI constraints).
//
// Usage:
//   bun scripts/aimock-bun.ts [--port 4010] [--fixtures tests/fixtures/llm]
//
// Spec: specs/debug-infra-rebuild/RFC.md § P0 — aimock fallback (option a)
// Decision: Docker unavailable on this machine (/usr/local/bin/docker is a
//           broken symlink to the uninstalled Docker.app). Bun is available
//           at /Users/um-yunsang/.bun/bin/bun (v1.3.12).

import { readdir, readFile } from "node:fs/promises";
import { join, resolve } from "node:path";

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
const args = process.argv.slice(2);
const portIdx = args.indexOf("--port");
const PORT = portIdx !== -1 ? parseInt(args[portIdx + 1], 10) : 4010;
const fixturesIdx = args.indexOf("--fixtures");
const FIXTURES_DIR =
  fixturesIdx !== -1
    ? resolve(args[fixturesIdx + 1])
    : resolve("tests/fixtures/llm");

// ---------------------------------------------------------------------------
// Fixture loading
// ---------------------------------------------------------------------------

interface MatchRule {
  userMessageContains?: string;
  userMessage?: string;
}

interface ToolCallDef {
  name: string;
  arguments: Record<string, unknown>;
}

interface ResponseDef {
  content?: string;
  toolCalls?: ToolCallDef[];
}

interface StreamingDef {
  ttft?: number; // ms
  tps?: number; // tokens per second
  jitter?: number; // ±ms
}

interface Fixture {
  match: MatchRule;
  response: ResponseDef;
  streaming?: StreamingDef;
}

interface FixtureFile {
  fixtures: Fixture[];
}

let allFixtures: Fixture[] = [];

async function loadFixtures(): Promise<void> {
  try {
    const files = await readdir(FIXTURES_DIR);
    for (const f of files) {
      if (!f.endsWith(".json") || f === "aimock.json") continue;
      try {
        const raw = await readFile(join(FIXTURES_DIR, f), "utf8");
        const parsed: FixtureFile = JSON.parse(raw);
        if (Array.isArray(parsed.fixtures)) {
          allFixtures.push(...parsed.fixtures);
          console.log(
            `[aimock-bun] loaded ${parsed.fixtures.length} fixture(s) from ${f}`
          );
        }
      } catch (e) {
        console.warn(`[aimock-bun] skipping ${f}: ${e}`);
      }
    }
  } catch (e) {
    console.error(`[aimock-bun] failed to read fixtures dir ${FIXTURES_DIR}: ${e}`);
  }
  console.log(`[aimock-bun] total fixtures: ${allFixtures.length}`);
}

// ---------------------------------------------------------------------------
// Fixture matching
// ---------------------------------------------------------------------------

function findFixture(messages: Array<{ role: string; content: string }>): Fixture | null {
  // Find the last user message
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (!lastUser) return null;
  const text = lastUser.content ?? "";

  for (const fixture of allFixtures) {
    const { match } = fixture;
    if (match.userMessage !== undefined && text === match.userMessage) {
      return fixture;
    }
    if (
      match.userMessageContains !== undefined &&
      text.includes(match.userMessageContains)
    ) {
      return fixture;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// SSE helpers
// ---------------------------------------------------------------------------

function makeId(): string {
  return `chatcmpl-${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
}

function sseData(obj: unknown): string {
  return `data: ${JSON.stringify(obj)}\n\n`;
}

const SSE_DONE = "data: [DONE]\n\n";

// Compute per-token delay from tps + jitter
function tokenDelayMs(tps?: number, jitter?: number): number {
  const base = tps && tps > 0 ? 1000 / tps : 20;
  const j = jitter ?? 0;
  return base + (Math.random() * 2 - 1) * j;
}

// ---------------------------------------------------------------------------
// Streaming response builders
// ---------------------------------------------------------------------------

async function* streamTextResponse(
  id: string,
  model: string,
  content: string,
  streaming?: StreamingDef
): AsyncIterable<string> {
  const ttft = streaming?.ttft ?? 100;
  const tps = streaming?.tps;
  const jitter = streaming?.jitter;

  // time-to-first-token
  await Bun.sleep(ttft);

  // message_start equivalent — first chunk
  const firstChunk = {
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: { role: "assistant", content: "" }, finish_reason: null }],
  };
  yield sseData(firstChunk);

  // Emit content word-by-word (simulates streaming)
  const words = content.split(/(\s+)/);
  for (const word of words) {
    await Bun.sleep(tokenDelayMs(tps, jitter));
    yield sseData({
      id,
      object: "chat.completion.chunk",
      model,
      choices: [{ index: 0, delta: { content: word }, finish_reason: null }],
    });
  }

  // Final chunk with finish_reason
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
    usage: { prompt_tokens: 10, completion_tokens: words.length },
  });

  yield SSE_DONE;
}

async function* streamToolCallResponse(
  id: string,
  model: string,
  toolCalls: ToolCallDef[],
  streaming?: StreamingDef
): AsyncIterable<string> {
  const ttft = streaming?.ttft ?? 100;
  const tps = streaming?.tps;
  const jitter = streaming?.jitter;

  // time-to-first-token
  await Bun.sleep(ttft);

  // First chunk: role delta
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [
      { index: 0, delta: { role: "assistant", content: null }, finish_reason: null },
    ],
  });

  // For each tool call, emit the OpenAI streaming tool_calls format:
  // First chunk: tool_call header (index, id, type, function.name)
  // Subsequent chunks: function.arguments fragments (simulate streaming)
  for (let tcIdx = 0; tcIdx < toolCalls.length; tcIdx++) {
    const tc = toolCalls[tcIdx];
    const callId = `call_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
    const argsStr = JSON.stringify(tc.arguments);

    // Header chunk with name
    await Bun.sleep(tokenDelayMs(tps, jitter));
    yield sseData({
      id,
      object: "chat.completion.chunk",
      model,
      choices: [
        {
          index: 0,
          delta: {
            tool_calls: [
              {
                index: tcIdx,
                id: callId,
                type: "function",
                function: { name: tc.name, arguments: "" },
              },
            ],
          },
          finish_reason: null,
        },
      ],
    });

    // Stream arguments in chunks of ~20 chars
    const chunkSize = 20;
    for (let i = 0; i < argsStr.length; i += chunkSize) {
      await Bun.sleep(tokenDelayMs(tps, jitter));
      yield sseData({
        id,
        object: "chat.completion.chunk",
        model,
        choices: [
          {
            index: 0,
            delta: {
              tool_calls: [
                {
                  index: tcIdx,
                  function: { arguments: argsStr.slice(i, i + chunkSize) },
                },
              ],
            },
            finish_reason: null,
          },
        ],
      });
    }
  }

  // Final stop chunk
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: {}, finish_reason: "tool_calls" }],
    usage: { prompt_tokens: 50, completion_tokens: 30 },
  });

  yield SSE_DONE;
}

// ---------------------------------------------------------------------------
// Fallback response (no fixture matched)
// ---------------------------------------------------------------------------

async function* streamFallbackResponse(
  id: string,
  model: string
): AsyncIterable<string> {
  await Bun.sleep(100);
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: { role: "assistant", content: "" }, finish_reason: null }],
  });
  const msg = "No fixture matched. Add a fixture in tests/fixtures/llm/.";
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: { content: msg }, finish_reason: null }],
  });
  yield sseData({
    id,
    object: "chat.completion.chunk",
    model,
    choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
  });
  yield SSE_DONE;
}

// ---------------------------------------------------------------------------
// Request handler
// ---------------------------------------------------------------------------

async function handleCompletions(req: Request): Promise<Response> {
  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return new Response("Bad request", { status: 400 });
  }

  const model =
    typeof body["model"] === "string"
      ? body["model"]
      : "LGAI-EXAONE/K-EXAONE-236B-A23B";
  const messages = (body["messages"] as Array<{ role: string; content: string }>) ?? [];
  const stream = body["stream"] === true || body["stream"] === undefined;

  const id = makeId();
  const fixture = findFixture(messages);

  console.log(
    `[aimock-bun] ${new Date().toISOString()} POST /chat/completions` +
      ` model=${model} messages=${messages.length}` +
      ` fixture=${fixture ? JSON.stringify(fixture.match) : "none"}`
  );

  // Non-streaming path (rare for KOSMOS but handle it)
  if (!stream) {
    if (!fixture) {
      return Response.json({
        id,
        object: "chat.completion",
        model,
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: "No fixture matched.",
            },
            finish_reason: "stop",
          },
        ],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      });
    }
    const { response } = fixture;
    if (response.toolCalls && response.toolCalls.length > 0) {
      return Response.json({
        id,
        object: "chat.completion",
        model,
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: null,
              tool_calls: response.toolCalls.map((tc, idx) => ({
                index: idx,
                id: `call_${idx}`,
                type: "function",
                function: {
                  name: tc.name,
                  arguments: JSON.stringify(tc.arguments),
                },
              })),
            },
            finish_reason: "tool_calls",
          },
        ],
        usage: { prompt_tokens: 50, completion_tokens: 30, total_tokens: 80 },
      });
    }
    return Response.json({
      id,
      object: "chat.completion",
      model,
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: response.content ?? "" },
          finish_reason: "stop",
        },
      ],
      usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
    });
  }

  // Streaming path
  let generator: AsyncIterable<string>;
  if (!fixture) {
    generator = streamFallbackResponse(id, model);
  } else if (fixture.response.toolCalls && fixture.response.toolCalls.length > 0) {
    generator = streamToolCallResponse(
      id,
      model,
      fixture.response.toolCalls,
      fixture.streaming
    );
  } else {
    generator = streamTextResponse(
      id,
      model,
      fixture.response.content ?? "",
      fixture.streaming
    );
  }

  const readable = new ReadableStream({
    async start(controller) {
      try {
        for await (const chunk of generator) {
          controller.enqueue(new TextEncoder().encode(chunk));
        }
      } finally {
        controller.close();
      }
    },
  });

  return new Response(readable, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Aimock-Fallback": "bun",
    },
  });
}

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

await loadFixtures();

const server = Bun.serve({
  port: PORT,
  fetch(req) {
    const url = new URL(req.url);

    // Health endpoint
    if (url.pathname === "/health" || url.pathname === "/v1/health") {
      return new Response(
        JSON.stringify({ status: "ok", server: "aimock-bun", fixtures: allFixtures.length }),
        { headers: { "Content-Type": "application/json" } }
      );
    }

    // Models endpoint (some clients ping this)
    if (url.pathname === "/v1/models") {
      return Response.json({
        object: "list",
        data: [{ id: "LGAI-EXAONE/K-EXAONE-236B-A23B", object: "model" }],
      });
    }

    // Main completions endpoint
    if (
      url.pathname === "/v1/chat/completions" &&
      req.method === "POST"
    ) {
      return handleCompletions(req);
    }

    return new Response("Not found", { status: 404 });
  },
  error(err) {
    console.error("[aimock-bun] server error:", err);
    return new Response("Internal server error", { status: 500 });
  },
});

console.log(
  `[aimock-bun] listening on http://localhost:${PORT} — ` +
    `${allFixtures.length} fixture(s) loaded from ${FIXTURES_DIR}`
);
console.log("[aimock-bun] set KOSMOS_FRIENDLI_BASE_URL=http://localhost:4010/v1 to use this server");
