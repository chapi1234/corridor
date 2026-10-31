import type { HourlyWindow } from '@/api/types'
import { formatInstant } from '@/domain/format'
import { LEVEL_META, UNKNOWN_META } from '@/domain/levels'
import {
  RAIN_BANDS_IN_HR,
  SNOW_BANDS_IN_HR,
  applyLoadRules,
  precipitationBand,
  windBand,
  type Level,
} from '@/domain/risk'

import styles from './HourlyStrip.module.css'

const HOUR_MS = 3_600_000

interface Series {
  key: keyof Omit<HourlyWindow, 'start'>
  label: string
  unit: string
  max: number
  level(value: number, loadLb: number): Level
}

const SERIES: readonly Series[] = [
  {
    key: 'gust_mph',
    label: 'Gust',
    unit: 'mph',
    max: 70,
    level: (v, loadLb) => applyLoadRules(windBand(v), loadLb).level,
  },
  {
    key: 'rain_in_hr',
    label: 'Rain',
    unit: 'in/hr',
    max: 1,
    level: (v) => precipitationBand(v, RAIN_BANDS_IN_HR).level,
  },
  {
    key: 'snow_in_hr',
    label: 'Snow',
    unit: 'in/hr',
    max: 3,
    level: (v) => precipitationBand(v, SNOW_BANDS_IN_HR).level,
  },
]

const ROW_H = 28
const COL_W = 18

interface HourlyStripProps {
  hourly: HourlyWindow
  etaUtc: string
  tz: string
  loadLb: number
}

/** ±6 h of forecast around the ETA: is the risk a passing spike or a long window? */
export function HourlyStrip({ hourly, etaUtc, tz, loadLb }: HourlyStripProps) {
  const start = Date.parse(hourly.start)
  const hours = hourly.gust_mph.length
  const width = hours * COL_W
  const etaX = ((Date.parse(etaUtc) - start) / HOUR_MS) * COL_W + COL_W / 2
  const labelAt = (i: number) =>
    formatInstant(new Date(start + i * HOUR_MS), tz, { withDay: false })

  return (
    <figure className={styles.figure}>
      <figcaption className="label">Hourly at this point · ±6 h</figcaption>
      <div className={styles.chart}>
        <div className={styles.rowLabels}>
          {SERIES.map((s) => (
            <span key={s.key} style={{ height: ROW_H }}>
              {s.label}
            </span>
          ))}
        </div>
        <svg
          viewBox={`0 0 ${width} ${SERIES.length * ROW_H + 14}`}
          className={styles.svg}
          preserveAspectRatio="none"
          role="img"
          aria-label="Hourly gust, rain and snow around the ETA"
        >
          {SERIES.map((series, row) =>
            hourly[series.key].map((value, i) => {
              const top = row * ROW_H
              if (value === null) {
                return (
                  <rect
                    key={`${series.key}-${i}`}
                    x={i * COL_W + 2}
                    y={top + ROW_H - 3}
                    width={COL_W - 4}
                    height={2}
                    fill={`var(${UNKNOWN_META.cssVar})`}
                  />
                )
              }
              const h = Math.max((Math.min(value, series.max) / series.max) * (ROW_H - 4), 1.5)
              return (
                <rect
                  key={`${series.key}-${i}`}
                  x={i * COL_W + 2}
                  y={top + ROW_H - 1 - h}
                  width={COL_W - 4}
                  height={h}
                  fill={`var(${LEVEL_META[series.level(value, loadLb)].cssVar})`}
                >
                  <title>{`${labelAt(i)} · ${series.label} ${value} ${series.unit}`}</title>
                </rect>
              )
            }),
          )}
          <line
            x1={etaX}
            x2={etaX}
            y1={0}
            y2={SERIES.length * ROW_H}
            className={styles.eta}
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div className={`${styles.axis} num`} aria-hidden>
        <span>{labelAt(0)}</span>
        <span className={styles.etaLabel}>ETA</span>
        <span>{labelAt(hours - 1)}</span>
      </div>
    </figure>
  )
}
