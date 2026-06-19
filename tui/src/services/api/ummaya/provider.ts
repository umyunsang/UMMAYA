import { assertFriendliApiKeyForUse } from '../../../utils/auth.js'
import {
  createAssistantAPIErrorMessage,
  createAssistantMessage,
} from '../../../utils/messages.js'
import { ensureUmmayaAdapterManifest } from '../../../ipc/bridgeSingleton.js'
import { latestUserText } from './messages.js'
import { buildProviderRequest, getAPIMetadata } from './request.js'
import {
  ProviderStreamIdleTimeoutError,
  streamResponseToMessages,
} from './streaming.js'
import { shouldWaitForAdapterManifestForProviderRequest } from './toolSelection.js'
import type { QueryModelParams } from './types.js'
import {
  appendProviderOutputEvidence,
  appendProviderTurnEvidence,
  createProviderTurnEvidenceContext,
} from './evidence.js'
import type { ProviderOptions } from './types.js'

export { getAPIMetadata }

export const PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS = 30_000
const PROVIDER_STREAM_TIMEOUT_HANDOFF =
  'K-EXAONE 응답이 지연되어 이번 요청을 이어갈 수 없습니다. 잠시 후 다시 시도해 주세요.'
const DEFAULT_PROVIDER_EVENT_IDLE_TIMEOUT_MS = 90_000
const PROVIDER_EVENT_IDLE_TIMEOUT_ENV = 'UMMAYA_TUI_PROVIDER_EVENT_IDLE_TIMEOUT_MS'
const FRAME_IDLE_TIMEOUT_ENV = 'UMMAYA_TUI_FRAME_IDLE_TIMEOUT_MS'
const FRIENDLI_CHAT_COMPLETIONS_URL =
  'https://api.friendli.ai/serverless/v1/chat/completions'
const TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_ENV =
  'UMMAYA_TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS'

function publicServiceManifestSyncTimeoutMs(): number {
  const rawTimeout = process.env[TEST_PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_ENV]
  if (rawTimeout === undefined) return PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS

  const parsedTimeout = Number(rawTimeout)
  if (!Number.isInteger(parsedTimeout) || parsedTimeout <= 0) {
    return PUBLIC_SERVICE_MANIFEST_SYNC_TIMEOUT_MS
  }
  return parsedTimeout
}

function adapterManifestTimeoutMessage(timeoutMs: number): string {
  return [
    `public-service adapter manifest did not sync within ${timeoutMs}ms;`,
    'backend readiness is required before starting public-service provider requests.',
    'Retry after adapter_manifest_sync arrives from the backend.',
  ].join(' ')
}

function providerEventIdleTimeoutMs(): number {
  const rawTimeout =
    process.env[PROVIDER_EVENT_IDLE_TIMEOUT_ENV] ??
    process.env[FRAME_IDLE_TIMEOUT_ENV]
  if (rawTimeout === undefined) return DEFAULT_PROVIDER_EVENT_IDLE_TIMEOUT_MS

  const parsedTimeout = Number.parseInt(rawTimeout, 10)
  if (!Number.isFinite(parsedTimeout) || parsedTimeout <= 0) {
    return DEFAULT_PROVIDER_EVENT_IDLE_TIMEOUT_MS
  }
  return parsedTimeout
}

export function getExtraBodyParams(_betaHeaders?: readonly string[]): Record<string, unknown> {
  return {}
}

export function configureTaskBudgetParams(
  taskBudget: { readonly total: number; readonly remaining?: number } | undefined,
  outputConfig: Record<string, unknown>,
  _betas: string[],
): void {
  if (!taskBudget) return
  outputConfig.task_budget = taskBudget
}

export async function verifyApiKey(
  apiKey: string,
  _isNonInteractiveSession: boolean,
): Promise<boolean> {
  return apiKey.trim().length > 0
}

export async function* queryModelWithStreaming(
  params: QueryModelParams,
): AsyncGenerator<unknown> {
  assertFriendliApiKeyForUse()
  const evidenceContext = createProviderTurnEvidenceContext(params)
  const userText = latestUserText(params.messages)
  if (
    shouldWaitForAdapterManifestForProviderRequest({
      querySource: params.options.querySource,
      userText,
    })
  ) {
    const timeoutMs = publicServiceManifestSyncTimeoutMs()
    const manifestSynced = await ensureUmmayaAdapterManifest(timeoutMs)
    if (!manifestSynced) {
      yield createAssistantAPIErrorMessage({
        content: adapterManifestTimeoutMessage(timeoutMs),
        apiError: 'api_error',
      })
      return
    }
  }
  const request = buildProviderRequest(params, evidenceContext)
  const fetchImpl: NonNullable<ProviderOptions['fetchOverride']> =
    params.options.fetchOverride ?? ((input, init) => fetch(input, init))
  yield { type: 'stream_request_start' as const }
  let providerTurnStarted = false
  try {
    appendProviderTurnEvidence('provider_turn_start', evidenceContext)
    providerTurnStarted = true
    const response = await fetchProviderResponse(
      fetchImpl,
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          authorization: `Bearer ${process.env.UMMAYA_FRIENDLI_TOKEN ?? ''}`,
        },
        body: JSON.stringify(request),
        signal: params.signal,
      },
      providerEventIdleTimeoutMs(),
    )
    for await (const event of streamResponseToMessages(response, {
      dataIdleTimeoutMs: providerEventIdleTimeoutMs(),
      availableToolNames: rawJsonToolCallNamesForRequest(request),
      includeReasoning: request.include_reasoning === true,
    })) {
      appendProviderOutputEvidence(event, evidenceContext)
      yield event
    }
  } catch (error) {
    if (error instanceof ProviderStreamIdleTimeoutError) {
      yield createAssistantMessage({
        content: PROVIDER_STREAM_TIMEOUT_HANDOFF,
      })
      return
    }
    throw error
  } finally {
    if (providerTurnStarted) {
      appendProviderTurnEvidence('provider_turn_complete', evidenceContext)
    }
  }
}

function rawJsonToolCallNamesForRequest(request: {
  readonly tools?: readonly {
    readonly function: { readonly name: string }
  }[]
}): readonly string[] {
  const names = new Set<string>()
  for (const tool of request.tools ?? []) {
    const name = tool.function.name.trim()
    if (name.length > 0) names.add(name)
  }
  return [...names]
}

async function fetchProviderResponse(
  fetchImpl: NonNullable<ProviderOptions['fetchOverride']>,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController()
  const upstreamSignal = init.signal
  const abortFromUpstream = () => {
    controller.abort(upstreamSignal?.reason)
  }
  if (upstreamSignal?.aborted) {
    controller.abort(upstreamSignal.reason)
  } else {
    upstreamSignal?.addEventListener('abort', abortFromUpstream, { once: true })
  }
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = setTimeout(() => {
      controller.abort()
      reject(new ProviderStreamIdleTimeoutError(timeoutMs))
    }, timeoutMs)
  })
  try {
    return await Promise.race([
      fetchImpl(FRIENDLI_CHAT_COMPLETIONS_URL, {
        ...init,
        signal: controller.signal,
      }),
      timeout,
    ])
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId)
    upstreamSignal?.removeEventListener('abort', abortFromUpstream)
  }
}
