import type { CriterionSlug, Factor, LoadRule, RouteTag } from '@/api/types'

import type { Level } from './risk'

export interface LevelMeta {
  level: Level
  label: string
  short: string
  /** CSS custom property holding the colour for the active theme. */
  cssVar: string
  /** Dark ink reads better on the lighter risk hues. */
  inkVar: string
}

export const LEVEL_META: Record<Level, LevelMeta> = {
  0: { level: 0, label: 'Low', short: 'LOW', cssVar: '--risk-0', inkVar: '--risk-ink-light' },
  1: { level: 1, label: 'Moderate', short: 'MOD', cssVar: '--risk-1', inkVar: '--risk-ink-light' },
  2: { level: 2, label: 'High', short: 'HIGH', cssVar: '--risk-2', inkVar: '--risk-ink-light' },
  3: { level: 3, label: 'Severe', short: 'SEV', cssVar: '--risk-3', inkVar: '--risk-ink-dark' },
  4: {
    level: 4,
    label: 'No Travel',
    short: 'NO TRAVEL',
    cssVar: '--risk-4',
    inkVar: '--risk-ink-dark',
  },
}

export const UNKNOWN_META = {
  label: 'No forecast',
  short: 'N/A',
  cssVar: '--risk-unknown',
  inkVar: '--risk-ink-dark',
} as const

export const FACTOR_LABEL: Record<Factor, string> = {
  wind: 'Wind gusts',
  rain: 'Rain',
  snow: 'Snow',
}

export const LOAD_RULE_TEXT: Record<LoadRule, string> = {
  wind_45_54_over_30k_lb: '45–54 mph gusts with a load over 30,000 lb → No Travel',
  wind_35_44_over_40k_lb: '35–44 mph gusts with a load over 40,000 lb → Severe',
}

export const CRITERION_LABEL: Record<CriterionSlug, string> = {
  no_travel_miles: 'No Travel miles',
  severe_miles: 'Severe miles',
  high_miles: 'High miles',
  average_risk: 'Average risk',
  duration: 'Travel time',
}

export const TAG_LABEL: Record<RouteTag, string> = {
  recommended: 'Recommended',
  fastest: 'Fastest',
  shortest: 'Shortest',
  lowest_risk: 'Lowest risk',
}

/** Resolve a CSS custom property to a concrete colour (MapLibre and canvas need literals). */
export function cssColor(variable: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(variable).trim() || '#888'
}
