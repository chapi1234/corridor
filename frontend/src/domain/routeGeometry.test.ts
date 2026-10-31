import { describe, expect, it } from 'vitest'

import type { Checkpoint, Route } from '@/api/types'

import { RouteTrack, riskGradientStops } from './routeGeometry'

const cp = (line_fraction: number, elapsed_s: number) =>
  ({ line_fraction, elapsed_s }) as Checkpoint

describe('riskGradientStops', () => {
  it('creates hard edges only where the colour changes', () => {
    const checkpoints = [cp(0, 0), cp(0.25, 0), cp(0.5, 0), cp(1, 0)]
    const colors = ['g', 'g', 'r', 'r']
    const stops = riskGradientStops(checkpoints, (i) => colors[i]!)

    expect(stops[0]).toBe(0)
    expect(stops).toContain('r')
    const numbers = stops.filter((s): s is number => typeof s === 'number')
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b))
    expect(new Set(numbers).size).toBe(numbers.length)
    expect(numbers[1]).toBeCloseTo(0.375, 4)
    expect(stops.at(-2)).toBe(1)
  })
})

describe('RouteTrack', () => {
  const route = {
    geometry: [
      [0, 0],
      [1, 0],
      [2, 0],
    ],
    checkpoints: [cp(0, 0), cp(0.5, 600), cp(1, 3600)],
  } as unknown as Route

  it('maps elapsed time to progress through checkpoints', () => {
    const track = new RouteTrack(route)
    expect(track.fractionAtElapsed(300)).toBeCloseTo(0.25)
    expect(track.fractionAtElapsed(2100)).toBeCloseTo(0.75)
    expect(track.fractionAtElapsed(99_999)).toBe(1)
  })

  it('interpolates position and bearing along the line', () => {
    const [lon, lat, bearing] = new RouteTrack(route).pointAt(0.75)
    expect(lon).toBeCloseTo(1.5)
    expect(lat).toBeCloseTo(0)
    expect(bearing).toBeCloseTo(90)
  })
})
