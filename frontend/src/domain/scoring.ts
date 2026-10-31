/**
 * A "scored" view of a plan: risk per checkpoint plus route summaries and ranking.
 * Normally this is exactly the server's result; for a what-if load it is recomputed
 * client-side from the raw ETA weather already in the response (no request).
 */

import type { Checkpoint, PlanResponse, Route, RouteTag } from '@/api/types'

import { assignTags, rank, summarize, type Ranking, type RouteRisk } from './ranking'
import { classify, type Classification, type Level } from './risk'

export interface ScoredCheckpoint {
  checkpoint: Checkpoint
  risk: Classification | null
}

export interface ScoredRoute {
  route: Route
  checkpoints: ScoredCheckpoint[]
  risk: RouteRisk
  tags: RouteTag[]
}

export interface ScoredPlan {
  plan: PlanResponse
  loadLb: number
  isWhatIf: boolean
  routes: ScoredRoute[]
  ranking: Ranking
}

export function fromServer(plan: PlanResponse): ScoredPlan {
  const rec = plan.recommendation
  return {
    plan,
    loadLb: plan.inputs.load_lb,
    isWhatIf: false,
    routes: plan.routes.map((route) => ({
      route,
      checkpoints: route.checkpoints.map((checkpoint) => ({
        checkpoint,
        risk: checkpoint.risk
          ? {
              level: checkpoint.risk.level as Level,
              index: checkpoint.risk.index,
              driver: checkpoint.risk.driver,
              factors: {
                wind: {
                  level: checkpoint.risk.factors.wind as Level,
                  index: checkpoint.risk.factors.wind,
                },
                rain: {
                  level: checkpoint.risk.factors.rain as Level,
                  index: checkpoint.risk.factors.rain,
                },
                snow: {
                  level: checkpoint.risk.factors.snow as Level,
                  index: checkpoint.risk.factors.snow,
                },
              },
              loadRule: checkpoint.risk.load_rule,
            }
          : null,
      })),
      risk: {
        routeId: route.id,
        distanceMi: route.distance_mi,
        durationS: route.duration_s,
        milesByLevel: route.summary.miles_by_level as RouteRisk['milesByLevel'],
        unknownMiles: route.summary.unknown_miles,
        averageRisk: route.summary.average_risk,
      },
      tags: route.tags,
    })),
    ranking: {
      order: rec.order,
      recommended: rec.route_id,
      competitor: rec.competitor_id,
      deciding: rec.deciding_criterion,
      beatsOn: rec.beats_on,
      keys: rec.keys as Ranking['keys'],
      reason: rec.reason,
      noSafeRoute: rec.no_safe_route,
    },
  }
}

export function rescore(plan: PlanResponse, loadLb: number): ScoredPlan {
  const routes = plan.routes.map((route) => {
    const checkpoints = route.checkpoints.map((checkpoint) => ({
      checkpoint,
      risk: checkpoint.weather
        ? classify(
            checkpoint.weather.gust_mph,
            checkpoint.weather.rain_in_hr,
            checkpoint.weather.snow_in_hr,
            loadLb,
          )
        : null,
    }))
    const risk = summarize(
      route.id,
      checkpoints.map(({ checkpoint, risk: r }) => ({
        ownedMiles: checkpoint.owned_miles,
        level: r?.level ?? null,
      })),
      route.distance_mi,
      route.duration_s,
    )
    return { route, checkpoints, risk }
  })
  const ranking = rank(routes.map((r) => r.risk))
  const tags = assignTags(
    routes.map((r) => r.risk),
    ranking,
  )
  return {
    plan,
    loadLb,
    isWhatIf: true,
    routes: routes.map((r) => ({ ...r, tags: tags[r.route.id] ?? [] })),
    ranking,
  }
}

export function scorePlan(plan: PlanResponse, loadOverrideLb: number | null): ScoredPlan {
  return loadOverrideLb === null || loadOverrideLb === plan.inputs.load_lb
    ? fromServer(plan)
    : rescore(plan, loadOverrideLb)
}

export function worstCheckpoint(route: ScoredRoute): ScoredCheckpoint | null {
  let worst: ScoredCheckpoint | null = null
  for (const scored of route.checkpoints) {
    if (scored.risk && (!worst?.risk || scored.risk.index > worst.risk.index)) worst = scored
  }
  return worst
}
