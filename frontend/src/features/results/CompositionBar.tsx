import type { CSSProperties } from 'react'

import { formatMiles } from '@/domain/format'
import { LEVEL_META } from '@/domain/levels'
import { LEVELS } from '@/domain/risk'
import type { RouteRisk } from '@/domain/ranking'

import styles from './CompositionBar.module.css'

/** Stacked bar of miles at each risk level, unknown miles last. */
export function CompositionBar({ risk }: { risk: RouteRisk }) {
  const total = risk.milesByLevel.reduce((a, b) => a + b, 0) + risk.unknownMiles
  const segments = [
    ...LEVELS.map((level) => ({
      key: String(level),
      level: String(level),
      miles: risk.milesByLevel[level],
      color: `var(${LEVEL_META[level].cssVar})`,
      label: LEVEL_META[level].label,
    })),
    {
      key: 'unknown',
      level: 'unknown',
      miles: risk.unknownMiles,
      color: 'var(--risk-unknown)',
      label: 'No forecast',
    },
  ].filter((s) => s.miles > 0)

  const description = segments.map((s) => `${s.label} ${formatMiles(s.miles)}`).join(', ')

  return (
    <div className={styles.bar} role="img" aria-label={`Risk composition: ${description}`}>
      {segments.map((segment) => (
        <span
          key={segment.key}
          className={styles.segment}
          data-level={segment.level}
          title={`${segment.label}: ${formatMiles(segment.miles)}`}
          style={
            {
              flexGrow: segment.miles / (total || 1),
              '--segment-color': segment.color,
            } as CSSProperties
          }
        />
      ))}
    </div>
  )
}
