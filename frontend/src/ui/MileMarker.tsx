import styles from './MileMarker.module.css'

/** Green highway mile-marker post. */
export function MileMarker({ mile }: { mile: number }) {
  return (
    <span className={styles.marker} aria-label={`Mile ${Math.round(mile)}`}>
      <span className={styles.caption}>MILE</span>
      <span className={styles.value}>{Math.round(mile)}</span>
    </span>
  )
}
