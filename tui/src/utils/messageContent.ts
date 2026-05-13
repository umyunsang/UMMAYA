import type { ContentBlockParam } from 'src/sdk-compat.js'
import type { DeepImmutable } from 'src/types/utils.js'
import { COMMAND_ARGS_TAG, COMMAND_NAME_TAG } from '../constants/xml.js'
import type {
  Message,
  NormalizedMessage,
  UserMessage,
} from '../types/message.js'
import { stripIdeContextTags } from './displayTags.js'
import { extractTag, extractTextContent } from './messageText.js'

export function getAssistantMessageText(message: Message): string | null {
  if (message.type !== 'assistant') {
    return null
  }

  if (Array.isArray(message.message.content)) {
    return (
      message.message.content
        .filter(block => block.type === 'text')
        .map(block => (block.type === 'text' ? block.text : ''))
        .join('\n')
        .trim() || null
    )
  }
  return null
}

export function getUserMessageText(
  message: Message | NormalizedMessage,
): string | null {
  if (message.type !== 'user') {
    return null
  }

  return getContentText(message.message.content)
}

export function textForResubmit(
  msg: UserMessage,
): { text: string; mode: 'bash' | 'prompt' } | null {
  const content = getUserMessageText(msg)
  if (content === null) return null
  const bash = extractTag(content, 'bash-input')
  if (bash) return { text: bash, mode: 'bash' }
  const cmd = extractTag(content, COMMAND_NAME_TAG)
  if (cmd) {
    const args = extractTag(content, COMMAND_ARGS_TAG) ?? ''
    return { text: `${cmd} ${args}`, mode: 'prompt' }
  }
  return { text: stripIdeContextTags(content), mode: 'prompt' }
}

export function getContentText(
  content: string | DeepImmutable<Array<ContentBlockParam>>,
): string | null {
  if (typeof content === 'string') {
    return content
  }
  if (Array.isArray(content)) {
    return extractTextContent(content, '\n').trim() || null
  }
  return null
}
