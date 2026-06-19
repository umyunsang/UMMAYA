import type { Tool } from '../../Tool.js'
import { BashTool } from '../BashTool/BashTool.js'
import { FileEditTool } from '../FileEditTool/FileEditTool.js'
import { FileReadTool } from '../FileReadTool/FileReadTool.js'
import { FileWriteTool } from '../FileWriteTool/FileWriteTool.js'
import { GlobTool } from '../GlobTool/GlobTool.js'
import { GrepTool } from '../GrepTool/GrepTool.js'
import { buildWorkspaceTool, type WorkspaceToolSpec } from './toolDefFactory.js'
import {
  WORKSPACE_BASH_TOOL_NAME,
  WORKSPACE_EDIT_TOOL_NAME,
  WORKSPACE_GLOB_TOOL_NAME,
  WORKSPACE_GREP_TOOL_NAME,
  WORKSPACE_READ_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
} from './toolNames.js'

export {
  WORKSPACE_BASH_TOOL_NAME,
  WORKSPACE_EDIT_TOOL_NAME,
  WORKSPACE_GLOB_TOOL_NAME,
  WORKSPACE_GREP_TOOL_NAME,
  WORKSPACE_READ_TOOL_NAME,
  WORKSPACE_WRITE_TOOL_NAME,
} from './toolNames.js'

const WORKSPACE_TOOL_SPECS: readonly WorkspaceToolSpec[] = [
  {
    name: WORKSPACE_GLOB_TOOL_NAME,
    source: () => GlobTool,
    searchHint: 'find local files by name pattern',
    alwaysLoad: true,
    supportsUserFolderHints: true,
    enforcesAllowedRoots: true,
    readSearchDefaultAllowed: true,
  },
  {
    name: WORKSPACE_GREP_TOOL_NAME,
    source: () => GrepTool,
    searchHint: 'search local file contents',
    alwaysLoad: true,
    supportsUserFolderHints: true,
    enforcesAllowedRoots: true,
    readSearchDefaultAllowed: true,
  },
  {
    name: WORKSPACE_READ_TOOL_NAME,
    source: () => FileReadTool,
    searchHint: 'read local text files',
    alwaysLoad: true,
    enforcesAllowedRoots: true,
    readSearchDefaultAllowed: true,
  },
  {
    name: WORKSPACE_WRITE_TOOL_NAME,
    source: () => FileWriteTool,
    searchHint:
      'create or overwrite local text files with visible permission boundary and blocked state',
    blocksDocumentFormats: true,
    enforcesAllowedRoots: true,
  },
  {
    name: WORKSPACE_EDIT_TOOL_NAME,
    source: () => FileEditTool,
    searchHint: 'modify local text files in place',
    blocksDocumentFormats: true,
    enforcesAllowedRoots: true,
  },
  {
    name: WORKSPACE_BASH_TOOL_NAME,
    source: () => BashTool,
    searchHint:
      'run local shell commands with visible permission boundary and blocked state',
  },
]

export function getWorkspaceTools(): readonly Tool[] {
  return WORKSPACE_TOOL_SPECS.map(buildWorkspaceTool)
}
