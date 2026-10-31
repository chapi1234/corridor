import styles from './RouteShield.module.css'

interface RouteShieldProps {
  id: string
  selected?: boolean
  size?: number
}

/** Interstate-style shield carrying the route letter. */
export function RouteShield({ id, selected = false, size = 30 }: RouteShieldProps) {
  return (
    <svg
      className={styles.shield}
      data-selected={selected}
      width={size}
      height={size * 1.08}
      viewBox="0 0 40 43"
      role="img"
      aria-label={`Route ${id}`}
    >
      <path
        className={styles.body}
        d="M3 4c5 1.6 11 1.6 17-1.8C26 5.6 32 5.6 37 4c2 9.5 2.4 18.6-.5 25.6C33.4 37 27 40.4 20 42c-7-1.6-13.4-5-16.5-12.4C.6 22.6 1 13.5 3 4Z"
      />
      <path
        className={styles.band}
        d="M3.3 6.2c5.2 1.4 11 1.2 16.7-2 5.7 3.2 11.5 3.4 16.7 2l.6 6.3H2.7l.6-6.3Z"
      />
      <text className={styles.letter} x="20" y="33" textAnchor="middle">
        {id}
      </text>
    </svg>
  )
}
