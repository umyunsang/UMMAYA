import { afterEach, describe, expect, it, mock } from 'bun:test'
import { render } from 'ink-testing-library'
import React from 'react'
import { Text } from '../../src/ink.js'
import { clearManifestCache } from '../../src/services/api/adapterManifest.js'
import { getEmptyToolPermissionContext, type Tools } from '../../src/Tool.js'

const prewarmAdapterManifestMock = mock(() => {})

const {
  setAdapterManifestPrewarmForTests,
  useMergedTools,
} = await import('../../src/hooks/useMergedTools.js')

function ToolNamesProbe({
  initialTools = [],
  mcpTools = [],
}: {
  initialTools?: Tools
  mcpTools?: Tools
}) {
  const tools = useMergedTools(
    initialTools,
    mcpTools,
    getEmptyToolPermissionContext(),
  )
  return <Text>{tools.map((tool) => tool.name).join('|')}</Text>
}

afterEach(() => {
  clearManifestCache()
  delete process.env.UMMAYA_TEST_PREWARM_ADAPTER_MANIFEST
  setAdapterManifestPrewarmForTests(null)
  prewarmAdapterManifestMock.mockClear()
})

describe('useMergedTools adapter manifest prewarm', () => {
  it('starts adapter manifest prewarm when the REPL tool pool mounts', async () => {
    process.env.UMMAYA_TEST_PREWARM_ADAPTER_MANIFEST = '1'
    setAdapterManifestPrewarmForTests(prewarmAdapterManifestMock)

    render(<ToolNamesProbe />)
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(prewarmAdapterManifestMock).toHaveBeenCalledTimes(1)
  })
})
