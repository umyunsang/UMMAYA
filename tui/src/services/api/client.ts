// SPDX-License-Identifier: Apache-2.0
// KOSMOS-original — Epic #2077 client.ts no-op stub.
//
// CC's client.ts constructed the Anthropic SDK client (AnthropicClient,
// AnthropicBedrock, AnthropicVertex, etc.) and exported getAnthropicClient.
// KOSMOS routes all LLM traffic through the Spec 1978 stdio IPC bridge —
// there is no Anthropic client to construct. This stub re-exports the
// CLIENT_REQUEST_ID_HEADER constant and a no-op getAnthropicClient so that
// claude.ts (which imports './client.js') continues to compile.
//
// The real import of getAnthropicClient in claude.ts (executeNonStreamingRequest
// and verifyApiKey) is dead code in KOSMOS — those functions are overridden to
// route through the bridge. The import only needs to typecheck.

export const CLIENT_REQUEST_ID_HEADER = 'x-client-request-id'

// KOSMOS Epic #2077 — no-op client factory.
// Returns a minimal object that satisfies the `Anthropic`-shaped type used
// by the single caller in claude.ts (executeNonStreamingRequest, which is
// itself a KOSMOS no-op wrapper). This never executes in production.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getAnthropicClient(_opts: Record<string, unknown>): Promise<any> {
  // KOSMOS: no Anthropic client needed — LLM traffic goes through stdio bridge.
  return {
    beta: {
      messages: {
        create: async () => {
          throw new Error(
            '[KOSMOS] getAnthropicClient: called in KOSMOS — all LLM calls must go through the stdio bridge (Epic #2077)',
          )
        },
        stream: () => {
          throw new Error(
            '[KOSMOS] getAnthropicClient: streaming called in KOSMOS — all LLM calls must go through the stdio bridge (Epic #2077)',
          )
        },
      },
    },
  }
}

// SWAP/anti-anthropic-1p(2521): byte-copied tui/src/services/api/claude.ts
// imports `getAnthropicClient`. KOSMOS routes LLM calls via stdio IPC bridge
// (Spec 1978) and never instantiates an Anthropic client directly. Stub
// returns null so the byte-copy's import resolves at link time; the zero-
// callers status guarantees this null is never dereferenced.
export function getAnthropicClient(..._args: unknown[]): null {
  return null
}
