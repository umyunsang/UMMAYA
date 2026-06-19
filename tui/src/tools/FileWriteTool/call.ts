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
import { countLinesChanged, getPatchForDisplay } from '../../utils/diff.js'
import { isEnvTruthy } from '../../utils/envUtils.js'
import { isENOENT } from '../../utils/errors.js'
import { getFileModificationTime, writeTextContent } from '../../utils/file.js'
import { logFileOperation } from '../../utils/fileOperationAnalytics.js'
import { readFileSyncWithMetadata } from '../../utils/fileRead.js'
import { getFsImplementation } from '../../utils/fsOperations.js'
import {
  fetchSingleFileGitDiff,
  type ToolUseDiff,
} from '../../utils/gitDiff.js'
import { logError } from '../../utils/log.js'
import { expandPath } from '../../utils/path.js'
import { documentDerivativeMutationValidationForResolvedTarget } from '../DocumentPrimitive/documentMutationGuard.js'
import { FILE_UNEXPECTEDLY_MODIFIED_ERROR } from '../FileEditTool/constants.js'
import type { FileWriteInput } from './validateInput.js'

type FileWritePatch = ReturnType<typeof getPatchForDisplay>

type FileWriteUpdateData = {
  type: 'update'
  filePath: string
  content: string
  structuredPatch: FileWritePatch
  originalFile: string
  gitDiff?: ToolUseDiff
}

type FileWriteCreateData = {
  type: 'create'
  filePath: string
  content: string
  structuredPatch: FileWritePatch
  originalFile: null
  gitDiff?: ToolUseDiff
}

type FileWriteData = FileWriteUpdateData | FileWriteCreateData

export async function callFileWriteTool(
  { file_path, content }: FileWriteInput,
  {
    readFileState,
    updateFileHistoryState,
    dynamicSkillDirTriggers,
  }: ToolUseContext,
  parentMessage: AssistantMessage,
): Promise<ToolResult<FileWriteData>> {
  const fullFilePath = expandPath(file_path)
  const documentValidation =
    documentDerivativeMutationValidationForResolvedTarget(fullFilePath)
  if (documentValidation !== null) throw new Error(documentValidation.message)

  const dir = dirname(fullFilePath)

  const cwd = getCwd()
  const newSkillDirs = await discoverSkillDirsForPaths([fullFilePath], cwd)
  if (newSkillDirs.length > 0) {
    for (const dir of newSkillDirs) {
      dynamicSkillDirTriggers?.add(dir)
    }
    addSkillDirectories(newSkillDirs).catch(() => {})
  }

  activateConditionalSkillsForPaths([fullFilePath], cwd)

  await diagnosticTracker.beforeFileEdited(fullFilePath)

  await getFsImplementation().mkdir(dir)
  const { fileHistoryEnabled, fileHistoryTrackEdit } = await import(
    '../../utils/fileHistory.js'
  )
  if (fileHistoryEnabled()) {
    await fileHistoryTrackEdit(
      updateFileHistoryState,
      fullFilePath,
      parentMessage.uuid,
    )
  }

  let meta: ReturnType<typeof readFileSyncWithMetadata> | null
  try {
    meta = readFileSyncWithMetadata(fullFilePath)
  } catch (e) {
    if (isENOENT(e)) {
      meta = null
    } else {
      throw e
    }
  }

  if (meta !== null) {
    const lastWriteTime = getFileModificationTime(fullFilePath)
    const lastRead = readFileState.get(fullFilePath)
    if (!lastRead || lastWriteTime > lastRead.timestamp) {
      const isFullRead =
        lastRead &&
        lastRead.offset === undefined &&
        lastRead.limit === undefined
      if (!isFullRead || meta.content !== lastRead.content) {
        throw new Error(FILE_UNEXPECTEDLY_MODIFIED_ERROR)
      }
    }
  }

  const enc = meta?.encoding ?? 'utf8'
  const oldContent = meta?.content ?? null
  writeTextContent(fullFilePath, content, enc, 'LF')

  const { getLspServerManager } = await import('../../services/lsp/manager.js')
  const lspManager = getLspServerManager()
  if (lspManager) {
    clearDeliveredDiagnosticsForFile(`file://${fullFilePath}`)
    lspManager.changeFile(fullFilePath, content).catch((err: Error) => {
      logForDebugging(
        `LSP: Failed to notify server of file change for ${fullFilePath}: ${err.message}`,
      )
      logError(err)
    })
    lspManager.saveFile(fullFilePath).catch((err: Error) => {
      logForDebugging(
        `LSP: Failed to notify server of file save for ${fullFilePath}: ${err.message}`,
      )
      logError(err)
    })
  }

  notifyVscodeFileUpdated(fullFilePath, oldContent, content)

  readFileState.set(fullFilePath, {
    content,
    timestamp: getFileModificationTime(fullFilePath),
    offset: undefined,
    limit: undefined,
  })

  if (fullFilePath.endsWith(`${sep}CLAUDE.md`)) {
    logEvent('tengu_write_claudemd', {})
  }

  let gitDiff: ToolUseDiff | undefined
  if (
    isEnvTruthy(process.env.CLAUDE_CODE_REMOTE) &&
    getFeatureValue_CACHED_MAY_BE_STALE('tengu_quartz_lantern', false)
  ) {
    const startTime = Date.now()
    const diff = await fetchSingleFileGitDiff(fullFilePath)
    if (diff) gitDiff = diff
    logEvent('tengu_tool_use_diff_computed', {
      isWriteTool: true,
      durationMs: Date.now() - startTime,
      hasDiff: !!diff,
    })
  }

  if (oldContent) {
    const patch = getPatchForDisplay({
      filePath: file_path,
      fileContents: oldContent,
      edits: [
        {
          old_string: oldContent,
          new_string: content,
          replace_all: false,
        },
      ],
    })

    const data: FileWriteUpdateData = {
      type: 'update',
      filePath: file_path,
      content,
      structuredPatch: patch,
      originalFile: oldContent,
      ...(gitDiff && { gitDiff }),
    }
    countLinesChanged(patch)

    logFileOperation({
      operation: 'write',
      tool: 'FileWriteTool',
      filePath: fullFilePath,
      type: 'update',
    })

    return { data }
  }

  const data: FileWriteCreateData = {
    type: 'create',
    filePath: file_path,
    content,
    structuredPatch: [],
    originalFile: null,
    ...(gitDiff && { gitDiff }),
  }

  countLinesChanged([], content)

  logFileOperation({
    operation: 'write',
    tool: 'FileWriteTool',
    filePath: fullFilePath,
    type: 'create',
  })

  return { data }
}
