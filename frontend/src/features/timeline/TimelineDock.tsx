import * as Slider from '@radix-ui/react-slider'
import { Pause, Play, SkipBack } from 'lucide-react'
import { useEffect } from 'react'

import type { Route } from '@/api/types'
import { REST_LABEL, restAt } from '@/domain/duty'
import { formatInstant, formatMiles } from '@/domain/format'
import { elapsedAtHour, frameInstant, hourOf, mileAtElapsed } from '@/domain/timeline'
import { clamp } from '@/lib/math'
import { useScoredPlan, useSelectedRoute } from '@/state/selectors'
import { FORECAST_HOURS, PLAYBACK_HOUR_MS, useAppStore, type PlaybackSpeed } from '@/state/store'
import { IconButton } from '@/ui/Button'
import { Segmented } from '@/ui/Segmented'

import styles from './TimelineDock.module.css'

const SPEEDS: readonly { value: PlaybackSpeed; label: string }[] = [
  { value: 1, label: '1×' },
  { value: 2, label: '2×' },
  { value: 4, label: '4×' },
]
const TICK_HOURS = [0, 6, 12, 18, 24, 30, 36, 42, 48]

function usePlayback() {
  const playing = useAppStore((s) => s.playing)
  const speed = useAppStore((s) => s.playbackSpeed)
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      const { forecastHour, setForecastHour, setPlaying } = useAppStore.getState()
      if (forecastHour >= FORECAST_HOURS) {
        setPlaying(false)
        return
      }
      setForecastHour(forecastHour + 1)
    }, PLAYBACK_HOUR_MS / speed)
    return () => window.clearInterval(timer)
  }, [playing, speed])
}

function truckStatus(route: Route, elapsedS: number): string {
  const where = formatMiles(mileAtElapsed(route, elapsedS))
  const rest = restAt(route, elapsedS)
  return rest
    ? `Route ${route.id} truck on ${REST_LABEL[rest.kind]} at ${where}`
    : `Route ${route.id} truck near ${where}`
}

/** 0–48 h forecast scrubber driving the heatmap frame and the ghost truck. */
export function TimelineDock() {
  const scored = useScoredPlan()
  const selected = useSelectedRoute()
  const hour = useAppStore((s) => s.forecastHour)
  const playing = useAppStore((s) => s.playing)
  const setForecastHour = useAppStore((s) => s.setForecastHour)
  const setPlaying = useAppStore((s) => s.setPlaying)
  const speed = useAppStore((s) => s.playbackSpeed)
  const setSpeed = useAppStore((s) => s.setPlaybackSpeed)
  usePlayback()

  if (!scored) return null
  const { plan } = scored
  const tz = plan.departure.tz
  const pct = (h: number) => `${(clamp(h, 0, FORECAST_HOURS) / FORECAST_HOURS) * 100}%`

  const trip = selected
    ? { start: hourOf(plan, plan.departure.utc), end: hourOf(plan, selected.route.arrival.utc) }
    : null
  const elapsedS = elapsedAtHour(plan, hour)
  const status = !selected
    ? null
    : elapsedS < 0
      ? 'Before departure'
      : elapsedS >= selected.route.duration_s
        ? `Arrived · Route ${selected.route.id}`
        : truckStatus(selected.route, elapsedS)

  const togglePlay = () => {
    if (!playing && hour >= FORECAST_HOURS) setForecastHour(0)
    setPlaying(!playing)
  }

  return (
    <section className={styles.dock} aria-label="Forecast timeline">
      <div className={styles.controls}>
        <IconButton
          label={playing ? 'Pause' : 'Play forecast'}
          variant="primary"
          icon={playing ? <Pause size={16} /> : <Play size={16} />}
          onClick={togglePlay}
        />
        <IconButton
          label="Back to departure"
          variant="ghost"
          icon={<SkipBack size={14} />}
          onClick={() => {
            setPlaying(false)
            setForecastHour(0)
          }}
        />
        <Segmented<PlaybackSpeed>
          size="sm"
          label="Playback speed"
          value={speed}
          options={SPEEDS}
          onChange={setSpeed}
        />
      </div>

      <div className={styles.readout}>
        <span className={`${styles.clock} num`}>{formatInstant(frameInstant(plan, hour), tz)}</span>
        <span className={styles.offset}>
          <span className="num">+{hour} h</span>
          {status && <span className={styles.status}> · {status}</span>}
        </span>
      </div>

      <div className={styles.scrubber}>
        <Slider.Root
          className={styles.root}
          min={0}
          max={FORECAST_HOURS}
          step={1}
          value={[hour]}
          onValueChange={([next]) => {
            setPlaying(false)
            setForecastHour(next ?? 0)
          }}
          aria-label="Forecast hour"
        >
          <Slider.Track className={styles.track}>
            {trip && (
              <span
                className={styles.trip}
                style={{
                  left: pct(trip.start),
                  width: `calc(${pct(trip.end)} - ${pct(trip.start)})`,
                }}
                title="Selected route's drive window"
              />
            )}
            <Slider.Range className={styles.range} />
          </Slider.Track>
          <Slider.Thumb
            className={styles.thumb}
            aria-valuetext={`${formatInstant(frameInstant(plan, hour), tz)}, ${hour} hours after departure`}
          />
        </Slider.Root>
        <div className={`${styles.ticks} num`} aria-hidden>
          {TICK_HOURS.map((tick) => (
            <span key={tick} style={{ left: pct(tick) }}>
              {tick === 0 ? 'DEP' : `+${tick}h`}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
