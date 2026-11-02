/**
 * Forecast-hour arithmetic. Hour 0 is the heatmap's base time (the departure hour,
 * floored), so the timeline, the heatmap frames and the ghost truck share one clock.
 */

import type { PlanResponse, Route } from '@/api/types'
import { lerp } from '@/lib/math'

import { drivingAt } from './duty'

const HOUR_MS = 3_600_000

export function frameInstant(plan: PlanResponse, hour: number): Date {
  return new Date(Date.parse(plan.heatmap.base_time) + hour * HOUR_MS)
}

/** Fractional forecast hour at which a UTC instant falls. */
export function hourOf(plan: PlanResponse, utc: string): number {
  return (Date.parse(utc) - Date.parse(plan.heatmap.base_time)) / HOUR_MS
}

/** Seconds since departure at a forecast hour (negative before departure). */
export function elapsedAtHour(plan: PlanResponse, hour: number): number {
  return (frameInstant(plan, hour).getTime() - Date.parse(plan.departure.utc)) / 1000
}

/** The forecast hour closest to a route's checkpoint ETA. */
export function hourOfCheckpoint(plan: PlanResponse, route: Route, index: number): number {
  const checkpoint = route.checkpoints[index]
  return checkpoint ? Math.round(hourOf(plan, checkpoint.eta.utc)) : 0
}

/**
 * Where the truck is (route mile) ``elapsedS`` seconds after departure, from the checkpoint
 * schedule. Rest time is removed first, so the truck stays put while resting.
 */
export function mileAtElapsed(route: Route, elapsedS: number): number {
  const checkpoints = route.checkpoints
  if (checkpoints.length === 0 || elapsedS <= 0) return 0
  if (elapsedS >= route.duration_s) return route.distance_mi
  const drivingS = drivingAt(route, elapsedS)
  for (let i = 1; i < checkpoints.length; i++) {
    const [a, b] = [checkpoints[i - 1]!, checkpoints[i]!]
    if (drivingS <= b.driving_s) {
      const span = b.driving_s - a.driving_s
      return lerp(a.mile, b.mile, span > 0 ? (drivingS - a.driving_s) / span : 0)
    }
  }
  return route.distance_mi
}
