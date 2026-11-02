import { describe, expect, it } from 'vitest'

import type { Heatmap } from '@/api/types'

import { buildFrames, HEATMAP_FLOOR, isCalmHour, LOW_PRESENCE_LEVEL } from './heatmap'

const MISSING = -1

/** One hour, three cells: calm, missing, and the given gust in mph. */
function heatmap(gustMph: number): Heatmap {
  return {
    base_time: '2026-01-01T00:00:00Z',
    spacing_m: 20_000,
    points: [
      [-104, 39],
      [-103, 39],
      [-102, 39],
    ],
    missing: MISSING,
    gust_mph_x10: [[100, MISSING, gustMph * 10]],
    rain_in_hr_x1000: [[0, 0, 0]],
    snow_in_hr_x100: [[0, 0, 0]],
  } as Heatmap
}

describe('buildFrames', () => {
  it('draws calm cells faintly and leaves missing cells empty', () => {
    const [weights] = buildFrames(heatmap(10), 'risk', 40_000)
    expect(weights![0]).toBeGreaterThan(HEATMAP_FLOOR)
    expect(weights![0]).toBeGreaterThan(LOW_PRESENCE_LEVEL / 5) // gust 10 sits inside Low
    expect(weights![0]).toBeLessThan(1 / 5) // still below the Moderate colour
    expect(weights![1]).toBe(0)
  })

  it('keeps raw variables proportional', () => {
    const [weights] = buildFrames(heatmap(30), 'gust', 40_000)
    expect(weights![2]).toBeCloseTo(30 / 75)
  })
})

describe('isCalmHour', () => {
  it('is calm only when every known cell is Low', () => {
    expect(isCalmHour(heatmap(10), 0, 40_000)).toBe(true)
    expect(isCalmHour(heatmap(40), 0, 40_000)).toBe(false)
  })

  it('never calls a missing hour calm', () => {
    expect(isCalmHour(heatmap(10), 5, 40_000)).toBe(false)
  })
})
