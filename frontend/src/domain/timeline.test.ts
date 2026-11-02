import { describe, expect, it } from 'vitest'

import type { PlanResponse, Route } from '@/api/types'

import { elapsedAtHour, hourOf, hourOfCheckpoint, mileAtElapsed } from './timeline'

const route = {
  distance_mi: 100,
  duration_s: 7200,
  rest_stops: [],
  checkpoints: [
    { mile: 0, elapsed_s: 0, driving_s: 0, eta: { utc: '2026-11-01T14:30:00Z' } },
    { mile: 50, elapsed_s: 2400, driving_s: 2400, eta: { utc: '2026-11-01T15:10:00Z' } },
    { mile: 100, elapsed_s: 7200, driving_s: 7200, eta: { utc: '2026-11-01T16:30:00Z' } },
  ],
} as unknown as Route

const plan = {
  departure: { utc: '2026-11-01T14:30:00Z' },
  heatmap: { base_time: '2026-11-01T14:00:00Z' },
} as unknown as PlanResponse

describe('mileAtElapsed', () => {
  it.each([
    [-60, 0],
    [0, 0],
    [1200, 25],
    [2400, 50],
    [4800, 75],
    [7200, 100],
    [9000, 100],
  ])('after %d s the truck is at mile %d', (elapsed, mile) => {
    expect(mileAtElapsed(route, elapsed)).toBeCloseTo(mile)
  })
})

describe('mileAtElapsed with rest', () => {
  const rested = {
    ...route,
    duration_s: 7200 + 1800,
    rest_stops: [{ kind: 'break', start_s: 2400, duration_s: 1800 }],
  } as unknown as Route

  it('parks the truck while it rests', () => {
    expect(mileAtElapsed(rested, 2400)).toBeCloseTo(50)
    expect(mileAtElapsed(rested, 3600)).toBeCloseTo(50)
    expect(mileAtElapsed(rested, 4200 + 2400)).toBeCloseTo(75)
  })
})

describe('forecast hours', () => {
  it('measures hours from the floored departure hour', () => {
    expect(hourOf(plan, plan.departure.utc)).toBe(0.5)
    expect(elapsedAtHour(plan, 0)).toBe(-1800)
    expect(elapsedAtHour(plan, 2)).toBe(5400)
  })

  it('rounds a checkpoint ETA to the nearest frame', () => {
    expect(hourOfCheckpoint(plan, route, 1)).toBe(1)
    expect(hourOfCheckpoint(plan, route, 2)).toBe(3)
  })
})
