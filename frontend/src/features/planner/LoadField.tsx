import * as Slider from '@radix-ui/react-slider'
import { useId } from 'react'

import { formatPounds } from '@/domain/format'
import { NO_TRAVEL_LOAD_THRESHOLD_LB, SEVERE_LOAD_THRESHOLD_LB } from '@/domain/risk'

import styles from './LoadField.module.css'

export const MAX_LOAD_LB = 80_000
const STEP_LB = 500

const THRESHOLDS = [
  {
    value: NO_TRAVEL_LOAD_THRESHOLD_LB,
    label: '30k',
    hint: 'Above 30,000 lb, 45–54 mph gusts become No Travel',
  },
  {
    value: SEVERE_LOAD_THRESHOLD_LB,
    label: '40k',
    hint: 'Above 40,000 lb, 35–44 mph gusts become Severe',
  },
] as const

const PRESETS = [
  { label: 'Empty', value: 0 },
  { label: '15k', value: 15_000 },
  { label: '30k', value: 30_000 },
  { label: '45k', value: 45_000 },
] as const

interface LoadFieldProps {
  value: number
  onChange(value: number): void
  compact?: boolean
}

/** Load weight with the load-rule thresholds marked on the track. */
export function LoadField({ value, onChange, compact = false }: LoadFieldProps) {
  const id = useId()
  const activeRule = [...THRESHOLDS].reverse().find((t) => value > t.value)

  return (
    <div className={styles.field} data-compact={compact}>
      <div className={styles.header}>
        <label htmlFor={id} className="label">
          Load weight
        </label>
        <div className={styles.inputGroup}>
          <input
            id={id}
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_LOAD_LB}
            step={STEP_LB}
            value={value}
            onChange={(event) => onChange(clampLoad(Number(event.target.value)))}
            className={`${styles.number} num`}
          />
          <span className={styles.unit}>lb</span>
        </div>
      </div>

      <div className={styles.sliderWrap}>
        <Slider.Root
          className={styles.root}
          min={0}
          max={MAX_LOAD_LB}
          step={STEP_LB}
          value={[value]}
          onValueChange={([next]) => onChange(next ?? 0)}
          aria-label="Load weight"
        >
          <Slider.Track className={styles.track}>
            <Slider.Range className={styles.range} />
          </Slider.Track>
          <Slider.Thumb className={styles.thumb} aria-valuetext={formatPounds(value)} />
        </Slider.Root>
        {THRESHOLDS.map((threshold) => (
          <span
            key={threshold.value}
            className={styles.tick}
            data-passed={value > threshold.value}
            style={{ left: `${(threshold.value / MAX_LOAD_LB) * 100}%` }}
            title={threshold.hint}
          >
            <span className={styles.tickLabel}>{threshold.label}</span>
          </span>
        ))}
      </div>

      {!compact && (
        <div className={styles.footer}>
          <div className={styles.presets}>
            {PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className={styles.preset}
                aria-pressed={value === preset.value}
                onClick={() => onChange(preset.value)}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      )}
      <p className={styles.rule} aria-live="polite">
        {activeRule ? activeRule.hint : 'Below 30,000 lb no load rules apply'}
      </p>
    </div>
  )
}

function clampLoad(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(Math.max(Math.round(value), 0), MAX_LOAD_LB)
}
