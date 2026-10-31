import { VARIABLE_SCALES, type VariableScale } from '@/domain/heatmap'
import { LEVEL_META } from '@/domain/levels'
import { LEVELS } from '@/domain/risk'
import { useAppStore } from '@/state/store'
import { RiskSwatch } from '@/ui/RiskChip'

import styles from './Legend.module.css'

/** CSS twin of the map's `heatmap-color` ramp: hard colour steps at the rule thresholds. */
function rampGradient(scale: VariableScale): string {
  const stops = scale.thresholds.map((value) => (value / scale.max) * 100)
  const [t1, t2, t3, t4] = stops as [number, number, number, number]
  return `linear-gradient(90deg,
    transparent 0%,
    color-mix(in srgb, var(--risk-0) 40%, transparent) ${t1}%,
    var(--risk-1) ${t1}%, var(--risk-1) ${t2}%,
    var(--risk-2) ${t2}%, var(--risk-2) ${t3}%,
    var(--risk-3) ${t3}%, var(--risk-3) ${t4}%,
    var(--risk-4) ${t4}%)`
}

export function Legend() {
  const heatmap = useAppStore((s) => s.heatmap)
  const scale = VARIABLE_SCALES[heatmap.variable]

  return (
    <aside className={styles.legend} aria-label="Map legend">
      <span className="label">Route risk</span>
      <ul className={styles.levels}>
        {LEVELS.map((level) => (
          <li key={level}>
            <RiskSwatch level={level} />
            {LEVEL_META[level].label}
          </li>
        ))}
        <li>
          <RiskSwatch level={null} />
          No forecast
        </li>
      </ul>
      {heatmap.visible && (
        <div className={styles.heat}>
          <span className="label">
            Heatmap · {scale.label}
            {heatmap.variable !== 'risk' && ` (${scale.unit})`}
          </span>
          <div className={styles.ramp} style={{ background: rampGradient(scale) }} aria-hidden />
          {/* The risk ramp shares the route-risk swatches above; raw variables get their thresholds. */}
          {heatmap.variable !== 'risk' && (
            <div className={`${styles.ticks} num`}>
              {scale.thresholds.map((value) => (
                <span key={value} style={{ left: `${(value / scale.max) * 100}%` }}>
                  {value}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  )
}
