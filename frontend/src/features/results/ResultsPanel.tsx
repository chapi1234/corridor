import { Pencil, RotateCcw, TriangleAlert } from 'lucide-react'

import { LoadField } from '@/features/planner/LoadField'
import { formatLocal, formatPounds } from '@/domain/format'
import { useScoredPlan } from '@/state/selectors'
import { useAppStore } from '@/state/store'
import { Button } from '@/ui/Button'

import { RecommendationHero } from './RecommendationHero'
import { RouteCard } from './RouteCard'
import styles from './ResultsPanel.module.css'

export function ResultsPanel() {
  const scored = useScoredPlan()
  const selectedRouteId = useAppStore((s) => s.selectedRouteId)
  const editTrip = useAppStore((s) => s.editTrip)
  const setLoadOverride = useAppStore((s) => s.setLoadOverride)
  if (!scored) return null

  const { plan } = scored

  return (
    <div className={styles.panel}>
      <div className={styles.summary}>
        <div className={styles.trip}>
          <span className={styles.endpoints}>
            {plan.inputs.origin.label} <span aria-hidden>→</span> {plan.inputs.destination.label}
          </span>
          <span className={`${styles.meta} num`}>
            {formatLocal(plan.departure)} · {formatPounds(plan.inputs.load_lb)} · every{' '}
            {plan.inputs.interval_mi} mi{plan.inputs.hos && ' · HOS rest'}
          </span>
        </div>
        <Button variant="ghost" size="sm" icon={<Pencil size={14} />} onClick={editTrip}>
          Edit
        </Button>
      </div>

      <RecommendationHero scored={scored} />

      <section className={styles.whatIf} aria-labelledby="what-if-title">
        <div className={styles.whatIfHeader}>
          <h2 id="what-if-title" className="label">
            What if the load were…
          </h2>
          {scored.isWhatIf && (
            <Button
              variant="ghost"
              size="sm"
              icon={<RotateCcw size={12} />}
              onClick={() => setLoadOverride(null)}
            >
              Reset
            </Button>
          )}
        </div>
        <LoadField compact value={scored.loadLb} onChange={setLoadOverride} />
        {scored.isWhatIf && (
          <p className={styles.whatIfNote}>
            Re-scored instantly on the same routes and forecasts. Replan to let the router account
            for the new weight.
          </p>
        )}
      </section>

      {plan.warnings.length > 0 && (
        <ul className={styles.warnings}>
          {plan.warnings.map((warning) => (
            <li key={warning.code}>
              <TriangleAlert size={14} aria-hidden />
              {warning.message}
            </li>
          ))}
        </ul>
      )}

      <section aria-labelledby="routes-title" className={styles.routes}>
        <h2 id="routes-title" className="label">
          Routes
        </h2>
        <div role="radiogroup" aria-label="Routes" className={styles.routeList}>
          {scored.routes.map((route) => (
            <RouteCard
              key={route.route.id}
              scored={route}
              selected={route.route.id === selectedRouteId}
            />
          ))}
        </div>
      </section>

      <footer className={styles.sources}>
        <span>Routing: {plan.meta.routing_source}</span>
        <span>Weather: {plan.meta.weather_source}</span>
      </footer>
    </div>
  )
}
