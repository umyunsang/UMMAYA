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

// KOSMOS hotfix (2026-05-04, KMA base_time hallucination 차단):
// LLM 이 KMA `base_time` (KST HHMM) 을 추측하지 않도록 KST 현재 시각을
// 동적 user-context 에 inject. 백엔드 stdio.py 가 system-prompt 동적
// suffix 에도 같은 정보를 emit — 양쪽 모두 inject 해야 sub-agent path
// (runAgent / btw / compact 등) 도 KST 시각을 본다. KOSMOS_OVERRIDE_KST_TIME
// env 는 테스트용 (HH:MM 또는 HHMM 또는 ISO-8601).
export interface KstTimeParts {
  iso: string // YYYY-MM-DD (KST date)
  hm: string // HH:MM
  hhmm: string // HHMM
}
export function getKstTimeParts(now?: Date): KstTimeParts {
  const override = process.env.KOSMOS_OVERRIDE_KST_TIME
  let instant: Date
  if (override) {
    // Accept full ISO-8601 (with offset) verbatim; bare HH:MM falls back to a
    // fixed reference date in Asia/Seoul so the host's wall-clock is irrelevant.
    const parsed = new Date(override.includes('T') ? override : `2026-01-01T${override}+09:00`)
    instant = isNaN(parsed.getTime()) ? new Date() : parsed
  } else {
    instant = now ?? new Date()
  }
  // Always project to Asia/Seoul wall-clock, regardless of host TZ. Intl
  // formatters take a UTC instant and emit the wall-clock string for the
  // requested zone — this is the only way to be portable across darwin/UTC
  // CI runners.
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = Object.fromEntries(fmt.formatToParts(instant).map(p => [p.type, p.value])) as {
    year: string
    month: string
    day: string
    hour: string
    minute: string
  }
  // Intl 'en-CA' renders hour=24 for midnight in some Node/Bun versions.
  const hh = parts.hour === '24' ? '00' : parts.hour
  return {
    iso: `${parts.year}-${parts.month}-${parts.day}`,
    hm: `${hh}:${parts.minute}`,
    hhmm: `${hh}${parts.minute}`,
  }
}
