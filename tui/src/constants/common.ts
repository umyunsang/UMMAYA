import memoize from 'lodash-es/memoize.js'

// This ensures you get the LOCAL date in ISO format
export function getLocalISODate(): string {
  // Check for ant-only date override
  if (process.env.CLAUDE_CODE_OVERRIDE_DATE) {
    return process.env.CLAUDE_CODE_OVERRIDE_DATE
  }

  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// Memoized for prompt-cache stability — captures the date once at session start.
// The main interactive path gets this behavior via memoize(getUserContext) in
// context.ts; simple mode (--bare) calls getSystemPrompt per-request and needs
// an explicit memoized date to avoid busting the cached prefix at midnight.
// When midnight rolls over, getDateChangeAttachments appends the new date at
// the tail (though simple mode disables attachments, so the trade-off there is:
// stale date after midnight vs. ~entire-conversation cache bust — stale wins).
export const getSessionStartDate = memoize(getLocalISODate)

// Returns "Month YYYY" (e.g. "February 2026") in the user's local timezone.
// Changes monthly, not daily — used in tool prompts to minimize cache busting.
export function getLocalMonthYear(): string {
  const date = process.env.CLAUDE_CODE_OVERRIDE_DATE
    ? new Date(process.env.CLAUDE_CODE_OVERRIDE_DATE)
    : new Date()
  return date.toLocaleString('en-US', { month: 'long', year: 'numeric' })
}

export interface KstTimeParts {
  iso: string
  hm: string
  hhmm: string
}

export function getKstTimeParts(now?: Date): KstTimeParts {
  const override = process.env.UMMAYA_OVERRIDE_KST_TIME
  const instant = override
    ? new Date(
        override.includes('T')
          ? override
          : `2026-01-01T${override}+09:00`,
      )
    : (now ?? new Date())
  const date = Number.isNaN(instant.getTime()) ? new Date() : instant
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = Object.fromEntries(
    fmt.formatToParts(date).map(part => [part.type, part.value]),
  ) as {
    year: string
    month: string
    day: string
    hour: string
    minute: string
  }
  const hour = parts.hour === '24' ? '00' : parts.hour
  return {
    iso: `${parts.year}-${parts.month}-${parts.day}`,
    hm: `${hour}:${parts.minute}`,
    hhmm: `${hour}${parts.minute}`,
  }
}
