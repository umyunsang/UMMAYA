// SWAP/llm-provider(2521) — Spec 2521 byte-copy relax (user-approved
// 2026-05-01) on the Ink rendering layer.
//
// CC's original value was 16 ms (~60 fps). That floor folds K-EXAONE on
// FriendliAI's content-channel chunks (13-17 ms inter-arrival latency,
// measured via deps.ts trace) into a single Ink commit — the answer
// paragraph paints atomically (Layer 5 frame_0294 / frame_0903 of the
// /tmp/tdb-* corpora). CC against Anthropic doesn't see the same fold
// because Anthropic's per-token cadence is ~50-100 ms, comfortably
// outside the 16 ms throttle.
//
// Lowering to 4 ms (~250 fps) lets K-EXAONE's natural per-token chunks
// pass through one-render-per-chunk for visible token-level streaming.
// CPU impact is negligible — Ink only re-renders when state actually
// changes; the throttle floor is a *minimum* gap, not a fixed tick.
export const FRAME_INTERVAL_MS = 4
