import { ChevronLeft, ChevronRight, Clock, Siren, TriangleAlert, X } from 'lucide-react'

import { ADVISORY_LABEL } from '@/domain/advisories'
import { alertsAtMile, alertTiming } from '@/domain/alerts'

import { formatDuration, formatLocal } from '@/domain/format'
import { FACTOR_LABEL, LEVEL_META, LOAD_RULE_TEXT } from '@/domain/levels'
import { RAIN_BANDS_IN_HR, SNOW_BANDS_IN_HR, WIND_BANDS_MPH } from '@/domain/risk'
import { hourOfCheckpoint } from '@/domain/timeline'
import { useScoredPlan } from '@/state/selectors'
import { FORECAST_HOURS, useAppStore } from '@/state/store'
import { Button, IconButton } from '@/ui/Button'
import { MileMarker } from '@/ui/MileMarker'
import { RiskChip } from '@/ui/RiskChip'
import { RouteShield } from '@/ui/RouteShield'

import styles from './CheckpointDrawer.module.css'
import { FactorGauge } from './FactorGauge'
import { HourlyStrip } from './HourlyStrip'

/** Non-modal drawer over the map: one checkpoint, why it scored what it did. */
export function CheckpointDrawer() {
  const scored = useScoredPlan()
  const ref = useAppStore((s) => s.openCheckpoint)
  const close = () => useAppStore.getState().openCheckpointDetail(null)
  const step = (delta: 1 | -1) => useAppStore.getState().stepCheckpoint(delta)

  const route = scored?.routes.find((r) => r.route.id === ref?.routeId)
  const entry = ref ? route?.checkpoints[ref.index] : undefined
  if (!scored || !ref || !route || !entry) return null

  const { checkpoint, risk } = entry
  const { weather } = checkpoint
  const count = route.checkpoints.length
  const etaHour = hourOfCheckpoint(scored.plan, route.route, ref.index)

  return (
    <aside className={styles.drawer} aria-labelledby="checkpoint-title">
      <header className={styles.header}>
        <MileMarker mile={checkpoint.mile} />
        <div className={styles.title}>
          <h2 id="checkpoint-title">
            <RouteShield id={route.route.id} size={20} />
            Checkpoint {ref.index + 1}
            <span className={styles.of}>/ {count}</span>
          </h2>
          <span className="num">
            ETA {formatLocal(checkpoint.eta)} · {formatDuration(checkpoint.elapsed_s)} in
          </span>
        </div>
        <IconButton
          label="Close checkpoint"
          variant="ghost"
          icon={<X size={16} />}
          onClick={close}
        />
      </header>

      <div className={styles.verdict} data-level={risk?.level ?? 'unknown'}>
        <RiskChip level={risk?.level ?? null} />
        <span>
          {risk
            ? `${FACTOR_LABEL[risk.driver]} drives this checkpoint · index ${risk.index.toFixed(2)}`
            : 'No forecast covers this ETA. These miles count as unknown, not as safe.'}
        </span>
      </div>

      {alertsAtMile(route.route, checkpoint.mile).map((alert) => (
        <p key={alert.id} className={styles.nws} data-active={alert.in_effect}>
          <Siren size={12} aria-hidden />
          <span>
            <strong>{alert.event}</strong> · {alertTiming(alert)}
          </span>
        </p>
      ))}

      {checkpoint.advisories.map((advisory) => (
        <p key={advisory.kind} className={styles.nws} data-kind="advisory">
          <TriangleAlert size={12} aria-hidden />
          <span>
            <strong>{ADVISORY_LABEL[advisory.kind]}</strong> · {advisory.message}
          </span>
        </p>
      ))}

      <div className={styles.body}>
        {weather && risk && (
          <>
            <FactorGauge
              label="Wind gusts"
              value={weather.gust_mph}
              unit="mph"
              digits={0}
              bands={WIND_BANDS_MPH}
              level={risk.factors.wind.level}
              isDriver={risk.driver === 'wind'}
              note={
                risk.loadRule
                  ? `Load rule: ${LOAD_RULE_TEXT[risk.loadRule]} (${scored.loadLb.toLocaleString('en-US')} lb)`
                  : undefined
              }
            />
            <FactorGauge
              label="Rain"
              value={weather.rain_in_hr}
              unit="in/hr"
              digits={2}
              bands={RAIN_BANDS_IN_HR}
              level={risk.factors.rain.level}
              isDriver={risk.driver === 'rain'}
            />
            <FactorGauge
              label="Snow"
              value={weather.snow_in_hr}
              unit="in/hr"
              digits={1}
              bands={SNOW_BANDS_IN_HR}
              level={risk.factors.snow.level}
              isDriver={risk.driver === 'snow'}
            />
            <dl className={`${styles.facts} num`}>
              <div>
                <dt className="label">Sustained</dt>
                <dd>{weather.wind_mph.toFixed(0)} mph</dd>
              </div>
              <div>
                <dt className="label">Temp</dt>
                <dd>{weather.temperature_f.toFixed(0)} °F</dd>
              </div>
              <div>
                <dt className="label">Owns</dt>
                <dd>{checkpoint.owned_miles.toFixed(1)} mi</dd>
              </div>
            </dl>
          </>
        )}

        {checkpoint.hourly && (
          <HourlyStrip
            hourly={checkpoint.hourly}
            etaUtc={checkpoint.eta.utc}
            tz={checkpoint.eta.tz}
            loadLb={scored.loadLb}
          />
        )}
      </div>

      <footer className={styles.footer}>
        <IconButton
          label="Previous checkpoint"
          icon={<ChevronLeft size={16} />}
          disabled={ref.index === 0}
          onClick={() => step(-1)}
        />
        <Button
          variant="ghost"
          size="sm"
          icon={<Clock size={14} />}
          disabled={etaHour < 0 || etaHour > FORECAST_HOURS}
          onClick={() => useAppStore.getState().setForecastHour(etaHour)}
        >
          Show map at ETA
        </Button>
        <IconButton
          label="Next checkpoint"
          icon={<ChevronRight size={16} />}
          disabled={ref.index === count - 1}
          onClick={() => step(1)}
        />
      </footer>
      <span className="visually-hidden" aria-live="polite">
        {risk ? LEVEL_META[risk.level].label : 'No forecast'} at mile {Math.round(checkpoint.mile)}
      </span>
    </aside>
  )
}
