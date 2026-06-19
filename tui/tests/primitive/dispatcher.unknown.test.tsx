import { describe, expect, test } from 'bun:test'
import { render } from 'ink-testing-library'
import { PrimitiveDispatcher } from '@/components/primitive'
import { stripSnapshotAnsi } from './snapshotFrame.js'
import { wrap } from './dispatcher.helpers.js'

describe('PrimitiveDispatcher — unknown kind', () => {
  test('renders UnrecognizedPayload for unknown kind', () => {
    const unknownPayload = { kind: 'telepath', data: 'something' }
    const frame = render(wrap(<PrimitiveDispatcher payload={unknownPayload} />)).lastFrame() ?? ''
    expect(frame).toContain('Unrecognized tool result')
    expect(frame).toContain('telepath')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })

  test('renders UnrecognizedPayload for missing kind', () => {
    const noKindPayload = { data: 'no kind here' }
    const frame = render(wrap(<PrimitiveDispatcher payload={noKindPayload} />)).lastFrame() ?? ''
    expect(frame).toContain('Unrecognized tool result')
    expect(stripSnapshotAnsi(frame)).toMatchSnapshot()
  })
})
