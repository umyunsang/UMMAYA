/**
 * UMMAYA-original — primitive renderer prop interfaces.
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

/** A single point-of-interest result from a find tool call. */
export interface LookupPointPayload {
  kind: 'find'
  subtype: 'point'
  tool_id: string
  title: string
  subtitle?: string
  fields: DisplayField[]
}

/** A timeseries of (timestamp, value) rows. */
export interface LookupTimeseriesPayload {
  kind: 'find'
  subtype: 'timeseries'
  tool_id: string
  unit?: string
  rows: Array<{ ts: string; value: string }>
}

/** A flat list of records with title + trailing metadata. */
export interface LookupCollectionPayload {
  kind: 'find'
  subtype: 'collection'
  tool_id: string
  items: Array<{ index: number; title: string; meta?: string }>
}

/** A key/value detail view for a single structured record. */
export interface LookupDetailPayload {
  kind: 'find'
  subtype: 'detail'
  tool_id: string
  fields: DisplayField[]
}

/** A find-level error result surfaced as a red banner. */
export interface LookupErrorPayload {
  kind: 'find'
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
 * locate envelope — holds optional slots for each resolved
 * representation.  At least one slot MUST be present.
 */
export interface ResolveLocationPayload {
  kind: 'locate'
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
  kind: 'send'
  tool_id: string
  family: SubmitFamily
  ok: true
  confirmation_id: string
  timestamp: string
  summary: string
  mock_reason?: MockReason
}

export interface SubmitErrorPayload {
  kind: 'send'
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
  kind: 'check'
  tool_id: string
  family: VerifyFamily
  ok: true
  korea_tier: string
  nist_aal_hint?: string
  identity_label: string
}

export interface VerifyFailPayload {
  kind: 'check'
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
// Public document harness mode
// ---------------------------------------------------------------------------

export type DocumentToolStatus = 'ok' | 'blocked' | 'failed' | 'needs_input'
export type DocumentWorkflowStepStatus =
  | 'pending'
  | 'completed'
  | 'current'
  | 'blocked'
  | 'failed'
  | 'skipped'

export interface DocumentChangePayload {
  change_id: string
  operation_id: string
  change_type: 'field' | 'table_cell' | 'text' | 'style' | 'metadata' | 'copy'
  target_path: string
  display_label?: string | null
  before_value?: string | null
  after_value?: string | null
}

export interface DocumentDiffPayload {
  diff_id?: string
  diff_sha256?: string
  resource_ref?: string
  source_artifact_id: string
  derivative_artifact_id: string
  changes: DocumentChangePayload[]
  render_artifacts?: DocumentRenderArtifactPayload[]
  baseline_render_artifacts?: DocumentRenderArtifactPayload[]
  changed_viewports?: DocumentChangedViewportPayload[]
  viewport_cameras?: DocumentViewportCameraPayload[]
  inline_truncated?: boolean
  omitted_change_count?: number
}

export interface DocumentClipRectPayload {
  x: number | string
  y: number | string
  width: number | string
  height: number | string
}

export interface DocumentChangedViewportPayload {
  viewport_id: string
  change_ids: string[]
  page_number: number
  source_render_artifact_id: string
  clip_rect: DocumentClipRectPayload
  padding_x?: number | string
  padding_y?: number | string
  svg_artifact_ref?: string | null
  svg_artifact_path?: string | null
  png_artifact_ref?: string | null
  png_artifact_path?: string | null
  before_svg_artifact_ref?: string | null
  before_svg_artifact_path?: string | null
  before_png_artifact_ref?: string | null
  before_png_artifact_path?: string | null
  after_svg_artifact_ref?: string | null
  after_svg_artifact_path?: string | null
  after_png_artifact_ref?: string | null
  after_png_artifact_path?: string | null
  text_fallback?: string[]
  anchor_strategy?: string
  confidence?: number | string
  warnings?: string[]
}

export interface DocumentViewportCameraPayload {
  source_render_artifact_id: string
  baseline_render_artifact_id: string
  page_index: number
  viewport_rect: DocumentClipRectPayload
  zoom: number | string
  change_ids: string[]
}

export interface DocumentRenderArtifactPayload {
  render_artifact_id: string
  source_artifact_id?: string
  render_sha256?: string
  render_path?: string
  render_mime_type?: string | null
  raster_artifact_ref?: string | null
  raster_artifact_path?: string | null
  raster_mime_type?: string | null
  page_number?: number
  engine_id?: string
}

export interface DocumentPromotionGatePayload {
  capability?: string
  promotion_state?: string
  hard_gate_failures?: string[]
  promotion_checklist?: Array<{
    check_id: string
    capability?: string
    status?: string
    evidence_required?: string
    detail?: string | null
  }>
}

export interface DocumentWorkflowStepPayload {
  step_id: string
  label: string
  status: DocumentWorkflowStepStatus
  artifact_id?: string | null
  artifact_sha256?: string | null
  detail?: string | null
}

export interface DocumentSavedExportPayload {
  export_id?: string | null
  artifact_id?: string | null
  local_path?: string | null
  sha256?: string | null
  mime_type?: string | null
}

export interface DocumentToolResultPayload {
  tool_id: string
  correlation_id: string
  status: DocumentToolStatus
  artifact_refs?: string[]
  text_summary: string
  blocked_reason?: string | null
  diff?: DocumentDiffPayload | null
  render_artifacts?: DocumentRenderArtifactPayload[]
  promotion_gate_result?: DocumentPromotionGatePayload | null
  workflow_steps?: DocumentWorkflowStepPayload[]
  saved_exports?: DocumentSavedExportPayload[]
}

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
