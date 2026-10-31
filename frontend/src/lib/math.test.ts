import { describe, expect, it } from 'vitest'

import { pyRound } from './math'

describe('pyRound', () => {
  it.each([
    [0.5, 0],
    [1.5, 2],
    [2.5, 2],
    [10.5, 10],
    [10.51, 11],
    [-0.5, 0],
    [-1.5, -2],
    [3.2, 3],
  ])('pyRound(%d) = %d', (value, expected) => {
    expect(pyRound(value)).toBe(expected)
  })
})
