import { Clock, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { ApiError } from '@/api/client'
import type { PlanResponse } from '@/api/types'
import { formatAge, freshness } from '@/domain/freshness'
import { useAppStore } from '@/state/store'
import { Button } from '@/ui/Button'

import styles from './Freshness.module.css'

const TICK_MS = 60_000

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), TICK_MS)
    return () => window.clearInterval(id)
  }, [])
  return now
}

interface FreshnessNoticeProps {
  plan: PlanResponse
  onRefresh(): void
  refreshing: boolean
  error: ApiError | null
}

/** Offers a live re-plan once the forecast behind a plan (often a shared one) has aged. */
export function FreshnessNotice({ plan, onRefresh, refreshing, error }: FreshnessNoticeProps) {
  const now = useNow()
  const editTrip = useAppStore((s) => s.editTrip)
  const state = freshness(plan.generated_at, plan.departure.utc, now)
  if (state === 'fresh' && !error) return null

  const age = formatAge(now - Date.parse(plan.generated_at))
  return (
    <div className={styles.notice} role="status">
      <Clock size={14} aria-hidden />
      <p>
        {state === 'departed'
          ? `This departure has passed; the forecast is from ${age} ago. Pick a new departure to plan with live weather.`
          : error
            ? error.message
            : `Forecast fetched ${age} ago — conditions may have changed.`}
      </p>
      {state === 'departed' ? (
        <Button size="sm" variant="ghost" onClick={editTrip}>
          Edit trip
        </Button>
      ) : (
        <Button
          size="sm"
          variant="ghost"
          icon={<RefreshCw size={12} className={refreshing ? styles.spin : undefined} />}
          onClick={onRefresh}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing' : 'Refresh'}
        </Button>
      )}
    </div>
  )
}
