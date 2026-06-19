import { notifyVscodeFileUpdated } from '../../services/mcp/vscodeSdkMcp.js';
import type { ToolUseContext } from '../../Tool.js';
import type { AssistantMessage } from '../../types/message.js';
import { isENOENT } from '../../utils/errors.js';
import { detectFileEncoding, detectLineEndings, getFileModificationTime, writeTextContent } from '../../utils/file.js';
import { fileHistoryEnabled, fileHistoryTrackEdit } from '../../utils/fileHistory.js';
import { getFsImplementation } from '../../utils/fsOperations.js';
import { expandPath } from '../../utils/path.js';
import type { Out } from './schemas.js';

type SimulatedSedEditResult = {
  readonly data: Out;
};

type SimulatedSedEditContext = Pick<ToolUseContext, 'readFileState' | 'updateFileHistoryState'>;

export async function applySedEdit(simulatedEdit: {
  readonly filePath: string;
  readonly newContent: string;
}, toolUseContext: SimulatedSedEditContext, parentMessage?: AssistantMessage): Promise<SimulatedSedEditResult> {
  const { filePath, newContent } = simulatedEdit;
  const absoluteFilePath = expandPath(filePath);
  const fs = getFsImplementation();
  const encoding = detectFileEncoding(absoluteFilePath);
  let originalContent: string;
  try {
    originalContent = await fs.readFile(absoluteFilePath, { encoding });
  } catch (error) {
    if (isENOENT(error)) {
      return {
        data: {
          stdout: '',
          stderr: `sed: ${filePath}: No such file or directory\nExit code 1`,
          interrupted: false
        }
      };
    }
    throw error;
  }
  if (fileHistoryEnabled() && parentMessage) {
    await fileHistoryTrackEdit(toolUseContext.updateFileHistoryState, absoluteFilePath, parentMessage.uuid);
  }
  const endings = detectLineEndings(absoluteFilePath);
  writeTextContent(absoluteFilePath, newContent, encoding, endings);
  notifyVscodeFileUpdated(absoluteFilePath, originalContent, newContent);
  toolUseContext.readFileState.set(absoluteFilePath, {
    content: newContent,
    timestamp: getFileModificationTime(absoluteFilePath),
    offset: undefined,
    limit: undefined
  });
  return {
    data: {
      stdout: '',
      stderr: '',
      interrupted: false
    }
  };
}
