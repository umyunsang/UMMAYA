export const ROOT_PRIMITIVE_TOOL_IDS = new Set([
  'find',
  'locate',
  'check',
  'send',
])

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

export function isRootPrimitiveToolId(value: unknown): value is string {
  return typeof value === 'string' && ROOT_PRIMITIVE_TOOL_IDS.has(value)
}

export function normalizeRootPrimitiveAdapterEnvelope(
  expectedPrimitive: string,
  value: unknown,
): unknown {
  const record = asRecord(value)
  if (!record) return value
  const topLevelToolId = record.tool_id

  const params = asRecord(record.params)
  if (!params) return value
  const nestedToolId = params.tool_id
  if (
    typeof topLevelToolId === 'string' &&
    topLevelToolId.length > 0 &&
    topLevelToolId !== expectedPrimitive &&
    nestedToolId === topLevelToolId
  ) {
    const { tool_id: _nestedToolId, ...adapterParams } = params
    return {
      ...record,
      params: adapterParams,
    }
  }

  if (topLevelToolId !== expectedPrimitive) return value
  if (
    typeof nestedToolId !== 'string' ||
    nestedToolId.trim().length === 0 ||
    ROOT_PRIMITIVE_TOOL_IDS.has(nestedToolId)
  ) {
    return value
  }

  const { tool_id: _nestedToolId, ...adapterParams } = params
  return {
    ...record,
    tool_id: nestedToolId,
    params: adapterParams,
  }
}

export function rootPrimitiveSelfTargetMessage(
  toolId: string,
  primitiveLabel: string,
): string {
  return (
    `Root primitive '${toolId}' is not a ${primitiveLabel} adapter tool_id. ` +
    'Pick a concrete adapter from <available_adapters>.'
  )
}
