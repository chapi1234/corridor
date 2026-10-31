import { describe, expect, it } from 'vitest'

import type { ScoredRoute } from '@/domain/scoring'

import { ownedSpans, spanAt } from './ribbonLayout'

function routeWithMiles(miles: number[], distance: number): ScoredRoute {
  return {
    route: { distance_mi: distance, checkpoints: miles.map((mile, index) => ({ index, mile })) },
  } as unknown as ScoredRoute
}

describe('ownedSpans', () => {
  it('splits ownership at midpoints and covers the whole route', () => {
    const spans = ownedSpans(routeWithMiles([0, 25, 50, 62], 62))
    expect(spans.map((s) => [s.startMi, s.endMi])).toEqual([
      [0, 12.5],
      [12.5, 37.5],
      [37.5, 56],
      [56, 62],
    ])
  })
})

describe('spanAt', () => {
  const spans = ownedSpans(routeWithMiles([0, 25, 50, 62], 62))

  it.each([
    [0, 0],
    [12.4, 0],
    [12.6, 1],
    [40, 2],
    [61.9, 3],
    [80, 3],
  ])('mile %d belongs to checkpoint %d', (mile, index) => {
    expect(spanAt(spans, mile)).toBe(index)
  })

  it('returns null without checkpoints', () => {
    expect(spanAt([], 3)).toBeNull()
  })
})
