/**
 * Departure advisor (backend `domain/departure.py`): the plan's routes re-scored for
 * nearby departures. Computed server-side at the request load.
 */

import type { DepartureAdvice, DepartureOption } from '@/api/types'

import { formatLocal } from './format'
import { CRITERION_LABEL } from './levels'
import type { Level } from './risk'

/** Miles at a level below which it doesn't colour an option's cell. */
const CELL_MIN_MI = 1

/** Worst level the option's best route spends at least a mile in; null when unforecast. */
export function optionLevel(option: DepartureOption): Level | null {
  for (let level = 4; level >= 0; level--) {
    if ((option.miles_by_level[level] ?? 0) >= CELL_MIN_MI) return level as Level
  }
  return option.unknown_miles > 0 ? null : 0
}

export function offsetLabel(offsetH: number): string {
  if (offsetH === 0) return 'As planned'
  return `${offsetH > 0 ? '+' : '−'}${Math.abs(offsetH)} h`
}

/** "Leave 6 h later (Tue 19:00): 80 fewer Severe miles on Route A." */
export function suggestionText(advice: DepartureAdvice): string | null {
  const { suggestion } = advice
  if (!suggestion) return null
  const option = advice.options.find((o) => o.offset_h === suggestion.offset_h)
  if (!option) return null
  const hours = Math.abs(suggestion.offset_h)
  const when = suggestion.offset_h > 0 ? 'later' : 'earlier'
  const criterion = CRITERION_LABEL[suggestion.criterion]
  return (
    `Leave ${hours} h ${when} (${formatLocal(option.departure)}): ` +
    `${suggestion.gain_mi} fewer ${criterion} on Route ${option.route_id}.`
  )
}

/** The `departure_local` form value (origin wall clock) for an option. */
export function departureLocal(option: DepartureOption): string {
  return option.departure.local.slice(0, 16)
}
