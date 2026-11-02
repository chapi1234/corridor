/**
 * How much to trust a plan that was computed earlier: shared links and long-open tabs show
 * the forecast as it was fetched, which drifts as the weather models update.
 */

/** Forecast models refresh roughly hourly; older plans are offered a refresh. */
export const STALE_AFTER_MS = 60 * 60_000
/** Matches the backend's departure grace: later than this, the trip can't be re-planned. */
export const DEPARTURE_GRACE_MS = 5 * 60_000

export type Freshness = 'fresh' | 'stale' | 'departed'

export function freshness(generatedAtUtc: string, departureUtc: string, now: number): Freshness {
  if (Date.parse(departureUtc) < now - DEPARTURE_GRACE_MS) return 'departed'
  return now - Date.parse(generatedAtUtc) > STALE_AFTER_MS ? 'stale' : 'fresh'
}

export function formatAge(ms: number): string {
  const minutes = Math.max(Math.round(ms / 60_000), 1)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours} h`
  return `${Math.round(hours / 24)} days`
}
