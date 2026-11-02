/**
 * Road advisories (crosswind, ice, visibility) computed per checkpoint by the backend
 * (`domain/advisories.py`). Like NWS alerts they sit beside the risk level, not in it.
 */

import type { Advisory, Route } from '@/api/types'

export type AdvisoryKind = Advisory['kind']

export const ADVISORY_LABEL: Record<AdvisoryKind, string> = {
  crosswind: 'Crosswind',
  ice: 'Ice',
  visibility: 'Low visibility',
}

export interface AdvisoryRange {
  kind: AdvisoryKind
  startMi: number
  endMi: number
  checkpoints: number
  /** Message from the first checkpoint in the range. */
  message: string
}

/** Consecutive checkpoints sharing an advisory kind, merged into mile ranges. */
export function advisoryRanges(route: Route): AdvisoryRange[] {
  const ranges: AdvisoryRange[] = []
  const open = new Map<AdvisoryKind, AdvisoryRange>()
  for (const checkpoint of route.checkpoints) {
    const here = new Map(checkpoint.advisories.map((a) => [a.kind, a.message]))
    for (const [kind, range] of open) {
      if (!here.has(kind)) {
        ranges.push(range)
        open.delete(kind)
      }
    }
    for (const [kind, message] of here) {
      const range = open.get(kind)
      if (range) {
        range.endMi = checkpoint.mile
        range.checkpoints++
      } else {
        open.set(kind, {
          kind,
          startMi: checkpoint.mile,
          endMi: checkpoint.mile,
          checkpoints: 1,
          message,
        })
      }
    }
  }
  ranges.push(...open.values())
  return ranges.sort((a, b) => a.startMi - b.startMi)
}

/** Advisory kinds present anywhere on the route, in a fixed order. */
export function advisoryKinds(route: Route): AdvisoryKind[] {
  const present = new Set(route.checkpoints.flatMap((c) => c.advisories.map((a) => a.kind)))
  return (Object.keys(ADVISORY_LABEL) as AdvisoryKind[]).filter((k) => present.has(k))
}
