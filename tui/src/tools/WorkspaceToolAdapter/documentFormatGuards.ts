import type { Tool, ValidationResult } from '../../Tool.js'
import { isWorkspaceInputRecord } from './inputNormalization.js'
import { WORKSPACE_BASH_TOOL_NAME } from './toolNames.js'

const DOCUMENT_DERIVATIVE_PATH_RE = /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)$/iu
const DOCUMENT_FORMAT_PATH_RE = /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)$/iu
const DOCUMENT_FORMAT_COMMAND_RE =
  /\.(?:hwp|hwpx|docx|pdf|xlsx|pptx)(?=$|[\s"'`;|&<>])/iu

export const DOCUMENT_DERIVATIVE_MUTATION_MESSAGE =
  'Document derivatives must be mutated through the document primitive, not raw file tools.'

const WORKSPACE_DOCUMENT_FORMAT_MESSAGE_PREFIX =
  'Document formats must be edited through the document primitive, not'

export function isDocumentDerivativePath(filePath: string): boolean {
  return DOCUMENT_DERIVATIVE_PATH_RE.test(filePath)
}

export function documentDerivativeMutationValidation(
  filePath: string,
): ValidationResult | null {
  if (!isDocumentDerivativePath(filePath)) return null
  return {
    result: false,
    message: DOCUMENT_DERIVATIVE_MUTATION_MESSAGE,
    errorCode: 20,
  }
}

export function documentPathFromInput(input: unknown): string | undefined {
  if (!isWorkspaceInputRecord(input)) return undefined
  return typeof input.file_path === 'string' ? input.file_path : undefined
}

export function workspaceDocumentFormatPathValidation(
  toolName: string,
  input: unknown,
): ValidationResult | null {
  const filePath = documentPathFromInput(input)
  if (filePath === undefined || !DOCUMENT_FORMAT_PATH_RE.test(filePath)) {
    return null
  }
  return {
    result: false,
    message: `${WORKSPACE_DOCUMENT_FORMAT_MESSAGE_PREFIX} ${toolName}.`,
    errorCode: 1,
  }
}

export function workspaceBashDocumentFormatValidation(
  source: Tool,
  input: unknown,
): ValidationResult | null {
  if (!isWorkspaceInputRecord(input)) return null
  if (input.dangerouslyDisableSandbox === true) {
    return {
      result: false,
      message:
        'workspace_bash does not allow dangerouslyDisableSandbox. Use the normal permission and sandbox boundary.',
      errorCode: 2,
    }
  }
  const command = typeof input.command === 'string' ? input.command : ''
  if (DOCUMENT_FORMAT_COMMAND_RE.test(command) && !source.isReadOnly(input)) {
    return {
      result: false,
      message: `${WORKSPACE_DOCUMENT_FORMAT_MESSAGE_PREFIX} ${WORKSPACE_BASH_TOOL_NAME}.`,
      errorCode: 1,
    }
  }
  return null
}
