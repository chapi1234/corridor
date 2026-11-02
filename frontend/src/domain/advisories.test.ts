import { describe, expect, it } from 'vitest'

import type { Advisory, Checkpoint, Route } from '@/api/types'

import { advisoryKinds, advisoryRanges } from './advisories'

function route(...perCheckpoint: Advisory['kind'][][]): Route {
  const checkpoints = perCheckpoint.map(
    (kinds, i) =>
      ({
        mile: i * 25,
        advisories: kinds.map((kind) => ({ kind, message: `${kind} at ${i * 25}` })),
      }) as unknown as Checkpoint,
  )
  return { checkpoints } as Route
}

describe('advisoryRanges', () => {
  it('merges consecutive checkpoints and splits on gaps', () => {
    const ranges = advisoryRanges(route(['ice'], ['ice', 'crosswind'], [], ['ice']))
    expect(ranges.map((r) => [r.kind, r.startMi, r.endMi, r.checkpoints])).toEqual([
      ['ice', 0, 25, 2],
      ['crosswind', 25, 25, 1],
      ['ice', 75, 75, 1],
    ])
    expect(ranges[0]!.message).toBe('ice at 0')
  })

  it('lists kinds in a fixed order', () => {
    expect(advisoryKinds(route(['visibility'], ['crosswind']))).toEqual(['crosswind', 'visibility'])
  })
})
