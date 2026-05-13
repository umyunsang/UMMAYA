// SPDX-License-Identifier: Apache-2.0
// Spec 1978 Phase 5 — AuthContextDisplay component (T066).
//
// Renders an AuthContext-shaped object returned by the check primitive in a
// citizen-readable form. Mirrors the field set of the Python
// _AuthContextBase + per-family variants from src/ummaya/primitives/verify.py.
//
// Design-system: uses existing theme tokens (text, inactive, subtle, success)
// from tui/src/theme/tokens.ts. No new color constants introduced.

import React from 'react'
import { Box, Text } from '../../ink.js'
import { useTheme } from '../../theme/provider.js'

// ---------------------------------------------------------------------------
// Public type — mirrors the Python AuthContext discriminated union's shared
// fields. Additional family-specific fields are captured by the index signature.
// ---------------------------------------------------------------------------

export type AuthContext = {
  family: string
  published_tier: string
  nist_aal_hint: 'AAL1' | 'AAL2' | 'AAL3'
  // additional family-specific fields pass through
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Korean display labels for each known family value
// ---------------------------------------------------------------------------

const FAMILY_LABEL: Record<string, string> = {
  gongdong_injeungseo: '공동인증서',
  geumyung_injeungseo: '금융인증서',
  ganpyeon_injeung: '간편인증',
  digital_onepass: 'Digital Onepass',
  mobile_id: '모바일 신분증',
  mydata: '마이데이터',
}

// Fields that are already rendered in the header and should be excluded from
// the supplemental key/value list.
const HEADER_KEYS = new Set(['family', 'published_tier', 'nist_aal_hint', 'verified_at'])

// ---------------------------------------------------------------------------
// AuthContextDisplay
// ---------------------------------------------------------------------------

export function AuthContextDisplay(props: { context: AuthContext }): React.ReactElement {
  const { context } = props
  const theme = useTheme()

  const familyLabel = FAMILY_LABEL[context.family] ?? context.family

  // Collect extra family-specific fields (exclude header fields + internal).
  const extraEntries = Object.entries(context).filter(([k]) => !HEADER_KEYS.has(k))

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.success}
      paddingX={1}
      paddingY={0}
    >
      {/* Header: verification badge + family label */}
      <Box>
        <Text bold color={theme.success}>
          {'✔ 인증 완료 — '}
        </Text>
        <Text bold color={theme.text}>
          {familyLabel}
        </Text>
      </Box>

      {/* Published tier (primary level label) */}
      <Box flexDirection="row" gap={1}>
        <Text color={theme.inactive} bold>
          등급
        </Text>
        <Text color={theme.success} bold>
          {context.published_tier}
        </Text>
      </Box>

      {/* NIST AAL hint */}
      <Box flexDirection="row" gap={1}>
        <Text color={theme.inactive}>NIST</Text>
        <Text color={theme.subtle}>{context.nist_aal_hint}</Text>
      </Box>

      {/* verified_at timestamp if present */}
      {context.verified_at !== undefined && (
        <Box flexDirection="row" gap={1}>
          <Text color={theme.inactive}>인증 시각</Text>
          <Text color={theme.subtle}>{String(context.verified_at)}</Text>
        </Box>
      )}

      {/* Family-specific extra fields */}
      {extraEntries.length > 0 && (
        <Box flexDirection="column" marginTop={0}>
          {extraEntries.map(([key, value]) => (
            <Box key={key} flexDirection="row" gap={1}>
              <Text color={theme.inactive}>{key}</Text>
              <Text color={theme.text}>{String(value ?? '')}</Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}
