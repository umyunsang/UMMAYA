import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { checkTeamMemSecrets } from '../../services/teamMemorySync/teamMemSecretGuard.js'
import { isENOENT } from '../../utils/errors.js'
import { getFsImplementation } from '../../utils/fsOperations.js'
import { expandPath } from '../../utils/path.js'
import { matchingRuleForInput } from '../../utils/permissions/filesystem.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'

export type FileWriteInput = {
  file_path: string
  content: string
}

export async function validateFileWriteInput(
  { file_path, content }: FileWriteInput,
  toolUseContext: ToolUseContext,
): Promise<ValidationResult> {
  const fullFilePath = expandPath(file_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(fullFilePath)
  if (documentValidation !== null) return documentValidation

  const secretError = checkTeamMemSecrets(fullFilePath, content)
  if (secretError) {
    return { result: false, message: secretError, errorCode: 0 }
  }

  const appState = toolUseContext.getAppState()
  const denyRule = matchingRuleForInput(
    fullFilePath,
    appState.toolPermissionContext,
    'edit',
    'deny',
  )
  if (denyRule !== null) {
    return {
      result: false,
      message:
        'File is in a directory that is denied by your permission settings.',
      errorCode: 1,
    }
  }

  if (fullFilePath.startsWith('\\\\') || fullFilePath.startsWith('//')) {
    return { result: true }
  }

  const fs = getFsImplementation()
  let fileMtimeMs: number
  try {
    const fileStat = await fs.stat(fullFilePath)
    fileMtimeMs = fileStat.mtimeMs
  } catch (e) {
    if (isENOENT(e)) {
      return { result: true }
    }
    throw e
  }

  const readTimestamp = toolUseContext.readFileState.get(fullFilePath)
  if (!readTimestamp || readTimestamp.isPartialView) {
    return {
      result: false,
      message: 'File has not been read yet. Read it first before writing to it.',
      errorCode: 2,
    }
  }

  const lastWriteTime = Math.floor(fileMtimeMs)
  if (lastWriteTime > readTimestamp.timestamp) {
    return {
      result: false,
      message:
        'File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.',
      errorCode: 3,
    }
  }

  return { result: true }
}
