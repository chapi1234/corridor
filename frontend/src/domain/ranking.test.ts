import { describe, expect, it } from 'vitest'

import {
  assignTags,
  formatDurationShort,
  rank,
  rankKey,
  summarize,
  type RouteRisk,
} from './ranking'
import type { Level } from './risk'

function route(
  id: string,
  { noTravel = 0, severe = 0, high = 0, moderate = 0, low = 100, hours = 10 } = {},
): RouteRisk {
  const miles: [Level, number][] = [
    [4, noTravel],
    [3, severe],
    [2, high],
    [1, moderate],
    [0, low],
  ]
  const segments = miles
    .filter(([, m]) => m > 0)
    .map(([level, ownedMiles]) => ({ level, ownedMiles }))
  const distance = segments.reduce((sum, s) => sum + s.ownedMiles, 0)
  return summarize(id, segments, distance, hours * 3600)
}

describe('rank (mirrors backend ranking)', () => {
  it.each([
    [
      'no travel',
      route('A', { noTravel: 5, hours: 8 }),
      route('B', { severe: 50, hours: 12 }),
      'no_travel_miles',
      'Avoids 5 No Travel miles that Route A crosses.',
    ],
    [
      'severe',
      route('A', { severe: 38, hours: 8 }),
      route('B', { high: 90, hours: 12 }),
      'severe_miles',
      'Avoids 38 Severe miles that Route A crosses.',
    ],
    [
      'high',
      route('A', { severe: 10, high: 5 }),
      route('B', { severe: 10, high: 27 }),
      'high_miles',
      'Same Severe exposure as Route B, but 22 fewer High miles.',
    ],
    [
      'duration',
      route('A', { hours: 10 }),
      route('B', { hours: 10.7 }),
      'duration',
      'Equal weather risk to Route B, and 42 min faster.',
    ],
  ] as const)('%s decides', (_, a, b, criterion, reason) => {
    const ranking = rank([a, b])
    expect(ranking.deciding).toBe(criterion)
    expect(ranking.reason).toBe(reason)
  })

  it('explains against the fastest route when the recommendation is slower', () => {
    const ranking = rank([
      route('A', { severe: 40, hours: 8 }),
      route('B', { hours: 10 }),
      route('C', { hours: 10.01 }),
    ])
    expect(ranking.recommended).toBe('B')
    expect(ranking.competitor).toBe('A')
    expect(ranking.beatsOn).toEqual({ A: 'severe_miles', C: 'duration' })
  })

  it('uses banker’s rounding like Python when quantising miles', () => {
    // Python rounds 10.5 to 10 and 11.5 to 12; Math.round would give 11 and 12.
    expect(rankKey(route('A', { severe: 10.5 }))[1]).toBe(10)
    expect(rankKey(route('A', { severe: 11.5 }))[1]).toBe(12)
  })

  it('flags when every route crosses No Travel', () => {
    expect(rank([route('A', { noTravel: 3 }), route('B', { noTravel: 1 })]).noSafeRoute).toBe(true)
  })

  it('assigns tags', () => {
    const a = route('A', { severe: 5, hours: 8, low: 90 })
    const b = route('B', { hours: 10, low: 120 })
    expect(assignTags([a, b], rank([a, b]))).toEqual({
      A: ['fastest', 'shortest'],
      B: ['recommended', 'lowest_risk'],
    })
  })

  it('formats durations like the backend', () => {
    expect(formatDurationShort(20)).toBe('under 1 min')
    expect(formatDurationShort(3900)).toBe('1 h 05 min')
  })
})
