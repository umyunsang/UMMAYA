// [P0] Ambient global declarations for CC-inlined build-time constants
// that are injected at runtime by `src/stubs/macro-preload.ts`.
// TypeScript needs these to type-check the bare `MACRO.VERSION` references
// throughout the CC 2.1.88 source.

declare const MACRO: {
  VERSION: string
  VERSION_CHANGELOG: string
  BUILD_TIME: string
  FEEDBACK_CHANNEL: string
  ISSUES_EXPLAINER: string
  PACKAGE_URL: string
  NATIVE_PACKAGE_URL: string
}

// Node 22 + Bun provide `Promise.withResolvers()` but CC uses the explicit
// TC39 global shape. TS 5.6 has this built-in but older targets may not.
declare interface PromiseConstructor {
  withResolvers<T>(): {
    promise: Promise<T>
    resolve: (value: T | PromiseLike<T>) => void
    reject: (reason?: unknown) => void
  }
}

// Legacy / experimental global used by CC.
declare type PromiseWithResolvers<T> = ReturnType<PromiseConstructor['withResolvers']>

// lodash-es sub-path modules don't ship their own .d.ts files — declare them.
declare module 'lodash-es/memoize.js' {
  const memoize: <Args extends unknown[], Result>(
    fn: (...args: Args) => Result,
  ) => (...args: Args) => Result
  export default memoize
}
declare module 'lodash-es/mapValues.js' {
  const mapValues: <T, R>(
    obj: Record<string, T>,
    fn: (v: T, k: string) => R,
  ) => Record<string, R>
  export default mapValues
}
declare module 'lodash-es/pickBy.js' {
  const pickBy: <T>(
    obj: Record<string, T>,
    fn: (v: T, k: string) => boolean,
  ) => Record<string, T>
  export default pickBy
}
declare module 'lodash-es/uniqBy.js' {
  const uniqBy: <T, K>(arr: readonly T[], fn: (v: T) => K) => T[]
  export default uniqBy
}
