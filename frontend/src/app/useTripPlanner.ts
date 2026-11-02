import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '@/api/client'
import { usePlanMutation } from '@/api/queries'
import type { PlanRequest } from '@/api/types'
import { useAppStore } from '@/state/store'
import { toPlanRequest } from '@/state/tripRequest'
import { draftFromSearch, draftToSearch, planIdFromSearch } from '@/state/urlState'

/**
 * Owns the plan request lifecycle: submit, show the result, mirror the trip into the URL,
 * and on first load show a shared plan's snapshot, or replay its inputs if it has expired.
 */
export function useTripPlanner() {
  const mutation = usePlanMutation((plan) => {
    const { showPlan, draft } = useAppStore.getState()
    showPlan(plan)
    const search = draftToSearch(draft, plan.plan_id)
    window.history.replaceState(null, '', `${window.location.pathname}${search}`)
  })
  const { mutate } = mutation
  const [opening, setOpening] = useState(false)

  const submit = useCallback((request: PlanRequest) => mutate(request), [mutate])

  /** Re-plan the current trip with live weather. */
  const refresh = useCallback(() => {
    const request = toPlanRequest(useAppStore.getState().draft)
    if (request) mutate(request)
  }, [mutate])

  const replayed = useRef(false)
  useEffect(() => {
    if (replayed.current) return
    replayed.current = true
    const draft = draftFromSearch(window.location.search)
    if (!draft) return
    useAppStore.getState().updateDraft(draft)
    const request = toPlanRequest(draft)
    const planId = planIdFromSearch(window.location.search)
    if (!planId) {
      if (request) mutate(request)
      return
    }
    setOpening(true)
    api
      .snapshot(planId)
      .then((plan) => useAppStore.getState().showPlan(plan))
      .catch(() => request && mutate(request))
      .finally(() => setOpening(false))
  }, [mutate])

  return {
    submit,
    refresh,
    pending: mutation.isPending || opening,
    error: mutation.error,
  }
}
