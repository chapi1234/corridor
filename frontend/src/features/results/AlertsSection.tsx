import { Siren } from 'lucide-react'

import type { Route } from '@/api/types'
import { alertTiming, sortAlerts } from '@/domain/alerts'

import styles from './AlertsSection.module.css'

const SEVERITY_LABEL = {
  extreme: 'Extreme',
  severe: 'Severe',
  moderate: 'Moderate',
  minor: 'Minor',
  unknown: 'Unrated',
} as const

/** Official NWS alerts on the selected route, in-effect first. */
export function AlertsSection({ route }: { route: Route }) {
  if (route.alerts.length === 0) return null
  const alerts = sortAlerts(route.alerts)

  return (
    <section className={styles.section} aria-labelledby="alerts-title">
      <h2 id="alerts-title" className="label">
        <Siren size={12} aria-hidden /> NWS alerts on Route {route.id}
      </h2>
      <ul className={styles.list}>
        {alerts.map((alert) => (
          <li
            key={`${alert.id}-${alert.start_mi}`}
            className={styles.alert}
            data-active={alert.in_effect}
            title={alert.area}
          >
            <div className={styles.head}>
              <span className={styles.event}>{alert.event}</span>
              <span className={`${styles.miles} num`}>
                mi {Math.round(alert.start_mi)}–{Math.round(alert.end_mi)}
              </span>
            </div>
            <span className={styles.meta}>
              {SEVERITY_LABEL[alert.severity]} · {alertTiming(alert)}
            </span>
          </li>
        ))}
      </ul>
      <p className={styles.note}>
        Issued by the National Weather Service. Shown alongside the risk rules, not scored.
      </p>
    </section>
  )
}
