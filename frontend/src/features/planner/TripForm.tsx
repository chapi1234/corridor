import { ArrowDownUp, ArrowLeft, Route as RouteIcon } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import type { ApiError } from '@/api/client'
import { useTimezone } from '@/api/queries'
import type { IntervalMi, PlanRequest } from '@/api/types'
import { useAppStore, type TripDraft } from '@/state/store'
import { toPlanRequest } from '@/state/tripRequest'
import { BROWSER_TZ, nextFullHour } from '@/lib/localTime'
import { Button, IconButton } from '@/ui/Button'
import { Segmented } from '@/ui/Segmented'
import { Switch } from '@/ui/Switch'

import { DepartureField } from './DepartureField'
import { LoadField } from './LoadField'
import { PlaceField } from './PlaceField'
import styles from './TripForm.module.css'

const INTERVALS: { value: IntervalMi; label: string }[] = [
  { value: 10, label: '10 mi' },
  { value: 25, label: '25 mi' },
  { value: 50, label: '50 mi' },
]

const STEPS = [
  'Finding three truck routes',
  'Placing checkpoints along each route',
  'Fetching the forecast at every ETA',
  'Scoring risk and ranking routes',
]

interface TripFormProps {
  onSubmit(request: PlanRequest): void
  pending: boolean
  error: ApiError | null
}

function validate(draft: TripDraft): Partial<Record<'origin' | 'destination', string>> {
  const errors: Partial<Record<'origin' | 'destination', string>> = {}
  if (!draft.origin) errors.origin = 'Choose an origin from the suggestions.'
  if (!draft.destination) errors.destination = 'Choose a destination from the suggestions.'
  if (
    draft.origin &&
    draft.destination &&
    draft.origin.lat === draft.destination.lat &&
    draft.origin.lon === draft.destination.lon
  ) {
    errors.destination = 'Origin and destination must differ.'
  }
  return errors
}

export function TripForm({ onSubmit, pending, error }: TripFormProps) {
  const draft = useAppStore((s) => s.draft)
  const updateDraft = useAppStore((s) => s.updateDraft)
  const swapEndpoints = useAppStore((s) => s.swapEndpoints)
  const hasPlan = useAppStore((s) => s.plan !== null)
  const cancelEdit = useAppStore((s) => s.cancelEdit)
  const originTz = useTimezone(draft.origin).data

  // The default departure was computed on the browser's clock. Once the origin's zone is
  // known, move a default (or already-past) departure to the next hour at the origin.
  useEffect(() => {
    if (!originTz) return
    const { departureLocal } = useAppStore.getState().draft
    const originNext = nextFullHour(originTz)
    if (departureLocal === nextFullHour(BROWSER_TZ) || departureLocal < originNext) {
      updateDraft({ departureLocal: originNext })
    }
  }, [originTz, updateDraft])
  const [submitted, setSubmitted] = useState(false)

  const errors = submitted ? validate(draft) : {}

  function submit(event?: FormEvent) {
    event?.preventDefault()
    setSubmitted(true)
    const request = toPlanRequest(draft)
    if (request && Object.keys(validate(draft)).length === 0) onSubmit(request)
  }

  return (
    <form className={styles.form} onSubmit={submit} noValidate aria-busy={pending}>
      <header className={styles.intro}>
        {hasPlan && (
          <Button
            variant="ghost"
            size="sm"
            icon={<ArrowLeft size={14} />}
            className={styles.back}
            onClick={cancelEdit}
            disabled={pending}
          >
            Back to results
          </Button>
        )}
        <h1 className={styles.title}>Plan a trip</h1>
        <p className={styles.lede}>
          Forecasts the weather your truck will drive into — at the hour it gets there — and weighs
          it against your load.
        </p>
      </header>

      <fieldset className={styles.endpoints} disabled={pending}>
        <legend className="visually-hidden">Route</legend>
        <PlaceField
          label="Origin"
          marker="origin"
          placeholder="City, address or truck stop"
          value={draft.origin}
          onChange={(origin) => updateDraft({ origin })}
          error={errors.origin}
        />
        <div className={styles.swap}>
          <IconButton
            label="Swap origin and destination"
            variant="ghost"
            size="sm"
            icon={<ArrowDownUp size={16} />}
            onClick={swapEndpoints}
          />
        </div>
        <PlaceField
          label="Destination"
          marker="destination"
          placeholder="Where is the load going?"
          value={draft.destination}
          onChange={(destination) => updateDraft({ destination })}
          error={errors.destination ?? error?.fieldError('destination')}
        />
      </fieldset>

      <div className={styles.lane} aria-hidden />

      <fieldset className={styles.group} disabled={pending}>
        <legend className="visually-hidden">Trip details</legend>
        <DepartureField
          value={draft.departureLocal}
          tz={originTz}
          onChange={(departureLocal) => updateDraft({ departureLocal })}
          error={error?.fieldError('departure') ?? error?.fieldError('departure_local')}
        />
        <LoadField value={draft.loadLb} onChange={(loadLb) => updateDraft({ loadLb })} />
        <div className={styles.interval}>
          <div className={styles.intervalHeader}>
            <span className="label">Weather checkpoints</span>
            <span className={styles.hint}>every</span>
          </div>
          <Segmented
            label="Checkpoint interval"
            value={draft.intervalMi}
            options={INTERVALS}
            onChange={(intervalMi) => updateDraft({ intervalMi })}
          />
        </div>
        <Switch
          label="Mandatory rest (HOS)"
          description="30-min break after 8 h driving, 10-h rest after 11 h"
          checked={draft.hos}
          onChange={(hos) => updateDraft({ hos })}
        />
      </fieldset>

      {error && !error.fieldError('departure') && !error.fieldError('destination') && (
        <div className={styles.error} role="alert">
          <strong>{error.problem?.title ?? 'Planning failed'}</strong>
          <span>{error.message}</span>
        </div>
      )}

      {pending ? (
        <PlanningProgress />
      ) : (
        <Button type="submit" variant="primary" size="lg" icon={<RouteIcon size={18} />}>
          Plan routes
        </Button>
      )}
    </form>
  )
}

function PlanningProgress() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className={styles.progress} role="status" aria-live="polite">
      <div className={styles.progressHeader}>
        <span className="label">Planning</span>
        <span className="num">{seconds}s</span>
      </div>
      <div className={styles.scan} aria-hidden />
      <ol className={styles.steps}>
        {STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  )
}
