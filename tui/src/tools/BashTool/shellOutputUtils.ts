import type {
  Base64ImageSource,
  ToolResultBlockParam,
} from '@anthropic-ai/sdk/resources/index.mjs'
import { readFile, stat } from 'fs/promises'
import { getOriginalCwd } from '../../bootstrap/state.js'
import { maybeResizeAndDownsampleImageBuffer } from '../../utils/imageResizer.js'

export function stripEmptyLines(content: string): string {
  const lines = content.split('\n')
  let startIndex = 0
  while (startIndex < lines.length && lines[startIndex]?.trim() === '') {
    startIndex++
  }
  let endIndex = lines.length - 1
  while (endIndex >= 0 && lines[endIndex]?.trim() === '') {
    endIndex--
  }
  if (startIndex > endIndex) return ''
  return lines.slice(startIndex, endIndex + 1).join('\n')
}

export function isImageOutput(content: string): boolean {
  return /^data:image\/[a-z0-9.+_-]+;base64,/i.test(content)
}

const DATA_URI_RE = /^data:([^;]+);base64,(.+)$/

function parseDataUri(
  value: string,
): { readonly mediaType: string; readonly data: string } | null {
  const match = value.trim().match(DATA_URI_RE)
  if (!match || !match[1] || !match[2]) return null
  return { mediaType: match[1], data: match[2] }
}

export function buildImageToolResult(
  stdout: string,
  toolUseID: string,
): ToolResultBlockParam | null {
  const parsed = parseDataUri(stdout)
  if (!parsed) return null
  return {
    tool_use_id: toolUseID,
    type: 'tool_result',
    content: [
      {
        type: 'image',
        source: {
          type: 'base64',
          media_type: parsed.mediaType as Base64ImageSource['media_type'],
          data: parsed.data,
        },
      },
    ],
  }
}

const MAX_IMAGE_FILE_SIZE = 20 * 1024 * 1024

export async function resizeShellImageOutput(
  stdout: string,
  outputFilePath: string | undefined,
  outputFileSize: number | undefined,
): Promise<string | null> {
  let source = stdout
  if (outputFilePath) {
    const size = outputFileSize ?? (await stat(outputFilePath)).size
    if (size > MAX_IMAGE_FILE_SIZE) return null
    source = await readFile(outputFilePath, 'utf8')
  }
  const parsed = parseDataUri(source)
  if (!parsed) return null
  const buffer = Buffer.from(parsed.data, 'base64')
  const extension = parsed.mediaType.split('/')[1] || 'png'
  const resized = await maybeResizeAndDownsampleImageBuffer(
    buffer,
    buffer.length,
    extension,
  )
  return `data:image/${resized.mediaType};base64,${resized.buffer.toString('base64')}`
}

export const stdErrAppendShellResetMessage = (stderr: string): string =>
  `${stderr.trim()}\nShell cwd was reset to ${getOriginalCwd()}`
