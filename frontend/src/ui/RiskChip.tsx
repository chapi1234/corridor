import type { CSSProperties } from 'react'

import { LEVEL_META, UNKNOWN_META } from '@/domain/levels'
import type { Level } from '@/domain/risk'

import styles from './RiskChip.module.css'

function levelStyle(level: Level | null): CSSProperties {
  const meta = level === null ? UNKNOWN_META : LEVEL_META[level]
  return {
    '--chip-bg': `var(${meta.cssVar})`,
    '--chip-ink': `var(${meta.inkVar})`,
  } as CSSProperties
}

interface RiskChipProps {
  level: Level | null
  size?: 'sm' | 'md'
  /** Render the short label (e.g. "SEV") for dense layouts. */
  short?: boolean
}

/** Risk level badge: colour + text, plus a hatch for No Travel and unknown. Never colour alone. */
export function RiskChip({ level, size = 'md', short = false }: RiskChipProps) {
  const meta = level === null ? UNKNOWN_META : LEVEL_META[level]
  return (
    <span
      className={`${styles.chip} ${styles[size]}`}
      data-level={level ?? 'unknown'}
      style={levelStyle(level)}
    >
      {short ? meta.short : meta.label}
    </span>
  )
}

export function RiskSwatch({ level }: { level: Level | null }) {
  return (
    <span
      aria-hidden
      className={styles.swatch}
      data-level={level ?? 'unknown'}
      style={levelStyle(level)}
    />
  )
}
