import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

import { CRITERION_LABEL, LOAD_RULE_TEXT } from '@/domain/levels'
import {
  LEVELS,
  RAIN_BANDS_IN_HR,
  SNOW_BANDS_IN_HR,
  WIND_BANDS_MPH,
  type Band,
  type Level,
} from '@/domain/risk'
import { useAppStore } from '@/state/store'
import { IconButton } from '@/ui/Button'
import { RiskChip } from '@/ui/RiskChip'

import styles from './RulesPanel.module.css'

const RANKING = [
  'no_travel_miles',
  'severe_miles',
  'high_miles',
  'average_risk',
  'duration',
] as const

const SHORTCUTS = [
  ['← / →', 'Forecast hour −1 / +1'],
  ['Shift + ← / →', 'Forecast hour −6 / +6'],
  ['Space', 'Play / pause the forecast'],
  ['1 / 2 / 3', 'Select route A / B / C'],
  ['H', 'Toggle the weather heatmap'],
  ['?', 'Open these rules'],
  ['Esc', 'Close the checkpoint drawer'],
] as const

/**
 * Band label in the brief's own words. Wind is quoted in whole mph (25–34), precipitation
 * as half-open ranges with a strict No Travel edge (D2, D3).
 */
function bandText(
  bands: readonly Band[],
  level: Level,
  unit: string,
  kind: 'wind' | 'precip',
): string {
  const strictTop = kind === 'precip'
  const band = bands.find((b) => b.level === level)!
  const ascending = [...bands].reverse()
  const next = ascending[ascending.indexOf(band) + 1]
  if (level === 0) return `< ${next!.lower} ${unit}`
  if (!next) return `${strictTop ? '>' : '≥'} ${band.lower} ${unit}`
  const upper = kind === 'wind' ? next.lower - 1 : next.lower
  return `${band.lower}–${upper} ${unit}`
}

export function RulesPanel() {
  const open = useAppStore((s) => s.rulesOpen)
  const setOpen = useAppStore((s) => s.setRulesOpen)

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content}>
          <header className={styles.header}>
            <Dialog.Title className={styles.title}>How Corridor scores a trip</Dialog.Title>
            <Dialog.Close asChild>
              <IconButton label="Close rules" variant="ghost" icon={<X size={16} />} />
            </Dialog.Close>
          </header>
          <Dialog.Description className={styles.lede}>
            Every checkpoint is scored with the weather forecast for the hour the truck reaches it.
            The worst of the three factors sets its level.
          </Dialog.Description>

          <section>
            <h3 className="label">Risk thresholds</h3>
            <table className={`${styles.table} num`}>
              <thead>
                <tr>
                  <th scope="col">Level</th>
                  <th scope="col">Wind gust</th>
                  <th scope="col">Rain</th>
                  <th scope="col">Snow</th>
                </tr>
              </thead>
              <tbody>
                {LEVELS.map((level) => (
                  <tr key={level}>
                    <th scope="row">
                      <RiskChip level={level} size="sm" />
                    </th>
                    <td>{bandText(WIND_BANDS_MPH, level, 'mph', 'wind')}</td>
                    <td>{bandText(RAIN_BANDS_IN_HR, level, 'in/hr', 'precip')}</td>
                    <td>{bandText(SNOW_BANDS_IN_HR, level, 'in/hr', 'precip')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="label">Load rules (wind only)</h3>
            <ul className={styles.list}>
              <li>≥ 55 mph gusts → No Travel for any load</li>
              {Object.values(LOAD_RULE_TEXT).map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="label">Recommendation order</h3>
            <ol className={styles.list}>
              {RANKING.map((criterion) => (
                <li key={criterion}>
                  Fewest {CRITERION_LABEL[criterion].toLowerCase()}
                  {criterion === 'no_travel_miles' && <em> (counted before Severe)</em>}
                  {criterion === 'average_risk' && <em> (mile-weighted)</em>}
                  {criterion === 'duration' && <em> (shortest)</em>}
                </li>
              ))}
            </ol>
          </section>

          <section>
            <h3 className="label">Method</h3>
            <ul className={styles.list}>
              <li>
                Checkpoints every 10, 25 or 50 miles; each owns the road halfway to its neighbours.
              </li>
              <li>ETAs follow the router's own speed profile, not a constant average.</li>
              <li>
                With mandatory rest on, ETAs include FMCSA hours of service: a 30-minute break after
                8 h of driving and a 10-hour rest after 11 h, assuming the driver starts rested.
              </li>
              <li>Wind uses gusts, which is what tips a high-sided trailer.</li>
              <li>Precipitation is the rate for the hour that contains the ETA.</li>
              <li>Miles without a forecast are shown as unknown, never as safe.</li>
            </ul>
          </section>

          <section>
            <h3 className="label">Keyboard</h3>
            <dl className={styles.shortcuts}>
              {SHORTCUTS.map(([keys, action]) => (
                <div key={keys}>
                  <dt>
                    <kbd>{keys}</kbd>
                  </dt>
                  <dd>{action}</dd>
                </div>
              ))}
            </dl>
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
