/** Shareable URLs: the trip inputs round-trip through the query string. */

import type { IntervalMi, Place } from '@/api/types'

import type { TripDraft } from './store'

const INTERVALS: readonly IntervalMi[] = [10, 25, 50]

function encodePlace(place: Place): string {
  return `${place.lat.toFixed(5)},${place.lon.toFixed(5)},${place.label}`
}

function decodePlace(value: string | null): Place | null {
  if (!value) return null
  const [lat, lon, ...label] = value.split(',')
  const parsed = { lat: Number(lat), lon: Number(lon), label: label.join(',').trim() }
  return Number.isFinite(parsed.lat) && Number.isFinite(parsed.lon) && parsed.label ? parsed : null
}

export function draftToSearch(draft: TripDraft): string {
  if (!draft.origin || !draft.destination) return ''
  const params = new URLSearchParams({
    o: encodePlace(draft.origin),
    d: encodePlace(draft.destination),
    t: draft.departureLocal,
    w: String(draft.loadLb),
    i: String(draft.intervalMi),
  })
  return `?${params}`
}

/** A complete draft from the URL, or null if the URL doesn't describe a trip. */
export function draftFromSearch(search: string): TripDraft | null {
  const params = new URLSearchParams(search)
  const origin = decodePlace(params.get('o'))
  const destination = decodePlace(params.get('d'))
  const departureLocal = params.get('t') ?? ''
  const loadLb = Number(params.get('w'))
  const intervalMi = Number(params.get('i')) as IntervalMi
  if (
    !origin ||
    !destination ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(departureLocal) ||
    !Number.isFinite(loadLb) ||
    !INTERVALS.includes(intervalMi)
  ) {
    return null
  }
  return { origin, destination, departureLocal, loadLb, intervalMi }
}
