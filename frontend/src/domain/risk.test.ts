import { describe, expect, it } from 'vitest'

import cases from '@shared/risk_cases.json'

import { classify } from './risk'

describe('classify (parity with backend via shared/risk_cases.json)', () => {
  it.each(cases.cases.map((c) => [c.name, c] as const))('%s', (_, c) => {
    const result = classify(c.gust, c.rain, c.snow, c.load)
    expect(result.level).toBe(c.level)
    expect(result.driver).toBe(c.driver)
    expect(result.loadRule).toBe(c.load_rule)
  })

  it('keeps the continuous index inside its level', () => {
    for (let gust = 0; gust <= 90; gust += 0.7) {
      for (const load of [0, 30_001, 40_001]) {
        const { level, index } = classify(gust, 0, 0, load)
        expect(Math.floor(index)).toBe(level)
      }
    }
  })
})
