import { beforeEach, describe, expect, it } from 'vitest'

import type { PlanResponse } from '@/api/types'

import { useAppStore } from './store'

const plan = { recommendation: { route_id: 'A' } } as PlanResponse

describe('edit flow', () => {
  beforeEach(() => useAppStore.setState({ plan: null, editing: true }))

  it('returns to the results without re-planning', () => {
    useAppStore.getState().showPlan(plan)
    useAppStore.getState().editTrip()
    expect(useAppStore.getState().editing).toBe(true)
    useAppStore.getState().cancelEdit()
    expect(useAppStore.getState().editing).toBe(false)
  })

  it('stays on the form when there is no plan to go back to', () => {
    useAppStore.getState().cancelEdit()
    expect(useAppStore.getState().editing).toBe(true)
  })
})
