# Research: Ctrl+O expand keybinding (Epic #2766 issue D)

## Diagnosis

Citizen reported: `^O` does not expand thinking / long output.

Code-path inspection:
1. `tui/src/keybindings/defaultBindings.ts:125` — `'ctrl+o': 'app:toggleTranscript'` ✓
2. `tui/src/hooks/useGlobalKeybindings.tsx:188` — `useKeybinding('app:toggleTranscript', handleToggleTranscript, {context: 'Global'})` ✓
3. `tui/src/keybindings/match.ts:172` — `getKeyName('o', {ctrl:true})` returns `'o'` ✓
4. `tui/src/ink/parse-keypress.ts:723-725` — `\x0F` (Ctrl+O byte) → `key.name='o', key.ctrl=true` ✓
5. `tui/src/ink/events/input-event.ts:58` — `input = key.ctrl ? key.name : key.sequence` → `'o'` ✓

The chord registry path SHOULD work. Yet the citizen reports it does not.

## Root cause hypotheses

- **H1**: `KeybindingProvider` mounts AFTER PromptInput's `useTextInput`, so
  PromptInput's `useInput` registers FIRST, sees Ctrl+O, and consumes it
  before ChordInterceptor or `useKeybinding` runs.
- **H2**: ChordInterceptor returns `match` for ctrl+o but doesn't invoke the
  handler (handler invocation only fires for `wasInChord=true` per
  `KeybindingProviderSetup.tsx:263`); it relies on `useKeybinding`'s OWN
  `useInput` to fire next. If KeybindingProvider's pendingChord state-set
  triggered a re-render that unmounted/remounted `useKeybinding`, the
  registration could lag.
- **H3**: An overlay (HelpV2 / MessageActions / Permission gauntlet) consumed
  the keystroke first.

## Fix

`tui/src/hooks/useGlobalKeybindings.tsx` — Add `useInput` fallback at the end
of the hook:

```tsx
useInput((input, key) => {
  if (key.ctrl && input === 'o') {
    handleToggleTranscript();
  }
});
```

This fires AFTER all chord-aware `useKeybinding` listeners (registered
earlier in `useGlobalKeybindings`'s execution order). When the chord
registry path consumed and stopImmediatePropagation'd, the fallback never
runs. When the chord path missed (any of H1-H3), the fallback rescues the
keystroke. Mirrors the PR #2754 Insight #4 pattern (`setToolJSX
isLocalJSXCommand:false` was the prior chord-fallback pattern).

## Defense-in-depth

Tier 1: Original `useKeybinding('app:toggleTranscript', ...)` — the
chord-aware path; respects user rebindings.

Tier 2: `useInput` fallback — fires on the literal Ctrl+O byte regardless
of chord state. Safety net only.

Tier 3 (deferred): A future spec can audit whether KeybindingProvider mounts
should be moved EARLIER in the React tree to make Tier 2 unnecessary.

## Verification

- Layer 1: `bun typecheck` PASS.
- Layer 1: `bun test` 982 pass / 0 fail.
- Live verification: manual citizen test (Ctrl+O during long response) —
  deferred to user smoke after merge.
