import { isIP } from 'node:net'

const MAX_WEB_FETCH_URL_LENGTH = 2000

const INTERNAL_HOSTNAMES = new Set([
  'localhost',
  'localhost.localdomain',
  'ip6-localhost',
  'ip6-loopback',
  'metadata',
  'metadata.google.internal',
])

const INTERNAL_HOSTNAME_SUFFIXES = [
  '.localhost',
  '.local',
  '.internal',
  '.intranet',
  '.lan',
  '.home',
  '.corp',
] as const

export type WebFetchUrlSafetyResult =
  | {
      readonly ok: true
      readonly parsedUrl: URL
      readonly hostname: string
    }
  | {
      readonly ok: false
      readonly reason: 'invalid_url' | 'unsafe_url'
      readonly message: string
    }

export function validatePublicWebFetchUrl(
  value: string,
): WebFetchUrlSafetyResult {
  if (value.length > MAX_WEB_FETCH_URL_LENGTH) {
    return unsafeUrl('URL exceeds the WebFetch length limit.')
  }

  let parsedUrl: URL
  try {
    parsedUrl = new URL(value)
  } catch (error) {
    if (error instanceof TypeError) {
      return {
        ok: false,
        reason: 'invalid_url',
        message: `Invalid URL "${value}". The URL provided could not be parsed.`,
      }
    }
    throw error
  }

  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    return unsafeUrl('WebFetch only allows public http or https URLs.')
  }

  if (parsedUrl.username || parsedUrl.password) {
    return unsafeUrl('WebFetch URLs must not contain credentials.')
  }

  const hostname = normalizeHostname(parsedUrl.hostname)
  if (hostname.length === 0) {
    return unsafeUrl('WebFetch URL host is empty.')
  }

  if (isIpAddress(hostname)) {
    return isNonPublicIpAddress(hostname)
      ? unsafeUrl('WebFetch cannot access private, loopback, metadata, or link-local IP ranges.')
      : { ok: true, parsedUrl, hostname }
  }

  if (isInternalHostname(hostname)) {
    return unsafeUrl('WebFetch cannot access private, loopback, metadata, or link-local hostnames.')
  }

  return { ok: true, parsedUrl, hostname }
}

export function isPublicWebFetchUrl(value: string): boolean {
  return validatePublicWebFetchUrl(value).ok
}

function unsafeUrl(message: string): WebFetchUrlSafetyResult {
  return {
    ok: false,
    reason: 'unsafe_url',
    message,
  }
}

function normalizeHostname(hostname: string): string {
  const lower = hostname.toLowerCase()
  const withoutBrackets =
    lower.startsWith('[') && lower.endsWith(']')
      ? lower.slice(1, lower.length - 1)
      : lower
  return withoutBrackets.replace(/\.$/u, '')
}

function isIpAddress(hostname: string): boolean {
  return isIP(hostname) !== 0
}

function isNonPublicIpAddress(hostname: string): boolean {
  switch (isIP(hostname)) {
    case 4:
      return isNonPublicIpv4(hostname)
    case 6:
      return isNonPublicIpv6(hostname)
    default:
      return true
  }
}

function isNonPublicIpv4(hostname: string): boolean {
  const octets = hostname.split('.').map(value => Number(value))
  const [first, second] = octets
  if (
    octets.length !== 4 ||
    first === undefined ||
    second === undefined ||
    octets.some(octet => !Number.isInteger(octet) || octet < 0 || octet > 255)
  ) {
    return true
  }

  return (
    first === 0 ||
    first === 10 ||
    first === 127 ||
    first >= 224 ||
    (first === 100 && second >= 64 && second <= 127) ||
    (first === 169 && second === 254) ||
    (first === 172 && second >= 16 && second <= 31) ||
    (first === 192 && second === 168) ||
    (first === 198 && (second === 18 || second === 19))
  )
}

function isNonPublicIpv6(hostname: string): boolean {
  const lower = hostname.toLowerCase()
  if (
    lower === '::' ||
    lower === '::1' ||
    lower.startsWith('::ffff:') ||
    lower.startsWith('2001:db8:')
  ) {
    return true
  }

  const firstSegment = lower.split(':').find(segment => segment.length > 0)
  if (firstSegment === undefined) {
    return true
  }
  const firstHextet = Number.parseInt(firstSegment, 16)
  if (!Number.isInteger(firstHextet)) {
    return true
  }

  return (
    (firstHextet & 0xfe00) === 0xfc00 ||
    (firstHextet & 0xffc0) === 0xfe80 ||
    (firstHextet & 0xff00) === 0xff00
  )
}

function isInternalHostname(hostname: string): boolean {
  if (INTERNAL_HOSTNAMES.has(hostname)) {
    return true
  }

  if (!hostname.includes('.')) {
    return true
  }

  return INTERNAL_HOSTNAME_SUFFIXES.some(suffix => hostname.endsWith(suffix))
}
