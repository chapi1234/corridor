import { describe, expect, it } from 'vitest'

import { formatAge, freshness } from './freshness'

const NOW = Date.parse('2026-11-02T12:00:00Z')

describe('freshness', () => {
  it('is fresh within the hour', () => {
    expect(freshness('2026-11-02T11:30:00Z', '2026-11-02T18:00:00Z', NOW)).toBe('fresh')
  })

  it('is stale after an hour while the departure is still ahead', () => {
    expect(freshness('2026-11-02T09:00:00Z', '2026-11-02T18:00:00Z', NOW)).toBe('stale')
  })

  it('is departed once the departure is past the grace period', () => {
    expect(freshness('2026-11-02T11:59:00Z', '2026-11-02T11:56:00Z', NOW)).toBe('fresh')
    expect(freshness('2026-11-01T09:00:00Z', '2026-11-02T11:00:00Z', NOW)).toBe('departed')
  })
})

describe('formatAge', () => {
  it.each([
    [20_000, '1 min'],
    [45 * 60_000, '45 min'],
    [3 * 3600_000, '3 h'],
    [3 * 86400_000, '3 days'],
  ])('%i ms → %s', (ms, text) => {
    expect(formatAge(ms)).toBe(text)
  })
})
