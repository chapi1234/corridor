import styles from './EmptyState.module.css'

const STEPS = [
  ['01', 'Three routes', 'Truck-legal alternatives between your origin and destination.'],
  [
    '02',
    'Weather at the ETA',
    'Forecast gusts, rain and snow for the hour the truck reaches each checkpoint.',
  ],
  [
    '03',
    'Load-aware risk',
    'Heavier trailers escalate in high wind; the safest route is recommended.',
  ],
] as const

/** Shown over the map before the first plan: what the tool does, in three beats. */
export function EmptyState() {
  return (
    <div className={styles.overlay}>
      <ol className={styles.card}>
        {STEPS.map(([number, title, body]) => (
          <li key={number}>
            <span className={`${styles.number} num`}>{number}</span>
            <strong>{title}</strong>
            <span>{body}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
