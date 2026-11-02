/**
 * Hours-of-service timing on the client (D25). Checkpoint ETAs already include rest; these
 * helpers convert trip time (since departure) to driving time so the truck can be placed
 * on the road — and parked while a rest is in progress.
 */

import type { RestStop, Route } from '@/api/types'

type WithRests = Pick<Route, 'rest_stops'>

/** The rest in progress ``tripS`` seconds after departure, if any. */
export function restAt(route: WithRests, tripS: number): RestStop | null {
  return (
    route.rest_stops.find((r) => tripS >= r.start_s && tripS < r.start_s + r.duration_s) ?? null
  )
}

/** Driving time accumulated ``tripS`` seconds after departure. */
export function drivingAt(route: WithRests, tripS: number): number {
  let rested = 0
  for (const rest of route.rest_stops) {
    if (tripS <= rest.start_s) break
    rested += Math.min(tripS - rest.start_s, rest.duration_s)
  }
  return tripS - rested
}

export const REST_LABEL: Record<RestStop['kind'], string> = {
  break: '30-min break',
  reset: '10-h rest',
}
