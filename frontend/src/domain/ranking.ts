/**
 * Client mirror of backend/corridor/domain/ranking.py (D10-D13). Used only to re-rank
 * instantly for a what-if load; fresh plans use the server's ranking.
 */

import type { CriterionSlug, RouteTag } from '@/api/types'
import { pyRound } from '@/lib/math'

import { LEVELS, NO_TRAVEL, SEVERE, HIGH, type Level } from './risk'

export const CRITERIA: readonly CriterionSlug[] = [
  'no_travel_miles',
  'severe_miles',
  'high_miles',
  'average_risk',
  'duration',
]
const AVERAGE_RISK_STEP = 0.05
const UNKNOWN_AVERAGE_KEY = Number.MAX_SAFE_INTEGER

export interface RiskSegment {
  ownedMiles: number
  level: Level | null
}

export interface RouteRisk {
  routeId: string
  distanceMi: number
  durationS: number
  milesByLevel: [number, number, number, number, number]
  unknownMiles: number
  averageRisk: number | null
}

export type RankKey = [number, number, number, number, number]

export interface Ranking {
  order: string[]
  recommended: string
  competitor: string | null
  deciding: CriterionSlug | null
  beatsOn: Record<string, CriterionSlug | null>
  keys: Record<string, RankKey>
  reason: string
  noSafeRoute: boolean
}

export function summarize(
  routeId: string,
  segments: Iterable<RiskSegment>,
  distanceMi: number,
  durationS: number,
): RouteRisk {
  const milesByLevel: RouteRisk['milesByLevel'] = [0, 0, 0, 0, 0]
  let unknownMiles = 0
  for (const segment of segments) {
    if (segment.level === null) unknownMiles += segment.ownedMiles
    else milesByLevel[segment.level] += segment.ownedMiles
  }
  const known = milesByLevel.reduce((a, b) => a + b, 0)
  const weighted = LEVELS.reduce<number>((sum, level) => sum + level * milesByLevel[level], 0)
  return {
    routeId,
    distanceMi,
    durationS,
    milesByLevel,
    unknownMiles,
    averageRisk: known > 0 ? weighted / known : null,
  }
}

export function rankKey(route: RouteRisk): RankKey {
  const m = route.milesByLevel
  return [
    pyRound(m[NO_TRAVEL]),
    pyRound(m[SEVERE]),
    pyRound(m[HIGH]),
    route.averageRisk === null
      ? UNKNOWN_AVERAGE_KEY
      : pyRound(route.averageRisk / AVERAGE_RISK_STEP),
    pyRound(route.durationS),
  ]
}

function compareKeys(a: RankKey, b: RankKey): number {
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return a[i]! - b[i]!
  }
  return 0
}

export function rank(routes: readonly RouteRisk[]): Ranking {
  if (routes.length === 0) throw new Error('Cannot rank an empty set of routes')
  const keys = Object.fromEntries(routes.map((r) => [r.routeId, rankKey(r)]))
  const ordered = [...routes].sort((a, b) => compareKeys(keys[a.routeId]!, keys[b.routeId]!))
  const [best, ...others] = ordered as [RouteRisk, ...RouteRisk[]]

  const firstDifference = (other: RouteRisk): CriterionSlug | null => {
    const bestKey = keys[best.routeId]!
    const otherKey = keys[other.routeId]!
    const index = bestKey.findIndex((value, i) => value !== otherKey[i])
    return index === -1 ? null : CRITERIA[index]!
  }
  const beatsOn = Object.fromEntries(others.map((o) => [o.routeId, firstDifference(o)]))
  const competitor = pickCompetitor(best, others)
  const deciding = competitor ? (beatsOn[competitor.routeId] ?? null) : null

  return {
    order: ordered.map((r) => r.routeId),
    recommended: best.routeId,
    competitor: competitor?.routeId ?? null,
    deciding,
    beatsOn,
    keys,
    reason: explain(best, competitor, deciding),
    noSafeRoute: routes.every((r) => keys[r.routeId]![0] > 0),
  }
}

function pickCompetitor(best: RouteRisk, others: RouteRisk[]): RouteRisk | null {
  if (others.length === 0) return null
  const fastest = others.reduce((a, b) => (b.durationS < a.durationS ? b : a))
  return fastest.durationS < best.durationS ? fastest : others[0]!
}

export function explain(
  best: RouteRisk,
  competitor: RouteRisk | null,
  deciding: CriterionSlug | null,
): string {
  if (!competitor) return 'Only one route is available for this trip.'
  const other = `Route ${competitor.routeId}`
  if (deciding === null) {
    return `Routes are equivalent on every criterion; Route ${best.routeId} is listed first.`
  }
  const index = CRITERIA.indexOf(deciding)
  const bestKey = rankKey(best)
  const diff = rankKey(competitor)[index]! - bestKey[index]!

  switch (deciding) {
    case 'no_travel_miles':
    case 'severe_miles': {
      const label = deciding === 'no_travel_miles' ? 'No Travel' : 'Severe'
      return bestKey[index] === 0
        ? `Avoids ${diff} ${label} miles that ${other} crosses.`
        : `${diff} fewer ${label} miles than ${other}.`
    }
    case 'high_miles':
      return `Same Severe exposure as ${other}, but ${diff} fewer High miles.`
    case 'average_risk': {
      const otherAvg =
        competitor.averageRisk === null ? 'unknown' : competitor.averageRisk.toFixed(2)
      return `Lower overall weather risk than ${other} (average ${best.averageRisk!.toFixed(2)} vs ${otherAvg}).`
    }
    case 'duration':
      return `Equal weather risk to ${other}, and ${formatDurationShort(diff)} faster.`
  }
}

export function assignTags(
  routes: readonly RouteRisk[],
  ranking: Ranking,
): Record<string, RouteTag[]> {
  const tags: Record<string, RouteTag[]> = Object.fromEntries(routes.map((r) => [r.routeId, []]))
  const minBy = (pick: (r: RouteRisk) => number, pool: readonly RouteRisk[] = routes) =>
    pool.reduce((a, b) => (pick(b) < pick(a) ? b : a))

  tags[ranking.recommended]!.push('recommended')
  tags[minBy((r) => r.durationS).routeId]!.push('fastest')
  tags[minBy((r) => r.distanceMi).routeId]!.push('shortest')
  const rated = routes.filter((r) => r.averageRisk !== null)
  if (rated.length > 0) tags[minBy((r) => r.averageRisk!, rated).routeId]!.push('lowest_risk')
  return tags
}

/** Matches the backend's format_duration for identical explanation text. */
export function formatDurationShort(seconds: number): string {
  if (seconds < 60) return 'under 1 min'
  const totalMinutes = pyRound(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours === 0 ? `${minutes} min` : `${hours} h ${String(minutes).padStart(2, '0')} min`
}
