import { describe, expect, it } from 'vitest'

import { nextFullHour, shiftHours, tomorrowAt, wallClockIn, zoneAbbreviation } from './localTime'

// 17:20 UTC: 10:20 in Denver (MST), 12:20 in New York, 20:20 in Addis Ababa.
const NOW = new Date('2026-11-02T17:20:00Z')

describe('localTime', () => {
  it('reads the wall clock in an explicit zone', () => {
    expect(wallClockIn('America/Denver', NOW)).toBe('2026-11-02T10:20')
    expect(wallClockIn('Africa/Addis_Ababa', NOW)).toBe('2026-11-02T20:20')
  })

  it('gives the next full hour at the origin, not in the browser', () => {
    expect(nextFullHour('America/Denver', NOW)).toBe('2026-11-02T11:00')
    expect(nextFullHour('America/New_York', NOW)).toBe('2026-11-02T13:00')
    // Newfoundland is UTC−3:30: 13:50 local, so the next hour is 14:00.
    expect(nextFullHour('America/St_Johns', NOW)).toBe('2026-11-02T14:00')
  })

  it('rolls over midnight and month ends on the wall clock', () => {
    expect(shiftHours('2026-11-30T22:00', 6)).toBe('2026-12-01T04:00')
    expect(tomorrowAt(6, 'America/Denver', NOW)).toBe('2026-11-03T06:00')
  })

  it('names the zone', () => {
    expect(zoneAbbreviation('America/Denver', NOW)).toBe('MST')
  })
})
