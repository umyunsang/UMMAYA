import { checkTeamMemSecrets } from '../../services/teamMemorySync/teamMemSecretGuard.js'
import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { getCwd } from '../../utils/cwd.js'
import { isENOENT } from '../../utils/errors.js'
import {
  FILE_NOT_FOUND_CWD_NOTE,
  findSimilarFile,
  getFileModificationTime,
  suggestPathUnderCwd,
} from '../../utils/file.js'
import { formatFileSize } from '../../utils/format.js'
import { getFsImplementation } from '../../utils/fsOperations.js'
import { expandPath } from '../../utils/path.js'
import { matchingRuleForInput } from '../../utils/permissions/filesystem.js'
import { validateInputForSettingsFileEdit } from '../../utils/settings/validateEditTool.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'
import { NOTEBOOK_EDIT_TOOL_NAME } from '../NotebookEditTool/constants.js'
import type { FileEditInput } from './types.js'
import { findActualString } from './utils.js'

const MAX_EDIT_FILE_SIZE = 1024 * 1024 * 1024

export async function validateFileEditInput(
  input: FileEditInput,
  toolUseContext: ToolUseContext,
): Promise<ValidationResult> {
  const { file_path, old_string, new_string, replace_all = false } = input
  const fullFilePath = expandPath(file_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(fullFilePath)
  if (documentValidation !== null) return documentValidation

  const secretError = checkTeamMemSecrets(fullFilePath, new_string)
  if (secretError) {
    return { result: false, message: secretError, errorCode: 0 }
  }
  if (old_string === new_string) {
    return {
      result: false,
      message:
        'No changes to make: old_string and new_string are exactly the same.',
      errorCode: 1,
    }
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
      errorCode: 2,
    }
  }

  if (fullFilePath.startsWith('\\\\') || fullFilePath.startsWith('//')) {
    return { result: true }
  }

  const fs = getFsImplementation()
  try {
    const { size } = await fs.stat(fullFilePath)
    if (size > MAX_EDIT_FILE_SIZE) {
      return {
        result: false,
        message: `File is too large to edit (${formatFileSize(size)}). Maximum editable file size is ${formatFileSize(MAX_EDIT_FILE_SIZE)}.`,
        errorCode: 10,
      }
    }
  } catch (e) {
    if (!isENOENT(e)) {
      throw e
    }
  }

  let fileContent: string | null
  try {
    const fileBuffer = await fs.readFileBytes(fullFilePath)
    const encoding: BufferEncoding =
      fileBuffer.length >= 2 &&
      fileBuffer[0] === 0xff &&
      fileBuffer[1] === 0xfe
        ? 'utf16le'
        : 'utf8'
    fileContent = fileBuffer.toString(encoding).replaceAll('\r\n', '\n')
  } catch (e) {
    if (isENOENT(e)) {
      fileContent = null
    } else {
      throw e
    }
  }

  if (fileContent === null) {
    if (old_string === '') {
      return { result: true }
    }
    const similarFilename = findSimilarFile(fullFilePath)
    const cwdSuggestion = await suggestPathUnderCwd(fullFilePath)
    let message = `File does not exist. ${FILE_NOT_FOUND_CWD_NOTE} ${getCwd()}.`

    if (cwdSuggestion) {
      message += ` Did you mean ${cwdSuggestion}?`
    } else if (similarFilename) {
      message += ` Did you mean ${similarFilename}?`
    }

    return {
      result: false,
      message,
      errorCode: 4,
    }
  }

  if (old_string === '') {
    if (fileContent.trim() !== '') {
      return {
        result: false,
        message: 'Cannot create new file - file already exists.',
        errorCode: 3,
      }
    }

    return { result: true }
  }

  if (fullFilePath.endsWith('.ipynb')) {
    return {
      result: false,
      message: `File is a Jupyter Notebook. Use the ${NOTEBOOK_EDIT_TOOL_NAME} to edit this file.`,
      errorCode: 5,
    }
  }

  const readTimestamp = toolUseContext.readFileState.get(fullFilePath)
  if (!readTimestamp || readTimestamp.isPartialView) {
    return {
      result: false,
      message: 'File has not been read yet. Read it first before writing to it.',
      errorCode: 6,
    }
  }

  const lastWriteTime = getFileModificationTime(fullFilePath)
  if (lastWriteTime > readTimestamp.timestamp) {
    const isFullRead =
      readTimestamp.offset === undefined && readTimestamp.limit === undefined
    if (!isFullRead || fileContent !== readTimestamp.content) {
      return {
        result: false,
        message:
          'File has been modified since read, either by the user or by a linter. Read it again before attempting to write it.',
        errorCode: 7,
      }
    }
  }

  const actualOldString = findActualString(fileContent, old_string)
  if (!actualOldString) {
    return {
      result: false,
      message: `String to replace not found in file.\nString: ${old_string}`,
      errorCode: 8,
    }
  }

  const matches = fileContent.split(actualOldString).length - 1
  if (matches > 1 && !replace_all) {
    return {
      result: false,
      message: `Found ${matches} matches of the string to replace, but replace_all is false. To replace all occurrences, set replace_all to true. To replace only one occurrence, please provide more context to uniquely identify the instance.\nString: ${old_string}`,
      errorCode: 9,
    }
  }

  const settingsValidationResult = validateInputForSettingsFileEdit(
    fullFilePath,
    fileContent,
    () =>
      replace_all
        ? fileContent.replaceAll(actualOldString, new_string)
        : fileContent.replace(actualOldString, new_string),
  )

  if (settingsValidationResult !== null) {
    return settingsValidationResult
  }

  return { result: true }
}
