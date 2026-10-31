import { lazy, Suspense } from 'react'

import { CheckpointDrawer } from '@/features/checkpoint/CheckpointDrawer'
import { TripForm } from '@/features/planner/TripForm'
import { ResultsPanel } from '@/features/results/ResultsPanel'
import { RiskRibbon } from '@/features/ribbon/RiskRibbon'
import { RulesPanel } from '@/features/rules/RulesPanel'
import { TimelineDock } from '@/features/timeline/TimelineDock'
import { useAppStore } from '@/state/store'

import styles from './App.module.css'
import { EmptyState } from './EmptyState'
import { Header } from './Header'
import { useShortcuts } from './useShortcuts'
import { useTripPlanner } from './useTripPlanner'

// MapLibre is the bulk of the bundle; the form is usable before it arrives.
const MapView = lazy(() => import('@/features/map/MapView'))

export function App() {
  const { submit, pending, error } = useTripPlanner()
  const editing = useAppStore((s) => s.editing)
  const hasPlan = useAppStore((s) => s.plan !== null)
  useShortcuts()

  const showResults = hasPlan && !editing

  return (
    <div className={styles.app}>
      <Header />
      <main className={styles.main} data-results={showResults}>
        <aside className={styles.panel} aria-label={showResults ? 'Route results' : 'Plan a trip'}>
          {showResults ? (
            <ResultsPanel />
          ) : (
            <TripForm onSubmit={submit} pending={pending} error={error} />
          )}
        </aside>
        <section className={styles.stage}>
          <div className={styles.mapArea}>
            <Suspense fallback={<div className={styles.mapFallback} />}>
              <MapView />
            </Suspense>
            {!hasPlan && <EmptyState />}
            {showResults && <CheckpointDrawer />}
          </div>
          {showResults && (
            <div className={styles.docks}>
              <RiskRibbon />
              <TimelineDock />
            </div>
          )}
        </section>
      </main>
      <RulesPanel />
    </div>
  )
}
