import { useId } from 'react'

import { BROWSER_TZ, nextFullHour, shiftHours, tomorrowAt, zoneAbbreviation } from '@/lib/localTime'

import styles from './DepartureField.module.css'

interface DepartureFieldProps {
  value: string
  onChange(value: string): void
  error?: string | undefined
  /** The origin's IANA zone, once known; quick picks and the hint use its clock. */
  tz?: string | undefined
}

/** Departure as wall-clock time at the origin; the server applies the origin's zone (D14). */
export function DepartureField({ value, onChange, error, tz }: DepartureFieldProps) {
  const id = useId()
  const zone = tz ?? BROWSER_TZ
  const next = nextFullHour(zone)
  const quick = [
    { label: 'Next hour', value: next },
    { label: '+6 h', value: shiftHours(next, 6) },
    { label: 'Tomorrow 06:00', value: tomorrowAt(6, zone) },
  ]

  return (
    <div className={styles.field}>
      <div className={styles.header}>
        <label htmlFor={id} className="label">
          Departure
        </label>
        <span className={styles.hint}>
          {tz ? `origin time · ${zoneAbbreviation(tz)}` : 'local time at origin'}
        </span>
      </div>
      <input
        id={id}
        type="datetime-local"
        className={`${styles.input} num`}
        value={value}
        step={900}
        aria-invalid={Boolean(error)}
        onChange={(event) => event.target.value && onChange(event.target.value.slice(0, 16))}
      />
      <div className={styles.quick}>
        {quick.map((option) => (
          <button
            key={option.label}
            type="button"
            className={styles.chip}
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {error && <p className={styles.error}>{error}</p>}
    </div>
  )
}
