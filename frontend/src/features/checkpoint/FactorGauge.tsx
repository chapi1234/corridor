import type { CSSProperties } from 'react'

import { LEVEL_META } from '@/domain/levels'
import type { Band, Level } from '@/domain/risk'
import { RiskChip } from '@/ui/RiskChip'

import styles from './FactorGauge.module.css'

interface FactorGaugeProps {
  label: string
  value: number
  unit: string
  digits: number
  /** Bands listed top-down as in the rule tables. */
  bands: readonly Band[]
  level: Level
  isDriver: boolean
  /** Shown under the gauge when a load rule escalated this factor. */
  note?: string
}

/**
 * The factor's value on its rule scale. Bands get equal widths (the scale is ordinal, like
 * the risk index) so the narrow low-precipitation bands stay readable.
 */
export function FactorGauge({
  label,
  value,
  unit,
  digits,
  bands,
  level,
  isDriver,
  note,
}: FactorGaugeProps) {
  const ascending = [...bands].reverse()
  const share = 100 / ascending.length
  const position = (v: number) => {
    const i = Math.max(
      ascending.findLastIndex((band) => v >= band.lower),
      0,
    )
    const band = ascending[i]!
    const fraction = Math.min((v - band.lower) / (band.upper - band.lower), 1)
    return `${(i + fraction) * share}%`
  }

  return (
    <div className={styles.gauge} data-driver={isDriver}>
      <div className={styles.header}>
        <span className={styles.label}>
          {label}
          {isDriver && <span className={styles.driver}>Driver</span>}
        </span>
        <span className={`${styles.value} num`}>
          {value.toFixed(digits)} <small>{unit}</small>
        </span>
        <RiskChip level={level} size="sm" short />
      </div>
      <div
        className={styles.track}
        role="img"
        aria-label={`${label} ${value.toFixed(digits)} ${unit}`}
      >
        {ascending.map((band, i) => (
          <span
            key={band.level}
            className={styles.band}
            style={
              {
                left: `${i * share}%`,
                width: `${share}%`,
                '--band': `var(${LEVEL_META[band.level].cssVar})`,
              } as CSSProperties
            }
          />
        ))}
        <span className={styles.needle} style={{ left: position(value) }} />
      </div>
      <div className={`${styles.scale} num`} aria-hidden>
        {ascending.slice(1).map((band, i) => (
          <span key={band.level} style={{ left: `${(i + 1) * share}%` }}>
            {band.lower}
          </span>
        ))}
      </div>
      {note && <p className={styles.note}>{note}</p>}
    </div>
  )
}
