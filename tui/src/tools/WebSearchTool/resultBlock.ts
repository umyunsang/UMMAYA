import { jsonStringify } from '../../utils/slowOperations.js'
import {
  formatSourceVerifiedToolResult,
  redactSourceVerificationText,
  redactSourceVerificationUrl,
} from '../WebFetchTool/sourceVerification.js'
import type { Output } from './schemas.js'

export function mapWebSearchResultToToolResultBlockParam(
  output: Output,
  toolUseID: string,
): {
  readonly tool_use_id: string
  readonly type: 'tool_result'
  readonly content: string
} {
  const { query, results, sourceVerification } = output
  let formattedOutput = `Web search results for query: "${redactSourceVerificationText(query)}"\n\n`

  for (const result of results) {
    if (typeof result === 'string') {
      formattedOutput += `${redactSourceVerificationText(result)}\n\n`
      continue
    }
    if (result.content.length > 0) {
      const safeContent = result.content.map(hit => ({
        title: redactSourceVerificationText(hit.title),
        url: redactSourceVerificationUrl(hit.url) ?? 'none',
      }))
      formattedOutput += `Links: ${jsonStringify(safeContent)}\n\n`
    } else {
      formattedOutput += 'No links found.\n\n'
    }
  }

  formattedOutput +=
    '\nREMINDER: You MUST include the sources above in your response to the user using markdown hyperlinks.'

  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: formatSourceVerifiedToolResult({
      result: formattedOutput.trim(),
      sourceVerification,
    }),
  }
}
