import type { PlanRequest } from '@/api/types'

import type { TripDraft } from './store'

/** The API request for a draft, or null while the draft is incomplete. */
export function toPlanRequest(draft: TripDraft): PlanRequest | null {
  if (!draft.origin || !draft.destination) return null
  return {
    origin: draft.origin,
    destination: draft.destination,
    departure_local: draft.departureLocal,
    load_lb: draft.loadLb,
    interval_mi: draft.intervalMi,
  }
}
