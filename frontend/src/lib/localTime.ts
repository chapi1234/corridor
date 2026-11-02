/**
 * Helpers for "YYYY-MM-DDTHH:MM" wall-clock strings, as used by <input type="datetime-local">.
 *
 * Departures are wall-clock time at the *origin* (D14), which is often not the browser's
 * zone, so "now" is always read in an explicit IANA zone. Arithmetic is done on the wall
 * clock itself (via UTC fields), which works for half-hour zones and never drifts by an
 * hour across the browser's own DST change.
 */

const pad = (n: number) => String(n).padStart(2, '0')

export const BROWSER_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone

/** Wall-clock fields of a "YYYY-MM-DDTHH:MM" string as a UTC timestamp (no zone meaning). */
function wallToUtcMs(value: string): number {
  const [date = '', time = '00:00'] = value.split('T')
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  return Date.UTC(y!, m! - 1, d!, hh!, mm!)
}

function utcMsToWall(ms: number): string {
  const t = new Date(ms)
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}T${pad(t.getUTCHours())}:${pad(t.getUTCMinutes())}`
}

/** The wall clock in ``tz`` at instant ``now``. */
export function wallClockIn(tz: string, now = new Date()): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
      .formatToParts(now)
      .map((p) => [p.type, p.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`
}

export function nextFullHour(tz = BROWSER_TZ, now = new Date()): string {
  const wall = wallToUtcMs(wallClockIn(tz, now))
  const hour = 3_600_000
  return utcMsToWall(Math.floor(wall / hour) * hour + hour)
}

export function shiftHours(value: string, hours: number): string {
  return utcMsToWall(wallToUtcMs(value) + hours * 3_600_000)
}

export function tomorrowAt(hour: number, tz = BROWSER_TZ, now = new Date()): string {
  const today = wallClockIn(tz, now).slice(0, 10)
  return utcMsToWall(wallToUtcMs(`${today}T${pad(hour)}:00`) + 86_400_000)
}

/** Short zone name for ``tz`` at ``now``, e.g. "MST" or "GMT-7". */
export function zoneAbbreviation(tz: string, now = new Date()): string {
  const part = new Intl.DateTimeFormat('en-US', { timeZone: tz, timeZoneName: 'short' })
    .formatToParts(now)
    .find((p) => p.type === 'timeZoneName')
  return part?.value ?? tz
}
