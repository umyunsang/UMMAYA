// SPDX-License-Identifier: Apache-2.0

import { createHash } from 'node:crypto'
import { appendFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { logForDebugging } from '../../utils/debug.js'

type RouteDiagnosticValue = string | number | boolean | null | string[]

type RouteDiagnosticPayload = Record<string, RouteDiagnosticValue>

const ROUTE_ROOT_TOOL_NAMES = new Set(['locate', 'find', 'check', 'send', 'document'])

export function hashRouteDiagnosticText(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex')
}

export function appendRouteDiagnostic(
  event: string,
  payload: RouteDiagnosticPayload,
): void {
  const path = process.env.UMMAYA_TUI_ROUTE_DIAGNOSTIC_FILE
  if (!path) return

  const record = {
    ts: new Date().toISOString(),
    event,
    ...payload,
  }
  try {
    mkdirSync(dirname(path), { recursive: true })
    appendFileSync(path, `${JSON.stringify(record)}\n`, 'utf8')
  } catch (error) {
    logForDebugging(`route diagnostics write failed: ${String(error)}`)
  }
}

export function appendRoutePermissionPromptDiagnostic(payload: {
  toolName: string
  input: Record<string, unknown>
  toolUseID: string
  messageID: string
  queryChainID: string | null
  queryDepth: number | null
  permissionMode: string | null
}): void {
  const toolSurface = routeToolSurface(payload.toolName)
  if (toolSurface === null) return
  appendRouteDiagnostic('route_tool_permission', {
    tool_name: payload.toolName,
    tool_surface: toolSurface,
    target_tool_id: routeTargetToolID(payload.input),
    tool_use_id: payload.toolUseID,
    message_id: payload.messageID,
    request_id: null,
    query_chain_id: payload.queryChainID,
    query_depth: payload.queryDepth,
    permission_mode: payload.permissionMode,
    permission_behavior: 'ask',
    result_status: 'prompted',
  })
}

function routeToolSurface(toolName: string): string | null {
  if (ROUTE_ROOT_TOOL_NAMES.has(toolName)) return 'root_primitive'
  if (/^[a-z][a-z0-9_]*$/u.test(toolName) && toolName.includes('_')) {
    return 'concrete_adapter'
  }
  return null
}

function routeTargetToolID(input: Record<string, unknown>): string | null {
  const toolID = input.tool_id
  return typeof toolID === 'string' && toolID.length > 0 ? toolID : null
}
