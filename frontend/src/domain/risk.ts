/**
 * Client mirror of backend/corridor/domain/risk.py, used to re-score instantly when the
 * load weight changes. Parity is enforced by shared/risk_cases.json (risk.test.ts).
 * Decision references (D2, D3, ...) are interpretations of the brief; README.md lists the key ones.
 */

import type { Factor, LoadRule } from '@/api/types'

export type Level = 0 | 1 | 2 | 3 | 4

export const LOW: Level = 0
export const MODERATE: Level = 1
export const HIGH: Level = 2
export const SEVERE: Level = 3
export const NO_TRAVEL: Level = 4
export const LEVELS: readonly Level[] = [LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL]

export interface Band {
  level: Level
  lower: number
  /** For the open-ended top band, a soft cap used only for the continuous index. */
  upper: number
}

/** Listed top-down: the first band whose lower edge is met wins. */
export const WIND_BANDS_MPH: readonly Band[] = [
  { level: NO_TRAVEL, lower: 55, upper: 75 },
  { level: SEVERE, lower: 45, upper: 55 },
  { level: HIGH, lower: 35, upper: 45 },
  { level: MODERATE, lower: 25, upper: 35 },
  { level: LOW, lower: 0, upper: 25 },
]
export const RAIN_BANDS_IN_HR: readonly Band[] = [
  { level: NO_TRAVEL, lower: 1.0, upper: 2.0 },
  { level: SEVERE, lower: 0.5, upper: 1.0 },
  { level: HIGH, lower: 0.25, upper: 0.5 },
  { level: MODERATE, lower: 0.1, upper: 0.25 },
  { level: LOW, lower: 0, upper: 0.1 },
]
export const SNOW_BANDS_IN_HR: readonly Band[] = [
  { level: NO_TRAVEL, lower: 3.0, upper: 5.0 },
  { level: SEVERE, lower: 2.0, upper: 3.0 },
  { level: HIGH, lower: 1.0, upper: 2.0 },
  { level: MODERATE, lower: 0.5, upper: 1.0 },
  { level: LOW, lower: 0, upper: 0.5 },
]

export const NO_TRAVEL_LOAD_THRESHOLD_LB = 30_000
export const SEVERE_LOAD_THRESHOLD_LB = 40_000
const MAX_BAND_FRACTION = 0.999

/** Wind edges are lower-inclusive everywhere, including No Travel at >=55 mph (D3). */
export function windBand(mph: number): Band {
  return WIND_BANDS_MPH.find((band) => mph >= band.lower) ?? WIND_BANDS_MPH.at(-1)!
}

/** Precipitation edges are lower-inclusive except No Travel, which is strict (D2). */
export function precipitationBand(rate: number, bands: readonly Band[]): Band {
  const [noTravel, ...lower] = bands
  if (rate > noTravel!.lower) return noTravel!
  return lower.find((band) => rate >= band.lower) ?? bands.at(-1)!
}

export function applyLoadRules(
  band: Band,
  loadLb: number,
): { level: Level; loadRule: LoadRule | null } {
  if (band.level === SEVERE && loadLb > NO_TRAVEL_LOAD_THRESHOLD_LB) {
    return { level: NO_TRAVEL, loadRule: 'wind_45_54_over_30k_lb' }
  }
  if (band.level === HIGH && loadLb > SEVERE_LOAD_THRESHOLD_LB) {
    return { level: SEVERE, loadRule: 'wind_35_44_over_40k_lb' }
  }
  return { level: band.level, loadRule: null }
}

function bandFraction(value: number, band: Band): number {
  const fraction = (value - band.lower) / (band.upper - band.lower)
  return Math.min(Math.max(fraction, 0), MAX_BAND_FRACTION)
}

export interface FactorAssessment {
  level: Level
  index: number
}

export interface Classification {
  level: Level
  /** Continuous risk in [0, 5): Math.floor(index) === level (D16). */
  index: number
  driver: Factor
  factors: Record<Factor, FactorAssessment>
  loadRule: LoadRule | null
}

export function classify(
  gustMph: number,
  rainInHr: number,
  snowInHr: number,
  loadLb: number,
): Classification {
  const wind = windBand(gustMph)
  const { level: windLevel, loadRule } = applyLoadRules(wind, loadLb)
  const rain = precipitationBand(rainInHr, RAIN_BANDS_IN_HR)
  const snow = precipitationBand(snowInHr, SNOW_BANDS_IN_HR)

  const factors: Record<Factor, FactorAssessment> = {
    wind: { level: windLevel, index: windLevel + bandFraction(gustMph, wind) },
    rain: { level: rain.level, index: rain.level + bandFraction(rainInHr, rain) },
    snow: { level: snow.level, index: snow.level + bandFraction(snowInHr, snow) },
  }
  // Ties resolve in this order, matching Python's max() over the dict (D9).
  const order: Factor[] = ['wind', 'rain', 'snow']
  const driver = order.reduce((best, f) => (factors[f].index > factors[best].index ? f : best))
  const worst = factors[driver]
  return { level: worst.level, index: worst.index, driver, factors, loadRule }
}
