import { describe, expect, it } from 'vitest'

import type { DepartureAdvice, DepartureOption } from '@/api/types'

import { departureLocal, offsetLabel, optionLevel, suggestionText } from './departure'

function option(offsetH: number, miles: number[], unknown = 0): DepartureOption {
  return {
    offset_h: offsetH,
    departure: {
      utc: '2026-11-03T19:00:00Z',
      local: '2026-11-03T12:00-07:00',
      tz: 'America/Denver',
    },
    route_id: 'A',
    miles_by_level: miles,
    unknown_miles: unknown,
    average_risk: 0.5,
    duration_s: 36000,
  }
}

describe('departure advisor', () => {
  it('colours a cell by the worst level with at least a mile', () => {
    expect(optionLevel(option(0, [300, 20, 0.4, 0, 0]))).toBe(1)
    expect(optionLevel(option(0, [300, 0, 0, 0, 5]))).toBe(4)
    expect(optionLevel(option(0, [0, 0, 0, 0, 0], 300))).toBeNull()
  })

  it('labels offsets', () => {
    expect([offsetLabel(-3), offsetLabel(0), offsetLabel(6)]).toEqual([
      '−3 h',
      'As planned',
      '+6 h',
    ])
  })

  it('words a suggestion', () => {
    const advice: DepartureAdvice = {
      options: [option(0, [200, 0, 0, 80, 0]), option(6, [280, 0, 0, 0, 0])],
      suggestion: { offset_h: 6, criterion: 'severe_miles', gain_mi: 80 },
    }
    expect(suggestionText(advice)).toMatch(
      /^Leave 6 h later \(.+\): 80 fewer Severe miles on Route A\.$/,
    )
    expect(suggestionText({ ...advice, suggestion: null })).toBeNull()
  })

  it('converts an option to the form value', () => {
    expect(departureLocal(option(0, [1, 0, 0, 0, 0]))).toBe('2026-11-03T12:00')
  })
})
