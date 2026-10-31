import { ArrowDownUp, Route as RouteIcon } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'

import type { ApiError } from '@/api/client'
import type { IntervalMi, PlanRequest } from '@/api/types'
import { useAppStore, type TripDraft } from '@/state/store'
import { toPlanRequest } from '@/state/tripRequest'
import { Button, IconButton } from '@/ui/Button'
import { Segmented } from '@/ui/Segmented'

import { DepartureField } from './DepartureField'
import { LoadField } from './LoadField'
import { PlaceField } from './PlaceField'
import styles from './TripForm.module.css'

const INTERVALS: { value: IntervalMi; label: string }[] = [
  { value: 10, label: '10 mi' },
  { value: 25, label: '25 mi' },
  { value: 50, label: '50 mi' },
]

const EXAMPLES: { label: string; draft: Pick<TripDraft, 'origin' | 'destination' | 'loadLb'> }[] = [
  {
    label: 'Denver → Chicago',
    draft: {
      origin: { label: 'Denver, CO', lat: 39.7392, lon: -104.9903 },
      destination: { label: 'Chicago, IL', lat: 41.8781, lon: -87.6298 },
      loadLb: 42_000,
    },
  },
  {
    label: 'Dallas → Atlanta',
    draft: {
      origin: { label: 'Dallas, TX', lat: 32.7767, lon: -96.797 },
      destination: { label: 'Atlanta, GA', lat: 33.749, lon: -84.388 },
      loadLb: 38_000,
    },
  },
  {
    label: 'Seattle → Salt Lake City',
    draft: {
      origin: { label: 'Seattle, WA', lat: 47.6062, lon: -122.3321 },
      destination: { label: 'Salt Lake City, UT', lat: 40.7608, lon: -111.891 },
      loadLb: 33_000,
    },
  },
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

      {!pending && (
        <div className={styles.examples}>
          <span className="label">Try an example</span>
          <div className={styles.exampleList}>
            {EXAMPLES.map((example) => (
              <button
                key={example.label}
                type="button"
                className={styles.example}
                onClick={() => updateDraft(example.draft)}
              >
                {example.label}
              </button>
            ))}
          </div>
        </div>
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
