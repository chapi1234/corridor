import { Clock3 } from 'lucide-react'

import type { PlanResponse } from '@/api/types'
import { departureLocal, offsetLabel, optionLevel, suggestionText } from '@/domain/departure'
import { formatLocal, formatPounds } from '@/domain/format'
import { LEVEL_META } from '@/domain/levels'
import { useAppStore } from '@/state/store'
import { Button } from '@/ui/Button'

import styles from './DepartureAdvisor.module.css'

interface DepartureAdvisorProps {
  plan: PlanResponse
  isWhatIf: boolean
  onReplan(): void
  replanning: boolean
}

/** Would leaving earlier or later be safer? A strip of nearby departures, best route each. */
export function DepartureAdvisor({ plan, isWhatIf, onReplan, replanning }: DepartureAdvisorProps) {
  const updateDraft = useAppStore((s) => s.updateDraft)
  const advice = plan.departure_advice
  if (advice.options.length < 2) return null

  const suggestion = advice.suggestion
  const text = suggestionText(advice)
  const suggested = advice.options.find((o) => o.offset_h === suggestion?.offset_h)

  const planAt = (local: string) => {
    updateDraft({ departureLocal: local })
    onReplan()
  }

  return (
    <section className={styles.advisor} aria-labelledby="departure-title">
      <h2 id="departure-title" className="label">
        <Clock3 size={12} aria-hidden /> Departure time
      </h2>

      <p className={styles.verdict} data-better={text !== null}>
        {text ??
          `Your departure is already the safest between ${offsetLabel(advice.options[0]!.offset_h)} and ${offsetLabel(advice.options.at(-1)!.offset_h)}.`}
      </p>

      <ol className={styles.strip} aria-label="Best route risk by departure time">
        {advice.options.map((option) => {
          const level = optionLevel(option)
          const meta = level === null ? null : LEVEL_META[level]
          const summary = `${formatLocal(option.departure)} · Route ${option.route_id} · ${
            meta ? `worst ${meta.label}` : 'partly unforecast'
          }`
          return (
            <li key={option.offset_h}>
              <button
                type="button"
                className={styles.cell}
                style={{ background: meta ? `var(${meta.cssVar})` : undefined }}
                data-current={option.offset_h === 0}
                data-suggested={option.offset_h === suggestion?.offset_h}
                data-unknown={level === null}
                title={summary}
                aria-label={`${offsetLabel(option.offset_h)}: ${summary}`}
                disabled={option.offset_h === 0 || replanning}
                onClick={() => planAt(departureLocal(option))}
              />
              <span className={`${styles.tick} num`}>
                {option.offset_h === 0
                  ? 'plan'
                  : option.offset_h % 6 === 0
                    ? offsetLabel(option.offset_h)
                    : ''}
              </span>
            </li>
          )
        })}
      </ol>

      <div className={styles.footer}>
        <span className={styles.note}>
          {isWhatIf
            ? `Computed at ${formatPounds(plan.inputs.load_lb)}, not the what-if load.`
            : 'Tap a time to plan it with live data.'}
        </span>
        {suggested && (
          <Button
            size="sm"
            variant="ghost"
            disabled={replanning}
            onClick={() => planAt(departureLocal(suggested))}
          >
            Plan {offsetLabel(suggested.offset_h)}
          </Button>
        )}
      </div>
    </section>
  )
}
