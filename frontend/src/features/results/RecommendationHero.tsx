import { ChevronDown, OctagonAlert } from 'lucide-react'
import { useState } from 'react'

import { CRITERION_LABEL } from '@/domain/levels'
import { CRITERIA } from '@/domain/ranking'
import type { ScoredPlan } from '@/domain/scoring'
import { RouteShield } from '@/ui/RouteShield'

import styles from './RecommendationHero.module.css'

export function RecommendationHero({ scored }: { scored: ScoredPlan }) {
  const [expanded, setExpanded] = useState(false)
  const { ranking } = scored

  return (
    <section className={styles.hero} data-unsafe={ranking.noSafeRoute} aria-live="polite">
      {ranking.noSafeRoute && (
        <p className={styles.alert} role="alert">
          <OctagonAlert size={16} aria-hidden />
          Every route crosses No Travel conditions at this departure. Consider leaving later.
        </p>
      )}
      <div className={styles.verdict}>
        <span className="label">{ranking.noSafeRoute ? 'Least exposed' : 'Recommended'}</span>
        <div className={styles.take}>
          <span className={styles.takeWord}>Take</span>
          <RouteShield id={ranking.recommended} selected size={40} />
          <span className={styles.takeWord}>Route {ranking.recommended}</span>
        </div>
        <p className={styles.reason}>{ranking.reason}</p>
      </div>

      {ranking.order.length > 1 && (
        <>
          <button
            type="button"
            className={styles.toggle}
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            Why Route {ranking.recommended}?
            <ChevronDown size={14} aria-hidden />
          </button>
          {expanded && <Explainer scored={scored} />}
        </>
      )}
    </section>
  )
}

/** The lexicographic comparison, with the deciding criterion for each rival highlighted. */
function Explainer({ scored }: { scored: ScoredPlan }) {
  const { ranking } = scored
  const routeIds = ranking.order
  const format = (criterionIndex: number, value: number) => {
    if (criterionIndex === 3)
      return value === Number.MAX_SAFE_INTEGER ? '—' : (value * 0.05).toFixed(2)
    if (criterionIndex === 4) return `${(value / 3600).toFixed(1)} h`
    return `${value} mi`
  }

  return (
    <div className={styles.explainer}>
      <table className={styles.table}>
        <caption className="visually-hidden">
          Route comparison by ranking criteria, in priority order
        </caption>
        <thead>
          <tr>
            <th scope="col" className="label">
              Priority
            </th>
            {routeIds.map((id) => (
              <th key={id} scope="col" className="label" data-best={id === ranking.recommended}>
                {id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CRITERIA.map((criterion, index) => (
            <tr key={criterion}>
              <th scope="row">
                <span className={styles.rank}>{index + 1}</span>
                {CRITERION_LABEL[criterion]}
              </th>
              {routeIds.map((id) => {
                const decidedHere = ranking.beatsOn[id] === criterion
                return (
                  <td
                    key={id}
                    className="num"
                    data-best={id === ranking.recommended}
                    data-decided={decidedHere}
                  >
                    {format(index, ranking.keys[id]![index]!)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.note}>
        Criteria are compared in order; the first difference decides. Highlighted cells show where
        Route {ranking.recommended} beats each alternative. Miles are rounded to whole miles before
        comparing.
      </p>
    </div>
  )
}
