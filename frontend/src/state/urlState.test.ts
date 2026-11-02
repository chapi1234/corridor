import { describe, expect, it } from 'vitest'

import type { TripDraft } from './store'
import { draftFromSearch, draftToSearch, planIdFromSearch } from './urlState'

const DRAFT: TripDraft = {
  origin: { lat: 39.7392, lon: -104.9903, label: 'Denver, CO' },
  destination: { lat: 41.8781, lon: -87.6298, label: 'Chicago, IL' },
  departureLocal: '2026-11-03T06:00',
  loadLb: 42000,
  intervalMi: 25,
  hos: true,
}

describe('urlState', () => {
  it('round-trips a draft with its plan id', () => {
    const search = draftToSearch(DRAFT, '0123456789abcdef')
    expect(draftFromSearch(search)).toEqual(DRAFT)
    expect(planIdFromSearch(search)).toBe('0123456789abcdef')
  })

  it('ignores a malformed plan id', () => {
    expect(planIdFromSearch('?p=../../etc')).toBeNull()
    expect(planIdFromSearch(draftToSearch(DRAFT))).toBeNull()
  })
})
