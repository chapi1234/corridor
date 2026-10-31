import { formatDuration, formatLocal, formatMiles } from '@/domain/format'
import { FACTOR_LABEL } from '@/domain/levels'
import type { ScoredPlan } from '@/domain/scoring'
import type { HoverTarget } from '@/state/store'
import { RiskChip } from '@/ui/RiskChip'
import { RouteShield } from '@/ui/RouteShield'

import styles from './MapTooltip.module.css'

interface MapTooltipProps {
  scored: ScoredPlan
  target: HoverTarget
  x: number
  y: number
}

export function MapTooltip({ scored, target, x, y }: MapTooltipProps) {
  const route = scored.routes.find((r) => r.route.id === target.routeId)
  if (!route) return null

  return (
    <div
      className={styles.tooltip}
      style={{ transform: `translate(${x + 14}px, ${y + 14}px)` }}
      role="tooltip"
    >
      {target.kind === 'route' ? (
        <div className={styles.row}>
          <RouteShield id={route.route.id} size={22} />
          <span className="num">
            {formatMiles(route.route.distance_mi)} · {formatDuration(route.route.duration_s)}
          </span>
        </div>
      ) : (
        <CheckpointSummary scored={scored} routeId={target.routeId} index={target.index} />
      )}
    </div>
  )
}

function CheckpointSummary({
  scored,
  routeId,
  index,
}: {
  scored: ScoredPlan
  routeId: string
  index: number
}) {
  const scoredCheckpoint = scored.routes.find((r) => r.route.id === routeId)?.checkpoints[index]
  if (!scoredCheckpoint) return null
  const { checkpoint, risk } = scoredCheckpoint
  return (
    <div className={styles.checkpoint}>
      <div className={styles.row}>
        <span className="label">Mile {Math.round(checkpoint.mile)}</span>
        <RiskChip level={risk?.level ?? null} size="sm" />
      </div>
      <span className="num">ETA {formatLocal(checkpoint.eta)}</span>
      {checkpoint.weather && risk ? (
        <span className={styles.detail}>
          {FACTOR_LABEL[risk.driver]} ·{' '}
          <span className="num">
            gust {checkpoint.weather.gust_mph.toFixed(0)} mph · rain{' '}
            {checkpoint.weather.rain_in_hr.toFixed(2)} · snow{' '}
            {checkpoint.weather.snow_in_hr.toFixed(1)}
          </span>
        </span>
      ) : (
        <span className={styles.detail}>No forecast for this ETA</span>
      )}
    </div>
  )
}
