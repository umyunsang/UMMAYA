import type { ToolResult } from '../../Tool.js'
import { errorMessage, isAbortError } from '../../utils/errors.js'
import { formatFileSize } from '../../utils/format.js'
import { WEB_FETCH_TOOL_NAME } from './prompt.js'
import {
  buildSourceEvidence,
  buildSourceVerification,
  redactSourceVerificationText,
} from './sourceVerification.js'
import type {
  WebFetchCallContext,
  WebFetchCallInput,
  WebFetchOutput,
} from './types.js'
import { validateResolvedPublicWebFetchUrl } from './resolvedAddressSafety.js'
import {
  applyPromptToMarkdown,
  getURLMarkdownContent,
  isPreapprovedUrl,
  MAX_MARKDOWN_LENGTH,
} from './utils.js'

export async function callWebFetch(
  { url, prompt }: WebFetchCallInput,
  { abortController, options: { isNonInteractiveSession } }: WebFetchCallContext,
): Promise<ToolResult<WebFetchOutput>> {
  const start = Date.now()
  const validation = await validateResolvedPublicWebFetchUrl(url)
  if (!validation.ok) {
    return blockedToolResult({
      url,
      start,
      message: `Source verification blocked: ${validation.message}`,
      sourceUrl: null,
      title: 'Unsafe URL',
    })
  }

  try {
    const response = await getURLMarkdownContent(url, abortController)

    if ('type' in response && response.type === 'redirect') {
      const redirectValidation = await validateResolvedPublicWebFetchUrl(
        response.redirectUrl,
      )
      if (!redirectValidation.ok) {
        return blockedToolResult({
          url,
          start,
          code: response.statusCode,
          codeText: 'Redirect Target Blocked',
          message: `Source verification blocked: ${redirectValidation.message}`,
          sourceUrl: null,
          title: 'Unsafe redirect target',
        })
      }
      return redirectedToolResult({
        url,
        prompt,
        start,
        originalUrl: response.originalUrl,
        redirectUrl: response.redirectUrl,
        statusCode: response.statusCode,
      })
    }

    const {
      content,
      bytes,
      code,
      codeText,
      contentType,
      persistedPath,
      persistedSize,
    } = response
    const isPreapproved = isPreapprovedUrl(url)
    let result =
      isPreapproved &&
      contentType.includes('text/markdown') &&
      content.length < MAX_MARKDOWN_LENGTH
        ? content
        : await applyPromptToMarkdown(
            prompt,
            content,
            abortController.signal,
            isNonInteractiveSession,
            isPreapproved,
          )

    if (persistedPath) {
      result += `\n\n[Binary content (${contentType}, ${formatFileSize(persistedSize ?? bytes)}) also saved to ${persistedPath}]`
    }

    const sourceVerification = buildSourceVerification([
      buildSourceEvidence({
        toolId: WEB_FETCH_TOOL_NAME,
        sourceUrl: url,
        title: contentType,
        blockedOrUsed: 'needs_input',
        rawText: result,
      }),
    ])
    const safeResult = redactSourceVerificationText(result)

    return {
      data: {
        bytes,
        code,
        codeText,
        result: safeResult,
        durationMs: Date.now() - start,
        url,
        sourceVerification,
      },
    }
  } catch (error) {
    if (isAbortError(error)) throw error
    const message = `Source verification blocked: ${errorMessage(error)}`
    return blockedToolResult({
      url,
      start,
      message,
      sourceUrl: url,
      title: 'Provider error',
    })
  }
}

function redirectedToolResult({
  url,
  prompt,
  start,
  originalUrl,
  redirectUrl,
  statusCode,
}: {
  readonly url: string
  readonly prompt: string
  readonly start: number
  readonly originalUrl: string
  readonly redirectUrl: string
  readonly statusCode: number
}): ToolResult<WebFetchOutput> {
  const statusText = redirectStatusText(statusCode)
  const message = `REDIRECT DETECTED: The URL redirects to a different host.

Original URL: ${originalUrl}
Redirect URL: ${redirectUrl}
Status: ${statusCode} ${statusText}

To complete your request, I need to fetch content from the redirected URL. Please use WebFetch again with these parameters:
- url: "${redirectUrl}"
- prompt: "${prompt}"`
  const safeMessage = redactSourceVerificationText(message)

  return {
    data: {
      bytes: Buffer.byteLength(safeMessage),
      code: statusCode,
      codeText: statusText,
      result: safeMessage,
      durationMs: Date.now() - start,
      url,
      sourceVerification: buildSourceVerification([
        buildSourceEvidence({
          toolId: WEB_FETCH_TOOL_NAME,
          sourceUrl: redirectUrl,
          title: 'Redirect target',
          blockedOrUsed: 'needs_input',
          rawText: message,
        }),
      ]),
    },
  }
}

function blockedToolResult({
  url,
  start,
  message,
  sourceUrl,
  title,
  code = 0,
  codeText = 'Source Verification Blocked',
}: {
  readonly url: string
  readonly start: number
  readonly message: string
  readonly sourceUrl: string | null
  readonly title: string
  readonly code?: number
  readonly codeText?: string
}): ToolResult<WebFetchOutput> {
  const safeMessage = redactSourceVerificationText(message)
  return {
    data: {
      bytes: Buffer.byteLength(safeMessage),
      code,
      codeText,
      result: safeMessage,
      durationMs: Date.now() - start,
      url,
      sourceVerification: buildSourceVerification([
        buildSourceEvidence({
          toolId: WEB_FETCH_TOOL_NAME,
          sourceUrl,
          title,
          blockedOrUsed: 'blocked',
          rawText: message,
        }),
      ]),
    },
  }
}

function redirectStatusText(statusCode: number): string {
  switch (statusCode) {
    case 301:
      return 'Moved Permanently'
    case 307:
      return 'Temporary Redirect'
    case 308:
      return 'Permanent Redirect'
    default:
      return 'Found'
  }
}
