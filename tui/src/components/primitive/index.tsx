/**
 * KOSMOS-original — PrimitiveDispatcher + barrel export.
 *
 * PrimitiveDispatcher receives a tool_result envelope payload and dispatches
 * to the appropriate renderer.  It is a pure component: no IPC awareness,
 * no store writes.
 *
 * Dispatch strategy:
 *   1. Switch on payload.kind (active primitive arms + unknown).
 *   2. Within lookup: switch on payload.subtype.
 *   3. Within submit / verify: switch on payload.ok.
 *   4. Unknown kind or subtype → <UnrecognizedPayload> (FR-033).
 *
 * TypeScript never-check ensures exhaustiveness at compile time.
 *
 * TODO (T087 handoff): Wire <PrimitiveDispatcher> into MessageList.tsx in the
 * post-wave Lead integration step.  MessageList.tsx is owned by the Lead and
 * MUST NOT be edited by Team C.  The dispatcher is ready for import as:
 *   import { PrimitiveDispatcher } from '@/components/primitive'
 * Pass the tool_result.envelope field as the `payload` prop.
 */
import React from 'react'
import { Box, Text } from 'ink'
import { useTheme } from '@/theme/provider'

import { PointCard } from './PointCard'
import { TimeseriesTable } from './TimeseriesTable'
import { CollectionList } from './CollectionList'
import { DetailView } from './DetailView'
import { ErrorBanner } from './ErrorBanner'
import { CoordPill } from './CoordPill'
import { AdmCodeBadge } from './AdmCodeBadge'
import { AddressBlock } from './AddressBlock'
import { POIMarker } from './POIMarker'
import { SubmitReceipt } from './SubmitReceipt'
import { SubmitErrorBanner } from './SubmitErrorBanner'
import { AuthContextCard } from './AuthContextCard'
import { AuthWarningBanner } from './AuthWarningBanner'
import { UnrecognizedPayload } from './UnrecognizedPayload'

import type {
  PrimitivePayload,
  LookupPayload,
  ResolveLocationPayload,
  SubmitPayload,
  VerifyPayload,
} from './types'

// ---------------------------------------------------------------------------
// Internal sub-dispatchers
// ---------------------------------------------------------------------------

function dispatchLookup(payload: LookupPayload): React.JSX.Element {
  switch (payload.subtype) {
    case 'point':
      return <PointCard payload={payload} />
    case 'timeseries':
      return <TimeseriesTable payload={payload} />
    case 'collection':
      return <CollectionList payload={payload} />
    case 'detail':
      return <DetailView payload={payload} />
    case 'error':
      return <ErrorBanner payload={payload} />
    default: {
      // TypeScript never-check
      const _exhaustive: never = payload
      return (
        <UnrecognizedPayload
          data={{ raw_kind: `lookup`, raw_data: _exhaustive as Record<string, unknown> }}
        />
      )
    }
  }
}

function dispatchResolveLocation(payload: ResolveLocationPayload): React.JSX.Element {
  const theme = useTheme()
  const { slots } = payload
  const hasCoords = slots.coords !== undefined
  const hasAdmCode = slots.adm_cd !== undefined
  const hasRegion = slots.region !== undefined
  const hasAddress = slots.address !== undefined
  const hasPoi = slots.poi !== undefined

  if (!hasCoords && !hasAdmCode && !hasRegion && !hasAddress && !hasPoi) {
    return (
      <UnrecognizedPayload
        data={{ raw_kind: 'resolve_location', raw_data: { reason: 'no slots present' } }}
      />
    )
  }

  return (
    <Box flexDirection="column" gap={0}>
      {hasCoords && slots.coords !== undefined && <CoordPill coords={slots.coords} />}
      {hasAdmCode && slots.adm_cd !== undefined && <AdmCodeBadge admCode={slots.adm_cd} />}
      {hasRegion && slots.region !== undefined && (
        <Box flexDirection="row">
          <Text color={theme.text} bold>{slots.region.address_name}</Text>
          <Text color={theme.subtle}>{` · ${slots.region.region_type} ${slots.region.code}`}</Text>
        </Box>
      )}
      {hasAddress && slots.address !== undefined && <AddressBlock address={slots.address} />}
      {hasPoi && slots.poi !== undefined && <POIMarker poi={slots.poi} />}
    </Box>
  )
}

function dispatchSubmit(payload: SubmitPayload): React.JSX.Element {
  if (payload.ok) {
    return <SubmitReceipt payload={payload} />
  }
  return <SubmitErrorBanner payload={payload} />
}

function dispatchVerify(payload: VerifyPayload): React.JSX.Element {
  if (payload.ok) {
    return <AuthContextCard payload={payload} />
  }
  return <AuthWarningBanner payload={payload} />
}

// ---------------------------------------------------------------------------
// PrimitiveDispatcher — public entry point
// ---------------------------------------------------------------------------

export interface PrimitiveDispatcherProps {
  /**
   * The envelope from a tool_result IPC frame.
   * Accepts any object; unknown shapes fall through to <UnrecognizedPayload>.
   */
  payload: PrimitivePayload | Record<string, unknown>
}

export function PrimitiveDispatcher({ payload }: PrimitiveDispatcherProps): React.JSX.Element {
  const _theme = useTheme() // ensure ThemeProvider is present in the tree

  const kind = (payload as { kind?: string }).kind

  switch (kind) {
    case 'lookup':
      return dispatchLookup(payload as LookupPayload)
    case 'resolve_location':
      return dispatchResolveLocation(payload as ResolveLocationPayload)
    case 'submit':
      return dispatchSubmit(payload as SubmitPayload)
    case 'verify':
      return dispatchVerify(payload as VerifyPayload)
    default:
      return (
        <UnrecognizedPayload
          data={{
            raw_kind: typeof kind === 'string' ? kind : '(unknown)',
            raw_data: payload as Record<string, unknown>,
          }}
        />
      )
  }
}

// ---------------------------------------------------------------------------
// Named exports — all renderers available for direct import
// ---------------------------------------------------------------------------

export { PointCard } from './PointCard'
export { TimeseriesTable } from './TimeseriesTable'
export { CollectionList } from './CollectionList'
export { DetailView } from './DetailView'
export { ErrorBanner } from './ErrorBanner'
export { CoordPill } from './CoordPill'
export { AdmCodeBadge } from './AdmCodeBadge'
export { AddressBlock } from './AddressBlock'
export { POIMarker } from './POIMarker'
export { SubmitReceipt } from './SubmitReceipt'
export { SubmitErrorBanner } from './SubmitErrorBanner'
export { AuthContextCard } from './AuthContextCard'
export { AuthWarningBanner } from './AuthWarningBanner'
export { UnrecognizedPayload } from './UnrecognizedPayload'
export type * from './types'
