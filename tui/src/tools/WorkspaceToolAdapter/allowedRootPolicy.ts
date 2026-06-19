import { relative } from 'node:path'
import type { ToolUseContext, ValidationResult } from '../../Tool.js'
import { getCwd } from '../../utils/cwd.js'
import { getPathsForPermissionCheck } from '../../utils/fsOperations.js'
import { expandPath } from '../../utils/path.js'
import type { PermissionDecision } from '../../utils/permissions/PermissionResult.js'
import {
  inferredDownloadsPath,
  latestUserTextFromWorkspaceContext,
} from './inputNormalization.js'

export const WORKSPACE_PATH_ESCAPE_MESSAGE =
  'Path resolves outside the allowed workspace roots. Re-select the folder or use an explicit document primitive flow.'

function pathIsInsideRoot(candidate: string, root: string): boolean {
  const rel = relative(root, candidate)
  return rel === '' || (!rel.startsWith('..') && !rel.startsWith('/'))
}

function resolvedForms(path: string): readonly string[] {
  return getPathsForPermissionCheck(expandPath(path))
}

function allowedWorkspaceRoots(context: ToolUseContext): readonly string[] {
  const roots = new Set<string>(resolvedForms(getCwd()))
  const appState = context.getAppState()
  for (const directory of appState.toolPermissionContext.additionalWorkingDirectories.values()) {
    for (const resolved of resolvedForms(directory.path)) {
      roots.add(resolved)
    }
  }
  const downloadsPath = inferredDownloadsPath(
    latestUserTextFromWorkspaceContext(context),
  )
  if (downloadsPath !== undefined) {
    for (const resolved of resolvedForms(downloadsPath)) {
      roots.add(resolved)
    }
  }
  return Array.from(roots)
}

export function validateWorkspacePathInsideAllowedRoots(
  path: string,
  context: ToolUseContext,
): ValidationResult {
  if (typeof context.getAppState !== 'function') return { result: true }
  const targetForms = resolvedForms(path)
  const rootForms = allowedWorkspaceRoots(context)
  const inside = targetForms.every(target =>
    rootForms.some(root => pathIsInsideRoot(target, root)),
  )
  if (inside) return { result: true }
  return {
    result: false,
    message: WORKSPACE_PATH_ESCAPE_MESSAGE,
    errorCode: 20,
  }
}

export function workspaceReadSearchDecision(
  path: string,
  input: Record<string, unknown>,
  context: ToolUseContext,
): PermissionDecision {
  const validation = validateWorkspacePathInsideAllowedRoots(path, context)
  if (!validation.result) {
    return {
      behavior: 'deny',
      message: validation.message,
      decisionReason: {
        type: 'workingDir',
        reason: 'Path resolves outside allowed workspace roots',
      },
    }
  }
  return {
    behavior: 'allow',
    updatedInput: input,
    decisionReason: {
      type: 'mode',
      mode: 'default',
    },
  }
}
