/**
 * Ribbon geometry: each checkpoint owns the stretch of road between the midpoints to its
 * neighbours (D11), so the ribbon shows exactly the miles the summary counts.
 */

import type { ScoredRoute } from '@/domain/scoring'

export interface RibbonSpan {
  index: number
  startMi: number
  endMi: number
}

export function ownedSpans(route: ScoredRoute): RibbonSpan[] {
  const checkpoints = route.route.checkpoints
  return checkpoints.map((checkpoint, index) => {
    const previous = checkpoints[index - 1]
    const next = checkpoints[index + 1]
    return {
      index,
      startMi: previous ? (previous.mile + checkpoint.mile) / 2 : 0,
      endMi: next ? (checkpoint.mile + next.mile) / 2 : route.route.distance_mi,
    }
  })
}

/** Index of the checkpoint owning ``mile`` (binary search over span ends). */
export function spanAt(spans: readonly RibbonSpan[], mile: number): number | null {
  if (spans.length === 0) return null
  let [low, high] = [0, spans.length - 1]
  while (low < high) {
    const mid = (low + high) >> 1
    if (spans[mid]!.endMi < mile) low = mid + 1
    else high = mid
  }
  return spans[low]!.index
}
