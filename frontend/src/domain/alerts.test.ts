import { describe, expect, it } from 'vitest'

import type { Route, RouteAlert } from '@/api/types'

import { activeEvents, alertsAtMile, alertTiming, sortAlerts } from './alerts'

const at = (utc: string) => ({ utc, local: utc, tz: 'UTC' })

function alert(event: string, changes: Partial<RouteAlert> = {}): RouteAlert {
  return {
    id: event,
    event,
    category: 'wind',
    severity: 'moderate',
    headline: event,
    area: '',
    starts: at('2026-11-03T12:00:00Z'),
    ends: at('2026-11-03T18:00:00Z'),
    start_mi: 100,
    end_mi: 150,
    enter: at('2026-11-03T14:00:00Z'),
    exit: at('2026-11-03T15:00:00Z'),
    in_effect: true,
    ...changes,
  }
}

const route = (alerts: RouteAlert[]) => ({ alerts }) as Route

describe('alerts', () => {
  it('orders in-effect and severe alerts first', () => {
    const sorted = sortAlerts([
      alert('Past', { in_effect: false, severity: 'extreme' }),
      alert('Advisory'),
      alert('Warning', { severity: 'severe', start_mi: 300 }),
    ])
    expect(sorted.map((a) => a.event)).toEqual(['Warning', 'Advisory', 'Past'])
  })

  it('lists each active event once', () => {
    const r = route([
      alert('Wind Advisory'),
      alert('Wind Advisory', { id: 'b' }),
      alert('X', { in_effect: false }),
    ])
    expect(activeEvents(r)).toEqual(['Wind Advisory'])
  })

  it('finds alerts covering a mile', () => {
    expect(alertsAtMile(route([alert('A')]), 120)).toHaveLength(1)
    expect(alertsAtMile(route([alert('A')]), 151)).toHaveLength(0)
  })

  it('explains alerts that end before the truck arrives', () => {
    const ended = alert('A', { in_effect: false, ends: at('2026-11-03T13:00:00Z') })
    expect(alertTiming(ended)).toMatch(/^Ends .*, before you arrive$/)
    expect(alertTiming(alert('B'))).toMatch(/^You pass .*, in effect until /)
  })
})
