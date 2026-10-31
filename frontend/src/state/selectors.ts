import { useAppStore } from './store'

import type { PlanResponse } from '@/api/types'
import { scorePlan, type ScoredPlan, type ScoredRoute } from '@/domain/scoring'

let cache: { plan: PlanResponse; override: number | null; scored: ScoredPlan } | null = null

/** Scored view of the current plan, memoised across all consumers. */
export function selectScoredPlan(
  plan: PlanResponse | null,
  override: number | null,
): ScoredPlan | null {
  if (!plan) return null
  if (cache?.plan !== plan || cache.override !== override) {
    cache = { plan, override, scored: scorePlan(plan, override) }
  }
  return cache.scored
}

export function useScoredPlan(): ScoredPlan | null {
  const plan = useAppStore((s) => s.plan)
  const override = useAppStore((s) => s.loadOverrideLb)
  return selectScoredPlan(plan, override)
}

export function useSelectedRoute(): ScoredRoute | null {
  const scored = useScoredPlan()
  const selectedId = useAppStore((s) => s.selectedRouteId)
  return scored?.routes.find((r) => r.route.id === selectedId) ?? null
}
