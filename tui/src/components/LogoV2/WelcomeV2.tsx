// SPDX-License-Identifier: Apache-2.0
// UMMAYA welcome banner with the terminal mascot.

import React from 'react'
import { Box, Text } from 'src/ink.js'
import { Umma } from './Umma.js'

const WELCOME_V2_WIDTH = 58

function safeVersion(): string {
  try {
    if (typeof MACRO !== 'undefined' && MACRO.VERSION) return MACRO.VERSION
  } catch {
    /* ignore */
  }
  return 'unknown'
}

export interface WelcomeV2Props {
  readonly version?: string
}

function MascotMark(): React.ReactElement {
  return (
    <Box flexDirection="column" alignItems="center" marginY={1}>
      <Umma />
    </Box>
  )
}

export function WelcomeV2({ version }: WelcomeV2Props = {}): React.ReactElement {
  const ver = version ?? safeVersion()

  return (
    <Box width={WELCOME_V2_WIDTH} flexDirection="column">
      <Text>
        <Text color="claude">{'Welcome to UMMAYA'} </Text>
        <Text dimColor>v{ver}</Text>
      </Text>
      <Text dimColor>{'Unified Multi-Ministry Agent for Your Administration'}</Text>
      <Text dimColor>{'………………………………………………………………………………………………………………'}</Text>
      <MascotMark />
    </Box>
  )
}
