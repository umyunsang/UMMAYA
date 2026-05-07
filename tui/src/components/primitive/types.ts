/**
 * KOSMOS-original — primitive renderer prop interfaces.
 *
 * All interfaces are derived from the Spec 031 PrimitiveEnvelope taxonomy
 * documented in data-model.md § 2.  No `any` types are used.
 *
 * Corresponds to tasks T072 (types.ts sub-task of PrimitiveDispatcher work).
 */

// ---------------------------------------------------------------------------
// Shared field types
// ---------------------------------------------------------------------------

/** An arbitrary key/value pair whose values are always strings for display. */
export interface DisplayField {
  label: string
  value: string
}

// ---------------------------------------------------------------------------
// Lookup mode — subtype discriminated union
// ---------------------------------------------------------------------------

/** A single point-of-interest result from a lookup tool call. */
export interface LookupPointPayload {
  kind: 'lookup'
  subtype: 'point'
  tool_id: string
  title: string
  subtitle?: string
  fields: DisplayField[]
}

/** A timeseries of (timestamp, value) rows. */
export interface LookupTimeseriesPayload {
  kind: 'lookup'
  subtype: 'timeseries'
  tool_id: string
  unit?: string
  rows: Array<{ ts: string; value: string }>
}

/** A flat list of records with title + trailing metadata. */
export interface LookupCollectionPayload {
  kind: 'lookup'
  subtype: 'collection'
  tool_id: string
  items: Array<{ index: number; title: string; meta?: string }>
}

/** A key/value detail view for a single structured record. */
export interface LookupDetailPayload {
  kind: 'lookup'
  subtype: 'detail'
  tool_id: string
  fields: DisplayField[]
}

/** A lookup-level error result surfaced as a red banner. */
export interface LookupErrorPayload {
  kind: 'lookup'
  subtype: 'error'
  tool_id: string
  title: string
  description: string
  retry_hint?: string
}

export type LookupPayload =
  | LookupPointPayload
  | LookupTimeseriesPayload
  | LookupCollectionPayload
  | LookupDetailPayload
  | LookupErrorPayload

// ---------------------------------------------------------------------------
// Resolve location mode
// ---------------------------------------------------------------------------

/** Coordinate pair slot. */
export interface CoordsSlot {
  lat: number
  lon: number
}

/** Administrative region code slot. */
export interface AdmCodeSlot {
  code: string
  name: string
}

/** Legal/admin region name slot. */
export interface RegionSlot {
  region_type: 'B' | 'H'
  address_name: string
  region_1depth_name: string
  region_2depth_name: string
  region_3depth_name?: string
  code: string
}

/** Full Korean address slot. */
export interface AddressSlot {
  road?: string
  parcel?: string
  detail?: string
  zip?: string
}

/** Named place / POI slot. */
export interface PoiSlot {
  name: string
  category?: string
  source?: string
}

/**
 * resolve_location envelope — holds optional slots for each resolved
 * representation.  At least one slot MUST be present.
 */
export interface ResolveLocationPayload {
  kind: 'resolve_location'
  tool_id: string
  slots: {
    coords?: CoordsSlot
    adm_cd?: AdmCodeSlot
    region?: RegionSlot
    address?: AddressSlot
    poi?: PoiSlot
  }
}

// ---------------------------------------------------------------------------
// Submit mode
// ---------------------------------------------------------------------------

export type SubmitFamily =
  | 'pay'
  | 'issue_certificate'
  | 'submit_application'
  | 'reserve_slot'
  | 'check_eligibility'

export type MockReason =
  | 'tee_bound'
  | 'payment_rail'
  | 'pii_gate'
  | 'delegation_absent'

export interface SubmitSuccessPayload {
  kind: 'submit'
  tool_id: string
  family: SubmitFamily
  ok: true
  confirmation_id: string
  timestamp: string
  summary: string
  mock_reason?: MockReason
}

export interface SubmitErrorPayload {
  kind: 'submit'
  tool_id: string
  family: SubmitFamily
  ok: false
  error_code: string
  message: string
  retry_hint?: string
  mock_reason?: MockReason
}

export type SubmitPayload = SubmitSuccessPayload | SubmitErrorPayload

// Verify mode
// ---------------------------------------------------------------------------

export type VerifyFamily =
  | 'gongdong_injeungseo'
  | 'geumyung_injeungseo'
  | 'ganpyeon_injeung'
  | 'digital_onepass'
  | 'mobile_id'
  | 'mydata'

export interface VerifySuccessPayload {
  kind: 'verify'
  tool_id: string
  family: VerifyFamily
  ok: true
  korea_tier: string
  nist_aal_hint?: string
  identity_label: string
}

export interface VerifyFailPayload {
  kind: 'verify'
  tool_id: string
  family: VerifyFamily
  ok: false
  korea_tier: string
  error_code: string
  message: string
  remediation?: string
}

export type VerifyPayload = VerifySuccessPayload | VerifyFailPayload

// ---------------------------------------------------------------------------
// Unrecognized payload (FR-033)
// ---------------------------------------------------------------------------

export interface UnrecognizedPayloadData {
  /** Preserved raw kind for diagnostics. */
  raw_kind: string
  raw_data: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Dispatcher union — exhaustive across active primitive modes
// ---------------------------------------------------------------------------

export type PrimitivePayload =
  | LookupPayload
  | ResolveLocationPayload
  | SubmitPayload
  | VerifyPayload
