import { useCallback, useEffect, useRef } from 'react'

import { usePlanMutation } from '@/api/queries'
import type { PlanRequest } from '@/api/types'
import { useAppStore } from '@/state/store'
import { toPlanRequest } from '@/state/tripRequest'
import { draftFromSearch, draftToSearch } from '@/state/urlState'

/**
 * Owns the plan request lifecycle: submit, show the result, mirror the trip into the URL,
 * and replay a shared URL on first load.
 */
export function useTripPlanner() {
  const mutation = usePlanMutation((plan) => {
    const { showPlan, draft } = useAppStore.getState()
    showPlan(plan)
    window.history.replaceState(null, '', `${window.location.pathname}${draftToSearch(draft)}`)
  })
  const { mutate } = mutation

  const submit = useCallback((request: PlanRequest) => mutate(request), [mutate])

  const replayed = useRef(false)
  useEffect(() => {
    if (replayed.current) return
    replayed.current = true
    const draft = draftFromSearch(window.location.search)
    if (!draft) return
    useAppStore.getState().updateDraft(draft)
    const request = toPlanRequest(draft)
    if (request) mutate(request)
  }, [mutate])

  return { submit, pending: mutation.isPending, error: mutation.error }
}
