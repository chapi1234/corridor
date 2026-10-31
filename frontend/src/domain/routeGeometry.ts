/** Geometry helpers for drawing routes: progress lookups and risk gradients. */

import type { Checkpoint, Route } from '@/api/types'
import { lerp } from '@/lib/math'

const EARTH_RADIUS_M = 6_371_008.8
const toRad = (deg: number) => (deg * Math.PI) / 180

export function haversineM([lon1, lat1]: number[], [lon2, lat2]: number[]): number {
  const dPhi = toRad(lat2! - lat1!)
  const dLambda = toRad(lon2! - lon1!)
  const h =
    Math.sin(dPhi / 2) ** 2 +
    Math.cos(toRad(lat1!)) * Math.cos(toRad(lat2!)) * Math.sin(dLambda / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

function bisectRight(values: ArrayLike<number>, target: number): number {
  let lo = 0
  let hi = values.length
  while (lo < hi) {
    const mid = (lo + hi) >>> 1
    if (values[mid]! <= target) lo = mid + 1
    else hi = mid
  }
  return lo
}

/** A route line indexed by progress (0..1) and by elapsed driving time. */
export class RouteTrack {
  private readonly coords: number[][]
  private readonly fractions: Float64Array
  private readonly cpElapsed: number[]
  private readonly cpFractions: number[]

  constructor(route: Route) {
    this.coords = route.geometry
    const cumulative = new Float64Array(this.coords.length)
    for (let i = 1; i < this.coords.length; i++) {
      cumulative[i] = cumulative[i - 1]! + haversineM(this.coords[i - 1]!, this.coords[i]!)
    }
    const total = cumulative[cumulative.length - 1] || 1
    this.fractions = cumulative.map((d) => d / total)
    this.cpElapsed = route.checkpoints.map((c) => c.elapsed_s)
    this.cpFractions = route.checkpoints.map((c) => c.line_fraction)
  }

  get durationS(): number {
    return this.cpElapsed.at(-1) ?? 0
  }

  /** [lon, lat, bearingDeg] at progress ``fraction`` along the line. */
  pointAt(fraction: number): [number, number, number] {
    const f = Math.min(Math.max(fraction, 0), 1)
    const i = Math.min(Math.max(bisectRight(this.fractions, f) - 1, 0), this.coords.length - 2)
    const [f0, f1] = [this.fractions[i]!, this.fractions[i + 1]!]
    const t = f1 > f0 ? (f - f0) / (f1 - f0) : 0
    const [a, b] = [this.coords[i]!, this.coords[i + 1]!]
    const bearing = (Math.atan2(b[0]! - a[0]!, b[1]! - a[1]!) * 180) / Math.PI
    return [lerp(a[0]!, b[0]!, t), lerp(a[1]!, b[1]!, t), bearing]
  }

  /** Progress at ``elapsedS`` seconds after departure, interpolated between checkpoints. */
  fractionAtElapsed(elapsedS: number): number {
    const times = this.cpElapsed
    if (elapsedS <= 0) return 0
    if (elapsedS >= this.durationS) return 1
    const i = bisectRight(times, elapsedS) - 1
    const span = times[i + 1]! - times[i]!
    const t = span > 0 ? (elapsedS - times[i]!) / span : 0
    return lerp(this.cpFractions[i]!, this.cpFractions[i + 1]!, t)
  }
}

/**
 * MapLibre ``line-gradient`` stops colouring each checkpoint's owned stretch of road with
 * hard edges at the midpoints between checkpoints (D11).
 */
export function riskGradientStops(
  checkpoints: readonly Checkpoint[],
  colorFor: (index: number) => string,
): (number | string)[] {
  const EDGE = 1e-5
  const stops: (number | string)[] = [0, colorFor(0)]
  let lastStop = 0
  for (let i = 1; i < checkpoints.length; i++) {
    const [previous, current] = [colorFor(i - 1), colorFor(i)]
    if (previous === current) continue
    const boundary = (checkpoints[i - 1]!.line_fraction + checkpoints[i]!.line_fraction) / 2
    const before = Math.max(boundary - EDGE, lastStop + EDGE)
    const after = before + EDGE
    if (after >= 1) break
    stops.push(before, previous, after, current)
    lastStop = after
  }
  stops.push(1, colorFor(checkpoints.length - 1))
  return stops
}
