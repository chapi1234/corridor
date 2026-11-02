import { Siren, TriangleAlert } from 'lucide-react'

import type { Route } from '@/api/types'
import { ADVISORY_LABEL, advisoryRanges } from '@/domain/advisories'
import { alertTiming, sortAlerts } from '@/domain/alerts'

import styles from './AlertsSection.module.css'

const SEVERITY_LABEL = {
  extreme: 'Extreme',
  severe: 'Severe',
  moderate: 'Moderate',
  minor: 'Minor',
  unknown: 'Unrated',
} as const

/**
 * Hazards on the selected route that the risk rules don't score: official NWS alerts
 * (in effect first) and computed road advisories.
 */
export function AlertsSection({ route }: { route: Route }) {
  const alerts = sortAlerts(route.alerts)
  const advisories = advisoryRanges(route)
  if (alerts.length === 0 && advisories.length === 0) return null

  return (
    <section className={styles.section} aria-labelledby="hazards-title">
      <h2 id="hazards-title" className="label">
        Also on Route {route.id}
      </h2>

      {alerts.length > 0 && (
        <>
          <h3 className={styles.group} data-kind="nws">
            <Siren size={12} aria-hidden /> NWS alerts
          </h3>
          <ul className={styles.list}>
            {alerts.map((alert) => (
              <li
                key={`${alert.id}-${alert.start_mi}`}
                className={styles.item}
                data-kind="nws"
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
        </>
      )}

      {advisories.length > 0 && (
        <>
          <h3 className={styles.group} data-kind="advisory">
            <TriangleAlert size={12} aria-hidden /> Road advisories
          </h3>
          <ul className={styles.list}>
            {advisories.map((range) => (
              <li
                key={`${range.kind}-${range.startMi}`}
                className={styles.item}
                data-kind="advisory"
              >
                <div className={styles.head}>
                  <span className={styles.event}>{ADVISORY_LABEL[range.kind]}</span>
                  <span className={`${styles.miles} num`}>
                    {range.startMi === range.endMi
                      ? `mi ${Math.round(range.startMi)}`
                      : `mi ${Math.round(range.startMi)}–${Math.round(range.endMi)}`}
                  </span>
                </div>
                <span className={styles.meta}>
                  {range.message}
                  {range.checkpoints > 1 && ` (${range.checkpoints} checkpoints)`}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className={styles.note}>
        Shown alongside the risk rules, not scored. Alerts are issued by the National Weather
        Service; advisories are computed from the forecast at each checkpoint's ETA.
      </p>
    </section>
  )
}
