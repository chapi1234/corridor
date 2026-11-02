import { describe, expect, it } from 'vitest'

import type { RestStop } from '@/api/types'

import { drivingAt, restAt } from './duty'

const H = 3600
const route = {
  rest_stops: [
    { kind: 'break', start_s: 8 * H, duration_s: 0.5 * H },
    { kind: 'reset', start_s: 11.5 * H, duration_s: 10 * H },
  ] as RestStop[],
}

describe('drivingAt', () => {
  it.each([
    [0, 0],
    [8, 8],
    [8.25, 8],
    [9, 8.5],
    [11.5, 11],
    [15, 11],
    [21.5, 11],
    [23.5, 13],
  ])('after %d h of trip, %d h of driving', (tripH, drivingH) => {
    expect(drivingAt(route, tripH * H)).toBeCloseTo(drivingH * H)
  })

  it('is the identity without rest', () => {
    expect(drivingAt({ rest_stops: [] }, 5 * H)).toBe(5 * H)
  })
})

describe('restAt', () => {
  it('finds the rest in progress', () => {
    expect(restAt(route, 7.9 * H)).toBeNull()
    expect(restAt(route, 8.1 * H)?.kind).toBe('break')
    expect(restAt(route, 20 * H)?.kind).toBe('reset')
    expect(restAt(route, 21.5 * H)).toBeNull()
  })
})
