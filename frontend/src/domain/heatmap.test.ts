import { describe, expect, it } from 'vitest'

import type { Heatmap } from '@/api/types'

import {
  buildFrames,
  drawFloor,
  HEATMAP_FLOOR,
  isCalmHour,
  LOW_PRESENCE_LEVEL,
  nothingToDraw,
} from './heatmap'

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

describe('nothingToDraw', () => {
  it('reports a dry corridor on the rain layer', () => {
    const frames = buildFrames(heatmap(10), 'rain', 40_000)
    expect(nothingToDraw(frames, 0, 'rain')).toBe(true)
  })

  it('is false once any cell reaches the draw floor', () => {
    const wet = heatmap(10)
    wet.rain_in_hr_x1000[0]![2] = 120 // 0.12 in/hr: Moderate
    expect(nothingToDraw(buildFrames(wet, 'rain', 40_000), 0, 'rain')).toBe(false)
  })

  it('never calls a missing hour empty', () => {
    expect(nothingToDraw(buildFrames(heatmap(10), 'rain', 40_000), 5, 'rain')).toBe(false)
  })

  it('keeps the floor below every first threshold', () => {
    expect(drawFloor('rain')).toBeLessThan(0.1 / 2)
    expect(drawFloor('risk')).toBe(HEATMAP_FLOOR)
  })
})
