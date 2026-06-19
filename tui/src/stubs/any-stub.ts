// SPDX-License-Identifier: Apache-2.0
// Stage-1 NO-OP stub — resolves unreachable CC-only module imports so the
// runtime bundle loads. Real implementations are tracked in the CC TUI
// Fidelity Meta-Epic (Epic #1633).

export type StubFunction = (..._args: readonly unknown[]) => unknown

const __noop = (..._args: readonly unknown[]): undefined => undefined

// Smart Proxy that cooperates with primitive coercion / iteration / JSON
export function createStub(): StubFunction {
  let stub: StubFunction
  const target = function stubTarget(..._args: readonly unknown[]): unknown {
    return stub
  }
  stub = new Proxy(target, {
    get(_t, p) {
      // Well-known symbols used by JS engine during coercion
      if (p === Symbol.toPrimitive) return () => ''
      if (p === Symbol.iterator) return function* () {}
      if (p === Symbol.asyncIterator) return async function* () {}
      if (p === Symbol.toStringTag) return 'Stub'
      if (p === Symbol.for('nodejs.util.inspect.custom')) return () => '<Stub>'
      // Node's util.format uses `inspect` internally — shim it too
      if (p === 'inspect') return () => '<Stub>'
      if (p === 'then') return undefined // not a thenable
      if (p === 'toString') return () => ''
      if (p === 'valueOf') return () => undefined
      if (p === 'toJSON') return () => null
      if (p === 'length') return 0
      if (p === 'name') return 'Stub'
      if (p === 'message') return ''
      if (p === 'stack') return ''
      if (p === 'constructor') return Object
      return stub
    },
    apply() { return stub },
    construct() { return stub },
  })
  return stub
}

const __stub = createStub()

export default __stub

// Common utility exports for lodash-es-style consumers
export const memoize = <T>(fn: T): T => fn
export const sample = <T>(arr: readonly T[]): T | undefined =>
  arr[Math.floor(Math.random() * arr.length)]
export const tokenize = (input: string): unknown[] => [input]

// CC internal symbols routed via tsconfig paths to this stub
export const BROWSER_TOOLS: readonly string[] = []
export const COMPUTER_USE_TOOLS: readonly string[] = []
export const datadogLogs = { logger: { log: __noop, error: __noop, warn: __noop, info: __noop } }
export const log = __noop
export const logger = { log: __noop, error: __noop, warn: __noop, info: __noop, debug: __noop }
