import { readFile } from 'node:fs/promises'
import { getWorkspaceTools } from '../../src/tools/WorkspaceToolAdapter/WorkspaceToolAdapter.js'

const WORKSPACE_ADAPTER_SOURCE_ROOT = 'src/tools/WorkspaceToolAdapter'

export function toolByName(name: string) {
  const tool = getWorkspaceTools().find(candidate => candidate.name === name)
  if (!tool) throw new Error(`Missing workspace tool: ${name}`)
  return tool
}

export async function workspaceAdapterSource(fileName: string): Promise<string> {
  return readFile(`${WORKSPACE_ADAPTER_SOURCE_ROOT}/${fileName}`, 'utf8')
}

export function pureLoc(source: string): number {
  return source
    .split(/\r?\n/u)
    .filter(line => {
      const trimmed = line.trim()
      return trimmed.length > 0 && !trimmed.startsWith('//')
    }).length
}
