// SPDX-License-Identifier: Apache-2.0

import { makeBaseEnvelope, makeUUIDv7 } from './envelope.js'
import type {
  ChatRequestFrame,
  IPCFrame,
  ToolCallFrame,
  ToolResultFrame,
} from './frames.generated.js'
import type { FrameHook, IPCBridge } from './bridge.js'
import { resolveAdapter } from '../services/api/adapterManifest.js'

const DEFAULT_LIVE_ADAPTER_PROXY_URL =
  'https://ummaya-live-gateway-ygjh3ipzqq-du.a.run.app/v1/adapters'

type PrimitiveName = 'find' | 'locate' | 'check' | 'send' | 'document'

type GatewayRequestContext = {
  readonly latestLocateResult: Record<string, unknown> | null
  readonly latestUserText: string
}

type LocateCoordinates = {
  readonly lat: number
  readonly lon: number
}

class AsyncQueue<T> {
  private queue: T[] = []
  private resolver: ((value: IteratorResult<T>) => void) | null = null
  private closed = false

  push(item: T): void {
    if (this.closed) return
    if (this.resolver) {
      const resolve = this.resolver
      this.resolver = null
      resolve({ value: item, done: false })
      return
    }
    this.queue.push(item)
  }

  close(): void {
    this.closed = true
    if (this.resolver) {
      const resolve = this.resolver
      this.resolver = null
      resolve({ value: undefined as unknown as T, done: true })
    }
  }

  [Symbol.asyncIterator](): AsyncIterator<T> {
    return {
      next: () => {
        if (this.queue.length > 0) {
          return Promise.resolve({ value: this.queue.shift()!, done: false })
        }
        if (this.closed) {
          return Promise.resolve({ value: undefined as unknown as T, done: true })
        }
        return new Promise((resolve) => {
          this.resolver = resolve
        })
      },
      return: () => {
        if (this.resolver) {
          const resolve = this.resolver
          this.resolver = null
          resolve({ value: undefined as unknown as T, done: true })
        }
        return Promise.resolve({ value: undefined as unknown as T, done: true })
      },
    }
  }
}

export function shouldUseHostedGatewayBridge(): boolean {
  const transport = process.env['UMMAYA_BACKEND_TRANSPORT']
  if (transport === 'hosted-gateway') return true
  if (transport === 'stdio') return false
  return Boolean(process.env['UMMAYA_PACKAGE_ROOT'])
}

export function liveAdapterProxyUrl(): string {
  return process.env['UMMAYA_LIVE_ADAPTER_PROXY_URL'] ?? DEFAULT_LIVE_ADAPTER_PROXY_URL
}

export function manifestUrlFromAdapterProxyUrl(rawUrl: string): string {
  const url = new URL(rawUrl)
  const trimmedPath = url.pathname.replace(/\/+$/, '')
  if (trimmedPath.endsWith('/v1/adapters')) {
    url.pathname = `${trimmedPath.slice(0, -'/adapters'.length)}/manifest`
  } else {
    url.pathname = `${trimmedPath}/manifest`
  }
  return url.toString()
}

export function createHostedGatewayBridge(
  opts: { onFrame?: FrameHook; sessionId?: string } = {},
): IPCBridge {
  const queue = new AsyncQueue<IPCFrame>()
  const appliedFrameSeqs = new Set<string>()
  let closed = false
  let sessionId: string | null = opts.sessionId ?? null
  let lastSeenCorrelationId: string | null = null
  let lastSeenFrameSeq: number | null = null
  let latestLocateResult: Record<string, unknown> | null = null
  let latestUserText = ''

  const bridge: IPCBridge = {
    proc: null,
    onFrame: opts.onFrame,
    applied_frame_seqs: appliedFrameSeqs,
    get lastSeenCorrelationId() {
      return lastSeenCorrelationId
    },
    get lastSeenFrameSeq() {
      return lastSeenFrameSeq
    },
    setSessionCredentials(nextSessionId: string): void {
      sessionId = nextSessionId
    },
    signalDrop(): void {},
    send(frame: IPCFrame): boolean {
      if (closed) return false
      dispatchHook(frame, 'send', 0)
      if (frame.kind === 'chat_request') {
        latestUserText = latestUserTextFromFrame(frame) ?? latestUserText
      }
      if (frame.kind !== 'tool_call') return true
      void invokeToolCall(frame)
      return true
    },
    frames(): AsyncIterable<IPCFrame> {
      return queue
    },
    async close(): Promise<void> {
      closed = true
      queue.close()
    },
  }

  function dispatchHook(frame: IPCFrame, direction: 'recv' | 'send', latencyMs: number): void {
    const hook = bridge.onFrame
    if (!hook) return
    queueMicrotask(() => {
      try {
        const result = hook(frame, direction, latencyMs) as unknown
        if (result instanceof Promise) {
          result.catch(() => {})
        }
      } catch {}
    })
  }

  function emit(frame: IPCFrame): void {
    if (closed) return
    if (typeof frame.frame_seq === 'number') {
      const seqSessionId = frame.session_id || sessionId || ''
      if (seqSessionId) appliedFrameSeqs.add(`${seqSessionId}:${frame.frame_seq}`)
      lastSeenFrameSeq = Math.max(lastSeenFrameSeq ?? 0, frame.frame_seq)
    }
    lastSeenCorrelationId = frame.correlation_id ?? lastSeenCorrelationId
    queue.push(frame)
    dispatchHook(frame, 'recv', 0)
  }

  async function fetchManifest(): Promise<void> {
    const response = await fetch(manifestUrlFromAdapterProxyUrl(liveAdapterProxyUrl()), {
      headers: { accept: 'application/json' },
    })
    if (!response.ok) {
      throw new Error(`manifest HTTP ${response.status}`)
    }
    emit((await response.json()) as IPCFrame)
  }

  async function invokeToolCall(frame: ToolCallFrame): Promise<void> {
    try {
      const request = gatewayRequestForToolCall(frame, {
        latestLocateResult,
        latestUserText,
      })
      if (request === null) {
        emit(toolResultFrame(frame, 'find', {
          error: `Hosted gateway cannot resolve tool '${frame.name}'.`,
        }))
        return
      }
      const started = Date.now()
      const response = await fetch(`${adapterProxyUrl().replace(/\/+$/, '')}/${request.toolId}`, {
        method: 'POST',
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
        },
        body: JSON.stringify({
          schema_version: 'ummaya.live_adapter.v1',
          tool_id: request.toolId,
          primitive: request.primitive,
          request_id: frame.call_id || makeUUIDv7(),
          params: request.params,
          session_identity: frame.session_id || sessionId,
        }),
      })
      const body = await response.json() as Record<string, unknown>
      if (!response.ok || body.ok !== true) {
        emit(toolResultFrame(frame, request.primitive, {
          error: gatewayErrorMessage(response.status, body),
          tool_id: request.toolId,
        }))
        return
      }
      latestLocateResult = rememberSuccessfulLocateResult(
        request.primitive,
        body.result,
        latestLocateResult,
      )
      emit(toolResultFrame(frame, request.primitive, { result: body.result }, Date.now() - started))
    } catch (error) {
      emit(toolResultFrame(frame, primitiveForFrame(frame) ?? 'find', {
        error: error instanceof Error ? error.message : String(error),
      }))
    }
  }

  void fetchManifest().catch(() => {})
  return bridge
}

function adapterProxyUrl(): string {
  return liveAdapterProxyUrl()
}

function gatewayRequestForToolCall(frame: ToolCallFrame): {
  toolId: string
  primitive: 'find' | 'locate'
  params: Record<string, unknown>
} | null
function gatewayRequestForToolCall(frame: ToolCallFrame, context: GatewayRequestContext): {
  toolId: string
  primitive: 'find' | 'locate'
  params: Record<string, unknown>
} | null
function gatewayRequestForToolCall(
  frame: ToolCallFrame,
  context: GatewayRequestContext = { latestLocateResult: null, latestUserText: '' },
): {
  toolId: string
  primitive: 'find' | 'locate'
  params: Record<string, unknown>
} | null {
  const args = recordFrom(frame.arguments)
  const rootPrimitive = rootPrimitiveFromName(frame.name)
  const toolId = rootPrimitive
    ? stringField(args, 'tool_id')
    : frame.name
  if (!toolId) return null

  const primitive = rootPrimitive ?? primitiveForAdapter(toolId)
  if (primitive !== 'find' && primitive !== 'locate') return null

  const rawParams = rootPrimitive ? args.params : args
  const params = recordFrom(rawParams)
  return {
    toolId,
    primitive,
    params: normalizeGatewayParamsForTool(
      toolId,
      primitive,
      params ?? {},
      context,
    ),
  }
}

function latestUserTextFromFrame(frame: ChatRequestFrame): string | null {
  for (let index = frame.messages.length - 1; index >= 0; index -= 1) {
    const message = frame.messages[index]
    if (!message || message.role !== 'user') continue
    const content = message.content.trim()
    if (content) return content
  }
  return null
}

function rememberSuccessfulLocateResult(
  primitive: 'find' | 'locate',
  result: unknown,
  current: Record<string, unknown> | null,
): Record<string, unknown> | null {
  if (primitive !== 'locate') return current
  const resultRecord = recordFrom(result)
  if (resultRecord === null) return current
  if (locateCoordinatesFromResult(resultRecord) === null) return current
  return resultRecord
}

function normalizeGatewayParamsForTool(
  toolId: string,
  primitive: 'find' | 'locate',
  params: Record<string, unknown>,
  context: GatewayRequestContext,
): Record<string, unknown> {
  if (primitive !== 'find' || toolId !== 'hira_hospital_search') return params
  return normalizeHiraParamsFromLocate(params, context.latestLocateResult, context.latestUserText)
}

function normalizeHiraParamsFromLocate(
  params: Record<string, unknown>,
  locateResult: Record<string, unknown> | null,
  userText: string,
): Record<string, unknown> {
  let changed = false
  const nextParams: Record<string, unknown> = { ...params }

  if (!hasValidHiraCoordinates(nextParams)) {
    const coords = locateResult ? locateCoordinatesFromResult(locateResult) : null
    if (coords === null) return params
    nextParams['xPos'] = coords.lon
    nextParams['yPos'] = coords.lat
    changed = true
  }

  if (!hasValidHiraRadius(nextParams['radius'])) {
    nextParams['radius'] = 2000
    changed = true
  }

  if (!hasNonEmptyString(nextParams['dgsbjt'])) {
    const department = hiraDepartmentFromQuery(userText)
    if (department !== null) {
      nextParams['dgsbjt'] = department
      changed = true
    }
  }

  return changed ? nextParams : params
}

function hasValidHiraCoordinates(params: Record<string, unknown>): boolean {
  const lon = params['xPos']
  const lat = params['yPos']
  return (
    isFiniteNumber(lon) &&
    isFiniteNumber(lat) &&
    lon >= 124 &&
    lon <= 132 &&
    lat >= 33 &&
    lat <= 39 &&
    !isWholeDegreePair(lat, lon)
  )
}

function hasValidHiraRadius(value: unknown): boolean {
  return isIntegerNumber(value) && value >= 1 && value <= 10000
}

function locateCoordinatesFromResult(result: Record<string, unknown>): LocateCoordinates | null {
  const directLat = numberField(result, 'lat')
  const directLon = numberField(result, 'lon')
  if (directLat !== null && directLon !== null) {
    return { lat: directLat, lon: directLon }
  }

  const latitude = numberField(result, 'latitude')
  const longitude = numberField(result, 'longitude')
  if (latitude !== null && longitude !== null) {
    return { lat: latitude, lon: longitude }
  }

  return null
}

function hiraDepartmentFromQuery(userText: string): string | null {
  const hints: readonly [RegExp, string][] = [
    [/소아청소년과|소아과|pediatrics?/i, '소아청소년과'],
    [/이비인후과|ent\b/i, '이비인후과'],
    [/내과|internal medicine/i, '내과'],
    [/피부과|dermatology/i, '피부과'],
    [/정형외과|orthopedics?/i, '정형외과'],
    [/산부인과|obgyn|ob\/gyn/i, '산부인과'],
    [/안과|ophthalmology/i, '안과'],
  ]
  for (const [pattern, department] of hints) {
    if (pattern.test(userText)) return department
  }
  return null
}

function numberField(record: Record<string, unknown>, key: string): number | null {
  const value = record[key]
  return isFiniteNumber(value) ? value : null
}

function hasNonEmptyString(value: unknown): boolean {
  return typeof value === 'string' && value.trim().length > 0
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function isIntegerNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value)
}

function isWholeDegreePair(lat: number, lon: number): boolean {
  return Number.isInteger(lat) && Number.isInteger(lon)
}

function toolResultFrame(
  requestFrame: ToolCallFrame,
  primitive: PrimitiveName,
  payload: { result?: unknown; error?: string; tool_id?: string },
  latencyMs = 0,
): ToolResultFrame {
  void latencyMs
  const envelope: Record<string, unknown> = { kind: primitive }
  if (payload.error) envelope.error = payload.error
  if ('result' in payload) envelope.result = payload.result
  if (payload.tool_id) envelope.tool_id = payload.tool_id
  return {
    ...makeBaseEnvelope({
      sessionId: requestFrame.session_id,
      correlationId: requestFrame.correlation_id || makeUUIDv7(),
    }),
    role: 'backend',
    kind: 'tool_result',
    call_id: requestFrame.call_id,
    envelope: envelope as ToolResultFrame['envelope'],
  }
}

function gatewayErrorMessage(status: number, body: Record<string, unknown>): string {
  const detail = body.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return `Hosted gateway request failed with HTTP ${status}.`
}

function primitiveForFrame(frame: ToolCallFrame): PrimitiveName | null {
  return rootPrimitiveFromName(frame.name) ?? primitiveForAdapter(frame.name)
}

function primitiveForAdapter(toolId: string): PrimitiveName | null {
  const primitive = resolveAdapter(toolId)?.primitive
  if (
    primitive === 'find' ||
    primitive === 'locate' ||
    primitive === 'check' ||
    primitive === 'send' ||
    primitive === 'document'
  ) {
    return primitive
  }
  return null
}

function rootPrimitiveFromName(name: string): PrimitiveName | null {
  if (
    name === 'find' ||
    name === 'locate' ||
    name === 'check' ||
    name === 'send' ||
    name === 'document'
  ) {
    return name
  }
  return null
}

function recordFrom(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  return Object.fromEntries(Object.entries(value))
}

function stringField(record: Record<string, unknown>, key: string): string | null {
  const value = record[key]
  return typeof value === 'string' && value.trim() ? value : null
}
