import { lookup } from 'node:dns/promises'
import { isIP } from 'node:net'
import {
  validatePublicWebFetchUrl,
  type WebFetchUrlSafetyResult,
} from './urlSafety.js'

type ResolvedAddress = {
  readonly address: string
  readonly family: 4 | 6
}

type LookupHost = (hostname: string) => Promise<readonly ResolvedAddress[]>

const lookupHost: LookupHost = async hostname => {
  const addresses = await lookup(hostname, { all: true, verbatim: true })
  return addresses.flatMap(({ address, family }) =>
    family === 4 || family === 6 ? [{ address, family }] : [],
  )
}

export async function validateResolvedPublicWebFetchUrl(
  value: string,
  resolveHost: LookupHost = lookupHost,
): Promise<WebFetchUrlSafetyResult> {
  const validation = validatePublicWebFetchUrl(value)
  if (!validation.ok || isIP(validation.hostname) !== 0) {
    return validation
  }

  let addresses: readonly ResolvedAddress[]
  try {
    addresses = await resolveHost(validation.hostname)
  } catch (error) {
    if (error instanceof Error) {
      return unsafeResolvedUrl(
        `WebFetch could not resolve ${validation.hostname} to a public address.`,
      )
    }
    return unsafeResolvedUrl(
      `WebFetch could not safely classify ${validation.hostname}.`,
    )
  }

  if (addresses.length === 0) {
    return unsafeResolvedUrl(
      `WebFetch could not safely classify ${validation.hostname}.`,
    )
  }

  for (const resolved of addresses) {
    const resolvedValidation = validatePublicWebFetchUrl(
      addressUrlForSafetyCheck(resolved),
    )
    if (!resolvedValidation.ok) {
      return unsafeResolvedUrl(
        `WebFetch cannot access ${validation.hostname} because it resolved to a private, loopback, metadata, or link-local address (${resolved.address}).`,
      )
    }
  }

  return validation
}

function addressUrlForSafetyCheck({
  address,
  family,
}: ResolvedAddress): string {
  return family === 6 ? `http://[${address}]/` : `http://${address}/`
}

function unsafeResolvedUrl(message: string): WebFetchUrlSafetyResult {
  return {
    ok: false,
    reason: 'unsafe_url',
    message,
  }
}
