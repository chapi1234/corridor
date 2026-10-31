/**
 * Heatmap frames: decode the quantised corridor weather and derive per-hour weights for
 * the selected variable. Weights are normalised to [0, 1] so that, with kernels sized to
 * the grid spacing, MapLibre's heatmap density approximates the weight itself and the
 * colour ramp can be keyed to exact rule thresholds.
 */

import type { Heatmap } from '@/api/types'

import { classify } from './risk'

export type HeatmapVariable = 'risk' | 'gust' | 'rain' | 'snow'

export interface VariableScale {
  label: string
  unit: string
  /** Value that maps to weight 1. */
  max: number
  /** Thresholds (in variable units) where the Moderate/High/Severe/No Travel colours start. */
  thresholds: [number, number, number, number]
}

export const VARIABLE_SCALES: Record<HeatmapVariable, VariableScale> = {
  risk: { label: 'Risk', unit: 'level', max: 5, thresholds: [1, 2, 3, 4] },
  gust: { label: 'Gusts', unit: 'mph', max: 75, thresholds: [25, 35, 45, 55] },
  rain: { label: 'Rain', unit: 'in/hr', max: 2, thresholds: [0.1, 0.25, 0.5, 1.0] },
  snow: { label: 'Snow', unit: 'in/hr', max: 5, thresholds: [0.5, 1, 2, 3] },
}

const GUST_SCALE = 10
const RAIN_SCALE = 1000
const SNOW_SCALE = 100

/** weights[hour][point] in [0, 1]; missing data has weight 0. */
export type Frames = Float32Array[]

export function buildFrames(heatmap: Heatmap, variable: HeatmapVariable, loadLb: number): Frames {
  const { max } = VARIABLE_SCALES[variable]
  const points = heatmap.points.length

  return heatmap.gust_mph_x10.map((gustRow, hour) => {
    const rainRow = heatmap.rain_in_hr_x1000[hour]!
    const snowRow = heatmap.snow_in_hr_x100[hour]!
    const weights = new Float32Array(points)
    for (let i = 0; i < points; i++) {
      const gustQ = gustRow[i]!
      if (gustQ === heatmap.missing) continue
      const gust = gustQ / GUST_SCALE
      const rain = rainRow[i]! / RAIN_SCALE
      const snow = snowRow[i]! / SNOW_SCALE
      const value =
        variable === 'risk'
          ? classify(gust, rain, snow, loadLb).index
          : variable === 'gust'
            ? gust
            : variable === 'rain'
              ? rain
              : snow
      weights[i] = Math.min(value / max, 1)
    }
    return weights
  })
}

/** Weight below which nothing is drawn: calm conditions stay transparent. */
export const HEATMAP_FLOOR = 0.06

/** Kernel radius as a multiple of grid spacing; tuned so neighbouring kernels blend evenly. */
export const KERNEL_SPACING_RATIO = 1.25
/**
 * Peak density of a uniform hex field with that kernel (MapLibre's kernel is
 * exp(-4.5 r²/R²)); dividing by it makes density ≈ weight across the field.
 */
export const UNIFORM_FIELD_DENSITY = 1.2
