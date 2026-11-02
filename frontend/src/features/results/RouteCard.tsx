import { Siren } from 'lucide-react'
import { memo } from 'react'

import type { RestStop } from '@/api/types'
import { activeEvents } from '@/domain/alerts'
import { formatDuration, formatLocal, formatMiles } from '@/domain/format'
import { FACTOR_LABEL, TAG_LABEL } from '@/domain/levels'
import { HIGH, NO_TRAVEL, SEVERE } from '@/domain/risk'
import { worstCheckpoint, type ScoredRoute } from '@/domain/scoring'
import { useAppStore } from '@/state/store'
import { RiskChip } from '@/ui/RiskChip'
import { RouteShield } from '@/ui/RouteShield'

import { CompositionBar } from './CompositionBar'
import styles from './RouteCard.module.css'

interface RouteCardProps {
  scored: ScoredRoute
  selected: boolean
}

export const RouteCard = memo(function RouteCard({ scored, selected }: RouteCardProps) {
  const selectRoute = useAppStore((s) => s.selectRoute)
  const setHover = useAppStore((s) => s.setHover)
  const hovered = useAppStore(
    (s) => s.hover?.kind === 'route' && s.hover.routeId === scored.route.id,
  )

  const { route, risk, tags } = scored
  const worst = worstCheckpoint(scored)
  const miles = risk.milesByLevel
  const alerts = activeEvents(route)

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      className={styles.card}
      data-selected={selected}
      data-hovered={hovered}
      onClick={() => selectRoute(route.id)}
      onMouseEnter={() => setHover({ kind: 'route', routeId: route.id })}
      onMouseLeave={() => setHover(null)}
      onFocus={() => setHover({ kind: 'route', routeId: route.id })}
      onBlur={() => setHover(null)}
    >
      <div className={styles.top}>
        <RouteShield id={route.id} selected={selected} />
        <div className={styles.headline}>
          <span className={styles.highways}>{route.highways.join(' · ') || 'Local roads'}</span>
          <span className={`${styles.stats} num`}>
            {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)}
          </span>
        </div>
        <div className={styles.tags}>
          {tags.map((tag) => (
            <span key={tag} className={styles.tag} data-tag={tag}>
              {TAG_LABEL[tag]}
            </span>
          ))}
        </div>
      </div>

      <CompositionBar risk={risk} />

      <dl className={styles.metrics}>
        <Metric label="No Travel" value={miles[NO_TRAVEL]} alert={miles[NO_TRAVEL] > 0} />
        <Metric label="Severe" value={miles[SEVERE]} alert={miles[SEVERE] > 0} />
        <Metric label="High" value={miles[HIGH]} />
        <div className={styles.metric}>
          <dt className="label">Avg risk</dt>
          <dd className="num">{risk.averageRisk === null ? '—' : risk.averageRisk.toFixed(2)}</dd>
        </div>
      </dl>

      {alerts.length > 0 && (
        <p className={styles.alerts}>
          <Siren size={12} aria-hidden />
          <span>
            NWS: {alerts[0]}
            {alerts.length > 1 && ` +${alerts.length - 1} more`} in effect as you pass
          </span>
        </p>
      )}

      <div className={styles.footer}>
        <span className={styles.arrival}>
          Arrive <span className="num">{formatLocal(route.arrival)}</span>
          {route.rest_stops.length > 0 && (
            <span className={styles.rests}>
              {' '}
              · {formatDuration(route.driving_s)} driving + {restSummary(route.rest_stops)}
            </span>
          )}
        </span>
        {worst?.risk && worst.risk.level > 0 && (
          <span className={styles.worst}>
            <RiskChip level={worst.risk.level} size="sm" short />
            {FACTOR_LABEL[worst.risk.driver].toLowerCase()} · mi {Math.round(worst.checkpoint.mile)}
          </span>
        )}
      </div>
    </button>
  )
})

function Metric({
  label,
  value,
  alert = false,
}: {
  label: string
  value: number
  alert?: boolean
}) {
  return (
    <div className={styles.metric} data-alert={alert}>
      <dt className="label">{label}</dt>
      <dd className="num">
        {Math.round(value)}
        <span className={styles.unit}> mi</span>
      </dd>
    </div>
  )
}

/** "1 × 10-h rest, 2 × break" */
function restSummary(rests: readonly RestStop[]): string {
  const resets = rests.filter((r) => r.kind === 'reset').length
  const breaks = rests.length - resets
  return [resets && `${resets} × 10-h rest`, breaks && `${breaks} × break`]
    .filter(Boolean)
    .join(', ')
}
