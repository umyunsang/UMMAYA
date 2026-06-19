import { dirname, sep } from 'path'
import { logEvent } from 'src/services/analytics/index.js'
import { getFeatureValue_CACHED_MAY_BE_STALE } from '../../services/analytics/growthbook.js'
import { diagnosticTracker } from '../../services/diagnosticTracking.js'
import { clearDeliveredDiagnosticsForFile } from '../../services/lsp/LSPDiagnosticRegistry.js'
import { notifyVscodeFileUpdated } from '../../services/mcp/vscodeSdkMcp.js'
import {
  activateConditionalSkillsForPaths,
  addSkillDirectories,
  discoverSkillDirsForPaths,
} from '../../skills/loadSkillsDir.js'
import type { ToolResult, ToolUseContext } from '../../Tool.js'
import type { AssistantMessage } from '../../types/message.js'
import { getCwd } from '../../utils/cwd.js'
import { logForDebugging } from '../../utils/debug.js'
import { countLinesChanged } from '../../utils/diff.js'
import { isEnvTruthy } from '../../utils/envUtils.js'
import { isENOENT } from '../../utils/errors.js'
import { getFileModificationTime, writeTextContent } from '../../utils/file.js'
import { logFileOperation } from '../../utils/fileOperationAnalytics.js'
import {
  type LineEndingType,
  readFileSyncWithMetadata,
} from '../../utils/fileRead.js'
import { getFsImplementation } from '../../utils/fsOperations.js'
import {
  fetchSingleFileGitDiff,
  type ToolUseDiff,
} from '../../utils/gitDiff.js'
import { logError } from '../../utils/log.js'
import { expandPath } from '../../utils/path.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'
import { FILE_UNEXPECTEDLY_MODIFIED_ERROR } from './constants.js'
import type { FileEditInput, FileEditOutput } from './types.js'
import {
  findActualString,
  getPatchForEdit,
  preserveQuoteStyle,
} from './utils.js'

export async function callFileEditTool(
  input: FileEditInput,
  {
    readFileState,
    userModified,
    updateFileHistoryState,
    dynamicSkillDirTriggers,
  }: ToolUseContext,
  parentMessage: AssistantMessage,
): Promise<ToolResult<FileEditOutput>> {
  const { file_path, old_string, new_string, replace_all = false } = input
  const fs = getFsImplementation()
  const absoluteFilePath = expandPath(file_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(absoluteFilePath)
  if (documentValidation !== null) throw new Error(documentValidation.message)

  const cwd = getCwd()
  if (!isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)) {
    const newSkillDirs = await discoverSkillDirsForPaths(
      [absoluteFilePath],
      cwd,
    )
    if (newSkillDirs.length > 0) {
      for (const dir of newSkillDirs) {
        dynamicSkillDirTriggers?.add(dir)
      }
      addSkillDirectories(newSkillDirs).catch(() => {})
    }

    activateConditionalSkillsForPaths([absoluteFilePath], cwd)
  }

  await diagnosticTracker.beforeFileEdited(absoluteFilePath)

  await fs.mkdir(dirname(absoluteFilePath))
  const { fileHistoryEnabled, fileHistoryTrackEdit } = await import(
    '../../utils/fileHistory.js'
  )
  if (fileHistoryEnabled()) {
    await fileHistoryTrackEdit(
      updateFileHistoryState,
      absoluteFilePath,
      parentMessage.uuid,
    )
  }

  const {
    content: originalFileContents,
    fileExists,
    encoding,
    lineEndings: endings,
  } = readFileForEdit(absoluteFilePath)

  if (fileExists) {
    const lastWriteTime = getFileModificationTime(absoluteFilePath)
    const lastRead = readFileState.get(absoluteFilePath)
    if (!lastRead || lastWriteTime > lastRead.timestamp) {
      const isFullRead =
        lastRead &&
        lastRead.offset === undefined &&
        lastRead.limit === undefined
      const contentUnchanged =
        isFullRead && originalFileContents === lastRead.content
      if (!contentUnchanged) {
        throw new Error(FILE_UNEXPECTEDLY_MODIFIED_ERROR)
      }
    }
  }

  const actualOldString =
    findActualString(originalFileContents, old_string) || old_string
  const actualNewString = preserveQuoteStyle(
    old_string,
    actualOldString,
    new_string,
  )

  const { patch, updatedFile } = getPatchForEdit({
    filePath: absoluteFilePath,
    fileContents: originalFileContents,
    oldString: actualOldString,
    newString: actualNewString,
    replaceAll: replace_all,
  })

  writeTextContent(absoluteFilePath, updatedFile, encoding, endings)

  const { getLspServerManager } = await import('../../services/lsp/manager.js')
  const lspManager = getLspServerManager()
  if (lspManager) {
    clearDeliveredDiagnosticsForFile(`file://${absoluteFilePath}`)
    lspManager
      .changeFile(absoluteFilePath, updatedFile)
      .catch((err: Error) => {
        logForDebugging(
          `LSP: Failed to notify server of file change for ${absoluteFilePath}: ${err.message}`,
        )
        logError(err)
      })
    lspManager.saveFile(absoluteFilePath).catch((err: Error) => {
      logForDebugging(
        `LSP: Failed to notify server of file save for ${absoluteFilePath}: ${err.message}`,
      )
      logError(err)
    })
  }

  notifyVscodeFileUpdated(absoluteFilePath, originalFileContents, updatedFile)

  readFileState.set(absoluteFilePath, {
    content: updatedFile,
    timestamp: getFileModificationTime(absoluteFilePath),
    offset: undefined,
    limit: undefined,
  })

  if (absoluteFilePath.endsWith(`${sep}CLAUDE.md`)) {
    logEvent('tengu_write_claudemd', {})
  }
  countLinesChanged(patch)

  logFileOperation({
    operation: 'edit',
    tool: 'FileEditTool',
    filePath: absoluteFilePath,
  })

  logEvent('tengu_edit_string_lengths', {
    oldStringBytes: Buffer.byteLength(old_string, 'utf8'),
    newStringBytes: Buffer.byteLength(new_string, 'utf8'),
    replaceAll: replace_all,
  })

  let gitDiff: ToolUseDiff | undefined
  if (
    isEnvTruthy(process.env.CLAUDE_CODE_REMOTE) &&
    getFeatureValue_CACHED_MAY_BE_STALE('tengu_quartz_lantern', false)
  ) {
    const startTime = Date.now()
    const diff = await fetchSingleFileGitDiff(absoluteFilePath)
    if (diff) gitDiff = diff
    logEvent('tengu_tool_use_diff_computed', {
      isEditTool: true,
      durationMs: Date.now() - startTime,
      hasDiff: !!diff,
    })
  }

  const data: FileEditOutput = {
    filePath: file_path,
    oldString: actualOldString,
    newString: new_string,
    originalFile: originalFileContents,
    structuredPatch: patch,
    userModified: userModified ?? false,
    replaceAll: replace_all,
    ...(gitDiff && { gitDiff }),
  }
  return { data }
}

function readFileForEdit(absoluteFilePath: string): {
  content: string
  fileExists: boolean
  encoding: BufferEncoding
  lineEndings: LineEndingType
} {
  try {
    const meta = readFileSyncWithMetadata(absoluteFilePath)
    return {
      content: meta.content,
      fileExists: true,
      encoding: meta.encoding,
      lineEndings: meta.lineEndings,
    }
  } catch (e) {
    if (isENOENT(e)) {
      return {
        content: '',
        fileExists: false,
        encoding: 'utf8',
        lineEndings: 'LF',
      }
    }
    throw e
  }
}
