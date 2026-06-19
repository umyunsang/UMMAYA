import { z } from 'zod/v4'
import { validatePublicWebFetchUrl } from './urlSafety.js'

export const SOURCE_VERIFICATION_POLICY =
  'source_results_untrusted_until_user_approval' as const

export const sourceVerificationEvidenceSchema = z.object({
  toolId: z.string(),
  sourceUrl: z.string().nullable(),
  title: z.string().nullable(),
  observedAt: z.string(),
  citationHandle: z.string(),
  blockedOrUsed: z.enum(['blocked', 'needs_input']),
  trust: z.literal('untrusted_source'),
  promptInjection: z.enum(['detected', 'not_detected']),
  redacted: z.boolean(),
})

export const sourceVerificationSchema = z.object({
  mutationAllowed: z.literal(false),
  userApprovalRequired: z.literal(true),
  secretEgress: z.literal(false),
  policy: z.literal(SOURCE_VERIFICATION_POLICY).default(SOURCE_VERIFICATION_POLICY),
  evidence: z.array(sourceVerificationEvidenceSchema),
})

export type SourceVerificationEvidence = z.infer<
  typeof sourceVerificationEvidenceSchema
>
export type SourceVerification = z.infer<typeof sourceVerificationSchema>

const SECRET_TEXT_PATTERNS: readonly RegExp[] = [
  /Authorization\s*:\s*[^\n\r]+/gi,
  /Bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /Cookie\s*:\s*[^\n\r]+/gi,
  /\b[A-Z0-9_]*(?:API|AUTH|ACCESS|REFRESH|SESSION)[_-]?KEY\s*=\s*[^\s&]+/gi,
  /\b(?:session|access|refresh|id)[_-]?token\s*=\s*[^\s&]+/gi,
  /\bsk-[A-Za-z0-9_-]{8,}\b/g,
]

const SECRET_QUERY_KEYS = new Set([
  'access_token',
  'api_key',
  'apikey',
  'auth',
  'authorization',
  'cookie',
  'id_token',
  'key',
  'refresh_token',
  'servicekey',
  'session',
  'session_token',
  'token',
])

const PROMPT_INJECTION_PATTERNS: readonly RegExp[] = [
  /ignore\s+(?:all\s+)?previous\s+instructions/i,
  /change\s+(?:the\s+)?permission\s+policy/i,
  /bypass\s+(?:permissions?|approval|policy)/i,
  /system\s+prompt/i,
  /treat\s+this\s+as\s+(?:a\s+)?system\s+instruction/i,
]

function stableHandlePart(value: string): string {
  const lowered = value.toLowerCase().replace(/[^a-z0-9]+/g, '-')
  const trimmed = lowered.replace(/^-+|-+$/g, '')
  return trimmed.length > 0 ? trimmed.slice(0, 48) : 'source'
}

function hasRedactionCandidate(value: string): boolean {
  return SECRET_TEXT_PATTERNS.some(pattern => {
    pattern.lastIndex = 0
    return pattern.test(value)
  })
}

export function redactSourceVerificationText(value: string): string {
  const redacted = SECRET_TEXT_PATTERNS.reduce(
    (current, pattern) => current.replace(pattern, '[REDACTED]'),
    value,
  )
  return redacted
    .replaceAll('<source_verification>', '[source_verification]')
    .replaceAll('</source_verification>', '[/source_verification]')
}

export function redactSourceVerificationUrl(value: string | null): string | null {
  if (value === null) return null
  const validation = validatePublicWebFetchUrl(value)
  if (!validation.ok) return null
  const { parsedUrl } = validation
  for (const key of [...parsedUrl.searchParams.keys()]) {
    if (SECRET_QUERY_KEYS.has(key.toLowerCase())) {
      parsedUrl.searchParams.set(key, '[REDACTED]')
    }
  }
  return redactSourceVerificationText(parsedUrl.toString())
}

export function detectPromptInjection(value: string): 'detected' | 'not_detected' {
  return PROMPT_INJECTION_PATTERNS.some(pattern => pattern.test(value))
    ? 'detected'
    : 'not_detected'
}

export function buildSourceEvidence({
  toolId,
  sourceUrl,
  title,
  observedAt = new Date().toISOString(),
  blockedOrUsed,
  rawText,
}: {
  toolId: string
  sourceUrl: string | null
  title: string | null
  observedAt?: string
  blockedOrUsed: SourceVerificationEvidence['blockedOrUsed']
  rawText: string
}): SourceVerificationEvidence {
  const redactedUrl = redactSourceVerificationUrl(sourceUrl)
  const redactedTitle = title === null ? null : redactSourceVerificationText(title)
  const combined = `${rawText}\n${redactedTitle ?? ''}\n${redactedUrl ?? ''}`
  return {
    toolId,
    sourceUrl: redactedUrl,
    title: redactedTitle,
    observedAt,
    citationHandle: `src-${stableHandlePart(toolId)}-${stableHandlePart(
      redactedUrl ?? redactedTitle ?? rawText,
    )}`,
    blockedOrUsed,
    trust: 'untrusted_source',
    promptInjection: detectPromptInjection(combined),
    redacted:
      hasRedactionCandidate(rawText) ||
      (sourceUrl !== null && redactSourceVerificationUrl(sourceUrl) !== sourceUrl) ||
      (title !== null && redactSourceVerificationText(title) !== title),
  }
}

export function buildSourceVerification(
  evidence: readonly SourceVerificationEvidence[],
): SourceVerification {
  return {
    mutationAllowed: false,
    userApprovalRequired: true,
    secretEgress: false,
    policy: SOURCE_VERIFICATION_POLICY,
    evidence: [...evidence],
  }
}

export function formatSourceVerificationForModel(
  sourceVerification: SourceVerification | undefined,
): string {
  if (sourceVerification === undefined) return ''
  const parsed = sourceVerificationSchema.safeParse(sourceVerification)
  if (!parsed.success) return ''

  const lines = [
    '<source_verification>',
    `policy: ${parsed.data.policy}`,
    `document_mutation_allowed: ${parsed.data.mutationAllowed}`,
    `user_approval_required: ${parsed.data.userApprovalRequired}`,
    `permission_policy_mutation_allowed: false`,
    `no_secret_egress: ${!parsed.data.secretEgress}`,
    `no_fabricated_fact: true`,
  ]

  for (const evidence of parsed.data.evidence) {
    const safeSourceUrl = redactSourceVerificationUrl(evidence.sourceUrl)
    const safeTitle =
      evidence.title === null ? null : redactSourceVerificationText(evidence.title)
    lines.push(
      `tool_id: ${redactSourceVerificationText(evidence.toolId)}`,
      `source_url: ${safeSourceUrl ?? 'none'}`,
      `title: ${safeTitle ?? 'none'}`,
      `timestamp: ${evidence.observedAt}`,
      `citation_handle: ${redactSourceVerificationText(evidence.citationHandle)}`,
      `blocked_or_used: ${evidence.blockedOrUsed}`,
      `trust: ${evidence.trust}`,
      `prompt_injection: ${evidence.promptInjection}`,
      `redacted: ${evidence.redacted}`,
    )
  }

  lines.push('</source_verification>')
  return lines.join('\n')
}

export function formatSourceVerifiedToolResult({
  result,
  sourceVerification,
}: {
  result: string
  sourceVerification?: SourceVerification
}): string {
  const safeResult = redactSourceVerificationText(result)
  const verification = formatSourceVerificationForModel(sourceVerification)
  if (!verification) return safeResult
  return `${safeResult}\n\n${verification}`
}
