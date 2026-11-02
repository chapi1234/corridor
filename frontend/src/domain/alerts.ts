/**
 * Official NWS alerts along a route. They are shown beside the rule-based risk, never
 * mixed into it (mirrors backend `domain/alerts.py`).
 */

import type { Route, RouteAlert } from '@/api/types'

import { formatLocal } from './format'

const SEVERITY_ORDER: Record<RouteAlert['severity'], number> = {
  extreme: 0,
  severe: 1,
  moderate: 2,
  minor: 3,
  unknown: 4,
}

/** In-effect first, then most severe, then route order. */
export function sortAlerts(alerts: readonly RouteAlert[]): RouteAlert[] {
  return [...alerts].sort(
    (a, b) =>
      Number(b.in_effect) - Number(a.in_effect) ||
      SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] ||
      a.start_mi - b.start_mi,
  )
}

/** Distinct events in effect while the truck passes, most important first. */
export function activeEvents(route: Route): string[] {
  return [...new Set(sortAlerts(route.alerts.filter((a) => a.in_effect)).map((a) => a.event))]
}

export function alertsAtMile(route: Route, mile: number): RouteAlert[] {
  return sortAlerts(route.alerts.filter((a) => a.start_mi <= mile && mile <= a.end_mi))
}

/** When the hazard runs relative to the truck's pass through its area. */
export function alertTiming(alert: RouteAlert): string {
  const pass = `You pass ${formatLocal(alert.enter)}`
  if (alert.in_effect) {
    return alert.ends ? `${pass}, in effect until ${formatLocal(alert.ends)}` : `${pass}, in effect`
  }
  if (alert.ends && Date.parse(alert.ends.utc) < Date.parse(alert.enter.utc)) {
    return `Ends ${formatLocal(alert.ends)}, before you arrive`
  }
  return alert.starts ? `Starts ${formatLocal(alert.starts)}, after you pass` : pass
}
